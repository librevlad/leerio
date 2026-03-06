"""Tests for admin ingest API endpoints."""

import pytest

from server import db


@pytest.fixture()
def client(api_client):
    """Reuse the existing api_client fixture which has auth mocked."""
    return api_client


def test_create_job(client):
    resp = client.post("/api/admin/ingest", json={
        "source": "librivox",
        "input_data": {"lang": "ru"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] > 0
    assert data["status"] == "pending"


def test_list_jobs(client):
    # Create a couple jobs first
    client.post("/api/admin/ingest", json={"source": "test", "input_data": {}})
    client.post("/api/admin/ingest", json={"source": "test2", "input_data": {}})
    resp = client.get("/api/admin/ingest/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


def test_get_job(client):
    resp = client.post("/api/admin/ingest", json={"source": "test", "input_data": {"key": "val"}})
    job_id = resp.json()["id"]
    resp = client.get(f"/api/admin/ingest/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "test"
    assert data["input_data"] == {"key": "val"}


def test_get_job_not_found(client):
    resp = client.get("/api/admin/ingest/jobs/99999")
    assert resp.status_code == 404


def test_retry_job(client):
    resp = client.post("/api/admin/ingest", json={"source": "test", "input_data": {}})
    job_id = resp.json()["id"]
    # Set to failed
    db.update_ingestion_job(job_id, status="failed")
    resp = client.post(f"/api/admin/ingest/retry/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_retry_non_failed(client):
    resp = client.post("/api/admin/ingest", json={"source": "test", "input_data": {}})
    job_id = resp.json()["id"]
    resp = client.post(f"/api/admin/ingest/retry/{job_id}")
    assert resp.status_code == 400


def test_stats(client):
    resp = client.get("/api/admin/ingest/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "done" in data
