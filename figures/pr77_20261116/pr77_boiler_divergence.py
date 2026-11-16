"""Figure for the #77 reply of 16 Nov 2026: how far apart two runs of the Boiler project end up, per situation.

Grouped bars, one group per weather situation: sum of absolute cell differences of the 2 m concentration over the
sum of the first run (NMAE), for
  - random seeds, GPU against GPU (seed noise),
  - fixed seeds, CPU against CPU with the source moved 1 cm,
  - fixed seeds, CPU against GPU,
  - fixed seeds, CPU against GPU without plume rise (exit velocity 0).
Numbers are recomputed here from the .grz files of the run folders (same decoding as tools/diff_detail.py).
"""
import json
import struct
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

JOB = Path(r'<job folder>')
OUT = Path(__file__).resolve().parent
NAME = 'pr77_boiler_divergence'
PAIRS = [
    ('gpu', 'gpu_repeat', 'random seeds: GPU against GPU (seed noise)', '#8a96a3'),
    ('cpu_fixed', 'cpu_fixed_pert', 'fixed seeds: CPU against CPU, source moved 1 cm', '#d9822b'),
    ('cpu_fixed', 'gpu_fixed', 'fixed seeds: CPU against GPU', '#2f6f9f'),
    ('cpu_fixed_nopr', 'gpu_fixed_nopr', 'fixed seeds: CPU against GPU, no plume rise', '#7fa7c9'),
]
INK, MUTED, GRID = '#1f2d3d', '#5b6b7b', '#d9e1e8'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': MUTED,
                     'axes.spines.top': False, 'axes.spines.right': False})


def load(run, sit):
    with zipfile.ZipFile(JOB / 'runs' / run / 'Computation' / f'{sit:05d}.grz') as z:
        name = [n for n in z.namelist() if n.endswith('.con')][0]
        p = z.read(name)
    assert struct.unpack_from('<i', p)[0] == -1
    rec = np.frombuffer(p, dtype=np.dtype([('x', '<i4'), ('y', '<i4'), ('v', '<f4')]), offset=4)
    return {(int(x), int(y)): float(v) for x, y, v in rec}


def nmae(a, b):
    keys = set(a) | set(b)
    va = np.array([a.get(k, 0.0) for k in keys])
    vb = np.array([b.get(k, 0.0) for k in keys])
    return float(np.abs(va - vb).sum() / va.sum())


def main():
    vals = {f'{a} vs {b}': [nmae(load(a, s), load(b, s)) for s in range(1, 5)] for a, b, _, _ in PAIRS}
    fig, ax = plt.subplots(figsize=(8.8, 4.2), dpi=200)
    w = 0.2
    x = np.arange(4)
    for i, (a, b, lab, col) in enumerate(PAIRS):
        v = vals[f'{a} vs {b}']
        bars = ax.bar(x + (i - 1.5) * w, v, w, color=col, label=lab)
        for bx, bv in zip(bars, v):
            ax.text(bx.get_x() + bx.get_width() / 2, bv + 0.01, f'{bv:.2f}', ha='center', va='bottom', fontsize=8.2, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels([f'situation {s}' for s in range(1, 5)])
    ax.set_ylabel('sum |difference| / sum of first run')
    ax.set_ylim(0, 0.85)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc='upper left', frameon=False, fontsize=9.2)
    fig.suptitle('Boiler project, 2 m concentration: difference between two runs (RX 9070 XT, Windows)',
                 x=0.01, ha='left', fontsize=11.5, color=INK)
    fig.tight_layout()
    fig.savefig(OUT / f'{NAME}.png', facecolor='white')
    (OUT / f'{NAME}.json').write_text(json.dumps(vals, indent=1), encoding='utf8')
    print(json.dumps({k: [round(x, 4) for x in v] for k, v in vals.items()}))


main()
