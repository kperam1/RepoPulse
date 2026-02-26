import logging
from datetime import datetime, timezone
from typing import Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.core.config import Config

logger = logging.getLogger("repopulse.core.influx")

_client: Optional[InfluxDBClient] = None


def get_client() -> InfluxDBClient:
    """Return a singleton InfluxDB client."""
    global _client
    if _client is None:
        if not Config.INFLUX_TOKEN:
            raise RuntimeError("INFLUX_TOKEN not configured")
        _client = InfluxDBClient(url=Config.INFLUX_URL, token=Config.INFLUX_TOKEN, org=Config.INFLUX_ORG)
    return _client


def _parse_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 timestamp string to datetime object or None."""
    if not ts_str:
        return None
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)
    except (ValueError, AttributeError):
        logger.warning(f"Failed to parse timestamp: {ts_str}")
        return None


def write_loc_metric(loc_metric: dict) -> None:
    """Write a LOC metric point to InfluxDB."""
    client = get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)

    p = Point("loc_metrics")
    
    for tag in ("repo_id", "repo_name", "branch", "language", "granularity",
                "project_name", "package_name", "file_path", "commit_hash"):
        v = loc_metric.get(tag)
        if v is not None:
            p = p.tag(tag, str(v))

    try:
        p = p.field("total_loc", int(loc_metric.get("total_loc", 0)))
        p = p.field("code_loc", int(loc_metric.get("code_loc", 0)))
        p = p.field("comment_loc", int(loc_metric.get("comment_loc", 0)))
        p = p.field("blank_loc", int(loc_metric.get("blank_loc", 0)))
    except (ValueError, TypeError):
        logger.warning(f"Non-numeric metric values, using defaults: {loc_metric}")
        p = p.field("total_loc", 0).field("code_loc", 0).field("comment_loc", 0).field("blank_loc", 0)

    collected_at = loc_metric.get("collected_at")
    if collected_at:
        ts = _parse_timestamp(collected_at)
        if ts:
            p = p.time(ts, WritePrecision.NS)
    else:
        p = p.time(datetime.now(timezone.utc), WritePrecision.NS)

    write_api.write(bucket=Config.INFLUX_BUCKET, org=Config.INFLUX_ORG, record=p)
    logger.debug(f"Wrote LOC metric to InfluxDB: {loc_metric.get('repo_name')} @ {loc_metric.get('collected_at', 'now')}")


def write_timeseries_snapshot(snapshot: dict) -> None:
    """Write a time-series metric snapshot to InfluxDB linked to a commit."""
    client = get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)

    p = Point("timeseries_snapshot")
    
    required_tags = ("repo_id", "repo_name", "commit_hash", "branch", "granularity")
    for tag in required_tags:
        v = snapshot.get(tag)
        if v is None:
            raise ValueError(f"Missing required tag for snapshot: {tag}")
        p = p.tag(tag, str(v))
    
    for tag in ("snapshot_type", "file_path", "package_name", "language"):
        v = snapshot.get(tag)
        if v is not None:
            p = p.tag(tag, str(v))

    metrics = snapshot.get("metrics", {})
    try:
        p = p.field("total_loc", int(metrics.get("total_loc", 0)))
        p = p.field("code_loc", int(metrics.get("code_loc", 0)))
        p = p.field("comment_loc", int(metrics.get("comment_loc", 0)))
        p = p.field("blank_loc", int(metrics.get("blank_loc", 0)))
    except (ValueError, TypeError):
        logger.warning(f"Non-numeric snapshot metrics: {snapshot}")
        p = p.field("total_loc", 0).field("code_loc", 0).field("comment_loc", 0).field("blank_loc", 0)

    snapshot_ts = snapshot.get("snapshot_timestamp")
    if snapshot_ts:
        ts = _parse_timestamp(snapshot_ts)
        if ts:
            p = p.time(ts, WritePrecision.NS)
    else:
        p = p.time(datetime.now(timezone.utc), WritePrecision.NS)

    write_api.write(bucket=Config.INFLUX_BUCKET, org=Config.INFLUX_ORG, record=p)
    logger.debug(f"Wrote time-series snapshot: {snapshot.get('repo_name')} @ commit {snapshot.get('commit_hash', '')[:8]}")


def query_flux(query: str):
    """Execute a Flux query against InfluxDB."""
    client = get_client()
    query_api = client.query_api()
    return query_api.query(org=Config.INFLUX_ORG, query=query)
