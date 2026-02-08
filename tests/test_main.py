import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    # The API root is provided by `src.api.routes` and currently returns this message
    assert response.json() == {"message": "Welcome to RepoPulse API"}


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}