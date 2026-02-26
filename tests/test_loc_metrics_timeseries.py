from src.api.models import LOCMetrics, TimeSeriesMetricSnapshot, SnapshotRecord, SnapshotData
from datetime import datetime
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_loc_metrics_time_series_query():
    # Create a list of LOCMetrics with different timestamps
    metrics_list = [
        LOCMetrics(
            repo_id="1",
            repo_name="repo1",
            branch="main",
            commit_hash="a1",
            language="Python",
            granularity="file",
            file_path="src/a.py",
            total_loc=100,
            code_loc=80,
            comment_loc=10,
            blank_loc=10,
            collected_at="2026-02-10T10:00:00Z"
        ),
        LOCMetrics(
            repo_id="1",
            repo_name="repo1",
            branch="main",
            commit_hash="a2",
            language="Python",
            granularity="file",
            file_path="src/a.py",
            total_loc=110,
            code_loc=90,
            comment_loc=10,
            blank_loc=10,
            collected_at="2026-02-12T10:00:00Z"
        ),
        LOCMetrics(
            repo_id="1",
            repo_name="repo1",
            branch="main",
            commit_hash="a3",
            language="Python",
            granularity="file",
            file_path="src/a.py",
            total_loc=120,
            code_loc=100,
            comment_loc=10,
            blank_loc=10,
            collected_at="2026-02-14T10:00:00Z"
        ),
    ]

    cutoff = datetime.fromisoformat("2026-02-11T00:00:00+00:00")
    filtered = [m for m in metrics_list if datetime.fromisoformat(m.collected_at.replace('Z', '+00:00')) > cutoff]

    assert len(filtered) == 2
    assert filtered[0].commit_hash == "a2"
    assert filtered[1].commit_hash == "a3"


def test_snapshot_record_creation():
    snapshot = SnapshotRecord(
        timestamp="2026-02-25T19:00:00+00:00",
        repo_id="test-repo",
        repo_name="test-repo",
        commit_hash="abc123def456",
        branch="main",
        granularity="project",
        metrics=SnapshotData(
            total_loc=500,
            code_loc=400,
            comment_loc=50,
            blank_loc=50
        )
    )
    assert snapshot.repo_id == "test-repo"
    assert snapshot.commit_hash == "abc123def456"
    assert snapshot.metrics.total_loc == 500
    assert snapshot.granularity == "project"


def test_timeseries_metric_snapshot_model():
    snapshot = TimeSeriesMetricSnapshot(
        repo_id="my-repo",
        repo_name="my-repo",
        commit_hash="xyz789",
        commit_timestamp="2026-02-25T18:00:00Z",
        branch="main",
        snapshot_timestamp="2026-02-25T19:00:00Z",
        granularity="project",
        total_loc=1000,
        code_loc=800,
        comment_loc=100,
        blank_loc=100,
        project_name="my-project"
    )
    assert snapshot.repo_id == "my-repo"
    assert snapshot.commit_hash == "xyz789"
    assert snapshot.total_loc == 1000


@patch("src.api.routes.query_latest_snapshot")
def test_get_latest_snapshot_endpoint(mock_query):
    mock_query.return_value = {
        "time": datetime.fromisoformat("2026-02-25T19:00:00+00:00"),
        "repo_id": "test-repo",
        "repo_name": "test-repo",
        "commit_hash": "abc123",
        "branch": "main",
        "granularity": "project",
        "file_path": None,
        "package_name": None
    }
    
    response = client.get("/metrics/timeseries/snapshots/test-repo/latest?granularity=project")
    assert response.status_code == 200
    data = response.json()
    assert data["repo_id"] == "test-repo"
    assert data["latest_snapshot"] is not None


@patch("src.api.routes.query_timeseries_snapshots_by_repo")
def test_get_snapshot_history_endpoint(mock_query):
    mock_query.return_value = [
        {
            "time": datetime.fromisoformat("2026-02-20T10:00:00+00:00"),
            "repo_id": "test-repo",
            "repo_name": "test-repo",
            "commit_hash": "hash1",
            "branch": "main",
            "granularity": "project",
            "file_path": None,
            "package_name": None
        },
        {
            "time": datetime.fromisoformat("2026-02-25T19:00:00+00:00"),
            "repo_id": "test-repo",
            "repo_name": "test-repo",
            "commit_hash": "hash2",
            "branch": "main",
            "granularity": "project",
            "file_path": None,
            "package_name": None
        }
    ]
    
    response = client.get(
        "/metrics/timeseries/snapshots/test-repo/range?"
        "start_time=2026-02-20T00:00:00Z&end_time=2026-02-26T00:00:00Z&granularity=project"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["repo_id"] == "test-repo"
    assert data["count"] == 2


@patch("src.api.routes.query_snapshot_at_timestamp")
def test_get_snapshot_at_time_endpoint(mock_query):
    mock_query.return_value = {
        "time": datetime.fromisoformat("2026-02-25T19:00:00+00:00"),
        "repo_id": "test-repo",
        "repo_name": "test-repo",
        "commit_hash": "abc123",
        "branch": "main",
        "granularity": "project",
        "file_path": None,
        "package_name": None
    }
    
    response = client.get("/metrics/timeseries/snapshots/test-repo/at/2026-02-25T19:00:00Z")
    assert response.status_code == 200
    data = response.json()
    assert data["repo_id"] == "test-repo"
    assert data["commit_hash"] == "abc123"


@patch("src.api.routes.query_snapshots_by_commit")
def test_get_snapshots_for_commit_endpoint(mock_query):
    mock_query.return_value = [
        {
            "time": datetime.fromisoformat("2026-02-25T19:00:00+00:00"),
            "repo_id": "test-repo",
            "repo_name": "test-repo",
            "commit_hash": "abc123",
            "branch": "main",
            "granularity": "project",
            "file_path": None,
            "package_name": None
        },
        {
            "time": datetime.fromisoformat("2026-02-25T19:00:00+00:00"),
            "repo_id": "test-repo",
            "repo_name": "test-repo",
            "commit_hash": "abc123",
            "branch": "main",
            "granularity": "file",
            "file_path": "src/main.py",
            "package_name": None
        }
    ]
    
    response = client.get("/metrics/timeseries/snapshots/test-repo/commit/abc123")
    assert response.status_code == 200
    data = response.json()
    assert data["repo_id"] == "test-repo"
    assert data["commit_hash"] == "abc123"
    assert data["count"] == 2
