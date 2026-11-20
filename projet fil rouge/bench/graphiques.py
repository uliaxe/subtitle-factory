import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "resultats"
GREY = "#9aa0a6"
LIGHT = "#d7dadd"
ACCENT = "#1f6feb"
TITLES = {
    "scen-10-petites": "10 petites vidéos (30 s) envoyées en même temps",
    "scen-10-grandes": "10 grandes vidéos (5 min) envoyées en même temps",
    "scen-1-grande-9-petites": "1 grande vidéo et 9 petites envoyées en même temps",
}
INK = "#202124"


def load(prefix: str) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RESULTS.glob(f"{prefix}*.json"))]


def style(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=INK)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def config_name(config: str) -> str:
    parts = dict(item.split("=") for item in config.split())
    batch = f", lots de {parts['batch']}" if parts["batch"] != "0" else ""
    workers = f"{parts['workers']} worker" + ("s" if parts["workers"] != "1" else "")
    return f"{workers}, beam {parts['beam']}{batch}"


def summarize_configs(runs: list[dict], tolerance: float = 1.25) -> list[dict]:
    rows = []
    for r in runs:
        scored = [x for x in r["results"] if x.get("real_error_rate") is not None]
        rows.append({"name": config_name(r["config"]), "throughput": r["throughput_x_realtime"],
                     "real_errors": mean([x["real_error_rate"] for x in scored]),
                     "wer": mean([x["wer"] for x in scored]), "words": mean([x["words"] for x in scored])})
    floor = min(row["real_errors"] for row in rows)
    for row in rows:
        row["acceptable"] = row["real_errors"] <= floor * tolerance
    return sorted(rows, key=lambda row: row["throughput"])


def chart_configs(runs: list[dict], target: float) -> Path:
    rows = summarize_configs(runs)
    names = [row["name"] for row in rows]
    values = [row["throughput"] for row in rows]
    best = max((i for i, row in enumerate(rows) if row["acceptable"]), key=lambda i: values[i])
    colors = [ACCENT if i == best else (GREY if row["acceptable"] else LIGHT) for i, row in enumerate(rows)]
    fig, ax = plt.subplots(figsize=(11, 0.55 * len(rows) + 1.8))
    bars = ax.barh(names, values, color=colors)
    for bar, row in zip(bars, rows):
        if not row["acceptable"]:
            bar.set_hatch("//")
            bar.set_edgecolor(GREY)
        verdict = "" if row["acceptable"] else "  rejeté : passages manqués"
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
                f"{row['throughput']:.1f} x   erreurs réelles {row['real_errors']:.1%}{verdict}",
                va="center", color=INK, fontsize=9,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    ax.axvline(target, color=INK, linestyle="--", linewidth=1, zorder=0)
    ax.text(target, len(rows) - 0.35, f" {target:.0f} x : requis pour 10 utilisateurs", color=INK, fontsize=9)
    ax.set_xlabel("Débit total de la carte (secondes de média traitées par seconde)")
    ax.set_title(f"GTX 1650 : meilleur réglage acceptable {values[best]:.1f} x le temps réel ({names[best]})",
                 loc="left", color=INK, fontsize=11)
    ax.set_xlim(0, max(max(values), target) * 2.0)
    style(ax)
    fig.tight_layout()
    path = RESULTS / "debit_reglages.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def chart_scenario(run: dict) -> Path:
    rows = sorted(run["results"], key=lambda r: r["user"])
    labels = [f"#{r['user']} {r['media'].replace('.mp4', '')}" for r in rows]
    processing = [(r["processing_time_s"] or 0) / (r["media_duration_s"] or 1) for r in rows]
    total = [(r["finished_at"] - r["submitted_at"]) / (r["media_duration_s"] or 1) for r in rows]
    waiting = [max(0.0, t - p) for t, p in zip(total, processing)]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(labels, processing, color=ACCENT, label="traitement")
    ax.bar(labels, waiting, bottom=processing, color=LIGHT, label="attente (capacité pleine, nouvel essai)")
    ax.axhline(1.0, color=INK, linestyle="--", linewidth=1)
    ax.text(len(rows) - 0.5, 1.02, "durée du média", ha="right", va="bottom", color=INK, fontsize=9)
    ax.set_ylabel("Temps / durée du média")
    worst = max(processing)
    title = TITLES.get(run["label"], run["label"])
    ax.set_title(f"{title} : {run['done']}/{len(rows)} terminées, traitement au pire {worst:.2f} x la durée",
                 loc="left", color=INK, fontsize=11)
    ax.legend(frameon=False, loc="upper left")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    style(ax)
    fig.tight_layout()
    path = RESULTS / f"{run['label']}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


if __name__ == "__main__":
    configs = load("cfg-")
    if configs:
        print(chart_configs(configs, target=10.0))
        for row in summarize_configs(configs):
            print(f"  {row['name']:32s} {row['throughput']:5.2f} x  erreurs réelles {row['real_errors']:.1%}  "
                  f"WER {row['wer']:.1%}  {row['words']:.0f} mots  {'OK' if row['acceptable'] else 'rejeté'}")
    for run in load("scen-"):
        print(chart_scenario(run))
