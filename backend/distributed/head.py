"""
Head node module for distributed mode.
Manages Redis job queue, worker registry, and dead worker detection.
"""

import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

REDIS_JOB_QUEUE = "exam_eval:jobs"
REDIS_DEAD_LETTER = "exam_eval:dead_letter"
WORKER_TIMEOUT_SECONDS = 300


class HeadNode:
    """Manages distributed job distribution via Redis."""

    def __init__(self):
        self.redis_client = None
        self.workers: Dict[str, dict] = {}

    def connect(self, redis_url: str) -> bool:
        """Connect to Redis."""
        try:
            import redis
            self.redis_client = redis.from_url(redis_url)
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {redis_url}")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False

    def disconnect(self):
        """Close Redis connection."""
        if self.redis_client:
            self.redis_client.close()
            self.redis_client = None

    def push_jobs(self, jobs: List[dict]) -> int:
        """Push jobs to the Redis queue. Returns number of jobs pushed."""
        if not self.redis_client:
            raise RuntimeError("Not connected to Redis")

        count = 0
        for job in jobs:
            self.redis_client.lpush(
                REDIS_JOB_QUEUE,
                json.dumps(job),
            )
            count += 1

        logger.info(f"Pushed {count} jobs to Redis queue")
        return count

    def get_queue_length(self) -> int:
        """Get current queue length."""
        if not self.redis_client:
            return 0
        return self.redis_client.llen(REDIS_JOB_QUEUE)

    def register_worker(self, worker_id: str, host: str, threads: int) -> None:
        """Register a worker."""
        self.workers[worker_id] = {
            "worker_id": worker_id,
            "host": host,
            "threads": threads,
            "status": "online",
            "jobs_processed": 0,
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Worker registered: {worker_id} ({host})")

    def heartbeat(self, worker_id: str) -> None:
        """Update worker heartbeat."""
        if worker_id in self.workers:
            self.workers[worker_id]["last_heartbeat"] = datetime.now(timezone.utc).isoformat()

    def report_job_done(self, worker_id: str, job_id: str) -> None:
        """Worker reports job completion."""
        if worker_id in self.workers:
            self.workers[worker_id]["jobs_processed"] += 1

    def detect_dead_workers(self) -> List[str]:
        """Find workers whose heartbeat is too old."""
        dead = []
        now = datetime.now(timezone.utc)
        for worker_id, info in self.workers.items():
            last_hb = datetime.fromisoformat(info["last_heartbeat"])
            if (now - last_hb).total_seconds() > WORKER_TIMEOUT_SECONDS:
                dead.append(worker_id)
                info["status"] = "dead"

        return dead

    def requeue_dead_worker_jobs(self, worker_id: str, mongo_manager) -> int:
        """Re-queue jobs assigned to a dead worker."""
        jobs = mongo_manager.get_jobs_by_status("QUEUED")
        requeued = 0
        for job in jobs:
            if job.get("node_id") == worker_id:
                job["node_id"] = "unassigned"
                mongo_manager.upsert_job(job)
                self.redis_client.lpush(REDIS_JOB_QUEUE, json.dumps(job))
                requeued += 1

        logger.info(f"Re-queued {requeued} jobs from dead worker {worker_id}")
        return requeued

    def move_to_dead_letter(self, job: dict) -> None:
        """Move a failed job to the dead letter queue."""
        if self.redis_client:
            self.redis_client.lpush(REDIS_DEAD_LETTER, json.dumps(job))

    def get_dead_letter_count(self) -> int:
        """Get number of jobs in dead letter queue."""
        if not self.redis_client:
            return 0
        return self.redis_client.llen(REDIS_DEAD_LETTER)

    def get_worker_start_command(self, head_ip: str, head_port: int) -> str:
        """Generate the copyable command for starting a worker."""
        return f"python worker.py --head http://{head_ip}:{head_port} --id worker_2 --threads 4"

    def get_all_workers(self) -> List[dict]:
        """Get all worker info."""
        return list(self.workers.values())


# Singleton
head_node = HeadNode()
