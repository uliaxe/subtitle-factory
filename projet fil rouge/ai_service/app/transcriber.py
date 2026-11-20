import asyncio
import logging
import multiprocessing
import os
import site
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
from typing import Protocol

from app.config import Settings
from app.subtitles import Segment

LOGGER = logging.getLogger(__name__)


class Transcriber(Protocol):
    async def start(self) -> None: ...
    async def transcribe(self, media_path: Path) -> list[Segment]: ...
    def stop(self) -> None: ...


_MODEL = None
_BEAM_SIZE = 5
_BATCH_SIZE = 0


def _add_nvidia_dll_dirs() -> None:
    if os.name != "nt":
        return
    for base in [*site.getsitepackages(), site.getusersitepackages()]:
        for bin_dir in (Path(base) / "nvidia").glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


def _init_worker(model_name: str, device: str, compute_type: str, beam_size: int, batch_size: int = 0) -> None:
    global _MODEL, _BEAM_SIZE, _BATCH_SIZE
    _add_nvidia_dll_dirs()
    from faster_whisper import BatchedInferencePipeline, WhisperModel

    _MODEL = WhisperModel(model_name, device=device, compute_type=compute_type)
    if batch_size > 0:
        _MODEL = BatchedInferencePipeline(model=_MODEL)
    _BEAM_SIZE = beam_size
    _BATCH_SIZE = batch_size


def decode_options(beam_size: int, batch_size: int) -> dict:
    options = {"language": "en", "beam_size": beam_size}
    if batch_size > 0:
        options.update(batch_size=batch_size, without_timestamps=False)
    return options


def _wait_all_workers(barrier) -> int:
    barrier.wait(timeout=600)
    return os.getpid()


def _transcribe_in_worker(media_path: str) -> list[Segment]:
    from app.media import load_audio

    audio = load_audio(Path(media_path))
    segments, _info = _MODEL.transcribe(audio, **decode_options(_BEAM_SIZE, _BATCH_SIZE))
    return [(s.start, s.end, s.text.strip()) for s in segments]


class WhisperPool:
    _initializer = staticmethod(_init_worker)
    _target = staticmethod(_transcribe_in_worker)

    def __init__(self, settings: Settings):
        self._settings = settings
        self._executor: ProcessPoolExecutor | None = None

    def _new_executor(self) -> ProcessPoolExecutor:
        s = self._settings
        return ProcessPoolExecutor(
            max_workers=s.num_workers,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=self._initializer,
            initargs=(s.model_name, s.device, s.compute_type, s.beam_size, s.batch_size),
        )

    async def start(self) -> None:
        self._executor = self._new_executor()
        n = self._settings.num_workers
        with multiprocessing.get_context("spawn").Manager() as manager:
            barrier = manager.Barrier(n)
            loop = asyncio.get_running_loop()
            pids = await asyncio.gather(
                *(loop.run_in_executor(self._executor, _wait_all_workers, barrier) for _ in range(n))
            )
        LOGGER.info("%d workers prêts (modèle %s) : pid %s", n, self._settings.model_name, sorted(pids))

    async def transcribe(self, media_path: Path) -> list[Segment]:
        loop = asyncio.get_running_loop()
        for attempt in (1, 2):
            executor = self._executor
            try:
                return await loop.run_in_executor(executor, self._target, str(media_path))
            except BrokenProcessPool:
                LOGGER.error("Un worker a planté (tentative %d) : redémarrage des workers", attempt)
                if self._executor is executor:
                    executor.shutdown(wait=False, cancel_futures=True)
                    self._executor = self._new_executor()
                if attempt == 2:
                    raise
        raise AssertionError("inatteignable")

    def stop(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)


class FakeTranscriber:
    SEGMENTS: list[Segment] = [
        (0.0, 1.5, "This is a simulated transcription."),
        (1.5, 3.0, "No GPU was used."),
    ]

    async def start(self) -> None:
        return None

    async def transcribe(self, media_path: Path) -> list[Segment]:
        if not media_path.is_file():
            raise FileNotFoundError(media_path)
        return list(self.SEGMENTS)

    def stop(self) -> None:
        return None


def build_transcriber(settings: Settings) -> Transcriber:
    return WhisperPool(settings) if settings.transcriber == "whisper" else FakeTranscriber()
