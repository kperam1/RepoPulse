import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to RepoPulse API"}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "RepoPulse API"
    assert data["version"] == "1.0.0"


def test_create_job_with_repo_url():
    response = client.post(
        "/jobs",
        json={"repo_url": "https://github.com/kperam1/RepoPulse"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["repo_url"] == "https://github.com/kperam1/RepoPulse"
    assert data["local_path"] is None
    assert data["message"] == "Job submitted successfully"
    assert "job_id" in data
    assert "created_at" in data


def test_create_job_with_local_path():
    response = client.post(
        "/jobs",
        json={"local_path": "/home/user/projects/my-repo"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["local_path"] == "/home/user/projects/my-repo"
    assert data["repo_url"] is None
    assert data["message"] == "Job submitted successfully"


def test_create_job_missing_fields():
    response = client.post("/jobs", json={})
    assert response.status_code == 422


def test_create_job_both_fields_provided():
    response = client.post(
        "/jobs",
        json={
            "repo_url": "https://github.com/kperam1/RepoPulse",
            "local_path": "/home/user/projects/my-repo",
        },
    )
    assert response.status_code == 422


def test_create_job_invalid_repo_url():
    response = client.post(
        "/jobs",
        json={"repo_url": "not-a-valid-url"},
    )
    assert response.status_code == 422


def test_create_job_invalid_local_path():
    response = client.post(
        "/jobs",
        json={"local_path": "relative/path/to/repo"},
    )
    assert response.status_code == 422


def test_openapi_docs_available():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "RepoPulse API"
    assert "/health" in data["paths"]
    assert "/jobs" in data["paths"]

    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "RepoPulse API"
    assert "/health" in data["paths"]
    assert "/jobs" in data["paths"]
