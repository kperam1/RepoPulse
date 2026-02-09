import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from src.api.models import (
    ErrorResponse,
    HealthResponse,
    JobRequest,
    JobResponse,
    JobStatus,
)

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


@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(job_request: JobRequest):
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

    return job
