from datetime import timedelta
from pathlib import Path

from app import cruds
from app.core import SessionLocal
from app.services import purge_expired_files

from conftest import upload


def test_stats_count_inferences_and_failures_by_type(client, alice, admin, monkeypatch):
    upload(client, alice, "reunion.wav", "text")
    upload(client, alice, "film.mp4", "text")
    upload(client, alice, "film.mp4", "subtitles")

    class BrokenAI:
        def process(self, *args):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.services._jobs.get_ai_client", lambda: BrokenAI())
    upload(client, alice, "film.mp4", "video_embedded")

    stats = client.get("/api/v1/admin/stats", headers=admin).json()
    assert stats["total"] == 4
    assert stats["done"] == 3
    assert stats["failed"] == 1
    assert stats["unfinished"] == 0
    assert stats["by_type"]["text"]["done"] == 2
    assert stats["by_type"]["video_embedded"]["failed"] == 1
    assert stats["avg_processing_s"] is not None


def test_admin_history_includes_every_user(client, alice, bob, admin):
    upload(client, alice)
    upload(client, bob)
    history = client.get("/api/v1/admin/jobs", headers=admin).json()
    assert {job["username"] for job in history} == {"alice", "bob"}


def test_retention_purges_old_files_and_keeps_history(client, alice):
    job_id = upload(client, alice).json()["id"]
    with SessionLocal() as db:
        job = cruds.get_job(db, job_id)
        job_dir = Path(job.input_path).parent
        assert job_dir.exists()

        assert purge_expired_files(db) == 0
        assert purge_expired_files(db, now=cruds.utcnow() + timedelta(days=8)) == 1

        db.refresh(job)
        assert job.files_purged
        assert job.result_text
        assert not job_dir.exists()
