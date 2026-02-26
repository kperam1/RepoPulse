import logging
import os
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    ChurnResponse,
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
from src.metrics.churn import compute_repo_churn
from src.core.influx import get_client, write_loc_metric, write_churn_metric
from src.core.git_clone import GitRepoCloner, GitCloneError

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


# --- LOC Metric Endpoint ---


@router.post("/metrics/loc", response_model=ProjectLOCResponse, status_code=200)
async def compute_loc(request: Request):
    """Compute LOC for a local repo path. Supports .java, .py, and .ts files."""
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


# --- Analyze Endpoint (clone -> LOC -> Churn -> InfluxDB) ---


@router.post("/analyze", response_model=AnalyzeResponse, status_code=200)
async def analyze_repo(request: Request):
    """Clone a public GitHub repo, compute LOC and churn metrics, write to InfluxDB, and return results."""
    body = await request.json()
    logger.info(f"Analyze request: {body}")

    try:
        analyze_request = AnalyzeRequest(**body)
    except ValidationError as e:
        errors = e.errors()
        messages = [err["msg"] for err in errors]
        logger.warning(f"Analyze validation failed: {messages}")
        return JSONResponse(status_code=400, content={"detail": messages})

    repo_url = analyze_request.repo_url

    # Determine date range — default to last 7 days if not provided
    today = datetime.now(timezone.utc).date()
    end_date = analyze_request.end_date or today.isoformat()
    start_date = analyze_request.start_date or (today - timedelta(days=7)).isoformat()

    cloner = GitRepoCloner()

    try:
        # 1. Clone the repo (full clone needed for commit history)
        logger.info(f"Cloning {repo_url} …")
        repo_path = cloner.clone(repo_url, shallow=False)
        logger.info(f"Clone complete → {repo_path}")

        # 2. Compute LOC
        project_loc = count_loc_in_directory(repo_path)

        # 3. Compute churn
        logger.info(f"Computing churn for {start_date} → {end_date}")
        churn = compute_repo_churn(repo_path, start_date, end_date)
        logger.info(f"Churn result: {churn}")

        # 4. Write metrics to InfluxDB
        repo_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]

        try:
            write_loc_metric(repo_name, project_loc.total_loc)
        except Exception as influx_err:
            logger.warning(f"Failed to write LOC to InfluxDB: {influx_err}")

        try:
            write_churn_metric(repo_url, start_date, end_date, churn)
        except Exception as influx_err:
            logger.warning(f"Failed to write churn to InfluxDB: {influx_err}")

        # 5. Build LOC response
        loc_response = ProjectLOCResponse(
            project_root=repo_path,
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
                            path=f.path, total_lines=f.total_lines, loc=f.loc,
                            blank_lines=f.blank_lines, excluded_lines=f.excluded_lines,
                            comment_lines=f.comment_lines,
                        )
                        for f in pkg.files
                    ],
                )
                for pkg in project_loc.packages
            ],
            files=[
                FileLOCResponse(
                    path=f.path, total_lines=f.total_lines, loc=f.loc,
                    blank_lines=f.blank_lines, excluded_lines=f.excluded_lines,
                    comment_lines=f.comment_lines,
                )
                for f in project_loc.files
            ],
        )

        # 6. Return combined response
        return AnalyzeResponse(
            repo_url=repo_url,
            start_date=start_date,
            end_date=end_date,
            loc=loc_response,
            churn=ChurnResponse(**churn),
        )

    except GitCloneError as e:
        logger.error(f"Clone failed for {repo_url}: {e}")
        return JSONResponse(status_code=400, content={"detail": str(e)})
    except Exception as e:
        logger.error(f"Analyze failed: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})
    finally:
        cloner.cleanup()

