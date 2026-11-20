import asyncio
import os
from pathlib import Path

import pytest
from concurrent.futures.process import BrokenProcessPool

from app.transcriber import WhisperPool
from tests.conftest import make_settings


def _no_model(*_args) -> None:
    pass


def _crash_if_marked(media_path: str):
    if not Path(media_path + ".crash").exists():
        return [(0.0, 1.0, "ok")]
    try:
        os.close(os.open(media_path + ".crashed", os.O_CREAT | os.O_EXCL))
    except FileExistsError:
        return [(0.0, 1.0, "ok")]
    os._exit(1)


def _always_crash(_media_path: str):
    os._exit(1)


class _TestPool(WhisperPool):
    _initializer = staticmethod(_no_model)
    _target = staticmethod(_crash_if_marked)


class _AlwaysCrashPool(WhisperPool):
    _initializer = staticmethod(_no_model)
    _target = staticmethod(_always_crash)


def _run(pool, coro_factory):
    async def scenario():
        await pool.start()
        try:
            return await coro_factory()
        finally:
            pool.stop()

    return asyncio.run(scenario())


def test_job_after_a_worker_crash_is_retried_and_succeeds(tmp_path):
    media = tmp_path / "input.wav"
    media.write_bytes(b"")
    (tmp_path / "input.wav.crash").write_bytes(b"")
    pool = _TestPool(make_settings(tmp_path, num_workers=2))

    assert _run(pool, lambda: pool.transcribe(media)) == [(0.0, 1.0, "ok")]


def test_media_that_always_crashes_fails_after_one_retry(tmp_path):
    media = tmp_path / "input.wav"
    media.write_bytes(b"")
    pool = _AlwaysCrashPool(make_settings(tmp_path, num_workers=1))

    with pytest.raises(BrokenProcessPool):
        _run(pool, lambda: pool.transcribe(media))


def test_two_jobs_hit_by_the_same_crash_both_recover(tmp_path):
    media = tmp_path / "input.wav"
    media.write_bytes(b"")
    pool = _TestPool(make_settings(tmp_path, num_workers=2))

    async def two_jobs():
        (tmp_path / "input.wav.crash").write_bytes(b"")
        return await asyncio.gather(pool.transcribe(media), pool.transcribe(media))

    assert _run(pool, two_jobs) == [[(0.0, 1.0, "ok")], [(0.0, 1.0, "ok")]]
