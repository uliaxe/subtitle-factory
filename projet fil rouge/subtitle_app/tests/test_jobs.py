import threading
import time

import pytest
from fastapi import HTTPException

from app import cruds, services
from app.core import SETTINGS, SessionLocal
from app.ressources import build_srt, format_srt_time
from app.schemas import OutputType

from conftest import upload


@pytest.mark.parametrize(
    "filename, output_type",
    [
        ("reunion.wav", "text"),
        ("reunion.wav", "subtitles"),
        ("film.mp4", "text"),
        ("film.mp4", "subtitles"),
        ("film.mp4", "video_embedded"),
        ("film.mp4", "video_metadata"),
    ],
)
def test_every_allowed_combination_completes(client, alice, filename, output_type):
    response = upload(client, alice, filename, output_type)
    assert response.status_code == 202

    job = client.get(f"/api/v1/jobs/{response.json()['id']}", headers=alice).json()
    assert job["status"] == "done"
    assert job["result_text"]
    assert job["processing_time_s"] is not None
    download = client.get(f"/api/v1/jobs/{job['id']}/result", headers=alice)
    assert download.status_code == 200


@pytest.mark.parametrize("output_type", ["video_embedded", "video_metadata"])
def test_audio_cannot_produce_a_video(client, alice, output_type):
    assert upload(client, alice, "reunion.wav", output_type).status_code == 400


def test_unsupported_extension_is_rejected(client, alice):
    assert upload(client, alice, "notes.pdf", "text").status_code == 400


def test_subtitles_result_is_a_valid_srt(client, alice):
    job_id = upload(client, alice, "reunion.wav", "subtitles").json()["id"]
    srt = client.get(f"/api/v1/jobs/{job_id}/result", headers=alice).text
    assert srt.startswith("1\n00:00:00,000 --> 00:00:02,800\n")


def test_users_only_see_their_own_jobs(client, alice, bob):
    job_id = upload(client, alice).json()["id"]
    assert client.get(f"/api/v1/jobs/{job_id}", headers=bob).status_code == 404
    assert client.get("/api/v1/jobs", headers=bob).json() == []
    assert len(client.get("/api/v1/jobs", headers=alice).json()) == 1


def test_deleted_files_cannot_be_downloaded_but_history_remains(client, alice, admin):
    job_id = upload(client, alice).json()["id"]
    assert client.delete(f"/api/v1/jobs/{job_id}/files", headers=alice).status_code == 200
    assert client.get(f"/api/v1/jobs/{job_id}/result", headers=alice).status_code == 410
    history = client.get("/api/v1/admin/jobs", headers=admin).json()
    assert history[0]["id"] == job_id and history[0]["result_text"]


def test_no_queue_new_job_refused_when_capacity_is_reached(client, alice, monkeypatch):
    monkeypatch.setattr(cruds, "count_unfinished", lambda db: SETTINGS.max_concurrent_jobs)
    response = upload(client, alice)
    assert response.status_code == 429
    assert "Capacité atteinte" in response.json()["detail"]


class _SlowUpload:
    def __init__(self, chunks: int = 3, delay_s: float = 0.2, fail: bool = False):
        self._chunks, self._delay_s, self._fail = chunks, delay_s, fail

    def read(self, _size: int) -> bytes:
        time.sleep(self._delay_s)
        if self._chunks == 0:
            return b""
        if self._fail:
            raise ConnectionError("envoi interrompu")
        self._chunks -= 1
        return b"x" * 10


def _last_slot_only(monkeypatch):
    real_count = cruds.count_unfinished
    monkeypatch.setattr(cruds, "count_unfinished",
                        lambda db: real_count(db) + SETTINGS.max_concurrent_jobs - 1)


def test_simultaneous_slow_uploads_cannot_exceed_capacity(client, monkeypatch):
    _last_slot_only(monkeypatch)
    outcomes = []

    def submit():
        with SessionLocal() as db:
            user = cruds.get_user_by_username(db, "alice")
            try:
                services.create_job(db, user, "film.mp4", _SlowUpload(), OutputType.TEXT)
                outcomes.append("accepté")
            except HTTPException as error:
                outcomes.append(error.status_code)

    threads = [threading.Thread(target=submit) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes, key=str) == [429, 429, "accepté"]


def test_interrupted_upload_frees_its_slot(client, alice, monkeypatch):
    _last_slot_only(monkeypatch)
    with SessionLocal() as db:
        user = cruds.get_user_by_username(db, "alice")
        with pytest.raises(ConnectionError):
            services.create_job(db, user, "film.mp4", _SlowUpload(fail=True), OutputType.TEXT)
        assert cruds.count_unfinished(db) == SETTINGS.max_concurrent_jobs - 1
    assert upload(client, alice).status_code == 202


def test_failure_of_the_ai_service_is_recorded(client, alice, monkeypatch):
    class BrokenAI:
        def process(self, *args):
            raise RuntimeError("GPU indisponible")

    monkeypatch.setattr("app.services._jobs.get_ai_client", lambda: BrokenAI())
    job_id = upload(client, alice).json()["id"]
    job = client.get(f"/api/v1/jobs/{job_id}", headers=alice).json()
    assert job["status"] == "failed"
    assert job["error_message"] == "GPU indisponible"


def test_jobs_left_running_are_failed_on_restart(client, alice):
    job_id = upload(client, alice).json()["id"]
    with SessionLocal() as db:
        cruds.get_job(db, job_id).status = "processing"
        db.commit()
        assert cruds.fail_unfinished(db, "redémarrage") == 1
        assert cruds.get_job(db, job_id).status == "failed"


def test_srt_time_format():
    assert format_srt_time(3725.5) == "01:02:05,500"
    assert build_srt([(0.0, 1.0, "Hello")]) == "1\n00:00:00,000 --> 00:00:01,000\nHello\n"
