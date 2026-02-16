import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/?$"
)


class JobStatus(str, Enum):
    PENDING = "pending"
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


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ErrorResponse(BaseModel):
    detail: str


# ── LOC Metric Models ────────────────────────────────────────────────────────


class FileLOCResponse(BaseModel):
    path: str
    total_lines: int
    loc: int
    blank_lines: int
    excluded_lines: int
    comment_lines: int


class PackageLOCResponse(BaseModel):
    package: str
    loc: int
    file_count: int
    comment_lines: int
    files: list[FileLOCResponse]


class ProjectLOCResponse(BaseModel):
    project_root: str
    total_loc: int
    total_files: int
    total_blank_lines: int
    total_excluded_lines: int
    total_comment_lines: int
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

