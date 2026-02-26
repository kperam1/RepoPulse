import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.models import (
    AnalyzeRequest,
    ErrorResponse,
    HealthResponse,
    JobDetailResponse,
    JobRequest,
    JobResponse,
    JobStatus,
    LOCRequest,
    ProjectLOCResponse,
    PackageLOCResponse,
    FileLOCResponse,
    WorkerHealthResponse,
    TimeSeriesMetricSnapshot,
)
from src.metrics.loc import count_loc_in_directory
from src.core.influx import get_client, write_loc_metric, write_timeseries_snapshot
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

@router.post("/analyze", response_model=ProjectLOCResponse, status_code=200)
async def analyze_repo(request: Request):
    """Clone a public GitHub repo, compute LOC metrics, write to InfluxDB, and return results."""
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
    cloner = GitRepoCloner()

    try:
        # 1. Clone the repo
        logger.info(f"Cloning {repo_url} …")
        repo_path = cloner.clone(repo_url, shallow=True)
        logger.info(f"Clone complete → {repo_path}")

        # 2. Compute LOC
        project_loc = count_loc_in_directory(repo_path)

        # 3. Extract git metadata & Write metrics to InfluxDB
        # Derive a simple repo name from the URL
        repo_name = repo_url.rstrip("/").rstrip(".git").split("/")[-1]
        collected_at = datetime.now(timezone.utc).isoformat()
        
        # Get commit information from cloned repo
        commit_hash = cloner.commit_hash  # Automatically extracted during clone
        commit_timestamp = GitRepoCloner.get_commit_timestamp(repo_path, commit_hash)
        
        logger.info(f"Repository at commit {commit_hash[:8] if commit_hash else 'unknown'}")

        # Write project-level metric
        try:
            write_loc_metric({
                "repo_id": repo_url,
                "repo_name": repo_name,
                "branch": "HEAD",
                "commit_hash": commit_hash,
                "language": "mixed",
                "granularity": "project",
                "project_name": repo_name,
                "total_loc": project_loc.total_loc,
                "code_loc": project_loc.total_loc,
                "comment_loc": project_loc.total_comment_lines,
                "blank_loc": project_loc.total_blank_lines,
                "collected_at": collected_at,
            })
            
            # Write time-series snapshot for project-level metrics
            if commit_hash:
                write_timeseries_snapshot({
                    "repo_id": repo_url,
                    "repo_name": repo_name,
                    "commit_hash": commit_hash,
                    "commit_timestamp": commit_timestamp,
                    "branch": "HEAD",
                    "snapshot_timestamp": collected_at,
                    "granularity": "project",
                    "snapshot_type": "loc",
                    "total_loc": project_loc.total_loc,
                    "code_loc": project_loc.total_loc,
                    "comment_loc": project_loc.total_comment_lines,
                    "blank_loc": project_loc.total_blank_lines,
                    "project_name": repo_name,
                    "language": "mixed",
                })
            
            # Write per-file metrics
            for f in project_loc.files:
                ext = os.path.splitext(f.path)[1].lower()
                lang_map = {".py": "python", ".java": "java", ".ts": "typescript"}
                lang = lang_map.get(ext, "unknown")
                
                write_loc_metric({
                    "repo_id": repo_url,
                    "repo_name": repo_name,
                    "branch": "HEAD",
                    "commit_hash": commit_hash,
                    "language": lang,
                    "granularity": "file",
                    "project_name": repo_name,
                    "file_path": f.path,
                    "total_loc": f.loc,
                    "code_loc": f.loc,
                    "comment_loc": f.comment_lines,
                    "blank_loc": f.blank_lines,
                    "collected_at": collected_at,
                })
                
                # Write time-series snapshot for file-level metrics
                if commit_hash:
                    write_timeseries_snapshot({
                        "repo_id": repo_url,
                        "repo_name": repo_name,
                        "commit_hash": commit_hash,
                        "commit_timestamp": commit_timestamp,
                        "branch": "HEAD",
                        "snapshot_timestamp": collected_at,
                        "granularity": "file",
                        "snapshot_type": "loc",
                        "total_loc": f.loc,
                        "code_loc": f.loc,
                        "comment_loc": f.comment_lines,
                        "blank_loc": f.blank_lines,
                        "file_path": f.path,
                        "project_name": repo_name,
                        "language": lang,
                    })
            
            # Write per-package metrics
            for pkg in project_loc.packages:
                write_loc_metric({
                    "repo_id": repo_url,
                    "repo_name": repo_name,
                    "branch": "HEAD",
                    "commit_hash": commit_hash,
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
                
                # Write time-series snapshot for package-level metrics
                if commit_hash:
                    write_timeseries_snapshot({
                        "repo_id": repo_url,
                        "repo_name": repo_name,
                        "commit_hash": commit_hash,
                        "commit_timestamp": commit_timestamp,
                        "branch": "HEAD",
                        "snapshot_timestamp": collected_at,
                        "granularity": "package",
                        "snapshot_type": "loc",
                        "total_loc": pkg.loc,
                        "code_loc": pkg.loc,
                        "comment_loc": pkg.comment_lines,
                        "blank_loc": 0,
                        "package_name": pkg.package,
                        "project_name": repo_name,
                        "language": "mixed",
                    })
            
            logger.info(f"Wrote {len(project_loc.files) + len(project_loc.packages) + 1} metric points to InfluxDB")
        except Exception as influx_err:
            # InfluxDB write failed but we still return the LOC data
            logger.warning(f"InfluxDB write failed (metrics still returned): {influx_err}")

        # 4. Build response
        response = ProjectLOCResponse(
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
            files=[
                FileLOCResponse(
                    path=f.path, total_lines=f.total_lines, loc=f.loc,
                    blank_lines=f.blank_lines, excluded_lines=f.excluded_lines,
                    comment_lines=f.comment_lines, weighted_loc=f.weighted_loc,
                )
                for f in project_loc.files
            ],
        )
        return response

    except GitCloneError as e:
        logger.error(f"Clone failed for {repo_url}: {e}")
        return JSONResponse(status_code=400, content={"detail": str(e)})
    except Exception as e:
        logger.error(f"Analyze failed: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})
    finally:
        cloner.cleanup()

