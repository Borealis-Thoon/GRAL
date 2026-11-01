"""Run a virtual mixed-deposition check for hourly source allocation."""

import argparse
import json
import math
import re
import struct
import subprocess
import zipfile
from pathlib import Path

from run_synthetic import PARTICLES, particle_allocations, write_case


CASES = {
    "control6": [(1, 1, 0)] * 6,
    "late6": [(0, 2, 0)] * 3 + [(2, 0, 0), (0, 2, 0), (2, 0, 0)],
    "cold6": [(0, 0, 0)] * 3 + [(2, 0, 0), (0, 0, 0), (2, 0, 0)],
}


def prepare(folder, factors):
    write_case(folder, factors, hourly_total=2)
    rows = ["x,y,z,emission,unused,unused,unused,velocity,diameter,temperature,SG\n",
            "virtual point sources, kg/h\n"]
    for group in (1, 2):
        base = f"100,100,2,0.5,0,0,0,0,1,293,{group}"
        rows.append(base + "\n")
        rows.append(base + ",100,100,30,1000,0.03,0,0,1\n")
    (folder / "point.dat").write_text("".join(rows), encoding="ascii", newline="\n")


def check_grids(folder, factors):
    counts = {"con": 0, "dep": 0}
    by_group = {group: {"con_sum": 0.0, "dep_sum": 0.0} for group in (1, 2, 3)}
    ever_active = {group: False for group in (1, 2, 3)}
    for hour, row in enumerate(factors, 1):
        with zipfile.ZipFile(folder / f"{hour:05d}.grz") as archive:
            assert len(archive.namelist()) == 6
            for group, factor in zip((1, 2, 3), row):
                group_sums = {}
                for extension in ("con", "dep"):
                    member = (f"{hour:05d}-1{group:02d}.con" if extension == "con"
                              else f"{hour:05d}-{group:02d}.dep")
                    payload = archive.read(member)
                    assert len(payload) == 428, (member, len(payload))
                    header = struct.unpack_from("<iiiffii", payload)
                    assert header[0] == -3 and header[-2:] == (10, 10), member
                    values = struct.unpack_from("<100f", payload, 28)
                    assert all(math.isfinite(value) and value >= 0 for value in values), member
                    counts[extension] += sum(value > 0 for value in values)
                    group_sums[extension] = sum(values)
                    by_group[group][f"{extension}_sum"] += group_sums[extension]
                if factor > 0:
                    assert group_sums["con"] > 0 and group_sums["dep"] > 0, (hour, group, group_sums)
                    ever_active[group] = True
                elif not ever_active[group]:
                    assert group_sums == {"con": 0, "dep": 0}, (hour, group, group_sums)
    assert counts["con"] > 0 and counts["dep"] > 0, counts
    counts["by_group"] = by_group
    return counts


def check_run(folder, stdout, factors, baseline):
    hours = len(factors)
    assert "GRAL simulations finished at:" in (folder / "Logfile_GRALCore.txt").read_text(errors="replace")
    assert not (folder / "Problemreport_GRAL.txt").exists()
    blocks = particle_allocations(stdout, source_count=4)
    assert len(blocks) == (1 if baseline else hours + 1), blocks
    assert blocks[0] == (27, 27, 27, 27), blocks[0]
    if not baseline:
        for hour, (actual, (group1, group2, _)) in enumerate(zip(blocks[1:], factors), 1):
            expected = (27 * group1, 27 * group1, 27 * group2, 27 * group2)
            assert actual == expected, (hour, actual, expected)
            assert sum(actual) == (PARTICLES if group1 + group2 else 0)
    totals = [int(n) for n in re.findall(r"Using a total of (\d+) particles", stdout)]
    assert totals == [sum(block) for block in blocks]
    mass_rows = re.findall(r"Summarized emission rates per source group in kg\s*\n[^\n]*\n([^\n]+)", stdout)
    assert len(mass_rows) == 1
    emitted = tuple(float(value.replace(",", ".")) for value in mass_rows[0].split())
    expected_mass = tuple(sum(row[index] for row in factors) for index in range(3))
    assert len(emitted) == 3
    assert all(abs(actual - expected) < 0.02 for actual, expected in zip(emitted, expected_mass)), (emitted, expected_mass)
    return {"hours": hours, "hourly_particles": blocks[1:], "emitted_mass_kg": emitted,
            "finite_positive_grid_cells": check_grids(folder, factors)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dll", type=Path, help="GRAL.dll; omit to prepare inputs only")
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    if args.baseline and args.case != "control6":
        parser.error("--baseline is only valid for control6")
    factors = CASES[args.case]
    prepare(args.out, factors)
    if not args.dll:
        print(f"[PREPARE] {args.case} {args.out}")
        return
    result = subprocess.run(["dotnet", str(args.dll.resolve()), str(args.out.resolve()), "LOGLEVEL02"],
                            cwd=args.out, capture_output=True, text=True, errors="replace", timeout=1200)
    (args.out / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (args.out / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    assert result.returncode == 0, f"GRAL returned {result.returncode}: {result.stderr[-500:]}"
    report = check_run(args.out, result.stdout, factors, args.baseline)
    (args.out / "check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[PASS] {args.case} {report['finite_positive_grid_cells']}")


if __name__ == "__main__":
    main()
