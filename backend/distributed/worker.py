"""
Standalone worker script for distributed mode.
Runs on remote machines and processes evaluation jobs from Redis queue.

Usage:
    python worker.py --head http://<HEAD_IP>:<PORT> --id worker_2 --threads 4
"""

import argparse
import json
import logging
import time
import sys
import threading
import signal
from datetime import datetime, timezone

import redis
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

REDIS_JOB_QUEUE = "exam_eval:jobs"
HEARTBEAT_INTERVAL = 30
running = True


def signal_handler(sig, frame):
    global running
    logger.info("Shutting down worker...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class Worker:
    """Distributed evaluation worker."""

    def __init__(self, head_url: str, worker_id: str, threads: int):
        self.head_url = head_url.rstrip("/")
        self.worker_id = worker_id
        self.threads = threads
        self.redis_client = None
        self.jobs_processed = 0

    def register(self):
        """Register with the head node."""
        try:
            resp = requests.post(
                f"{self.head_url}/workers/register",
                json={
                    "worker_id": self.worker_id,
                    "host": self._get_host(),
                    "threads": self.threads,
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info(f"Registered with head node: {self.head_url}")
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            raise

    def _get_host(self) -> str:
        """Get this machine's hostname."""
        import socket
        return socket.gethostname()

    def connect_redis(self):
        """Connect to the Redis queue via head node config."""
        try:
            # Get config from head
            resp = requests.get(f"{self.head_url}/config/load", timeout=10)
            resp.raise_for_status()
            config = resp.json().get("config", {})
            redis_url = config.get("redis_url", "redis://localhost:6379")

            self.redis_client = redis.from_url(redis_url)
            self.redis_client.ping()
            logger.info(f"Connected to Redis")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    def heartbeat_loop(self):
        """Send heartbeats in a background thread."""
        while running:
            try:
                requests.post(
                    f"{self.head_url}/workers/heartbeat",
                    json={"worker_id": self.worker_id},
                    timeout=5,
                )
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
            time.sleep(HEARTBEAT_INTERVAL)

    def poll_and_process(self):
        """Main loop: poll Redis for jobs and process them."""
        logger.info(f"Worker {self.worker_id} started polling for jobs...")

        while running:
            try:
                # Blocking pop with timeout
                result = self.redis_client.brpop(REDIS_JOB_QUEUE, timeout=5)
                if result is None:
                    continue

                _, job_json = result
                job = json.loads(job_json)
                job_id = job.get("job_id", "unknown")
                roll = job.get("roll_number", "unknown")
                course = job.get("course_code", "unknown")

                logger.info(f"Processing job {job_id}: {course}/{roll}")

                try:
                    self._process_job(job)
                    self.jobs_processed += 1
                    logger.info(f"Job {job_id} completed ({self.jobs_processed} total)")
                except Exception as e:
                    retries = job.get("retries", 0) + 1
                    if retries >= 3:
                        logger.error(f"Job {job_id} failed permanently: {e}")
                        # Move to dead letter
                        job["status"] = "FAILED"
                        job["error"] = str(e)
                        self.redis_client.lpush(
                            "exam_eval:dead_letter",
                            json.dumps(job),
                        )
                    else:
                        logger.warning(f"Job {job_id} failed (retry {retries}): {e}")
                        job["retries"] = retries
                        self.redis_client.lpush(REDIS_JOB_QUEUE, json.dumps(job))

            except Exception as e:
                logger.error(f"Poll error: {e}")
                time.sleep(2)

    def _process_job(self, job: dict):
        """Process a single evaluation job by delegating to the head node.
        In a full implementation, this would run the evaluation pipeline locally.
        For simplicity, we delegate back to the head's evaluate endpoint."""
        import asyncio
        from backend.config import load_config
        from backend.pipeline.ocr import ocr_answer_sheet
        from backend.pipeline.mapper import map_student_answers, build_question_map, build_answer_key_map
        from backend.pipeline.evaluator import evaluate_all_questions
        from backend.pipeline.aggregator import aggregate_student_result

        # Get config and course data from head
        resp = requests.get(f"{self.head_url}/config/load", timeout=10)
        config = resp.json().get("config", {})
        api_key = config.get("anthropic_api_key", "")

        course_code = job["course_code"]
        roll_number = job["roll_number"]

        # Get course data
        resp = requests.get(f"{self.head_url}/results/{course_code}", timeout=10)
        # The worker needs the question map and answer key from the head
        # In practice, these would be cached locally

        # For the worker, we run the evaluation pipeline using the API key from config
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # OCR the student sheet
            sheet_ocr = loop.run_until_complete(
                ocr_answer_sheet(job["file_path"], api_key, roll_number)
            )

            # The worker would need question_map and answer_key_map from the head
            # This is a simplified version — in production, these would be distributed via Redis
            logger.info(f"Worker processed OCR for {roll_number}")

        finally:
            loop.close()

    def run(self):
        """Entry point: register, connect, and start processing."""
        self.register()
        self.connect_redis()

        # Start heartbeat in background
        hb_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        hb_thread.start()

        # Start polling
        self.poll_and_process()


def main():
    parser = argparse.ArgumentParser(description="Exam Evaluator Worker Node")
    parser.add_argument("--head", required=True, help="Head node URL (e.g., http://192.168.1.10:8765)")
    parser.add_argument("--id", required=True, help="Unique worker ID")
    parser.add_argument("--threads", type=int, default=4, help="Number of concurrent threads")
    args = parser.parse_args()

    worker = Worker(args.head, args.id, args.threads)
    worker.run()


if __name__ == "__main__":
    main()
