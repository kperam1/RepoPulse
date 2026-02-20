from datetime import datetime
from typing import Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.core.config import Config

_client: Optional[InfluxDBClient] = None


def get_client() -> InfluxDBClient:
    """Return a singleton InfluxDB client."""
    global _client
    if _client is None:
        if not Config.INFLUX_TOKEN:
            raise RuntimeError("INFLUX_TOKEN not configured")
        _client = InfluxDBClient(url=Config.INFLUX_URL, token=Config.INFLUX_TOKEN, org=Config.INFLUX_ORG)
    return _client


def write_loc_metric(loc_metric: dict) -> None:
    """Write a single LOC metric point to InfluxDB."""
    client = get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)

    p = Point("loc_metrics")
    # tags
    for tag in ("repo_id", "repo_name", "branch", "language", "granularity",
                "project_name", "package_name", "file_path"):
        v = loc_metric.get(tag)
        if v is not None:
            p = p.tag(tag, str(v))

    # fields
    try:
        p = p.field("total_loc", int(loc_metric.get("total_loc", 0)))
        p = p.field("code_loc", int(loc_metric.get("code_loc", 0)))
        p = p.field("comment_loc", int(loc_metric.get("comment_loc", 0)))
        p = p.field("blank_loc", int(loc_metric.get("blank_loc", 0)))
    except Exception:
        # fallback if values aren't numeric
        p = p.field("total_loc", 0).field("code_loc", 0).field("comment_loc", 0).field("blank_loc", 0)

    # timestamp
    ts = loc_metric.get("collected_at")
    if ts:
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            p = p.time(t, WritePrecision.NS)
        except Exception:
            pass

    write_api.write(bucket=Config.INFLUX_BUCKET, org=Config.INFLUX_ORG, record=p)


def query_flux(query: str):
    client = get_client()
    query_api = client.query_api()
    return query_api.query(org=Config.INFLUX_ORG, query=query)
