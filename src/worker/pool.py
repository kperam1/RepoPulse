"""Thread-pool based worker pool for running analysis jobs concurrently."""

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timezone
from typing import Optional

from src.core.git_clone import GitRepoCloner, GitCloneError
from src.metrics.loc import count_loc_in_directory
from src.metrics.churn import compute_repo_churn

logger = logging.getLogger("repopulse.pool")

# default to 4 workers, configurable via env
DEFAULT_POOL_SIZE = int(os.getenv("WORKER_POOL_SIZE", "4"))


class JobRecord:
    """In-memory record for a single job."""

    def __init__(self, job_id: str, repo_url: str = None, local_path: str = None):
        self.job_id = job_id
        self.repo_url = repo_url
        self.local_path = local_path
        self.status = "queued"
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.future: Optional[Future] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "repo_url": self.repo_url,
            "local_path": self.local_path,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
        }


class WorkerPool:
    """Manages a thread pool that runs repo-analysis jobs concurrently."""

    def __init__(self, pool_size: int = DEFAULT_POOL_SIZE):
        self.pool_size = pool_size
        self._executor: Optional[ThreadPoolExecutor] = None
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._active_count = 0

    # -- lifecycle --

    def start(self):
        """Create the thread pool (idempotent — safe to call more than once)."""
        if self._executor is not None:
            return
        self._executor = ThreadPoolExecutor(
            max_workers=self.pool_size,
            thread_name_prefix="repopulse-worker",
        )
        logger.info(f"Worker pool started with {self.pool_size} workers")

    def shutdown(self, wait: bool = True):
        """Shut down the thread pool."""
        if self._executor:
            self._executor.shutdown(wait=wait)
            logger.info("Worker pool shut down")

    # -- job submission --

    def submit(self, job_id: str, repo_url: str = None, local_path: str = None) -> JobRecord:
        """Submit a new analysis job and return its record."""
        if self._executor is None:
            raise RuntimeError("Worker pool is not running")

        record = JobRecord(job_id=job_id, repo_url=repo_url, local_path=local_path)
        with self._lock:
            self._jobs[job_id] = record

        future = self._executor.submit(self._run_job, record)
        record.future = future
        return record

    # -- job lookup --

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        return [r.to_dict() for r in self._jobs.values()]

    # -- health --

    def health(self) -> dict:
        with self._lock:
            queued = sum(1 for j in self._jobs.values() if j.status == "queued")
            processing = sum(1 for j in self._jobs.values() if j.status == "processing")
            completed = sum(1 for j in self._jobs.values() if j.status == "completed")
            failed = sum(1 for j in self._jobs.values() if j.status == "failed")

        return {
            "pool_size": self.pool_size,
            "active_workers": processing,
            "queued_jobs": queued,
            "processing_jobs": processing,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "total_jobs": len(self._jobs),
        }

    # -- internal --

    def _run_job(self, record: JobRecord):
        """Execute the analysis for one job (runs inside a worker thread)."""
        record.status = "processing"
        record.started_at = datetime.now(timezone.utc).isoformat()
        logger.info(f"[{record.job_id}] processing started")

        cloner = GitRepoCloner()
        try:
            # figure out what to analyze
            if record.repo_url:
                repo_path = cloner.clone(record.repo_url, shallow=True)
            elif record.local_path:
                repo_path = record.local_path
            else:
                raise ValueError("No repo_url or local_path provided")

            # compute LOC
            project_loc = count_loc_in_directory(repo_path)

            # write to influxdb (best-effort)
            try:
                from src.core.influx import write_loc_metric

                repo_name = (record.repo_url or record.local_path or "unknown")
                repo_name = repo_name.rstrip("/").rstrip(".git").split("/")[-1]
                collected_at = datetime.now(timezone.utc).isoformat()

                # project-level metric
                write_loc_metric({
                    "repo_id": record.repo_url or record.local_path,
                    "repo_name": repo_name,
                    "branch": "HEAD",
                    "language": "mixed",
                    "granularity": "project",
                    "project_name": repo_name,
                    "total_loc": project_loc.total_loc,
                    "code_loc": project_loc.total_loc,
                    "comment_loc": project_loc.total_comment_lines,
                    "blank_loc": project_loc.total_blank_lines,
                    "collected_at": collected_at,
                })

                # per-file metrics
                for f in project_loc.files:
                    ext = os.path.splitext(f.path)[1].lower()
                    lang_map = {".py": "python", ".java": "java", ".ts": "typescript"}
                    write_loc_metric({
                        "repo_id": record.repo_url or record.local_path,
                        "repo_name": repo_name,
                        "branch": "HEAD",
                        "language": lang_map.get(ext, "unknown"),
                        "granularity": "file",
                        "project_name": repo_name,
                        "file_path": f.path,
                        "total_loc": f.loc,
                        "code_loc": f.loc,
                        "comment_loc": f.comment_lines,
                        "blank_loc": f.blank_lines,
                        "collected_at": collected_at,
                    })

                # per-package metrics
                for pkg in project_loc.packages:
                    write_loc_metric({
                        "repo_id": record.repo_url or record.local_path,
                        "repo_name": repo_name,
                        "branch": "HEAD",
                        "language": "mixed",
                        "granularity": "package",
                        "project_name": repo_name,
                        "package_name": pkg.package,
                        "total_loc": pkg.loc,
                        "code_loc": pkg.loc,
                        "comment_loc": pkg.comment_lines,
                        "blank_loc": 0,
                        "collected_at": collected_at,
                    })

                logger.info(f"[{record.job_id}] wrote {len(project_loc.files) + len(project_loc.packages) + 1} metric points to InfluxDB")
            except Exception as influx_err:
                logger.warning(f"[{record.job_id}] InfluxDB write failed: {influx_err}")

            # store result
            record.result = {
                "project_root": project_loc.project_root,
                "total_loc": project_loc.total_loc,
                "total_files": project_loc.total_files,
                "total_blank_lines": project_loc.total_blank_lines,
                "total_excluded_lines": project_loc.total_excluded_lines,
                "total_comment_lines": project_loc.total_comment_lines,
                "total_weighted_loc": project_loc.total_weighted_loc,
            }

            # compute churn (best-effort; requires a .git directory)
            try:
                churn = compute_repo_churn(repo_path, "1970-01-01", "2100-01-01")
                record.result["churn"] = churn
            except Exception as churn_err:
                logger.warning(f"[{record.job_id}] churn computation failed: {churn_err}")
                record.result["churn"] = {"added": 0, "deleted": 0, "modified": 0, "total": 0}

            record.status = "completed"
            logger.info(f"[{record.job_id}] completed — {project_loc.total_loc} LOC")

        except (GitCloneError, Exception) as exc:
            record.status = "failed"
            record.error = str(exc)
            logger.error(f"[{record.job_id}] failed: {exc}")
        finally:
            record.completed_at = datetime.now(timezone.utc).isoformat()
            cloner.cleanup()
