import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Request, Query
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
    SnapshotHistoryResponse,
    LatestSnapshotResponse,
    CommitSnapshotsResponse,
    SnapshotRecord,
    SnapshotData,
    CommitInfo,
    CommitListResponse,
    CommitComparisonResponse,
)
from src.metrics.loc import count_loc_in_directory
from src.core.influx import (
    get_client,
    write_loc_metric,
    write_timeseries_snapshot,
    query_timeseries_snapshots_by_repo,
    query_latest_snapshot,
    query_snapshot_at_timestamp,
    query_snapshots_by_commit,
    query_commits_in_range,
    query_compare_commits,
)
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


@router.get("/metrics/timeseries/snapshots/{repo_id}/latest", response_model=LatestSnapshotResponse)
async def get_latest_snapshot(repo_id: str, granularity: str = Query("project")):
    """Get the most recent metric snapshot for a repository."""
    try:
        if granularity not in ("project", "package", "file"):
            return JSONResponse(
                status_code=400,
                content={"detail": "granularity must be 'project', 'package', or 'file'"}
            )
        
        snapshot_data = query_latest_snapshot(repo_id, granularity)
        
        if not snapshot_data:
            return LatestSnapshotResponse(
                repo_id=repo_id,
                repo_name="unknown",
                latest_snapshot=None
            )
        
        snapshot_record = SnapshotRecord(
            timestamp=snapshot_data["time"].isoformat() if snapshot_data["time"] else "",
            repo_id=snapshot_data.get("repo_id", ""),
            repo_name=snapshot_data.get("repo_name", ""),
            commit_hash=snapshot_data.get("commit_hash", ""),
            branch=snapshot_data.get("branch", ""),
            granularity=snapshot_data.get("granularity", ""),
            metrics=SnapshotData(
                total_loc=0,
                code_loc=0,
                comment_loc=0,
                blank_loc=0
            ),
            file_path=snapshot_data.get("file_path"),
            package_name=snapshot_data.get("package_name")
        )
        
        return LatestSnapshotResponse(
            repo_id=repo_id,
            repo_name=snapshot_data.get("repo_name", ""),
            latest_snapshot=snapshot_record
        )
    except Exception as e:
        logger.error(f"Error querying latest snapshot: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})


@router.get("/metrics/timeseries/snapshots/{repo_id}/range", response_model=SnapshotHistoryResponse)
async def get_snapshot_history(
    repo_id: str,
    start_time: str = Query(..., description="Start timestamp (ISO 8601)"),
    end_time: str = Query(..., description="End timestamp (ISO 8601)"),
    granularity: str = Query("project", description="Granularity filter")
):
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        
        if start_dt >= end_dt:
            return JSONResponse(
                status_code=400,
                content={"detail": "start_time must be before end_time"}
            )
        
        snapshots_data = query_timeseries_snapshots_by_repo(
            repo_id,
            start_dt,
            end_dt,
            granularity if granularity != "all" else None
        )
        
        snapshots = []
        repo_name = "unknown"
        
        for snap in snapshots_data:
            if not repo_name or repo_name == "unknown":
                repo_name = snap.get("repo_name", "unknown")
            
            snapshot_record = SnapshotRecord(
                timestamp=snap["time"].isoformat() if snap.get("time") else "",
                repo_id=snap.get("repo_id", ""),
                repo_name=snap.get("repo_name", ""),
                commit_hash=snap.get("commit_hash", ""),
                branch=snap.get("branch", ""),
                granularity=snap.get("granularity", ""),
                metrics=SnapshotData(
                    total_loc=0,
                    code_loc=0,
                    comment_loc=0,
                    blank_loc=0
                ),
                file_path=snap.get("file_path"),
                package_name=snap.get("package_name")
            )
            snapshots.append(snapshot_record)
        
        return SnapshotHistoryResponse(
            repo_id=repo_id,
            repo_name=repo_name,
            granularity=granularity,
            start_time=start_time,
            end_time=end_time,
            snapshots=snapshots,
            count=len(snapshots)
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Invalid timestamp format: {e}"}
        )
    except Exception as e:
        logger.error(f"Error querying snapshot history: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})


@router.get("/metrics/timeseries/snapshots/{repo_id}/at/{timestamp}", response_model=SnapshotRecord)
async def get_snapshot_at_time(repo_id: str, timestamp: str):
    try:
        target_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        
        snapshot_data = query_snapshot_at_timestamp(repo_id, target_dt)
        
        if not snapshot_data:
            return JSONResponse(
                status_code=404,
                content={"detail": f"No snapshot found for {repo_id} at or before {timestamp}"}
            )
        
        return SnapshotRecord(
            timestamp=snapshot_data["time"].isoformat() if snapshot_data.get("time") else "",
            repo_id=snapshot_data.get("repo_id", ""),
            repo_name=snapshot_data.get("repo_name", ""),
            commit_hash=snapshot_data.get("commit_hash", ""),
            branch=snapshot_data.get("branch", ""),
            granularity=snapshot_data.get("granularity", ""),
            metrics=SnapshotData(
                total_loc=0,
                code_loc=0,
                comment_loc=0,
                blank_loc=0
            ),
            file_path=snapshot_data.get("file_path"),
            package_name=snapshot_data.get("package_name")
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Invalid timestamp format: {e}"}
        )
    except Exception as e:
        logger.error(f"Error querying snapshot: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})


@router.get("/metrics/timeseries/snapshots/{repo_id}/commit/{commit_hash}", response_model=CommitSnapshotsResponse)
async def get_snapshots_for_commit(repo_id: str, commit_hash: str):
    try:
        snapshots_data = query_snapshots_by_commit(repo_id, commit_hash)
        
        snapshots = []
        repo_name = "unknown"
        
        for snap in snapshots_data:
            if not repo_name or repo_name == "unknown":
                repo_name = snap.get("repo_name", "unknown")
            
            snapshot_record = SnapshotRecord(
                timestamp=snap["time"].isoformat() if snap.get("time") else "",
                repo_id=snap.get("repo_id", ""),
                repo_name=snap.get("repo_name", ""),
                commit_hash=snap.get("commit_hash", ""),
                branch=snap.get("branch", ""),
                granularity=snap.get("granularity", ""),
                metrics=SnapshotData(
                    total_loc=0,
                    code_loc=0,
                    comment_loc=0,
                    blank_loc=0
                ),
                file_path=snap.get("file_path"),
                package_name=snap.get("package_name")
            )
            snapshots.append(snapshot_record)
        
        return CommitSnapshotsResponse(
            repo_id=repo_id,
            repo_name=repo_name,
            commit_hash=commit_hash,
            snapshots=snapshots,
            count=len(snapshots)
        )
    except Exception as e:
        logger.error(f"Error querying commit snapshots: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})


@router.get("/metrics/timeseries/commits/{repo_id}", response_model=CommitListResponse)
async def get_commits_in_range(
    repo_id: str,
    start_time: str = Query(...),
    end_time: str = Query(...),
    branch: Optional[str] = Query(None)
):
    try:
        start = _parse_timestamp(start_time)
        end = _parse_timestamp(end_time)
        
        if not start or not end:
            return JSONResponse(status_code=400, content={"detail": "Invalid timestamp format"})
        
        if start >= end:
            return JSONResponse(status_code=400, content={"detail": "start_time must be before end_time"})
        
        commits_data = query_commits_in_range(repo_id, start, end, branch)
        
        commits = [
            CommitInfo(
                commit_hash=c.get("commit_hash", ""),
                branch=c.get("branch", ""),
                time=c["time"].isoformat() if c.get("time") else ""
            )
            for c in commits_data
        ]
        
        return CommitListResponse(
            repo_id=repo_id,
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            branch=branch,
            commits=commits,
            count=len(commits)
        )
    except Exception as e:
        logger.error(f"Error querying commits: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})


@router.get("/metrics/timeseries/commits/{repo_id}/compare", response_model=CommitComparisonResponse)
async def compare_commits(
    repo_id: str,
    commit1: str = Query(...),
    commit2: str = Query(...),
    granularity: str = Query("project")
):
    try:
        if granularity not in ("project", "package", "file"):
            return JSONResponse(
                status_code=400,
                content={"detail": "granularity must be 'project', 'package', or 'file'"}
            )
        
        comparison = query_compare_commits(repo_id, commit1, commit2, granularity)
        
        return CommitComparisonResponse(
            repo_id=comparison["repo_id"],
            commit1=comparison["commit1"],
            commit2=comparison["commit2"],
            granularity=comparison["granularity"],
            snapshots_commit1=comparison["snapshots_commit1"],
            snapshots_commit2=comparison["snapshots_commit2"]
        )
    except Exception as e:
        logger.error(f"Error comparing commits: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})
