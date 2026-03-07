"""
Scanner module — scans the root exam folder and builds a job list.
Validates required files (QuestionPaper, AnswerKey) and enumerates student sheets.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff"}


def scan_exam_folder(root_folder: str, selected_courses: str = "ALL") -> dict:
    """
    Scan the root exam folder and return a structured inventory.

    Returns:
        {
            "courses": [...],
            "total_students": int,
            "total_courses": int,
            "incomplete_courses": [...]
        }
    """
    root = Path(root_folder)
    if not root.exists() or not root.is_dir():
        return {
            "courses": [],
            "total_students": 0,
            "total_courses": 0,
            "incomplete_courses": [],
            "error": f"Root folder does not exist: {root_folder}",
        }

    courses = []
    total_students = 0
    incomplete_courses = []

    # Each subfolder is a course
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue

        course_code = entry.name

        # Filter courses if specified
        if selected_courses != "ALL":
            selected_list = [c.strip() for c in selected_courses.split(",")]
            if course_code not in selected_list:
                continue

        course_info = _scan_course_folder(entry, course_code)
        courses.append(course_info)

        if course_info["status"] == "INCOMPLETE":
            incomplete_courses.append(course_code)
        else:
            total_students += course_info["student_count"]

    return {
        "courses": courses,
        "total_students": total_students,
        "total_courses": len(courses),
        "incomplete_courses": incomplete_courses,
    }


def _scan_course_folder(folder: Path, course_code: str) -> dict:
    """Scan a single course folder and return its inventory."""
    question_paper = None
    answer_key = None
    student_sheets = []
    errors = []

    for file_path in sorted(folder.iterdir()):
        if not file_path.is_file():
            continue

        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        name = file_path.stem  # filename without extension

        # Check for question paper
        if _is_question_paper(name, course_code):
            question_paper = str(file_path)
            continue

        # Check for answer key
        if _is_answer_key(name, course_code):
            answer_key = str(file_path)
            continue

        # Otherwise it's a student sheet
        roll_number = _extract_roll_number(name, course_code)
        if roll_number:
            student_sheets.append({
                "roll_number": roll_number,
                "file_path": str(file_path),
            })

    # Validate required files
    status = "READY"
    if not question_paper:
        errors.append(f"Missing QuestionPaper for {course_code}")
        status = "INCOMPLETE"
    if not answer_key:
        errors.append(f"Missing AnswerKey for {course_code}")
        status = "INCOMPLETE"

    return {
        "course_code": course_code,
        "status": status,
        "file_inventory": {
            "question_paper": question_paper,
            "answer_key": answer_key,
            "student_sheets": student_sheets,
        },
        "student_count": len(student_sheets),
        "error": "; ".join(errors) if errors else None,
    }


def _is_question_paper(filename: str, course_code: str) -> bool:
    """Check if filename matches question paper pattern."""
    patterns = [
        f"{course_code}_QuestionPaper",
        f"{course_code}_questionpaper",
        f"{course_code}_Question_Paper",
        f"{course_code}_QP",
    ]
    return filename.lower() in [p.lower() for p in patterns]


def _is_answer_key(filename: str, course_code: str) -> bool:
    """Check if filename matches answer key pattern."""
    patterns = [
        f"{course_code}_AnswerKey",
        f"{course_code}_answerkey",
        f"{course_code}_Answer_Key",
        f"{course_code}_AK",
    ]
    return filename.lower() in [p.lower() for p in patterns]


def _extract_roll_number(filename: str, course_code: str) -> Optional[str]:
    """Extract roll number from student sheet filename.
    Expected format: <COURSE_CODE>_<ROLL_NUMBER>
    """
    prefix = f"{course_code}_"
    if filename.startswith(prefix):
        roll = filename[len(prefix):]
        # Avoid matching QuestionPaper, AnswerKey
        if roll.lower() in ("questionpaper", "answerkey", "question_paper", "answer_key", "qp", "ak"):
            return None
        return roll if roll else None
    return None


def build_job_list(scan_result: dict) -> List[dict]:
    """Build a list of evaluation jobs from scan results."""
    import uuid

    jobs = []
    for course in scan_result["courses"]:
        if course["status"] == "INCOMPLETE":
            continue

        for sheet in course["file_inventory"]["student_sheets"]:
            jobs.append({
                "job_id": str(uuid.uuid4()),
                "course_code": course["course_code"],
                "roll_number": sheet["roll_number"],
                "file_path": sheet["file_path"],
                "question_paper_path": course["file_inventory"]["question_paper"],
                "answer_key_path": course["file_inventory"]["answer_key"],
                "status": "QUEUED",
                "error": None,
                "retries": 0,
                "node_id": "local",
            })

    return jobs
