"""Tests for ingestion job queue."""

import json

from server import db


def test_books_table_has_language_column(tmp_data_dir):
    db.init_db()
    conn = db._get_conn()
    row = conn.execute("PRAGMA table_info(books)").fetchall()
    columns = [r[1] for r in row]
    assert "language" in columns
    assert "source" in columns
    assert "external_id" in columns
    assert "fingerprint" in columns
    conn.close()


def test_ingestion_jobs_table_exists(tmp_data_dir):
    db.init_db()
    conn = db._get_conn()
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ingestion_jobs'").fetchone()
    assert row is not None
    conn.close()


def test_ingestion_jobs_columns(tmp_data_dir):
    db.init_db()
    conn = db._get_conn()
    row = conn.execute("PRAGMA table_info(ingestion_jobs)").fetchall()
    columns = [r[1] for r in row]
    assert "source" in columns
    assert "status" in columns
    assert "input_data" in columns
    assert "result" in columns
    assert "retries" in columns
    assert "timeout_seconds" in columns
    assert "started_at" in columns
    assert "heartbeat_at" in columns
    conn.close()


def test_create_ingestion_job(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("librivox", {"lang": "ru", "limit": 10})
    assert job_id > 0
    job = db.get_ingestion_job(job_id)
    assert job["source"] == "librivox"
    assert job["status"] == "pending"
    assert json.loads(job["input_data"]) == {"lang": "ru", "limit": 10}


def test_update_ingestion_job_status(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("normalize", {})
    db.update_ingestion_job(job_id, status="processing")
    job = db.get_ingestion_job(job_id)
    assert job["status"] == "processing"
    assert job["started_at"] is not None


def test_heartbeat_ingestion_job(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("normalize", {})
    db.update_ingestion_job(job_id, status="processing")
    db.heartbeat_ingestion_job(job_id)
    job = db.get_ingestion_job(job_id)
    assert job["heartbeat_at"] is not None


def test_list_ingestion_jobs(tmp_data_dir):
    db.init_db()
    db.create_ingestion_job("librivox", {})
    db.create_ingestion_job("normalize", {})
    jobs = db.list_ingestion_jobs()
    assert len(jobs) == 2
    jobs_pending = db.list_ingestion_jobs(status="pending")
    assert len(jobs_pending) == 2


def test_recover_stalled_jobs(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("normalize", {}, timeout_seconds=1)
    db.update_ingestion_job(job_id, status="processing")
    db.heartbeat_ingestion_job(job_id)
    # Simulate stalled: set heartbeat to past
    conn = db._get_conn()
    conn.execute(
        "UPDATE ingestion_jobs SET heartbeat_at = datetime('now', '-10 seconds') WHERE id = ?",
        (job_id,),
    )
    conn.commit()
    conn.close()
    recovered = db.recover_stalled_jobs()
    assert recovered == 1
    job = db.get_ingestion_job(job_id)
    assert job["status"] == "pending"


def test_update_job_result(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("normalize", {})
    result = {"book_id": 42, "tracks_processed": 10}
    db.update_ingestion_job(job_id, status="done", result=result)
    job = db.get_ingestion_job(job_id)
    assert job["status"] == "done"
    assert json.loads(job["result"])["book_id"] == 42
