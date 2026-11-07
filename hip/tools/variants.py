"""B00 kernel-time comparison of launch and code-generation variants on the RX 9070 XT (GPU event times).

Kernel device time comes from gpu_metrics.jsonl (kernel_total_ms per situation), so CPU load from 7-Zip affects it
little; wall time is reported but not used. Every variant is also checked against the frozen CPU output (NMAE).
Usage: variants.py <build> <out json>
"""
import json, os, subprocess, sys
from pathlib import Path

JOB = Path(__file__).resolve().parent
PY = r'<user>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
build, out = sys.argv[1], Path(sys.argv[2])
VARIANTS = [("base_b128", {}), ("block64", {"SMOKE_INU_GRAL_GPU_BLOCK": "64"}), ("block256", {"SMOKE_INU_GRAL_GPU_BLOCK": "256"}),
            ("cumode", {"SMOKE_INU_GPU_HIPRTC_EXTRA": "-mcumode"}), ("wave64", {"SMOKE_INU_GPU_HIPRTC_EXTRA": "-mwavefrontsize64"}),
            ("base_b128_repeat", {})]
res = json.loads(out.read_text(encoding='utf8')) if out.exists() else {}
for name, extra in VARIANTS:
    if name in res:
        continue
    label = f'var_{name}_{Path(build).name}'
    env = {k: v for k, v in os.environ.items() if not k.startswith('SMOKE_')}
    env.update(extra)
    subprocess.run([PY, '-X', 'utf8', '-B', str(JOB / 'smoke_hip.py'), 'gpu', label, build, 'B00_fixed00'], env=env,
                   capture_output=True, text=True, encoding='utf8', errors='replace')
    tgt = JOB / 'smoke' / label
    s = json.loads((tgt / 'smoke_result.json').read_text(encoding='utf8')) if (tgt / 'smoke_result.json').exists() else {}
    mets = [json.loads(l) for l in open(tgt / 'logs' / 'gpu_metrics.jsonl', encoding='utf8')] if (tgt / 'logs' / 'gpu_metrics.jsonl').exists() else []
    res[name] = {'rc': s.get('rc'), 'wall_s': s.get('wall_s'), 'fallback': s.get('gpu_fallback_lines'),
                 'kernel_total_ms': round(sum(m.get('kernel_total_ms') or 0 for m in mets), 1),
                 'fresh_kernel_ms': round(sum(m.get('fresh_kernel_ms') or 0 for m in mets), 1),
                 'residual_kernel_ms': round(sum(m.get('residual_kernel_ms') or 0 for m in mets), 1),
                 'block': mets[0].get('block') if mets else None,
                 'resources': (mets[0].get('result_server_metrics') or {}).get('kernel_resources') if mets else None,
                 'nmae_vs_cpu': (s.get('vs_frozen_cpu') or {}).get('con_nmae_pooled')}
    out.write_text(json.dumps(res, indent=1), encoding='utf8')
    print(name, json.dumps(res[name]), flush=True)
