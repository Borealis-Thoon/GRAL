"""Summarize perf2/results.json into PERF_RESULTS.json (kernel sums, ratios vs same-session baseline and stored RTX 5080 runs)."""
import json
from pathlib import Path

P2 = Path(__file__).resolve().parent
FV = Path(r'<jobs>\20261103_gral_gpu_final_validation\runs\final448_001\targets')
res = json.loads((P2 / 'results.json').read_text(encoding='utf8'))


def cuda(case):
    m = [json.loads(l) for l in open(FV / f'{case}_fixed00_gpu' / 'logs' / 'gpu_metrics.jsonl', encoding='utf8')]
    return {'fresh_kernel_s': round(sum(x['fresh_kernel_ms'] for x in m) / 1000, 3),
            'residual_kernel_s': round(sum(x.get('residual_kernel_ms') or 0 for x in m) / 1000, 3),
            'elapsed_s': round(sum(x['elapsed_s'] for x in m), 3)}


out = {'note': 'kernel times are GPU-event sums over 24 situations (fixed seed 00); RTX 5080 values are the stored 2026-11-03 study runs; '
               '7-Zip archiving ran on CPUs during this session, so elapsed/wall values are indicative',
       'variants': {k: {kk: v[kk] for kk in ('case', 'build', 'overrides', 'fresh_kernel_s', 'residual_kernel_s', 'elapsed_s', 'wall_s',
                                              'nmae_vs_cpu', 'identity_vs_reference', 'resources') if kk in v} for k, v in res.items()},
       'before_after': {}}
for case, before, after in (('B00', 'ref_B00', 'perf2_B00'), ('I14', 'ref_I14', 'perf2_I14'), ('P04', 'ref_P04', 'perf2_P04')):
    b, a, c = res[before], res[after], cuda(case)
    out['before_after'][case] = {
        'before': {k: b[k] for k in ('fresh_kernel_s', 'residual_kernel_s', 'elapsed_s', 'nmae_vs_cpu')},
        'after': {k: a[k] for k in ('fresh_kernel_s', 'residual_kernel_s', 'elapsed_s', 'nmae_vs_cpu')},
        'rtx5080': c,
        'speedup_fresh': round(b['fresh_kernel_s'] / a['fresh_kernel_s'], 2),
        'speedup_elapsed': round(b['elapsed_s'] / a['elapsed_s'], 2),
        'hip_over_cuda_fresh_before': round(b['fresh_kernel_s'] / c['fresh_kernel_s'], 2),
        'hip_over_cuda_fresh_after': round(a['fresh_kernel_s'] / c['fresh_kernel_s'], 2),
        'hip_over_cuda_kernel_after': round((a['fresh_kernel_s'] + a['residual_kernel_s']) / (c['fresh_kernel_s'] + c['residual_kernel_s']), 2),
        'hip_over_cuda_elapsed_after': round(a['elapsed_s'] / c['elapsed_s'], 2)}
(P2 / 'PERF_RESULTS.json').write_text(json.dumps(out, indent=1), encoding='utf8')
print(json.dumps(out['before_after'], indent=1))
