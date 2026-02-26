import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(\.git)?/?$"
)


class JobStatus(str, Enum):
    QUEUED = "queued"
    PENDING = "pending"
    PROCESSING = "processing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRequest(BaseModel):
    repo_url: Optional[str] = Field(default=None)
    local_path: Optional[str] = Field(default=None)

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("repo_url cannot be empty")
            if not GITHUB_URL_PATTERN.match(v):
                raise ValueError(
                    "repo_url must be a valid GitHub URL in the format "
                    "https://github.com/owner/repo"
                )
        return v

    @field_validator("local_path")
    @classmethod
    def validate_local_path(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("local_path cannot be empty")
            if not v.startswith("/"):
                raise ValueError("local_path must be an absolute path starting with /")
            if ".." in v:
                raise ValueError("local_path must not contain '..'")
        return v

    def model_post_init(self, __context):
        if not self.repo_url and not self.local_path:
            raise ValueError("Either 'repo_url' or 'local_path' must be provided")
        if self.repo_url and self.local_path:
            raise ValueError("Only one of 'repo_url' or 'local_path' should be provided, not both")


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    repo_url: Optional[str] = None
    local_path: Optional[str] = None
    created_at: str
    message: str


class JobDetailResponse(BaseModel):
    """Full job status including results (returned by GET /jobs/{job_id})."""
    job_id: str
    status: str
    repo_url: Optional[str] = None
    local_path: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class WorkerHealthResponse(BaseModel):
    """Worker pool health info."""
    pool_size: int
    active_workers: int
    queued_jobs: int
    processing_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_jobs: int


class CommitMetadata(BaseModel):
    """Git commit information linked to metric snapshots."""
    commit_hash: str = Field(..., description="Full commit SHA-1 hash")
    commit_timestamp: Optional[str] = Field(None, description="Commit timestamp (ISO 8601)")
    branch: str = Field(..., description="Branch name")
    author: Optional[str] = Field(None, description="Commit author")


class TimeSeriesMetricSnapshot(BaseModel):
    """Point-in-time metric snapshot linked to a Git commit."""
    repo_id: str = Field(..., description="Repository identifier")
    repo_name: str = Field(..., description="Repository name")
    commit_hash: str = Field(..., description="Git commit SHA-1 hash for metric linkage")
    commit_timestamp: Optional[str] = Field(None, description="Timestamp of commit (ISO 8601)")
    branch: str = Field(..., description="Branch name")
    snapshot_timestamp: str = Field(..., description="When snapshot was captured (ISO 8601)")
    granularity: str = Field(..., description="Snapshot granularity: 'project', 'package', or 'file'")
    snapshot_type: str = Field(default="loc", description="Type of metrics: 'loc' for lines of code")
    
    total_loc: int = Field(..., description="Total lines of code")
    code_loc: int = Field(..., description="Lines of actual code")
    comment_loc: int = Field(..., description="Lines of comments")
    blank_loc: int = Field(..., description="Blank lines")
    
    file_path: Optional[str] = Field(None, description="File path for file-level snapshots")
    package_name: Optional[str] = Field(None, description="Package name for package-level snapshots")
    language: Optional[str] = Field(None, description="Programming language")
    project_name: Optional[str] = Field(None, description="Project name if applicable")


class SnapshotData(BaseModel):
    total_loc: int = Field(..., description="Total LOC")
    code_loc: int = Field(..., description="Code LOC")
    comment_loc: int = Field(..., description="Comment LOC")
    blank_loc: int = Field(..., description="Blank lines")


class SnapshotRecord(BaseModel):
    timestamp: str = Field(..., description="Snapshot timestamp")
    repo_id: str = Field(..., description="Repository ID")
    repo_name: str = Field(..., description="Repository name")
    commit_hash: str = Field(..., description="Commit hash")
    branch: str = Field(..., description="Branch")
    granularity: str = Field(..., description="Granularity")
    metrics: SnapshotData = Field(..., description="Metrics")
    file_path: Optional[str] = Field(None, description="File path")
    package_name: Optional[str] = Field(None, description="Package name")


class SnapshotHistoryResponse(BaseModel):
    """Historical snapshots for a repository within a date range."""
    repo_id: str = Field(..., description="Repository ID")
    repo_name: str = Field(..., description="Repository name")
    granularity: str = Field(..., description="Granularity")
    start_time: str = Field(..., description="Range start")
    end_time: str = Field(..., description="Range end")
    snapshots: list[SnapshotRecord] = Field(..., description="Snapshots")
    count: int = Field(..., description="Count")


class LatestSnapshotResponse(BaseModel):
    """Latest snapshot for a repository."""
    repo_id: str = Field(..., description="Repository ID")
    repo_name: str = Field(..., description="Repository name")
    latest_snapshot: Optional[SnapshotRecord] = Field(None, description="Latest snapshot")


class CommitSnapshotsResponse(BaseModel):
    repo_id: str = Field(..., description="Repository ID")
    repo_name: str = Field(..., description="Repository name")
    commit_hash: str = Field(..., description="Commit hash")
    snapshots: list[SnapshotRecord] = Field(..., description="Snapshots")
    count: int = Field(..., description="Count")


class SnapshotQueryRequest(BaseModel):
    repo_id: str = Field(..., description="Repository ID")
    start_time: str = Field(..., description="Start timestamp")
    end_time: str = Field(..., description="End timestamp")
    granularity: Optional[str] = Field(None, description="Granularity filter")

# LOC Metrics Schema
class LOCMetrics(BaseModel):
    repo_id: str = Field(..., description="Unique identifier for the repository")
    repo_name: str = Field(..., description="Repository name")
    branch: str = Field(..., description="Branch name")
    commit_hash: Optional[str] = Field(None, description="Git commit hash for metric linkage")
    language: str = Field(..., description="Programming language")
    granularity: str = Field(..., description="Granularity of the metric: 'project', 'package', or 'file'")
    project_name: Optional[str] = Field(None, description="Project name if applicable")
    package_name: Optional[str] = Field(None, description="Package name if applicable")
    file_path: Optional[str] = Field(None, description="File path if applicable")
    total_loc: int = Field(..., description="Total lines of code")
    code_loc: int = Field(..., description="Lines of code (excluding comments and blanks)")
    comment_loc: int = Field(..., description="Lines of comments")
    blank_loc: int = Field(..., description="Blank lines")
    collected_at: str = Field(..., description="Timestamp when metrics were collected (ISO format)")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ErrorResponse(BaseModel):
    detail: str


class FileLOCResponse(BaseModel):
    path: str
    total_lines: int
    loc: int
    blank_lines: int
    excluded_lines: int
    comment_lines: int
    weighted_loc: float


class PackageLOCResponse(BaseModel):
    package: str
    loc: int
    file_count: int
    comment_lines: int
    weighted_loc: float
    files: list[FileLOCResponse]


class ProjectLOCResponse(BaseModel):
    project_root: str
    total_loc: int
    total_files: int
    total_blank_lines: int
    total_excluded_lines: int
    total_comment_lines: int
    total_weighted_loc: float
    packages: list[PackageLOCResponse]
    files: list[FileLOCResponse]


class LOCRequest(BaseModel):
    repo_path: str = Field(
        ..., description="Absolute path to the local repository to analyse"
    )

    @field_validator("repo_path")
    @classmethod
    def validate_repo_path(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("repo_path cannot be empty")
        if not v.startswith("/"):
            raise ValueError("repo_path must be an absolute path starting with /")
        if ".." in v:
            raise ValueError("repo_path must not contain '..'")
        return v


class AnalyzeRequest(BaseModel):
    """Request to clone and analyze a public GitHub repository."""
    repo_url: str = Field(..., description="Public GitHub HTTPS URL to analyse")

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("repo_url cannot be empty")
        if not GITHUB_URL_PATTERN.match(v):
            raise ValueError(
                "repo_url must be a valid GitHub URL (e.g. https://github.com/owner/repo)"
            )
        return v

