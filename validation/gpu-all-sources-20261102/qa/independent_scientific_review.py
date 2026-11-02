"""Independent post-run audit. Requires explicit completion confirmation; never runs models."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import struct
import zipfile
from pathlib import Path

import numpy as np

MODES = ("transient_all_sources", "steady_all_sources")
OFFSETS = tuple(range(0, 600000, 100000))
GROUPS = ("1", "2", "3", "4", "aggregate")
BLOCKS = ((0, 1), (2, 3), (4, 5))
ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def finite_json(value):
    if isinstance(value, dict):
        return {k: finite_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else "Infinity" if value > 0 else "-Infinity"
    return value


def divide(a, b, both_zero=0.0):
    return float(a / b) if b else both_zero if a == 0 else math.copysign(math.inf, a)


class Audit:
    def __init__(self):
        self.checks = []

    def check(self, name, condition):
        self.checks.append({"check": name, "pass": bool(condition)})

    def compare(self, name, actual, expected):
        if isinstance(actual, dict):
            self.check(name + "/mapping", isinstance(expected, dict))
            if isinstance(expected, dict):
                for key, value in actual.items():
                    self.check(name + "/" + key + "/present", key in expected)
                    if key in expected:
                        self.compare(name + "/" + key, value, expected[key])
        elif isinstance(actual, (tuple, list)):
            self.check(name + "/length", isinstance(expected, list) and len(actual) == len(expected))
            if isinstance(expected, list) and len(actual) == len(expected):
                for index, (a, b) in enumerate(zip(actual, expected)):
                    self.compare(f"{name}/{index}", a, b)
        elif isinstance(actual, float):
            if expected in ("Infinity", "-Infinity", "NaN"):
                expected = float(expected)
            same = isinstance(expected, (float, int)) and (
                math.isnan(actual) and math.isnan(expected)
                or math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-13))
            self.check(name, same)
        else:
            self.check(name, actual == expected)


def decode_run(folder, count):
    """Decode independently; do not import the analysis or shared comparison decoder."""
    comp = folder / "Computation"
    expected = {f"{s:05d}.grz" for s in range(1, count + 1)}
    if {f.name for f in comp.glob("*.grz")} != expected:
        raise ValueError(f"Unexpected output situation set: {folder}")
    result = {g: np.zeros((count, 50, 50), dtype=np.float64) for g in GROUPS[:-1]}
    for s in range(1, count + 1):
        with zipfile.ZipFile(comp / f"{s:05d}.grz") as archive:
            names = archive.namelist()
            wanted = {f"{s:05d}-1{g:02d}.con" for g in range(1, 5)}
            if len(names) != 4 or set(names) != wanted:
                raise ValueError(f"Unexpected or duplicate archive member: {folder}, {s}")
            for g in range(1, 5):
                payload = archive.read(f"{s:05d}-1{g:02d}.con")
                if len(payload) < 4:
                    raise ValueError("Truncated concentration header")
                mode = struct.unpack_from("<i", payload)[0]
                target = result[str(g)][s - 1]
                if mode == -3:
                    if len(payload) != 28 + 4 * 2500:
                        raise ValueError("Unexpected dense record size")
                    if struct.unpack_from("<iiiffii", payload) != (-3, 2000, 2000, 20.0, 20.0, 50, 50):
                        raise ValueError("Unexpected dense grid header")
                    target[:] = np.frombuffer(payload, dtype="<f4", offset=28).reshape((50, 50))
                elif mode == -1:
                    if (len(payload) - 4) % 12:
                        raise ValueError("Truncated sparse record")
                    seen = set()
                    for x, y, value in struct.iter_unpack("<iif", payload[4:]):
                        if (x, y) in seen or (x - 2010) % 20 or (y - 2010) % 20:
                            raise ValueError("Duplicate or off-grid sparse coordinate")
                        i, j = (x - 2010) // 20, (y - 2010) // 20
                        if not (0 <= i < 50 and 0 <= j < 50):
                            raise ValueError("Sparse coordinate outside fixed grid")
                        seen.add((x, y))
                        target[i, j] = value
                else:
                    raise ValueError(f"Unsupported grid encoding: {mode}")
                if not np.isfinite(target).all() or (target < 0).any():
                    raise ValueError("Nonfinite or negative concentration")
    result["aggregate"] = sum(result.values())
    return result


def field_stats(x, y):
    difference = y - x
    mx, my = float(x.mean()), float(y.mean())
    scale = (mx + my) / 2
    absolute_mean = float(np.abs(difference).mean())
    xmap, ymap = x.mean(axis=0).ravel(), y.mean(axis=0).ravel()
    constant = np.ptp(xmap) == 0 or np.ptp(ymap) == 0
    out = {
        "values": int(x.size), "hours": len(x), "mean_cpu": mx, "mean_gpu": my,
        "L": absolute_mean, "mean_difference": my - mx,
        "weighted_nmae": divide(absolute_mean, scale),
        "normalized_bias": divide(my - mx, scale),
        "spatial_pearson": None if constant else float(np.corrcoef(xmap, ymap)[0, 1]),
        "spatial_pearson_reason": "constant_map" if constant else None,
        "zero_status": "both_zero" if scale == 0 else "positive_reference_scale",
        "max_absolute_difference": float(np.abs(difference).max()),
        "cpu_max": float(x.max()), "gpu_max": float(y.max()),
        "cpu_max_index_hour0_x0_y0": list(map(int, np.unravel_index(x.argmax(), x.shape))),
        "gpu_max_index_hour0_x0_y0": list(map(int, np.unravel_index(y.argmax(), y.shape))),
    }
    for name, quantile in (("p95", 0.95), ("p99", 0.99)):
        a, b = map(float, (np.quantile(x, quantile, method="linear"), np.quantile(y, quantile, method="linear")))
        out[name] = {"cpu": a, "gpu": b, "difference": b - a, "absolute_difference": abs(b - a)}
    return out


def sample_stats(values):
    x = np.array(values, dtype=float)
    sd = float(x.std(ddof=1)) if len(x) > 1 else None
    mean = float(x.mean())
    return {"n": len(x), "raw": list(map(float, x)), "mean": mean,
            "median": float(np.median(x)), "min": float(x.min()), "max": float(x.max()),
            "sample_sd": sd, "cv": None if sd is None else divide(sd, mean)}


def audit_mode(mode, audit, analysis_root):
    manifest_path = ROOT / "study_manifests" / (mode + ".json")
    manifest = read_json(manifest_path)
    analysis = analysis_root / mode
    summary = read_json(analysis / "analysis_summary.json")
    audit.check(mode + "/cohort", manifest["cohort"] == summary["cohort"] == mode)
    audit.check(mode + "/allocation", len(manifest["runs"]) == 22)
    audit.check(mode + "/manifest_binding", digest(manifest_path) == summary["study_sha256"])
    audit.check(mode + "/protocol_binding", digest(ROOT / "qa/statistical_protocol_new_modes.json") == summary["protocol_sha256"])
    fields, receipts, states, clocks = {}, {}, {}, {}
    measurements = {r["run_id"]: r for r in summary["run_measurements"]}
    phases = {(r["run_id"], r["situation"]): r for r in read_json(analysis / "gpu_pipeline_phases.json")}
    scientific_runs = {}
    for run in manifest["runs"]:
        name = run["run_id"]
        folder = Path(run["path"])
        folder = (folder if folder.is_absolute() else manifest_path.parent / folder).resolve()
        if not folder.is_relative_to(ROOT / "runs/study" / mode):
            raise ValueError("Run escaped the new-mode study directory")
        result = read_json(folder / "logs/result.json")
        inputs = read_json(folder / "input_manifest.json")
        receipts[name] = result
        audit.check(name + "/completed", result["status"] == "pass" and result["exit_code"] == 0 and not result["errors"])
        audit.check(name + "/timing_eligible", result["timing_eligible"])
        audit.check(name + "/mode", run["cohort"] == mode and inputs["case"] == mode and bool(inputs["config"].get("steady")) == (mode == MODES[1]))
        audit.check(name + "/fixture", inputs["grid_cells"] == [50, 50] and inputs["workers"] == 16 and inputs["particles_per_hour"] == 360000 and inputs["source_groups"] == [1, 2, 3, 4])
        audit.check(name + "/quiet", result["quiet_gate"]["rule"]["window_seconds"] == 10)
        audit.check(name + "/dispatch", result["dispatch"]["path"] == ("gpu" if run["backend"] == "gpu" else "cpu_requested"))
        for rel, sha in inputs["input_sha256"].items():
            path = (folder / rel).resolve()
            if not path.is_relative_to(folder):
                raise ValueError("Input manifest path escaped run directory")
            audit.check(name + "/input/" + rel, digest(path) == sha == run["input_sha256"][rel])
        fields[name] = decode_run(folder, run["hours"])
        for group in GROUPS[:-1]:
            audit.check(name + "/positive_group/" + group, np.any(fields[name][group] > 0))
        observer = result["observer"]
        states[name] = [(row["Seed1"], row["Seed2"]) for row in observer["seed_rows"]]
        audit.check(name + "/seed_coverage", [row["IWET"] for row in observer["seed_rows"]] == list(range(1, run["hours"] + 1)) and all(row["fixed_mode"] for row in observer["seed_rows"]))
        series = observer["situation_series"]
        start = [r for r in observer["raw_events"] if r.get("event_type") == "boundary" and r.get("boundary") == "start"]
        stop = [r for r in observer["raw_events"] if r.get("event_type") == "boundary" and r.get("boundary") == "stop"]
        if len(start) != 1 or len(stop) != 1:
            raise ValueError("Missing or duplicate timing boundary")
        clocks[name] = {"process_start_to_exit_s": result["process_start_to_exit_s"],
                        "steady_wall_sum_s": sum(s["wall_s"] for s in series[3:]),
                        "steady_boundary_wall_s": stop[0]["elapsed_s"] - start[0]["elapsed_s"]}
        audit.compare(name + "/clocks", clocks[name], measurements[name])
        with (folder / "logs/process_telemetry.csv").open(encoding="utf-8-sig", newline="") as stream:
            telemetry = list(csv.DictReader(stream))
        for key in ("tree_rss_bytes", "tree_private_bytes", "dotnet_rss_bytes", "python_rss_bytes", "os_peak_working_set_bytes"):
            values = [float(row[key]) for row in telemetry if row.get(key) not in (None, "")]
            audit.compare(name + "/memory/" + key, max(values) if values else None, measurements[name]["memory"][key + "_observed_max"])
        if run["backend"] == "gpu":
            rows = [json.loads(line) for line in (folder / "logs/gpu_metrics.jsonl").read_text().splitlines() if line.strip()]
            audit.check(name + "/gpu_sequence", [r["situation"] for r in rows] == list(range(1, run["hours"] + 1)))
            previous_device, previous_launches, previous_fresh, previous_residual = 0.0, 0, 0, 0
            for row in rows:
                key = name + "/gpu/" + str(row["situation"])
                counters = row["result_server_metrics"]
                current = counters["kernel_device_ms"]
                audit.check(key + "/device_work", current > previous_device and counters["kernel_launches"] > previous_launches)
                audit.compare(key + "/event_delta", current - previous_device, phases[(name, row["situation"])]["kernel_device_interval_ms"])
                audit.check(key + "/host_completed_requests", row["phase_counts"]["fresh"] - previous_fresh == row["fresh_particles"] and row["phase_counts"]["residual"] - previous_residual == row["residual_particles"])
                audit.check(key + "/cache", counters["cache_status"] == "hit")
                if mode == MODES[1]:
                    audit.check(key + "/no_carryover", row["residual_particles"] == row["residual_batches"] == row["phase_counts"]["residual"] == 0)
                previous_device, previous_launches = current, counters["kernel_launches"]
                previous_fresh, previous_residual = row["phase_counts"]["fresh"], row["phase_counts"]["residual"]
            if mode == MODES[0]:
                audit.check(name + "/carryover_exercised", previous_residual > 0)
        if run["role"] == "science":
            scientific_runs[(run["backend"], run["seed_offset"])] = name
    audit.check(mode + "/science_pairs", set(scientific_runs) == set(itertools.product(("cpu", "gpu"), OFFSETS)))
    for offset in OFFSETS:
        audit.check(mode + f"/paired_seed/{offset}", states[scientific_runs[("cpu", offset)]] == states[scientific_runs[("gpu", offset)]])
    audit.check(mode + "/six_distinct_states", len({tuple(states[scientific_runs[("cpu", s)]]) for s in OFFSETS}) == 6)
    report = {"cohort": mode, "summary_sha256": digest(analysis / "analysis_summary.json"),
              "duration_semantics": summary["duration_semantics"], "groups": {}, "timing": {}}
    for group in GROUPS:
        cpu = [fields[scientific_runs[("cpu", s)]][group] for s in OFFSETS]
        gpu = [fields[scientific_runs[("gpu", s)]][group] for s in OFFSETS]
        published = summary["scientific"]["groups"][group]
        windows = {}
        for label, first in (("primary_seed_metrics", 3), ("all_hour_seed_metrics", 0)):
            windows[label] = [field_stats(x[first:], y[first:]) for x, y in zip(cpu, gpu)]
            audit.compare(mode + "/" + group + "/" + label, windows[label], published[label])
        blocks = []
        for index, (i, j) in enumerate(BLOCKS):
            x, y = cpu[i][3:], cpu[j][3:]
            u, v = gpu[i][3:], gpu[j][3:]
            aa = (np.abs(x - u).mean() + np.abs(y - v).mean()) / 2
            bb, dd = np.abs(x - y).mean(), np.abs(u - v).mean()
            block = {"seed_indices": [i, j], "A": float(aa), "B": float(bb), "D": float(dd),
                     "R": divide(aa, bb, None), "V": divide(dd, bb, None),
                     "primary_pass": bool(aa == 0 if bb == 0 else aa < bb),
                     "dispersion_review": bool(dd != 0 if bb == 0 else not 0.5 <= dd / bb <= 2.0)}
            audit.compare(mode + f"/{group}/block/{index}", block, published["blocks"][index])
            blocks.append(block)
        for item in published["interseed_pairs_dependent"]:
            i, j = item["seed_indices"]
            audit.compare(mode + f"/{group}/interseed_cpu/{i}/{j}", field_stats(cpu[i][3:], cpu[j][3:]), item["cpu"])
            audit.compare(mode + f"/{group}/interseed_gpu/{i}/{j}", field_stats(gpu[i][3:], gpu[j][3:]), item["gpu"])
        report["groups"][group] = {**windows, "blocks": blocks}
    for duration in (24, 48):
        selected = [r for r in manifest["runs"] if r["hours"] == duration and r["seed_offset"] == 0]
        report["timing"][str(duration)] = {}
        for metric in ("process_start_to_exit_s", "steady_wall_sum_s", "steady_boundary_wall_s"):
            summary_metric = {}
            for backend in ("cpu", "gpu"):
                values = [clocks[r["run_id"]][metric] for r in selected if r["backend"] == backend]
                summary_metric[backend] = sample_stats(values)
            pairs = {}
            for run in selected:
                pairs.setdefault(run["pair_id"], {})[run["backend"]] = clocks[run["run_id"]][metric]
            summary_metric["paired_speedup"] = sample_stats([v["cpu"] / v["gpu"] for v in pairs.values()])
            audit.compare(mode + f"/timing/{duration}/{metric}", summary_metric, summary["timing"][str(duration)][metric])
            report["timing"][str(duration)][metric] = summary_metric
        repeat = summary["fixed_seed_numerical_repeatability"]["durations"][str(duration)]
        for window, first in (("all_hours", 0), ("hours_4_to_end", 3)):
            for group in GROUPS:
                for pair_type, comparisons in repeat["windows"][window]["groups"][group].items():
                    audit.check(mode + f"/repeat_count/{duration}/{window}/{group}/{pair_type}", len(comparisons) == 3)
                    for pair in comparisons:
                        x = fields[pair["reference_run_id"]][group][first:]
                        y = fields[pair["candidate_run_id"]][group][first:]
                        stat = field_stats(x, y)
                        check = {"raw_array_equal": bool(np.array_equal(x, y)), "different_values": int(np.count_nonzero(x != y)),
                                 "compared_values": int(x.size), "symmetric_weighted_nmae": stat["weighted_nmae"],
                                 "normalized_bias_candidate_minus_reference": stat["normalized_bias"],
                                 "mean_difference_candidate_minus_reference": stat["mean_difference"],
                                 "maximum_absolute_difference": stat["max_absolute_difference"], "zero_status": stat["zero_status"]}
                        audit.compare(mode + f"/repeat/{duration}/{window}/{group}/{pair['reference_run_id']}/{pair['candidate_run_id']}", check, pair)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-models-finished", action="store_true", required=True)
    parser.add_argument("--analysis-root", type=Path, default=ROOT / "analysis/measured")
    parser.add_argument("--out", type=Path, default=ROOT / "qa/independent_raw_review.json")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Choose a new output path; existing review evidence is preserved.")
    audit = Audit()
    report = {"status": "running", "method": "Independent GRZ decoding and raw receipt/CSV audit; no analysis/validation module imports.",
              "source_sha256": digest(Path(__file__)), "cohorts": {}, "checks": audit.checks,
              "limitations": {"random_stream_independence_verified": False, "physical_equivalence_established": False,
                              "automatic_final_engineering_pass": False, "source_type_device_counts_measured": False}}
    try:
        for mode in MODES:
            report["cohorts"][mode] = audit_mode(mode, audit, args.analysis_root)
        report["status"] = "pass_pending_human_diagnostics" if all(x["pass"] for x in audit.checks) else "fail"
    except (OSError, ValueError, KeyError, TypeError, struct.error, zipfile.BadZipFile) as exc:
        report["status"] = "INVALID"
        report["error"] = f"{type(exc).__name__}: {exc}"
    report["check_count"] = len(audit.checks)
    report["fail_count"] = sum(not x["pass"] for x in audit.checks)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(finite_json(report), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(report["status"], report["check_count"], report["fail_count"])
    return 0 if report["status"] == "pass_pending_human_diagnostics" else 1


if __name__ == "__main__":
    raise SystemExit(main())
