"""Tests for POST /analyze and GET /health/db endpoints, and AnalyzeRequest model."""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.main import app
from src.api.models import AnalyzeRequest

client = TestClient(app)

# ── AnalyzeRequest model validation ──────────────────────────────────────────

def test_analyze_request_valid_url():
    req = AnalyzeRequest(repo_url="https://github.com/owner/repo")
    assert req.repo_url == "https://github.com/owner/repo"

def test_analyze_request_valid_url_with_git_suffix():
    req = AnalyzeRequest(repo_url="https://github.com/owner/repo.git")
    assert req.repo_url == "https://github.com/owner/repo.git"

def test_analyze_request_invalid_url():
    with pytest.raises(Exception):
        AnalyzeRequest(repo_url="not-a-valid-url")

def test_analyze_request_empty_url():
    with pytest.raises(Exception):
        AnalyzeRequest(repo_url="")

def test_analyze_request_non_github_url():
    with pytest.raises(Exception):
        AnalyzeRequest(repo_url="https://gitlab.com/owner/repo")


# ── POST /analyze endpoint ───────────────────────────────────────────────────

def _make_sample_tree(dest):
    """Create a tiny sample project in *dest* for LOC analysis."""
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "Main.java"), "w") as f:
        f.write("public class Main {\n    public static void main(String[] args) {\n        System.out.println(\"hi\");\n    }\n}\n")
    with open(os.path.join(dest, "app.py"), "w") as f:
        f.write("# a comment\nprint('hello')\n")


@patch("src.api.routes.write_loc_metric")
@patch("src.api.routes.GitRepoCloner")
def test_analyze_success(mock_cloner_cls, mock_write):
    """Mock the clone, verify LOC is computed and response looks right."""
    import tempfile, shutil
    tmp = tempfile.mkdtemp(prefix="test_analyze_")
    _make_sample_tree(tmp)

    mock_cloner = MagicMock()
    mock_cloner.clone.return_value = tmp
    mock_cloner_cls.return_value = mock_cloner

    response = client.post("/analyze", json={"repo_url": "https://github.com/owner/repo"})
    assert response.status_code == 200
    data = response.json()
    assert data["total_files"] >= 2
    assert data["total_loc"] > 0
    assert "files" in data
    assert "packages" in data

    # write_loc_metric should have been called (project + per-file)
    assert mock_write.call_count >= 2
    mock_cloner.cleanup.assert_called_once()
    shutil.rmtree(tmp, ignore_errors=True)


@patch("src.api.routes.GitRepoCloner")
def test_analyze_clone_failure(mock_cloner_cls):
    """If clone fails, we get a 400 with an error message."""
    from src.core.git_clone import GitCloneError
    mock_cloner = MagicMock()
    mock_cloner.clone.side_effect = GitCloneError("clone boom")
    mock_cloner_cls.return_value = mock_cloner

    response = client.post("/analyze", json={"repo_url": "https://github.com/owner/repo"})
    assert response.status_code == 400
    assert "clone boom" in response.json()["detail"]
    mock_cloner.cleanup.assert_called_once()


def test_analyze_bad_url():
    response = client.post("/analyze", json={"repo_url": "not-a-url"})
    assert response.status_code == 400
    assert "detail" in response.json()


def test_analyze_empty_body():
    response = client.post("/analyze", json={})
    assert response.status_code == 400


@patch("src.api.routes.write_loc_metric")
@patch("src.api.routes.GitRepoCloner")
def test_analyze_influx_failure_still_returns_data(mock_cloner_cls, mock_write):
    """Even if InfluxDB write fails, the LOC data should still be returned."""
    import tempfile, shutil
    tmp = tempfile.mkdtemp(prefix="test_analyze_influx_fail_")
    _make_sample_tree(tmp)

    mock_cloner = MagicMock()
    mock_cloner.clone.return_value = tmp
    mock_cloner_cls.return_value = mock_cloner
    mock_write.side_effect = RuntimeError("influx down")

    response = client.post("/analyze", json={"repo_url": "https://github.com/owner/repo"})
    assert response.status_code == 200
    assert response.json()["total_files"] >= 2
    shutil.rmtree(tmp, ignore_errors=True)


# ── GET /health/db endpoint ──────────────────────────────────────────────────

@patch("src.api.routes.get_client")
def test_health_db_healthy(mock_get_client):
    mock_client = MagicMock()
    health_obj = MagicMock()
    health_obj.status = "pass"
    health_obj.message = "ready for queries and writes"
    mock_client.health.return_value = health_obj
    mock_get_client.return_value = mock_client

    response = client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pass"


@patch("src.api.routes.get_client")
def test_health_db_unhealthy(mock_get_client):
    mock_get_client.side_effect = RuntimeError("INFLUX_TOKEN not configured")
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
