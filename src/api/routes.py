import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import ValidationError

from src.api.models import (
    ErrorResponse,
    HealthResponse,
    JobRequest,
    JobResponse,
    JobStatus,
)

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
        from fastapi.responses import JSONResponse
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

