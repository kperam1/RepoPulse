import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
            if not v.startswith(("https://github.com/", "http://github.com/")):
                raise ValueError("repo_url must be a valid GitHub URL")
        return v

    @field_validator("local_path")
    @classmethod
    def validate_local_path(cls, v):
        if v is not None:
            v = v.strip()
            if not v.startswith("/"):
                raise ValueError("local_path must be an absolute path starting with /")
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
