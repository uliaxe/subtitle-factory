import io

import pytest


def _post(client, path, output_type):
    with open(path, "rb") as f:
        return client.post("/v1/jobs", files={"file": (path.name, f)}, data={"output_type": output_type})


def test_healthz(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok" and body["workers"] == 2 and body["active_jobs"] == 0


@pytest.mark.parametrize("output_type, filename", [
    ("text", "transcript.txt"),
    ("subtitles", "subtitles.srt"),
    ("video_embedded", "video_sous_titree.mp4"),
    ("video_metadata", "video_piste_sous_titres.mp4"),
])
def test_video_gives_each_output_type(client, media_dir, output_type, filename):
    response = _post(client, media_dir / "sample.mp4", output_type)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["output_filename"] == filename
    assert body["text"] == "This is a simulated transcription. No GPU was used."
    assert abs(body["media_duration_s"] - 3.0) < 0.1

    download = client.get(f"/v1/jobs/{body['job_id']}/files/{filename}")
    assert download.status_code == 200 and len(download.content) > 0


@pytest.mark.parametrize("output_type", ["text", "subtitles"])
def test_audio_gives_text_or_subtitles(client, media_dir, output_type):
    assert _post(client, media_dir / "sample.wav", output_type).status_code == 200


@pytest.mark.parametrize("output_type", ["video_embedded", "video_metadata"])
def test_audio_cannot_give_video(client, media_dir, output_type):
    assert _post(client, media_dir / "sample.wav", output_type).status_code == 400


def test_unsupported_format_is_refused(client):
    response = client.post("/v1/jobs", files={"file": ("notes.pdf", io.BytesIO(b"x"))},
                           data={"output_type": "text"})
    assert response.status_code == 400


def test_busy_workers_give_429_without_queue(client, media_dir):
    client.app.state.active_jobs = 2
    assert _post(client, media_dir / "sample.mp4", "text").status_code == 429
    client.app.state.active_jobs = 0
    assert _post(client, media_dir / "sample.mp4", "text").status_code == 200


def test_unreadable_media_fails_and_frees_the_worker(client, tmp_path):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"ceci n'est pas une video")
    assert _post(client, broken, "video_metadata").status_code == 500
    assert client.get("/healthz").json()["active_jobs"] == 0


def test_delete_removes_files(client, media_dir):
    job_id = _post(client, media_dir / "sample.mp4", "text").json()["job_id"]
    assert client.delete(f"/v1/jobs/{job_id}").status_code == 204
    assert client.get(f"/v1/jobs/{job_id}/files/transcript.txt").status_code == 404


def test_only_known_files_can_be_downloaded(client, media_dir):
    job_id = _post(client, media_dir / "sample.mp4", "text").json()["job_id"]
    assert client.get(f"/v1/jobs/{job_id}/files/input.mp4").status_code == 404
    assert client.get("/v1/jobs/..%2F..%2Fsecret/files/transcript.txt").status_code == 404
