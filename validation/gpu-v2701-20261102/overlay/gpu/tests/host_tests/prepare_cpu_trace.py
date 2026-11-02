"""Create a disposable CPU tracing copy; never patch the repository source."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"Patch anchor count {text.count(old)}: {old[:90]!r}")
    return text.replace(old, new, 1)


def prepare(root: Path, target: Path) -> dict:
    source = root / "src"
    if target.exists() or target.resolve() == source.resolve() or source.resolve() in target.resolve().parents:
        raise ValueError("Target must be a new separate source directory")
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("bin", "obj"))
    fresh = (target / "Zeitschleife.cs").read_text(encoding="utf-8-sig")
    fresh = replace_once(fresh, "            float auszeit = 0;", "            auszeit = 0;")
    fresh = replace_once(fresh, "            int timestep_number = 0;", "            timestep_number = 0;")
    fresh = replace_once(fresh, "        public static void Calculate(int nteil)\n        {", "        public static void Calculate(int nteil)\n        {\n            float auszeit=0;int timestep_number=0;")
    fresh = replace_once(fresh, "            float zahl1 = 0;", "            CpuTrace.InitialFresh(nteil,m_w,m_z);\n            float zahl1 = 0;")
    fresh = replace_once(fresh, "                return;", "                CpuTrace.Fresh(nteil,xcoord_nteil,ycoord_nteil,zcoord_nteil,0,0,m_w,m_z,masse);\n                return;")
    fresh = replace_once(fresh, "            return;\n        }\n\n        [MethodImpl", "            CpuTrace.Fresh(nteil,xcoord_nteil,ycoord_nteil,zcoord_nteil,auszeit,timestep_number,m_w,m_z,masse);\n            return;\n        }\n\n        [MethodImpl")
    (target / "Zeitschleife.cs").write_text(fresh, encoding="utf-8")
    residual = (target / "Zeitschleife_nonsteadystate.cs").read_text(encoding="utf-8-sig")
    residual = replace_once(residual, "            float auszeit = 0;", "            auszeit = 0;")
    residual = replace_once(residual, "            int timestep_number = 0;", "            timestep_number = 0;")
    residual = replace_once(residual, "        private static void ParticleDriver(int i, int j, int k, int SG, float TransConcentration, int splitIndex)\n        {", "        private static void ParticleDriver(int i, int j, int k, int SG, float TransConcentration, int splitIndex)\n        {\n            float auszeit=0;int timestep_number=0;")
    residual = replace_once(residual, "Math.Floor(Math.Floor(masse / Program.ParticleMassMean) / 10) + 1);", "Math.Floor(Math.Floor(masse / Program.ParticleMassMean) / 10) + 1);\n            CpuTrace.AddResidualCount(Math.Max(1,transParticlesSplit));")
    residual = replace_once(residual, "            ResidualSeeds(i, j, k, SG, splitIndex, ref m_w, ref m_z);", "            ResidualSeeds(i, j, k, SG, splitIndex, ref m_w, ref m_z);\n            uint initialW=m_w, initialZ=m_z;")
    call = "CpuTrace.Residual(i,j,k,SG,splitIndex,initialW,initialZ,xcoord_nteil,ycoord_nteil,zcoord_nteil,{elapsed},{steps},m_w,m_z,masse);"
    residual = replace_once(residual, "                return;\n", "                " + call.format(elapsed="0", steps="0") + "\n                return;\n")
    residual = replace_once(residual, "                return; // goto REMOVE_PARTICLE;", "                " + call.format(elapsed="auszeit", steps="0") + "\n                return; // goto REMOVE_PARTICLE;")
    residual = replace_once(residual, "            return;\n        }\n\n        private static ulong MixSeed", "            " + call.format(elapsed="auszeit", steps="timestep_number") + "\n            return;\n        }\n\n        private static ulong MixSeed")
    (target / "Zeitschleife_nonsteadystate.cs").write_text(residual, encoding="utf-8")
    program = (target / "Program.cs").read_text(encoding="utf-8-sig")
    program = replace_once(program, "                        // start the calculation for transient particle from all cells", "                        CpuTrace.Prepare(NTEILMAX);\n                        // start the calculation for transient particle from all cells")
    program = replace_once(program, "                    if (!GpuExperimental.Enabled) { ParallelParticleDriver(1, NTEILMAX + 1); }", "                    if (!GpuExperimental.Enabled) { ParallelParticleDriver(1, NTEILMAX + 1); }\n                    CpuTrace.Save();")
    (target / "Program.cs").write_text(program, encoding="utf-8")
    shutil.copyfile(Path(__file__).with_name("CpuTrace.cs.txt"), target / "CpuTrace.cs")
    hashes = lambda folder: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.cs"))}
    before, after = hashes(source), hashes(target)
    changed = [name for name in before if before[name] != after[name]]
    if sorted(changed) != ["Program.cs", "Zeitschleife.cs", "Zeitschleife_nonsteadystate.cs"]:
        raise ValueError(f"Unexpected instrumentation scope: {changed}")
    return {"status": "prepared", "source": str(source), "target": str(target), "source_sha256": before, "target_sha256": after, "modified": changed,
            "test_only": True, "model_run": False, "residual_counter": "after bounded split planning, before split dispatch"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    report = prepare(root, args.target.resolve())
    output = args.report
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("PREPARED " + report["target"])
