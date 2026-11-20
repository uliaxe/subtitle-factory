import argparse
import json
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
import jiwer

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "experiments"))
from essai_whisper import normalize, reference_text

SCENARIOS = {
    "debit": lambda n: ["input.mp4"] * n,
    "petites": lambda n: ["petite.mp4"] * n,
    "grandes": lambda n: ["grande.mp4"] * n,
    "mixte": lambda n: ["grande.mp4"] + ["petite.mp4"] * (n - 1),
}
POLL_S = 1.0
RETRY_S = 3.0


@dataclass
class Result:
    user: int
    media: str
    media_duration_s: float | None = None
    submitted_at: float = 0.0
    accepted_at: float = 0.0
    finished_at: float = 0.0
    refusals: int = 0
    status: str = ""
    processing_time_s: float | None = None
    error: str | None = None
    wer: float | None = None
    real_error_rate: float | None = None
    words: int | None = None


def media_path(name: str) -> Path:
    return ROOT.parent / name if name == "input.mp4" else ROOT / "media" / name


def run_user(base: str, token: str, result: Result, output_type: str, start: float, reference: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=base, headers=headers, timeout=600) as http:
        result.submitted_at = time.perf_counter() - start
        while True:
            with media_path(result.media).open("rb") as f:
                response = http.post("/api/v1/jobs", files={"file": (result.media, f)},
                                     data={"output_type": output_type})
            if response.status_code != 429:
                break
            result.refusals += 1
            time.sleep(RETRY_S)
        response.raise_for_status()
        result.accepted_at = time.perf_counter() - start
        job_id = response.json()["id"]
        while True:
            job = http.get(f"/api/v1/jobs/{job_id}").json()
            if job["status"] in ("done", "failed"):
                break
            time.sleep(POLL_S)
        result.finished_at = time.perf_counter() - start
        result.status = job["status"]
        result.processing_time_s = job["processing_time_s"]
        result.media_duration_s = job["media_duration_s"]
        result.error = job["error_message"]
        if result.media == "input.mp4" and job["result_text"]:
            hypothesis = normalize(job["result_text"])
            counts = jiwer.process_words(reference, hypothesis)
            result.wer = round(counts.wer, 4)
            result.real_error_rate = round((counts.substitutions + counts.deletions) / len(reference.split()), 4)
            result.words = len(hypothesis.split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--output", default="text")
    parser.add_argument("--label", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--config", default="", help="réglages du service IA, pour mémoire")
    args = parser.parse_args()

    token = httpx.post(f"{args.url}/api/v1/auth/login",
                       data={"username": args.user, "password": args.password}).json()["access_token"]
    reference = reference_text(ROOT.parent / "real_subtitle.txt")
    results = [Result(user=i + 1, media=m) for i, m in enumerate(SCENARIOS[args.scenario](args.users))]
    start = time.perf_counter()
    threads = [threading.Thread(target=run_user, args=(args.url, token, r, args.output, start, reference))
               for r in results]
    for t in threads:
        t.start()
        time.sleep(0.2)
    for t in threads:
        t.join()

    makespan = max(r.finished_at for r in results) - min(r.submitted_at for r in results)
    audio = sum(r.media_duration_s or 0 for r in results if r.status == "done")
    summary = {
        "label": args.label, "scenario": args.scenario, "users": args.users, "config": args.config,
        "output": args.output, "makespan_s": round(makespan, 1), "audio_s": round(audio, 1),
        "throughput_x_realtime": round(audio / makespan, 2) if makespan else None,
        "done": sum(r.status == "done" for r in results), "failed": sum(r.status == "failed" for r in results),
        "results": [asdict(r) for r in results],
    }
    out_dir = ROOT / "resultats"
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{args.label}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{args.label} : {summary['done']}/{len(results)} terminés, durée totale {makespan:.0f} s, "
          f"débit {summary['throughput_x_realtime']} x temps réel")
    for r in results:
        total = r.finished_at - r.submitted_at
        ratio_srv = (r.processing_time_s or 0) / (r.media_duration_s or 1)
        ratio_tot = total / (r.media_duration_s or 1)
        wer = (f" WER {r.wer:.1%} erreurs réelles {r.real_error_rate:.1%} ({r.words} mots)"
               if r.wer is not None else "")
        print(f"  #{r.user:2d} {r.media:10s} refus {r.refusals:2d}  traitement {r.processing_time_s or 0:6.1f} s "
              f"(ratio {ratio_srv:.2f})  attente+traitement {total:6.1f} s (ratio {ratio_tot:.2f}) {r.status}{wer}")


if __name__ == "__main__":
    main()
