"""Figure for the #77 reply of 16 Nov 2026: Markus's Boiler project (4 GRAMM situations) on the RX 9070 XT.

Horizontal bars: sum of the "Dispersion [s]" lines of the 4 situations for each run, read from
evidence/summary.json (written by tools/summarize.py from the run folders). Writes the PNG and a JSON with the
plotted numbers next to this script. Run with a Python that has Matplotlib.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

JOB = Path(r'<job folder>')
OUT = Path(__file__).resolve().parent
NAME = 'pr77_boiler_rx9070xt'
ORDER = [  # run folder, label, colour key
    ('cpu', 'CPU, 8 threads', 'cpu'),
    ('gpu_budget_1650', 'GPU, VK and WK in host memory\n(budget of the GTX 1650 run)', 'host'),
    ('gpu_general', 'GPU, all arrays in GPU memory,\ngeneral kernel only', 'gen'),
    ('gpu_budget_wk', 'GPU, WK in host memory', 'host'),
    ('gpu', 'GPU, all arrays in GPU memory', 'gpu'),
]
INK, MUTED, GRID = '#1f2d3d', '#5b6b7b', '#d9e1e8'
COLOUR = {'cpu': '#8a96a3', 'host': '#d9822b', 'gen': '#7fa7c9', 'gpu': '#2f6f9f'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': INK,
                     'axes.spines.top': False, 'axes.spines.right': False})


def main():
    rows = {r['run']: r for r in json.loads((JOB / 'evidence/summary.json').read_text(encoding='utf8'))}
    vals = [rows[k]['dispersion_sum'] for k, _, _ in ORDER]
    assert all(rows[k]['situations'] == 4 and rows[k]['rc'] == 0 for k, _, _ in ORDER)
    fig, ax = plt.subplots(figsize=(8.8, 3.9), dpi=200)
    y = range(len(ORDER))
    ax.barh(list(y), vals, color=[COLOUR[c] for _, _, c in ORDER], height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + 6, i, f'{v:.1f} s', va='center', color=INK, fontsize=10)
    ax.set_yticks(list(y))
    ax.set_yticklabels([lab for _, lab, _ in ORDER])
    ax.set_xlabel('dispersion time, sum of 4 weather situations [s]')
    ax.set_xlim(0, max(vals) * 1.15)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.suptitle('Boiler project (4 GRAMM situations, 1.8 million particles each), RX 9070 XT, Windows',
                 x=0.01, ha='left', fontsize=11.5, color=INK)
    fig.tight_layout()
    fig.savefig(OUT / f'{NAME}.png', facecolor='white')
    (OUT / f'{NAME}.json').write_text(json.dumps({k: rows[k]['dispersion_sum'] for k, _, _ in ORDER}, indent=1), encoding='utf8')
    print('ok', vals)


main()
