import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.models import (
    ErrorResponse,
    HealthResponse,
    JobRequest,
    JobResponse,
    JobStatus,
    LOCRequest,
    ProjectLOCResponse,
    PackageLOCResponse,
    FileLOCResponse,
)
from src.metrics.loc import count_loc_in_directory
from src.core.influx import get_client

logger = logging.getLogger("repopulse")

router = APIRouter()

jobs_store: dict[str, JobResponse] = {}


@router.get("/")
async def read_root():
    return {"message": "Welcome to RepoPulse API"}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        service="RepoPulse API",
        version="1.0.0",
    )


@router.get("/health/db")
async def db_health():
    """Check connectivity to InfluxDB using the client health endpoint."""
    try:
        client = get_client()
        health = client.health()
        status = getattr(health, "status", None) or (health.get("status") if isinstance(health, dict) else "unknown")
        message = getattr(health, "message", None) or (health.get("message") if isinstance(health, dict) else "")
        return {"status": status, "message": message}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "detail": str(e)})


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(request: Request):
    body = await request.json()
    logger.info(f"Incoming job request: {body}")

    try:
        job_request = JobRequest(**body)
    except ValidationError as e:
        errors = e.errors()
        messages = [err["msg"] for err in errors]
        logger.warning(f"Validation failed: {messages}")
        return JSONResponse(
            status_code=400,
            content={"detail": messages},
        )

    job_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    job = JobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        repo_url=job_request.repo_url,
        local_path=job_request.local_path,
        created_at=created_at,
        message="Job submitted successfully",
    )

    jobs_store[job_id] = job
    logger.info(f"Job created: {job_id}")

    return job


# ── LOC Metric Endpoint ─────────────────────────────────────────────────────


@router.post("/metrics/loc", response_model=ProjectLOCResponse, status_code=200)
async def compute_loc(request: Request):
    """
    Compute Lines of Code (LOC) for a local repository.

    Scans .java, .py, and .ts files. Excludes blank lines,
    whitespace-only lines, and brace-only lines.
    Returns counts at file, package, and project scope.
    """
    body = await request.json()
    logger.info(f"LOC metric request: {body}")

    try:
        loc_request = LOCRequest(**body)
    except ValidationError as e:
        errors = e.errors()
        messages = [err["msg"] for err in errors]
        logger.warning(f"LOC validation failed: {messages}")
        return JSONResponse(
            status_code=400,
            content={"detail": messages},
        )

    repo_path = loc_request.repo_path

    if not os.path.isdir(repo_path):
        logger.warning(f"LOC path not found: {repo_path}")
        return JSONResponse(
            status_code=404,
            content={"detail": f"Directory not found: {repo_path}"},
        )

    project_loc = count_loc_in_directory(repo_path)

    return ProjectLOCResponse(
        project_root=project_loc.project_root,
        total_loc=project_loc.total_loc,
        total_files=project_loc.total_files,
        total_blank_lines=project_loc.total_blank_lines,
        total_excluded_lines=project_loc.total_excluded_lines,
        total_comment_lines=project_loc.total_comment_lines,
        packages=[
            PackageLOCResponse(
                package=pkg.package,
                loc=pkg.loc,
                file_count=pkg.file_count,
                comment_lines=pkg.comment_lines,
                files=[
                    FileLOCResponse(
                        path=f.path,
                        total_lines=f.total_lines,
                        loc=f.loc,
                        blank_lines=f.blank_lines,
                        excluded_lines=f.excluded_lines,
                        comment_lines=f.comment_lines,
                    )
                    for f in pkg.files
                ],
            )
            for pkg in project_loc.packages
        ],
        files=[
            FileLOCResponse(
                path=f.path,
                total_lines=f.total_lines,
                loc=f.loc,
                blank_lines=f.blank_lines,
                excluded_lines=f.excluded_lines,
                comment_lines=f.comment_lines,
            )
            for f in project_loc.files
        ],
    )

