"""Baseline differences between frozen study outputs, to put the HIP result in scale.

Pairs: CPU fixed00 vs CUDA fixed00 (same seed, CPU vs GPU), CPU fixed00 vs CPU fixed01 (seed noise),
CUDA fixed00 vs CUDA fixed01 (GPU seed noise), and any extra pairs given as name pairs on the command line.
"""
import json, sys
from pathlib import Path

FV = Path(r'<jobs>\20261103_gral_gpu_final_validation')
sys.path.insert(0, str(FV / 'validation'))
import compare  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from smoke_hip import summary  # noqa: E402

T = FV / 'runs/final448_001/targets'


def run(a, b):
    man = json.loads((T / a / 'input_manifest.json').read_text(encoding='utf8'))
    cfg = man['config']; groups = tuple(man.get('source_groups', (1, 2, 3)))
    pa = Path(a) if Path(a).is_absolute() else T / a / 'Computation'
    pb = Path(b) if Path(b).is_absolute() else T / b / 'Computation'
    cmp = compare.compare_outputs(pa, pb, hours=man['hours'], expected_groups=groups, deposition=cfg.get('deposition', False),
                                  required_receptors=('Receptor_Timeseries_Transient.txt',) if cfg.get('receptors') else (),
                                  expected_receptor_columns=cfg['receptors'] * len(groups) if cfg.get('receptors') else None)
    s = summary(cmp)
    return {k: s[k] for k in ('members_identical', 'members', 'con_nmae_pooled', 'con_nmae_max_hour', 'con_bias_pooled', 'con_jaccard_min_hour')}


pairs = [('B00_fixed00_cpu', 'B00_fixed00_gpu'), ('B00_fixed00_cpu', 'B00_fixed01_cpu'), ('B00_fixed00_gpu', 'B00_fixed01_gpu')]
for a, b in pairs:
    print(a, 'vs', b, json.dumps(run(a, b)))
