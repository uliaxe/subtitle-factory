import argparse
import os
import re
import site
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def add_nvidia_dll_dirs() -> None:
    if os.name != "nt":
        return
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        nvidia = Path(base) / "nvidia"
        if nvidia.is_dir():
            for bin_dir in nvidia.glob("*/bin"):
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"


def media_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def load_audio(path: Path, sample_rate: int = 16_000):
    import numpy as np

    out = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
         "-f", "f32le", "-ac", "1", "-ar", str(sample_rate), "-"],
        capture_output=True, check=True,
    )
    return np.frombuffer(out.stdout, dtype=np.float32)


def srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return " ".join(text.split())


def reference_text(path: Path) -> str:
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = re.sub(r"^\[[^\]]*\]\s*", "", line)
        line = line.replace(">>", " ")
        line = re.sub(r"^\s*[A-Z][A-Z .']*:\s*", "", line)
        words.append(line)
    return normalize(" ".join(words))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=HERE / "input.mp4")
    parser.add_argument("--reference", type=Path, default=HERE / "real_subtitle.txt")
    parser.add_argument("--model", default="medium.en")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute", default="int8_float16")
    parser.add_argument("--beam", type=int, default=5)
    args = parser.parse_args()

    add_nvidia_dll_dirs()
    from faster_whisper import WhisperModel
    import jiwer

    duration = media_duration(args.input)
    print(f"Média : {args.input.name}, {duration:.1f} s")

    t0 = time.perf_counter()
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute)
    load_s = time.perf_counter() - t0
    print(f"Modèle {args.model} ({args.device}, {args.compute}) chargé en {load_s:.1f} s")

    t0 = time.perf_counter()
    audio = load_audio(args.input)
    segments_iter, _info = model.transcribe(audio, language="en", beam_size=args.beam)
    segments = list(segments_iter)
    compute_s = time.perf_counter() - t0

    hypothesis = " ".join(s.text.strip() for s in segments)
    srt = "\n".join(
        f"{i}\n{srt_time(s.start)} --> {srt_time(s.end)}\n{s.text.strip()}\n"
        for i, s in enumerate(segments, start=1)
    )
    srt_path = Path(tempfile.gettempdir()) / f"essai_{args.model}_{args.compute}.srt"
    srt_path.write_text(srt, encoding="utf-8")

    ref = reference_text(args.reference)
    wer = jiwer.wer(ref, normalize(hypothesis))

    print(f"Transcription : {compute_s:.1f} s, soit {compute_s / duration:.2f} x la durée du média "
          f"({'OK' if compute_s < duration else 'TROP LENT'})")
    print(f"WER : {wer:.1%} ({len(ref.split())} mots de référence, {len(segments)} segments)")
    print(f"Début : {hypothesis[:200]}...")
    print(f".srt écrit dans {srt_path}")


if __name__ == "__main__":
    sys.exit(main())
