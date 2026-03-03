"""InfluxDB write pipeline with batch optimisation, retry logic, and write confirmation."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.core.config import Config

logger = logging.getLogger("repopulse.influx")

_client: Optional[InfluxDBClient] = None

# -- Configurable pipeline knobs --
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 0.5          # seconds — doubles each attempt
BATCH_SIZE = 500                   # flush every N points


# ---------------------------------------------------------------------------
# Write result model — returned by every write function for confirmation
# ---------------------------------------------------------------------------

@dataclass
class WriteResult:
    """Acknowledgment returned after a write (or batch write) attempt."""
    success: bool
    points_written: int = 0
    points_failed: int = 0
    errors: list[str] = field(default_factory=list)
    retries_used: int = 0


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

def get_client() -> InfluxDBClient:
    global _client
    if _client is None:
        if not Config.INFLUX_TOKEN:
            raise RuntimeError("INFLUX_TOKEN not configured")
        _client = InfluxDBClient(
            url=Config.INFLUX_URL,
            token=Config.INFLUX_TOKEN,
            org=Config.INFLUX_ORG,
        )
    return _client


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_loc_point(loc_metric: dict) -> Point:
    """Convert a LOC metric dict to an InfluxDB Point."""
    p = Point("loc_metrics")
    for tag in ("repo_id", "repo_name", "branch", "language", "granularity",
                "project_name", "package_name", "file_path"):
        v = loc_metric.get(tag)
        if v is not None:
            p = p.tag(tag, str(v))

    try:
        p = p.field("total_loc", int(loc_metric.get("total_loc", 0)))
        p = p.field("code_loc", int(loc_metric.get("code_loc", 0)))
        p = p.field("comment_loc", int(loc_metric.get("comment_loc", 0)))
        p = p.field("blank_loc", int(loc_metric.get("blank_loc", 0)))
    except Exception:
        p = p.field("total_loc", 0).field("code_loc", 0).field("comment_loc", 0).field("blank_loc", 0)

    ts = loc_metric.get("collected_at")
    if ts:
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            p = p.time(t, WritePrecision.NS)
        except Exception:
            pass
    return p


def _write_with_retry(points: list[Point], max_retries: int = MAX_RETRIES) -> WriteResult:
    """Write a list of points with exponential-backoff retry.

    Returns a ``WriteResult`` with confirmation details.
    """
    client = get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)

    result = WriteResult(success=False)
    attempt = 0

    while attempt <= max_retries:
        try:
            write_api.write(
                bucket=Config.INFLUX_BUCKET,
                org=Config.INFLUX_ORG,
                record=points,
            )
            result.success = True
            result.points_written = len(points)
            result.retries_used = attempt
            return result
        except Exception as exc:
            attempt += 1
            result.errors.append(f"attempt {attempt}/{max_retries + 1}: {exc}")
            if attempt <= max_retries:
                backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning(
                    f"InfluxDB write failed (attempt {attempt}), retrying in {backoff:.1f}s: {exc}"
                )
                time.sleep(backoff)

    # all retries exhausted
    result.points_failed = len(points)
    result.retries_used = max_retries
    logger.error(f"InfluxDB write failed after {max_retries + 1} attempts: {result.errors[-1]}")
    return result


# ---------------------------------------------------------------------------
# Public write functions
# ---------------------------------------------------------------------------

def write_loc_metric(loc_metric: dict) -> WriteResult:
    """Write a single LOC metric point with retry. Returns WriteResult."""
    point = _build_loc_point(loc_metric)
    return _write_with_retry([point])


def batch_write_loc_metrics(metrics: list[dict]) -> WriteResult:
    """Write many LOC metrics in batches for performance.

    Points are flushed in chunks of ``BATCH_SIZE``.  Each chunk is retried
    independently so a transient failure doesn't discard the whole payload.

    Returns an aggregate ``WriteResult`` with totals.
    """
    if not metrics:
        return WriteResult(success=True)

    points = [_build_loc_point(m) for m in metrics]

    aggregate = WriteResult(success=True)

    # chunk the points into batches
    for i in range(0, len(points), BATCH_SIZE):
        chunk = points[i : i + BATCH_SIZE]
        chunk_result = _write_with_retry(chunk)
        aggregate.points_written += chunk_result.points_written
        aggregate.points_failed += chunk_result.points_failed
        aggregate.errors.extend(chunk_result.errors)
        aggregate.retries_used = max(aggregate.retries_used, chunk_result.retries_used)
        if not chunk_result.success:
            aggregate.success = False

    logger.info(
        f"Batch write complete: {aggregate.points_written} written, "
        f"{aggregate.points_failed} failed, {aggregate.retries_used} max retries"
    )
    return aggregate


def write_churn_metric(repo_url: str, start_date: str, end_date: str, churn: dict) -> WriteResult:
    """Write a single churn summary point with retry."""
    point = (
        Point("repo_churn")
        .tag("repo_url", repo_url)
        .tag("start_date", start_date)
        .tag("end_date", end_date)
        .field("added", churn["added"])
        .field("deleted", churn["deleted"])
        .field("modified", churn["modified"])
        .field("total", churn["total"])
    )
    return _write_with_retry([point])


def write_daily_churn_metrics(repo_url: str, daily: dict[str, dict[str, int]]) -> WriteResult:
    """Write daily churn points as a batch with retry."""
    points: list[Point] = []
    for date_str, churn in daily.items():
        ts = datetime.fromisoformat(f"{date_str}T00:00:00+00:00")
        point = (
            Point("repo_churn_daily")
            .tag("repo_url", repo_url)
            .field("added", churn["added"])
            .field("deleted", churn["deleted"])
            .field("modified", churn["modified"])
            .field("total", churn["total"])
            .time(ts, WritePrecision.NS)
        )
        points.append(point)

    if not points:
        return WriteResult(success=True)

    return _write_with_retry(points)


# ---------------------------------------------------------------------------
# Query helper
# ---------------------------------------------------------------------------

def query_flux(query: str):
    client = get_client()
    query_api = client.query_api()
    return query_api.query(org=Config.INFLUX_ORG, query=query)
