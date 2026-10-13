"""Build and run actual-DLL writer lifecycle checks; no model algorithm is reimplemented."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import time

DOTNET = Path(r"C:\Program Files\dotnet\dotnet.exe")
DEFAULT_JOB = Path(__file__).resolve().parents[2]
VARIANTS = ["double", "dictionary_fixed", "static_update", "output_index", "combined"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(record):
    data = bytes.fromhex(record["hex"])
    if record["category"] == "lifecycle_ascii":
        lines = data.decode("utf-8-sig").splitlines()
        values = [float(value) for line in lines[6:] for value in line.split()]
        assert len(values) == 6 and all(math.isfinite(x) for x in values)
        return {"header": lines[:6], "values": values}
    width = 4 if record["category"] == "odour" or record["name"].endswith(".odr") else 1
    h, = struct.unpack_from("<i", data)
    result = {"header": h, "cells": []}
    pos = 4
    if h == -1:
        while pos < len(data):
            x, y = struct.unpack_from("<ii", data, pos)
            pos += 8
            values = list(struct.unpack_from("<" + "f" * width, data, pos))
            pos += 4 * width
            assert all(math.isfinite(v) for v in values)
            result["cells"].append({"x": x, "y": y, "values": values})
    elif h in (-2, -3):
        ox, oy, dx, dy = struct.unpack_from("<iiff", data, pos)
        pos += 16
        result["origin"] = [ox, oy]
        result["spacing"] = [dx, dy]
        if h == -2:
            while True:
                count, = struct.unpack_from("<i", data, pos)
                pos += 4
                if count == -1:
                    break
                assert count > 0 and count % width == 0
                i, j = struct.unpack_from("<ii", data, pos)
                pos += 8
                for offset in range(count // width):
                    values = list(struct.unpack_from("<" + "f" * width, data, pos))
                    pos += 4 * width
                    assert all(math.isfinite(v) for v in values)
                    result["cells"].append({"i": i, "j": j + offset, "values": values})
        else:
            nx, ny = struct.unpack_from("<ii", data, pos)
            pos += 8
            result["grid"] = [nx, ny]
            for i in range(1, nx + 1):
                for j in range(1, ny + 1):
                    values = list(struct.unpack_from("<" + "f" * width, data, pos))
                    pos += 4 * width
                    assert all(math.isfinite(v) for v in values)
                    if any(v != 0 for v in values):
                        result["cells"].append({"i": i, "j": j, "values": values})
    else:
        raise ValueError(h)
    assert pos == len(data), (pos, len(data), record["name"])
    return result


def call(command, logfile, timeout):
    start = time.monotonic()
    with logfile.open("w", encoding="utf-8") as log:
        result = subprocess.run([str(x) for x in command], stdout=log, stderr=subprocess.STDOUT,
                                timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(f"Process failed ({result.returncode}): {logfile}")
    return time.monotonic() - start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=Path, default=DEFAULT_JOB)
    parser.add_argument("--variants", nargs="+", default=VARIANTS)
    parser.add_argument("--stage", choices=["build", "run", "all"], default="all")
    args = parser.parse_args()
    job = args.job.resolve()
    source = job / "work/benchmark/writer_lifecycle_probe.cs"
    generated = job / "work/benchmark/writer_lifecycle_generated"
    qa = job / "qa/writer_lifecycle"
    logs = job / "logs"
    for folder in [generated, qa, logs]:
        folder.mkdir(parents=True, exist_ok=True)
    project = generated / "WriterLifecycle.csproj"
    project.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
        '<TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable>'
        '<EnableDefaultCompileItems>false</EnableDefaultCompileItems><UseSharedCompilation>false</UseSharedCompilation>'
        '</PropertyGroup><ItemGroup><Compile Include="../writer_lifecycle_probe.cs" /></ItemGroup></Project>\n', encoding="utf-8")
    binary = generated / "bin/Release/net10.0/WriterLifecycle.dll"
    started = time.monotonic()
    if args.stage in ["build", "all"]:
        call([DOTNET, "build", project, "-c", "Release", "-p:TreatWarningsAsErrors=true", "--disable-build-servers"],
             logs / "writer_lifecycle_build.log", 120)
        print("[BUILD] PASS", flush=True)
    if args.stage == "build":
        return
    raw = {}
    run_records = []
    for variant in args.variants:
        assert time.monotonic() - started < 840, "Batch time cap"
        assembly = job / "build" / variant / "GRAL.dll"
        result_path = qa / f"{variant}.json"
        scratch = qa / f"{variant}_scratch"
        if scratch.exists():
            raise RuntimeError(f"Use a fresh scratch directory: {scratch}")
        elapsed = call([DOTNET, binary, assembly, result_path, scratch], logs / f"writer_lifecycle_{variant}.log", 120)
        raw[variant] = json.loads(result_path.read_text(encoding="utf-8"))
        assert len(raw[variant]["records"]) == 980
        assert len(raw[variant]["lifecycle"]) == 65
        assert all(x["cache_null_after"] for x in raw[variant]["lifecycle"])
        run_records.append({"variant": variant, "elapsed_s": elapsed, "assembly_sha256": sha(assembly), "result_sha256": sha(result_path)})
        print(f"[RUN] {variant} 980 outputs 65 lifecycle checks", flush=True)
    if "double" not in raw:
        raise ValueError("Include double as the reference")
    base = raw["double"]["records"]
    decoded_base = [decode(record) for record in base]
    comparisons = {}
    for variant, result in raw.items():
        differences = []
        for index, (reference, candidate) in enumerate(zip(base, result["records"], strict=True)):
            identity = ["category", "name", "method", "header", "group", "slice"]
            assert all(reference[k] == candidate[k] for k in identity)
            decoded_candidate = decode(candidate)
            byte_equal = reference["sha256"] == candidate["sha256"]
            decoded_equal = decoded_base[index] == decoded_candidate
            if not byte_equal or not decoded_equal:
                differences.append({"index": index, **{k: reference[k] for k in identity},
                                    "byte_equal": byte_equal, "decoded_equal": decoded_equal,
                                    "reference": decoded_base[index], "candidate": decoded_candidate})
        comparisons[variant] = {"count": len(base), "byte_mismatches": sum(not d["byte_equal"] for d in differences),
                                "decoded_mismatches": sum(not d["decoded_equal"] for d in differences), "differences": differences}
        if variant != "dictionary":
            assert not differences, (variant, len(differences))
        print(f"[COMPARE] {variant} {len(differences)} mismatches", flush=True)
    summary = {"method": "Actual compiled GRAL public and private writers, with synthetic dictionary/array inputs; no writer code is reimplemented.",
               "source_sha256": sha(source), "runner_sha256": sha(Path(__file__)), "runs": run_records,
               "original_writer_outputs": 84, "new_public_outputs": 896, "public_calls": 64,
               "public_exception_cleanup_cases": 1, "public_output_headers": [-1, -2, -3],
               "public_modes": ["zipped plain", "zipped strong compressed", "zipped all compressed", "unzipped plain"],
               "ascii": True, "deposition": True, "odour_presence_masks": list(range(8)),
               "same_instance_consecutive_situations": 2, "comparisons_against_double": comparisons,
               "cache_checks": {v: r["lifecycle"] for v, r in raw.items()}}
    (qa / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("[DONE] writer lifecycle", flush=True)


if __name__ == "__main__":
    main()