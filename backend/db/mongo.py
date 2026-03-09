"""
MongoDB manager for the Exam Evaluator backend.
Handles all database operations: connect, upsert, query.
"""

import logging
import ssl
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import certifi
from pymongo import MongoClient, errors as pymongo_errors
from pymongo.collection import Collection

logger = logging.getLogger(__name__)


def _configure_dns():
    """Configure dnspython to use Google/Cloudflare DNS servers.
    Fixes SRV resolution failures when the local DNS server can't resolve
    MongoDB Atlas hostnames (common on restricted networks)."""
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
        resolver.lifetime = 10
        dns.resolver.default_resolver = resolver
        logger.info("Configured DNS resolver to use Google/Cloudflare DNS")
    except ImportError:
        logger.warning("dnspython not installed, SRV resolution may fail")
    except Exception as e:
        logger.warning(f"Failed to configure DNS resolver: {e}")


# Configure DNS on module load so SRV lookups work
_configure_dns()


class MongoManager:
    """Manages MongoDB connections and operations for exam evaluation data."""

    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db = None

    def connect(self, uri: str, db_name: str = "exam_evaluations") -> bool:
        """Connect to MongoDB. Returns True if successful."""
        try:
            self.client = MongoClient(
                uri,
                serverSelectionTimeoutMS=10000,
                tls=True,
                tlsCAFile=certifi.where(),
                tlsAllowInvalidCertificates=True,
            )
            # Force a connection attempt
            self.client.admin.command("ping")
            self.db = self.client[db_name]
            logger.info(f"Connected to MongoDB at {uri}")
            return True
        except pymongo_errors.ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            self.client = None
            self.db = None
            return False
        except Exception as e:
            logger.error(f"MongoDB connection error: {e}")
            self.client = None
            self.db = None
            return False

    def disconnect(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    def is_connected(self) -> bool:
        """Check if connected to MongoDB."""
        if not self.client:
            return False
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    @property
    def results_col(self) -> Collection:
        return self.db["results"]

    @property
    def courses_col(self) -> Collection:
        return self.db["courses"]

    @property
    def job_log_col(self) -> Collection:
        return self.db["job_log"]

    @property
    def workers_col(self) -> Collection:
        return self.db["workers"]

    # --- Results ---

    def upsert_result(self, result: dict) -> None:
        """Upsert a student evaluation result."""
        self.results_col.update_one(
            {"roll_number": result["roll_number"], "course_code": result["course_code"]},
            {"$set": result},
            upsert=True,
        )

    def get_result(self, course_code: str, roll_number: str) -> Optional[dict]:
        """Get a single student result."""
        return self.results_col.find_one(
            {"course_code": course_code, "roll_number": roll_number},
            {"_id": 0},
        )

    def result_exists(self, course_code: str, roll_number: str) -> bool:
        """Check if a result already exists for this student+course."""
        return self.results_col.count_documents(
            {"course_code": course_code, "roll_number": roll_number}
        ) > 0

    def get_results_by_course(self, course_code: str) -> List[dict]:
        """Get all results for a course."""
        return list(self.results_col.find(
            {"course_code": course_code},
            {"_id": 0},
        ).sort("roll_number", 1))

    def get_all_results(self) -> List[dict]:
        """Get all results across all courses."""
        return list(self.results_col.find({}, {"_id": 0}).sort([("course_code", 1), ("roll_number", 1)]))

    def get_course_summary(self) -> List[dict]:
        """Get summary statistics per course."""
        pipeline = [
            {"$group": {
                "_id": "$course_code",
                "student_count": {"$sum": 1},
                "avg_percentage": {"$avg": "$percentage"},
                "max_percentage": {"$max": "$percentage"},
                "min_percentage": {"$min": "$percentage"},
                "total_marks_possible": {"$first": "$total_marks_possible"},
            }},
            {"$sort": {"_id": 1}},
        ]
        return list(self.results_col.aggregate(pipeline))

    # --- Courses ---

    def upsert_course(self, course_data: dict) -> None:
        """Upsert course data (question map, calibration, etc.)."""
        course_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.courses_col.update_one(
            {"course_code": course_data["course_code"]},
            {"$set": course_data},
            upsert=True,
        )

    def get_course(self, course_code: str) -> Optional[dict]:
        """Get course data."""
        return self.courses_col.find_one(
            {"course_code": course_code},
            {"_id": 0},
        )

    def get_all_courses(self) -> List[dict]:
        """Get all course data."""
        return list(self.courses_col.find({}, {"_id": 0}).sort("course_code", 1))

    # --- Job Log ---

    def upsert_job(self, job: dict) -> None:
        """Upsert a job log entry."""
        job["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.job_log_col.update_one(
            {"job_id": job["job_id"]},
            {"$set": job},
            upsert=True,
        )

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get a job by ID."""
        return self.job_log_col.find_one({"job_id": job_id}, {"_id": 0})

    def get_jobs_by_course(self, course_code: str) -> List[dict]:
        """Get all jobs for a course."""
        return list(self.job_log_col.find(
            {"course_code": course_code},
            {"_id": 0},
        ))

    def get_jobs_by_status(self, status: str) -> List[dict]:
        """Get all jobs with a given status."""
        return list(self.job_log_col.find(
            {"status": status},
            {"_id": 0},
        ))

    def get_failed_jobs(self) -> List[dict]:
        """Get all failed jobs."""
        return list(self.job_log_col.find(
            {"status": "FAILED"},
            {"_id": 0},
        ))

    def increment_retry(self, job_id: str) -> int:
        """Increment the retry count for a job. Returns new count."""
        result = self.job_log_col.find_one_and_update(
            {"job_id": job_id},
            {"$inc": {"retries": 1}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
            return_document=True,
        )
        return result.get("retries", 0) if result else 0

    def clear_jobs(self, course_code: Optional[str] = None) -> None:
        """Clear job logs, optionally for a specific course."""
        query = {"course_code": course_code} if course_code else {}
        self.job_log_col.delete_many(query)

    # --- Workers ---

    def register_worker(self, worker: dict) -> None:
        """Register or update a worker."""
        worker["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        self.workers_col.update_one(
            {"worker_id": worker["worker_id"]},
            {"$set": worker},
            upsert=True,
        )

    def update_worker_heartbeat(self, worker_id: str) -> None:
        """Update worker heartbeat timestamp."""
        self.workers_col.update_one(
            {"worker_id": worker_id},
            {"$set": {"last_heartbeat": datetime.now(timezone.utc).isoformat()}},
        )

    def get_all_workers(self) -> List[dict]:
        """Get all registered workers."""
        return list(self.workers_col.find({}, {"_id": 0}))

    def increment_worker_jobs(self, worker_id: str) -> None:
        """Increment jobs_processed for a worker."""
        self.workers_col.update_one(
            {"worker_id": worker_id},
            {"$inc": {"jobs_processed": 1}},
        )


# Singleton instance
mongo_manager = MongoManager()
