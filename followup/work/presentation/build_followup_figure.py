"""Render the reviewed dictionary follow-up comparison from final measured summaries."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np

VARIANTS = ["double", "dictionary_fixed", "output_index", "static_update", "combined"]
LABELS = ["Dense double (#64)", "Dictionary, corrected", "+ Grouped output", "+ Static updates", "+ Both"]
COLORS = ["#656C76", "#C78646", "#287EAB", "#8774A8", "#318267"]
CASES = [
    ("sparse_sg99_fine9_t4", "Large sparse output", {"nx": 240, "ny": 240, "conc": 10, "sg": 99, "slices": 9, "pps": 1000, "workers": 4}),
    ("neutral_sg26_t14", "Smaller output, more workers", {"nx": 60, "ny": 60, "conc": 20, "sg": 26, "slices": 1, "pps": 1000, "workers": 14}),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paired(summary, tag, case, reference, variant, metric):
    matches = [r for r in summary["paired_performance"] if
               (r["tag"], r["case"], r["reference"], r["variant"]) == (tag, case, reference, variant)]
    if len(matches) != 1:
        raise ValueError(("Missing unique paired comparison", tag, case, reference, variant))
    row = matches[0]
    if row["n"] != 3:
        raise ValueError("Figure requires three measured comparison pairs")
    return float(row[f"{metric}_change_pct_median"])


def change_text(change, metric, reference):
    if change < 0:
        return f"{abs(change):.1f}% less {metric} than {reference}"
    return f"{change:.1f}% more {metric} than {reference}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--tag", default="ablation_clean")
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()
    job = args.job.resolve()
    if args.tag == "ablation":
        raise ValueError("The contaminated ablation batch is excluded from this figure")
    source_json = job / "results/followup_analysis.json"
    source_csv = job / "results/followup_variant_summary.csv"
    summary = json.loads(source_json.read_text(encoding="utf-8-sig"))
    csv_rows = list(csv.DictReader(source_csv.open(encoding="utf-8-sig", newline="")))
    if args.tag not in summary["selected_tags"]:
        raise ValueError("Requested final batch is absent from the analysis")
    data = {}
    for case, _, condition in CASES:
        for variant in VARIANTS:
            selected = [r for r in summary["variant_summaries"] if
                        (r["tag"], r["case"], r["variant"]) == (args.tag, case, variant)]
            table = [r for r in csv_rows if (r["tag"], r["case"], r["variant"]) == (args.tag, case, variant)]
            if len(selected) != 1 or len(table) != 1:
                raise ValueError(("Missing unique variant row", case, variant))
            row = selected[0]
            if row["n"] != 3 or row["repeats"] != [1, 2, 3]:
                raise ValueError(("Unexpected measured-repeat set", case, variant))
            for key, value in condition.items():
                if row["condition"][key] != value:
                    raise ValueError(("Unexpected condition", case, key, row["condition"][key]))
            for metric in ["wall_s", "peak_commit_mib"]:
                for kind in ["min", "median", "max"]:
                    key = f"{metric}_{kind}"
                    if not math.isfinite(row[key]) or row[key] < 0:
                        raise ValueError(("Invalid metric", case, variant, key))
                    if not math.isclose(row[key], float(table[0][key]), rel_tol=1e-12, abs_tol=1e-12):
                        raise ValueError(("CSV/JSON disagree", case, variant, key))
            data[case, variant] = row
    out_dir = args.out_dir.resolve() if args.out_dir else job / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
                         "axes.labelcolor": "#343D48", "text.color": "#202B36",
                         "xtick.color": "#54606D", "ytick.color": "#202B36",
                         "svg.fonttype": "none", "savefig.facecolor": "white"})
    fig, axes = plt.subplots(2, 2, figsize=(14.4, 9.6), gridspec_kw={"wspace": 0.36, "hspace": 0.71})
    fig.subplots_adjust(left=0.235, right=0.965, bottom=0.14, top=0.785)
    fig.patch.set_facecolor("white")
    fig.text(0.035, 0.966, "Group sparse output once to avoid repeated scans", fontsize=21, weight="bold", va="top")
    fig.text(0.035, 0.922, "Dictionary storage saves memory on the larger grid; dense arrays remain faster with 14 workers.", fontsize=12.5, color="#586473", va="top")
    titles_y = [0.876, 0.462]
    callouts = []
    for r, (case, heading, condition) in enumerate(CASES):
        fig.text(0.035, titles_y[r], heading, fontsize=15, weight="bold", va="top")
        heights = "height" if condition["slices"] == 1 else "heights"
        metadata = (f'{condition["nx"]} × {condition["ny"]} cells at {condition["conc"]} m  |  '
                    f'{condition["sg"]} groups × {condition["slices"]} {heights}  |  '
                    f'{condition["workers"]} workers  |  1,000 particles/s')
        fig.text(0.035, titles_y[r] - 0.028, metadata, fontsize=11.2, color="#586473", va="top")
        for c, metric in enumerate(["wall_s", "peak_commit_mib"]):
            ax = axes[r, c]
            medians = np.array([data[case, v][metric + "_median"] for v in VARIANTS])
            maxima = np.array([data[case, v][metric + "_max"] for v in VARIANTS])
            minima = np.array([data[case, v][metric + "_min"] for v in VARIANTS])
            y = np.arange(len(VARIANTS))
            ax.barh(y, medians, color=COLORS, height=0.58, zorder=3)
            if c == 0:
                ax.errorbar(medians, y, xerr=np.vstack([medians-minima, maxima-medians]), fmt="none",
                            ecolor="#263441", elinewidth=1.15, capsize=3.3, capthick=1.15, zorder=4)
            limit = max(maxima if c == 0 else medians) * 1.24
            ax.set_xlim(0, limit)
            ax.set_ylim(len(VARIANTS)-0.45, -0.55)
            ax.set_yticks(y, LABELS if c == 0 else [""] * len(y))
            ax.tick_params(axis="y", length=0, pad=10, labelsize=12)
            ax.tick_params(axis="x", length=0, pad=7, labelsize=10.5)
            ax.xaxis.set_major_locator(MaxNLocator(4))
            ax.grid(axis="x", color="#E9EDF1", linewidth=0.8, zorder=0)
            ax.set_axisbelow(True)
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.set_title("Elapsed time (seconds)" if c == 0 else "Peak process commit (MiB)", loc="left", fontsize=12.5, pad=12)
            for index, value in enumerate(medians):
                xpos = (maxima[index] if c == 0 else value) + limit * 0.022
                ax.text(xpos, index, f"{value:.2f}" if c == 0 else f"{value:.1f}", va="center", ha="left", fontsize=11.5)
        if r == 0:
            time_delta = paired(summary, args.tag, case, "dictionary_fixed", "output_index", "wall_s")
            memory_delta = paired(summary, args.tag, case, "double", "output_index", "peak_commit_mib")
            messages = ["Grouped output: " + change_text(time_delta, "time", "dictionary"),
                        "Grouped output: " + change_text(memory_delta, "memory", "dense")]
        else:
            time_delta = paired(summary, args.tag, case, "double", "combined", "wall_s")
            memory_delta = paired(summary, args.tag, case, "double", "combined", "peak_commit_mib")
            messages = ["Both changes: " + change_text(time_delta, "time", "dense"),
                        "Both changes: " + change_text(memory_delta, "memory", "dense")]
        for c, message in enumerate(messages):
            axes[r, c].text(0, -0.22, message, transform=axes[r, c].transAxes, fontsize=10.6,
                            color="#287EAB" if r == 0 else "#586473", ha="left", va="top")
            callouts.append({"case": case, "column": c, "text": message,
                             "paired_change_pct_median": time_delta if c == 0 else memory_delta})
    fig.text(0.035, 0.053, "Bars: median of 3 measured runs; time whiskers: min–max. One warm-up excluded. + variants modify the corrected dictionary.", fontsize=10.5, color="#586473", va="bottom")
    fig.text(0.035, 0.027, "Source: followup_analysis.json and followup_variant_summary.csv. Reproduction steps and conditions: README.", fontsize=10.5, color="#586473", va="bottom")
    stem = "dictionary_followup_tradeoff"
    png, svg = out_dir / (stem + ".png"), out_dir / (stem + ".svg")
    fig.savefig(png, dpi=180)
    fig.savefig(svg)
    plt.close(fig)
    artifact = {"tag": args.tag, "analysis_sha256": sha(source_json), "csv_sha256": sha(source_csv),
                "script_sha256": sha(Path(__file__)), "cases": [{"id": c, "title": h, "condition": d} for c,h,d in CASES],
                "variants": [{"id": v, "label": l, "color": color} for v,l,color in zip(VARIANTS,LABELS,COLORS)],
                "data": [data[c,v] for c,_,_ in CASES for v in VARIANTS], "callouts": callouts,
                "png_sha256": sha(png), "svg_sha256": sha(svg),
                "method": "Median bars; wall-time whiskers show the observed min/max. Callouts use within-repeat percentage-change medians from the analysis, not ratios of bar medians."}
    (out_dir / (stem + ".json")).write_text(json.dumps(artifact, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    print("[SAVE]", png)
    print("[SAVE]", svg)
    print("[SAVE]", out_dir / (stem + ".json"))


if __name__ == "__main__":
    main()