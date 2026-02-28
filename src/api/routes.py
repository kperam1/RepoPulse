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
    JobDetailResponse,
    JobRequest,
    JobResponse,
    JobStatus,
    LOCRequest,
    ProjectLOCResponse,
    PackageLOCResponse,
    ModuleLOCResponse,
    FileLOCResponse,
    WorkerHealthResponse,
)
from src.metrics.loc import count_loc_in_directory
from src.metrics.churn import compute_repo_churn, compute_daily_churn
from src.core.influx import get_client, write_loc_metric, write_churn_metric, write_daily_churn_metrics
from src.core.git_clone import GitRepoCloner, GitCloneError

logger = logging.getLogger("repopulse")

router = APIRouter()


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
    """Submit a repo analysis job to the worker pool."""
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

    # submit to the worker pool
    pool = request.app.state.worker_pool
    try:
        pool.submit(
            job_id=job_id,
            repo_url=job_request.repo_url,
            local_path=job_request.local_path,
        )
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"detail": str(e)})

    created_at = datetime.now(timezone.utc).isoformat()

    job = JobResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        repo_url=job_request.repo_url,
        local_path=job_request.local_path,
        created_at=created_at,
        message="Job queued for processing",
    )
    logger.info(f"Job queued: {job_id}")
    return job


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: str, request: Request):
    """Get the current status and result of a job."""
    pool = request.app.state.worker_pool
    record = pool.get_job(job_id)
    if record is None:
        return JSONResponse(status_code=404, content={"detail": "Job not found"})
    return JobDetailResponse(**record.to_dict())


@router.get("/jobs", response_model=list[JobDetailResponse])
async def list_jobs(request: Request):
    """List all jobs with their statuses."""
    pool = request.app.state.worker_pool
    return [JobDetailResponse(**j) for j in pool.list_jobs()]


@router.get("/workers/health", response_model=WorkerHealthResponse)
async def workers_health(request: Request):
    """Return worker pool health: pool size, active/queued/completed counts."""
    pool = request.app.state.worker_pool
    return WorkerHealthResponse(**pool.health())


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
        total_weighted_loc=project_loc.total_weighted_loc,
        packages=[
            PackageLOCResponse(
                package=pkg.package,
                loc=pkg.loc,
                file_count=pkg.file_count,
                comment_lines=pkg.comment_lines,
                weighted_loc=pkg.weighted_loc,
                files=[
                    FileLOCResponse(
                        path=f.path,
                        total_lines=f.total_lines,
                        loc=f.loc,
                        blank_lines=f.blank_lines,
                        excluded_lines=f.excluded_lines,
                        comment_lines=f.comment_lines,
                        weighted_loc=f.weighted_loc,
                    )
                    for f in pkg.files
                ],
            )
            for pkg in project_loc.packages
        ],
        modules=[
            ModuleLOCResponse(
                module=m.module,
                loc=m.loc,
                package_count=len(m.packages),
                file_count=m.file_count,
                comment_lines=m.comment_lines,
                packages=[
                    PackageLOCResponse(
                        package=p.package,
                        loc=p.loc,
                        file_count=p.file_count,
                        comment_lines=p.comment_lines,
                        files=[
                            FileLOCResponse(
                                path=f.path,
                                total_lines=f.total_lines,
                                loc=f.loc,
                                blank_lines=f.blank_lines,
                                excluded_lines=f.excluded_lines,
                                comment_lines=f.comment_lines,
                            )
                            for f in p.files
                        ],
                    )
                    for p in m.packages
                ],
            )
            for m in project_loc.modules
        ],
        files=[
            FileLOCResponse(
                path=f.path,
                total_lines=f.total_lines,
                loc=f.loc,
                blank_lines=f.blank_lines,
                excluded_lines=f.excluded_lines,
                comment_lines=f.comment_lines,
                weighted_loc=f.weighted_loc,
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

        # 3. Compute daily churn
        logger.info(f"Computing daily churn for {start_date} → {end_date}")
        daily = compute_daily_churn(repo_path, start_date, end_date)
        logger.info(f"Daily churn days: {len(daily)}")

        churn_summary = {"added": 0, "deleted": 0, "modified": 0, "total": 0}
        for day_churn in daily.values():
            churn_summary["added"] += day_churn["added"]
            churn_summary["deleted"] += day_churn["deleted"]
        churn_summary["modified"] = min(churn_summary["added"], churn_summary["deleted"])
        churn_summary["total"] = churn_summary["added"] + churn_summary["deleted"]

        # 4. Write metrics to InfluxDB
        repo_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]

        try:
            write_loc_metric(repo_name, project_loc.total_loc)
        except Exception as influx_err:
            logger.warning(f"Failed to write LOC to InfluxDB: {influx_err}")

        try:
            write_churn_metric(repo_url, start_date, end_date, churn_summary)
        except Exception as influx_err:
            logger.warning(f"Failed to write churn to InfluxDB: {influx_err}")

        try:
            write_daily_churn_metrics(repo_url, daily)
        except Exception as influx_err:
            logger.warning(f"Failed to write daily churn to InfluxDB: {influx_err}")

        # 5. Build LOC response
        loc_response = ProjectLOCResponse(
            project_root=repo_path,
            total_loc=project_loc.total_loc,
            total_files=project_loc.total_files,
            total_blank_lines=project_loc.total_blank_lines,
            total_excluded_lines=project_loc.total_excluded_lines,
            total_comment_lines=project_loc.total_comment_lines,
            total_weighted_loc=project_loc.total_weighted_loc,
            packages=[
                PackageLOCResponse(
                    package=pkg.package,
                    loc=pkg.loc,
                    file_count=pkg.file_count,
                    comment_lines=pkg.comment_lines,
                    weighted_loc=pkg.weighted_loc,
                    files=[
                        FileLOCResponse(
                            path=f.path, total_lines=f.total_lines, loc=f.loc,
                            blank_lines=f.blank_lines, excluded_lines=f.excluded_lines,
                            comment_lines=f.comment_lines, weighted_loc=f.weighted_loc,
                        )
                        for f in pkg.files
                    ],
                )
                for pkg in project_loc.packages
            ],
            modules=[
                ModuleLOCResponse(
                    module=m.module,
                    loc=m.loc,
                    package_count=len(m.packages),
                    file_count=m.file_count,
                    comment_lines=m.comment_lines,
                    packages=[
                        PackageLOCResponse(
                            package=p.package,
                            loc=p.loc,
                            file_count=p.file_count,
                            comment_lines=p.comment_lines,
                            files=[
                                FileLOCResponse(
                                    path=f.path, total_lines=f.total_lines, loc=f.loc,
                                    blank_lines=f.blank_lines, excluded_lines=f.excluded_lines,
                                    comment_lines=f.comment_lines,
                                )
                                for f in p.files
                            ],
                        )
                        for p in m.packages
                    ],
                )
                for m in project_loc.modules
            ],
            files=[
                FileLOCResponse(
                    path=f.path, total_lines=f.total_lines, loc=f.loc,
                    blank_lines=f.blank_lines, excluded_lines=f.excluded_lines,
                    comment_lines=f.comment_lines, weighted_loc=f.weighted_loc,
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
            churn=ChurnResponse(**churn_summary),
            churn_daily={day: ChurnResponse(**vals) for day, vals in daily.items()},
        )

    except GitCloneError as e:
        logger.error(f"Clone failed for {repo_url}: {e}")
        return JSONResponse(status_code=400, content={"detail": str(e)})
    except Exception as e:
        logger.error(f"Analyze failed: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})
    finally:
        cloner.cleanup()

