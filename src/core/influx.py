from datetime import datetime
from typing import Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.core.config import Config

_client: Optional[InfluxDBClient] = None


def get_client() -> InfluxDBClient:
    global _client
    if _client is None:
        if not Config.INFLUX_TOKEN:
            raise RuntimeError("INFLUX_TOKEN not configured")
        _client = InfluxDBClient(url=Config.INFLUX_URL, token=Config.INFLUX_TOKEN, org=Config.INFLUX_ORG)
    return _client


def write_loc_metric(loc_metric: dict) -> None:
    client = get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)

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

    write_api.write(bucket=Config.INFLUX_BUCKET, org=Config.INFLUX_ORG, record=p)


def write_churn_metric(repo_url: str, start_date: str, end_date: str, churn: dict) -> None:
    client = get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)

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

    write_api.write(bucket=Config.INFLUX_BUCKET, org=Config.INFLUX_ORG, record=point)


def write_daily_churn_metrics(repo_url: str, daily: dict[str, dict[str, int]]) -> None:
    client = get_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)

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
        write_api.write(bucket=Config.INFLUX_BUCKET, org=Config.INFLUX_ORG, record=point)


def query_flux(query: str):
    client = get_client()
    query_api = client.query_api()
    return query_api.query(org=Config.INFLUX_ORG, query=query)
