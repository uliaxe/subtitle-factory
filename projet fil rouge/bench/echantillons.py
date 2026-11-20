import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "input.mp4"
MEDIA = ROOT / "media"


def make_small(duration_s: int = 30) -> Path:
    target = MEDIA / "petite.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SOURCE), "-t", str(duration_s),
                    "-c", "copy", str(target)], check=True)
    return target


def make_large(repeat: int = 2) -> Path:
    target = MEDIA / "grande.mp4"
    listing = MEDIA / "liste.txt"
    listing.write_text("".join(f"file '{SOURCE.as_posix()}'\n" for _ in range(repeat)), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(target)], check=True)
    listing.unlink()
    return target


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


if __name__ == "__main__":
    if not SOURCE.is_file():
        sys.exit(f"Échantillon introuvable : {SOURCE}")
    MEDIA.mkdir(exist_ok=True)
    for path in (make_small(), make_large()):
        print(f"{path.name} : {duration(path):.1f} s")
