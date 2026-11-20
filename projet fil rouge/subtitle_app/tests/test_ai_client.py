import httpx
import pytest

from app.ressources import AIServiceError, HttpAIClient
from app.schemas import InputKind, OutputType

JOB_ID = "a" * 32


def _client(handler) -> HttpAIClient:
    return HttpAIClient("http://ia.test", timeout_s=60, transport=httpx.MockTransport(handler))


@pytest.fixture
def media(tmp_path):
    path = tmp_path / "input.mp4"
    path.write_bytes(b"fausse video")
    return path


def test_success_downloads_result_and_cleans_service(media, tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            body = request.read()
            assert b'name="output_type"' in body and b"video_metadata" in body
            assert b'filename="input.mp4"' in body and b"fausse video" in body
            return httpx.Response(200, json={
                "job_id": JOB_ID, "text": "Hello world.", "output_filename": "video_piste_sous_titres.mp4",
                "media_duration_s": 148.9, "transcription_s": 20.0, "total_s": 21.0, "video_encoder": None,
            })
        if request.method == "GET":
            return httpx.Response(200, content=b"video avec piste")
        return httpx.Response(204)

    result = _client(handler).process(media, InputKind.VIDEO, OutputType.VIDEO_METADATA, tmp_path)

    assert result.text == "Hello world."
    assert result.media_duration_s == 148.9
    assert result.output_path == tmp_path / "video_piste_sous_titres.mp4"
    assert result.output_path.read_bytes() == b"video avec piste"
    assert calls == [
        ("POST", "/v1/jobs"),
        ("GET", f"/v1/jobs/{JOB_ID}/files/video_piste_sous_titres.mp4"),
        ("DELETE", f"/v1/jobs/{JOB_ID}"),
    ]


def test_busy_service_gives_clear_error(media, tmp_path):
    client = _client(lambda request: httpx.Response(429, json={"detail": "occupé"}))
    with pytest.raises(AIServiceError, match="saturé"):
        client.process(media, InputKind.VIDEO, OutputType.TEXT, tmp_path)


def test_service_failure_message_is_kept(media, tmp_path):
    client = _client(lambda request: httpx.Response(500, json={"detail": "Échec du traitement : ffmpeg"}))
    with pytest.raises(AIServiceError, match="500 Échec du traitement : ffmpeg"):
        client.process(media, InputKind.VIDEO, OutputType.TEXT, tmp_path)


def test_unreachable_service_gives_clear_error(media, tmp_path):
    def handler(request):
        raise httpx.ConnectError("connexion refusée")

    with pytest.raises(AIServiceError, match="injoignable"):
        _client(handler).process(media, InputKind.VIDEO, OutputType.TEXT, tmp_path)


def test_service_files_are_deleted_even_if_download_fails(media, tmp_path):
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(200, json={"job_id": JOB_ID, "text": "x", "output_filename": "transcript.txt",
                                             "media_duration_s": 1.0})
        if request.method == "GET":
            return httpx.Response(404, json={"detail": "Fichier introuvable"})
        return httpx.Response(204)

    with pytest.raises(AIServiceError, match="404"):
        _client(handler).process(media, InputKind.VIDEO, OutputType.TEXT, tmp_path)
    assert methods == ["POST", "GET", "DELETE"]
