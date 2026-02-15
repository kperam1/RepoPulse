from src.api.models import LOCMetrics
from datetime import datetime
import pytest

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

    # Query: get all metrics collected after 2026-02-11
    cutoff = datetime.fromisoformat("2026-02-11T00:00:00+00:00")
    filtered = [m for m in metrics_list if datetime.fromisoformat(m.collected_at.replace('Z', '+00:00')) > cutoff]

    assert len(filtered) == 2
    assert filtered[0].commit_hash == "a2"
    assert filtered[1].commit_hash == "a3"
