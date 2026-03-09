"""
FastAPI application — all routes for the Exam Evaluator backend.
Includes health, config, scan, evaluate (with SSE), results, export, and workers.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from openai import OpenAI

from backend.config import load_config, save_config, validate_config
from backend.db.mongo import mongo_manager
from backend.pipeline.scanner import scan_exam_folder, build_job_list
from backend.pipeline.ocr import ocr_question_paper, ocr_answer_key, ocr_answer_sheet
from backend.pipeline.mapper import (
    build_question_map, build_answer_key_map, map_student_answers,
    handle_optional_sections, apply_optional_counting,
)
from backend.pipeline.calibration import find_pregraded_answers, build_calibration_profile
from backend.pipeline.evaluator import evaluate_all_questions
from backend.pipeline.aggregator import aggregate_student_result
from backend.export.excel import generate_course_excel, generate_all_courses_zip

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Exam Evaluator API", version="1.0.0")

# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global State ---
pipeline_running = False
pipeline_cancel = False
progress_events: asyncio.Queue = asyncio.Queue()


# --- Request Models ---
class ConfigSaveRequest(BaseModel):
    config: dict


class WorkerRegisterRequest(BaseModel):
    worker_id: str
    host: str = ""
    threads: int = 1


class WorkerHeartbeatRequest(BaseModel):
    worker_id: str


# --- Health ---

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# --- Config ---

@app.post("/config/save")
async def config_save(req: ConfigSaveRequest):
    saved = save_config(req.config)
    return {"status": "saved", "config": saved}


@app.get("/config/load")
async def config_load():
    cfg = load_config()
    return {"config": cfg}


@app.post("/config/validate")
async def config_validate():
    """Test MongoDB, Redis, and OpenAI API connections."""
    cfg = load_config()
    results = {}

    # Test MongoDB
    try:
        connected = mongo_manager.connect(cfg.get("mongodb_uri", ""))
        results["mongodb"] = connected
        if not connected:
            results["mongodb_error"] = "Connection failed"
    except Exception as e:
        results["mongodb"] = False
        results["mongodb_error"] = str(e)

    # Test OpenAI API
    try:
        api_key = cfg.get("openai_api_key", "")
        if api_key:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            results["openai"] = True
        else:
            results["openai"] = False
            results["openai_error"] = "API key not configured"
    except Exception as e:
        results["openai"] = False
        results["openai_error"] = str(e)

    # Test Redis (only if distributed mode enabled)
    if cfg.get("distributed_mode"):
        try:
            import redis
            r = redis.from_url(cfg.get("redis_url", "redis://localhost:6379"))
            r.ping()
            results["redis"] = True
            r.close()
        except Exception as e:
            results["redis"] = False
            results["redis_error"] = str(e)
    else:
        results["redis"] = None  # Not applicable

    return {"results": results}


# --- Scan ---

@app.get("/scan")
async def scan():
    cfg = load_config()
    root = cfg.get("root_exam_folder", "")
    if not root:
        raise HTTPException(status_code=400, detail="Root exam folder not configured")

    result = scan_exam_folder(root, cfg.get("selected_courses", "ALL"))
    return result


# --- Evaluate ---

@app.post("/evaluate/start")
async def evaluate_start(background_tasks: BackgroundTasks):
    global pipeline_running, pipeline_cancel

    if pipeline_running:
        raise HTTPException(status_code=409, detail="Pipeline already running")

    pipeline_cancel = False
    pipeline_running = True

    background_tasks.add_task(_run_pipeline)
    return {"status": "started"}


@app.get("/evaluate/progress")
async def evaluate_progress(request: Request):
    """SSE endpoint for live pipeline progress."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(progress_events.get(), timeout=1.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive
                yield f"data: {json.dumps({'stage': 'KEEPALIVE'})}\n\n"
            except Exception:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/evaluate/stop")
async def evaluate_stop():
    global pipeline_cancel
    pipeline_cancel = True
    return {"status": "stopping"}


async def _emit_progress(event: dict):
    """Push a progress event to the SSE queue."""
    await progress_events.put(event)


async def _run_pipeline():
    """Main evaluation pipeline — runs as a background task."""
    global pipeline_running, pipeline_cancel

    try:
        cfg = load_config()
        api_key = cfg.get("openai_api_key", "")
        grading_scale = cfg.get("grading_scale", {})
        re_evaluate = cfg.get("re_evaluate", False)
        max_concurrent = cfg.get("max_concurrent_api_calls", 5)
        distributed = cfg.get("distributed_mode", False)

        # Ensure MongoDB is connected
        if not mongo_manager.is_connected():
            connected = mongo_manager.connect(cfg.get("mongodb_uri", ""))
            if not connected:
                await _emit_progress({"stage": "FAILED", "message": "MongoDB connection failed. Check your connection string and network."})
                return

        # Step 1: Scan
        await _emit_progress({"stage": "SCANNING", "message": "Scanning exam folder..."})
        scan_result = scan_exam_folder(cfg.get("root_exam_folder", ""), cfg.get("selected_courses", "ALL"))

        if not scan_result.get("courses"):
            await _emit_progress({"stage": "FAILED", "message": "No courses found."})
            return

        # Build job list
        jobs = build_job_list(scan_result)

        # Save jobs to MongoDB
        for job in jobs:
            mongo_manager.upsert_job(job)

        await _emit_progress({
            "stage": "SCAN_DONE",
            "message": f"Found {len(scan_result['courses'])} courses, {len(jobs)} student sheets.",
        })

        # Process each course
        for course_info in scan_result["courses"]:
            if pipeline_cancel:
                await _emit_progress({"stage": "CANCELLED", "message": "Pipeline cancelled by user."})
                return

            course_code = course_info["course_code"]

            if course_info["status"] == "INCOMPLETE":
                await _emit_progress({
                    "stage": "SKIPPED",
                    "course_code": course_code,
                    "message": f"Skipping {course_code}: {course_info.get('error', 'incomplete')}",
                })
                continue

            await _emit_progress({
                "stage": "PROCESSING_COURSE",
                "course_code": course_code,
                "message": f"Processing {course_code}...",
            })

            try:
                await _process_course(course_info, cfg, api_key, grading_scale, re_evaluate, max_concurrent)
            except Exception as e:
                logger.error(f"Course {course_code} failed: {e}")
                await _emit_progress({
                    "stage": "FAILED",
                    "course_code": course_code,
                    "message": f"Course {course_code} failed: {str(e)}",
                })

        await _emit_progress({"stage": "COMPLETE", "message": "Evaluation pipeline complete."})

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        await _emit_progress({"stage": "FAILED", "message": f"Pipeline error: {str(e)}"})
    finally:
        pipeline_running = False


async def _process_course(
    course_info: dict,
    cfg: dict,
    api_key: str,
    grading_scale: dict,
    re_evaluate: bool,
    max_concurrent: int,
):
    """Process a single course: OCR → Map → Calibrate → Evaluate → Aggregate."""
    global pipeline_cancel

    course_code = course_info["course_code"]
    inventory = course_info["file_inventory"]

    # Step 2: OCR question paper
    await _emit_progress({
        "stage": "OCR_QP",
        "course_code": course_code,
        "message": f"OCR: Question paper for {course_code}",
    })
    qp_ocr = await ocr_question_paper(inventory["question_paper"], api_key)

    # OCR answer key
    await _emit_progress({
        "stage": "OCR_AK",
        "course_code": course_code,
        "message": f"OCR: Answer key for {course_code}",
    })
    ak_ocr = await ocr_answer_key(inventory["answer_key"], api_key)

    # Build question map and answer key map
    question_map = build_question_map(qp_ocr)
    answer_key_map = build_answer_key_map(ak_ocr)

    # Save course data
    mongo_manager.upsert_course({
        "course_code": course_code,
        "question_map": question_map,
        "total_marks": qp_ocr.get("total_marks", 100),
    })

    # Step 3: OCR all student sheets (for calibration)
    student_ocr_results = []
    for sheet in inventory["student_sheets"]:
        if pipeline_cancel:
            return

        roll = sheet["roll_number"]

        # Skip if already evaluated and re_evaluate is false
        if not re_evaluate and mongo_manager.result_exists(course_code, roll):
            await _emit_progress({
                "stage": "SKIPPED",
                "course_code": course_code,
                "roll_number": roll,
                "message": f"Skipping {roll} — already evaluated",
            })
            continue

        await _emit_progress({
            "stage": "OCR_SHEET",
            "course_code": course_code,
            "roll_number": roll,
            "message": f"OCR: {roll} answer sheet",
        })

        try:
            sheet_ocr = await ocr_answer_sheet(sheet["file_path"], api_key, roll)
            student_ocr_results.append({"roll_number": roll, "ocr": sheet_ocr, "file_path": sheet["file_path"]})

            # Update job status
            jobs = [j for j in mongo_manager.get_jobs_by_course(course_code) if j.get("roll_number") == roll]
            for j in jobs:
                j["status"] = "OCR_DONE"
                mongo_manager.upsert_job(j)

            await _emit_progress({
                "stage": "OCR_DONE",
                "course_code": course_code,
                "roll_number": roll,
                "message": f"OCR complete for {roll}",
            })
        except Exception as e:
            logger.error(f"OCR failed for {roll}: {e}")
            await _emit_progress({
                "stage": "FAILED",
                "course_code": course_code,
                "roll_number": roll,
                "message": f"OCR failed for {roll}: {str(e)}",
            })

    if not student_ocr_results:
        return

    # Step 3b: Calibration
    await _emit_progress({
        "stage": "CALIBRATING",
        "course_code": course_code,
        "message": f"Building calibration profile for {course_code}",
    })

    all_ocr_data = [s["ocr"] for s in student_ocr_results]
    pregraded = await find_pregraded_answers(all_ocr_data)
    calibration_profile = await build_calibration_profile(
        pregraded, question_map, answer_key_map, api_key,
    )

    # Save calibration to course
    mongo_manager.upsert_course({
        "course_code": course_code,
        "question_map": question_map,
        "calibration_profile": calibration_profile,
        "total_marks": qp_ocr.get("total_marks", 100),
    })

    # Step 4 & 5: Map + Evaluate each student
    for student_data in student_ocr_results:
        if pipeline_cancel:
            return

        roll = student_data["roll_number"]
        sheet_ocr = student_data["ocr"]

        await _emit_progress({
            "stage": "EVALUATING",
            "course_code": course_code,
            "roll_number": roll,
            "message": f"Evaluating {roll}...",
        })

        try:
            # Map student answers
            mapped = map_student_answers(question_map, answer_key_map, sheet_ocr)
            mapped = handle_optional_sections(mapped)

            # Evaluate all questions
            evaluated = await evaluate_all_questions(
                mapped, calibration_profile, api_key, max_concurrent,
            )

            # Apply optional counting
            evaluated = apply_optional_counting(evaluated)

            # Step 6: Aggregate
            result = await aggregate_student_result(
                roll, course_code, evaluated, grading_scale, api_key,
            )

            # Step 7: Save to MongoDB
            mongo_manager.upsert_result(result)

            # Update job status
            jobs = [j for j in mongo_manager.get_jobs_by_course(course_code) if j.get("roll_number") == roll]
            for j in jobs:
                j["status"] = "SAVED"
                mongo_manager.upsert_job(j)

            await _emit_progress({
                "stage": "SAVED",
                "course_code": course_code,
                "roll_number": roll,
                "marks": result.get("total_marks_awarded"),
                "total": result.get("total_marks_possible"),
                "message": f"{roll}: {result.get('total_marks_awarded')}/{result.get('total_marks_possible')} ({result.get('grade')})",
            })

        except Exception as e:
            logger.error(f"Evaluation failed for {roll}: {e}")

            # Update job status
            jobs = [j for j in mongo_manager.get_jobs_by_course(course_code) if j.get("roll_number") == roll]
            for j in jobs:
                retries = mongo_manager.increment_retry(j["job_id"])
                if retries >= 3:
                    j["status"] = "FAILED"
                    j["error"] = str(e)
                    mongo_manager.upsert_job(j)
                    await _emit_progress({
                        "stage": "FAILED",
                        "course_code": course_code,
                        "roll_number": roll,
                        "flag": "MANUAL_REVIEW",
                        "message": f"{roll} failed after 3 retries: {str(e)}",
                    })
                else:
                    j["status"] = "QUEUED"
                    mongo_manager.upsert_job(j)

            await _emit_progress({
                "stage": "FAILED",
                "course_code": course_code,
                "roll_number": roll,
                "message": f"Evaluation failed for {roll}: {str(e)}",
            })


# --- Results ---

@app.get("/results")
async def results():
    cfg = load_config()
    if not mongo_manager.is_connected():
        mongo_manager.connect(cfg.get("mongodb_uri", ""))

    summaries = mongo_manager.get_course_summary()
    courses = []
    for s in summaries:
        courses.append({
            "course_code": s["_id"],
            "student_count": s.get("student_count", 0),
            "avg_percentage": round(s.get("avg_percentage", 0), 2),
            "max_percentage": round(s.get("max_percentage", 0), 2),
            "min_percentage": round(s.get("min_percentage", 0), 2),
            "total_marks_possible": s.get("total_marks_possible", 100),
        })

    return {"courses": courses}


@app.get("/results/{course_code}")
async def results_by_course(course_code: str):
    cfg = load_config()
    if not mongo_manager.is_connected():
        mongo_manager.connect(cfg.get("mongodb_uri", ""))

    students = mongo_manager.get_results_by_course(course_code)
    return {"course_code": course_code, "students": students}


@app.get("/results/{course_code}/{roll}")
async def result_detail(course_code: str, roll: str):
    cfg = load_config()
    if not mongo_manager.is_connected():
        mongo_manager.connect(cfg.get("mongodb_uri", ""))

    result = mongo_manager.get_result(course_code, roll)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


# --- Export ---

@app.post("/export/{course_code}")
async def export_course(course_code: str):
    cfg = load_config()
    if not mongo_manager.is_connected():
        mongo_manager.connect(cfg.get("mongodb_uri", ""))

    students = mongo_manager.get_results_by_course(course_code)
    if not students:
        raise HTTPException(status_code=404, detail="No results for this course")

    course_data = mongo_manager.get_course(course_code)
    output_dir = cfg.get("export_output_folder", "") or os.path.join(os.path.expanduser("~"), "Downloads")

    filepath = generate_course_excel(course_code, students, course_data, output_dir)
    return FileResponse(
        filepath,
        filename=os.path.basename(filepath),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/export/all")
async def export_all():
    cfg = load_config()
    if not mongo_manager.is_connected():
        mongo_manager.connect(cfg.get("mongodb_uri", ""))

    all_results = mongo_manager.get_all_results()
    all_courses = mongo_manager.get_all_courses()
    output_dir = cfg.get("export_output_folder", "") or os.path.join(os.path.expanduser("~"), "Downloads")

    filepath = generate_all_courses_zip(all_results, all_courses, output_dir)
    return FileResponse(
        filepath,
        filename=os.path.basename(filepath),
        media_type="application/zip",
    )


# --- Workers ---

@app.get("/workers")
async def list_workers():
    cfg = load_config()
    if not mongo_manager.is_connected():
        mongo_manager.connect(cfg.get("mongodb_uri", ""))

    workers = mongo_manager.get_all_workers()
    return {"workers": workers}


@app.post("/workers/register")
async def register_worker(req: WorkerRegisterRequest):
    cfg = load_config()
    if not mongo_manager.is_connected():
        mongo_manager.connect(cfg.get("mongodb_uri", ""))

    mongo_manager.register_worker({
        "worker_id": req.worker_id,
        "host": req.host,
        "threads": req.threads,
        "status": "online",
        "jobs_processed": 0,
    })
    return {"status": "registered"}


@app.post("/workers/heartbeat")
async def worker_heartbeat(req: WorkerHeartbeatRequest):
    cfg = load_config()
    if not mongo_manager.is_connected():
        mongo_manager.connect(cfg.get("mongodb_uri", ""))

    mongo_manager.update_worker_heartbeat(req.worker_id)
    return {"status": "ok"}


# --- Startup ---

@app.on_event("startup")
async def startup():
    cfg = load_config()
    uri = cfg.get("mongodb_uri", "")
    if uri:
        try:
            mongo_manager.connect(uri)
        except Exception as e:
            logger.warning(f"MongoDB not available on startup: {e}")


@app.on_event("shutdown")
async def shutdown():
    mongo_manager.disconnect()
