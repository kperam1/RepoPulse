import os
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
            # Allow absolute paths on Windows and POSIX.
            # Also accept a leading '/' on Windows (tests use this form).
            if not (os.path.isabs(v) or v.startswith("/")):
                raise ValueError("local_path must be an absolute path")
            # Normalize and disallow any '..' path parts
            norm = os.path.normpath(v)
            if ".." in norm.split(os.path.sep):
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


# LOC Metrics Schema
class LOCMetrics(BaseModel):
    repo_id: str = Field(..., description="Unique identifier for the repository")
    repo_name: str = Field(..., description="Repository name")
    branch: str = Field(..., description="Branch name")
    commit_hash: str = Field(..., description="Commit hash")
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


# LOC response models


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


class ModuleLOCResponse(BaseModel):
    module: str
    loc: int
    package_count: int
    file_count: int
    comment_lines: int
    packages: list[PackageLOCResponse]


class ProjectLOCResponse(BaseModel):
    project_root: str
    total_loc: int
    total_files: int
    total_blank_lines: int
    total_excluded_lines: int
    total_comment_lines: int
    total_weighted_loc: float
    packages: list[PackageLOCResponse]
    modules: list[ModuleLOCResponse]
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
        # Allow absolute paths for the current OS.
        # Also accept paths that start with '/' on Windows.
        if not (os.path.isabs(v) or v.startswith("/")):
            raise ValueError("repo_path must be an absolute path")
        norm = os.path.normpath(v)
        if ".." in norm.split(os.path.sep):
            raise ValueError("repo_path must not contain '..'")
        return v


class AnalyzeRequest(BaseModel):
    """Request body for the /analyze endpoint."""
    repo_url: str = Field(..., description="Public GitHub HTTPS URL to analyse")
    start_date: Optional[str] = Field(None, description="Start date for the analysis in ISO format")
    end_date: Optional[str] = Field(None, description="End date for the analysis in ISO format")

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


class ChurnResponse(BaseModel):
    """Churn metrics for a date range."""
    added: int
    deleted: int
    modified: int
    total: int


class AnalyzeResponse(BaseModel):
    """Full response for the /analyze endpoint including LOC and churn."""
    repo_url: str
    start_date: Optional[str] = Field(None, description="Start date for the analysis in ISO format")
    end_date: Optional[str] = Field(None, description="End date for the analysis in ISO format")
    loc: ProjectLOCResponse
    churn: Optional[ChurnResponse] = None
    churn_daily: Optional[dict[str, ChurnResponse]] = None

