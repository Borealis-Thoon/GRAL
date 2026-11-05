"""Precision figure for the GRAL PR #77 description (single-precision trial on B00).

Reads ../pinvoke/precision/compare.json and runs.jsonl (paths relative to this script) and writes
pr77_precision.png/.svg plus the plotted values in precision_numbers.json next to this script.
Run with matplotlib 3.x.
"""
import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / 'pinvoke' / 'precision'
INK, MUTED, GRID = '#1f2d3d', '#5b6b7b', '#d9e1e8'
BLUE, ORANGE, GREY = '#2f6f9f', '#d9822b', '#9aa5b1'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': MUTED,
                     'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none'})

comp = json.loads((DATA / 'compare.json').read_text(encoding='utf-8'))
runs = {json.loads(l)['run']: json.loads(l) for l in (DATA / 'runs.jsonl').read_text(encoding='utf-8').splitlines() if l}
# Current kernel = D2 (double, with the float cs_cast overload); its output equals D byte for byte.
VARIANTS = [('D2', 'double\n(current kernel)'), ('M2', 'mixed\n(positions double)'), ('F2', 'float\n(trajectory scalars)')]
rel = {v: (comp[f'B00:{v} vs cpu']['relative'], comp[f'B00s:{v} vs cpu']['relative']) for v, _ in VARIANTS}
kernel = {v: statistics.mean([runs[f'r_B00_{v}']['kernel_device_s'], runs[f'r_B00s_{v}']['kernel_device_s']]) for v, _ in VARIANTS}
noise_shifted = comp['B00s noise: native cpu vs cpu']['relative']
# Seed noise at the origin: CPU fixed-seed pairs 00-01, 00-02, 01-02 of the main study (see README).
noise_origin = statistics.mean([0.15411701157744656, 0.1532273360505262, 0.15450145054758296])

fig, ax = plt.subplots(figsize=(9.6, 5.2))
x = range(len(VARIANTS))
w = 0.36
b1 = ax.bar([i - w / 2 for i in x], [rel[v][0] for v, _ in VARIANTS], w, color=GREY, label='case at the origin (0-2 km)')
b2 = ax.bar([i + w / 2 for i in x], [rel[v][1] for v, _ in VARIANTS], w, color=BLUE, label='same case moved to x+150 km, y+430 km')
for bars in (b1, b2):
    for bar in bars:
        ax.annotate(f'{bar.get_height():.4f}', (bar.get_x() + bar.get_width() / 2, bar.get_height()), xytext=(0, 3),
                    textcoords='offset points', ha='center', fontsize=9, color=INK)
ax.axhline(noise_origin, color=GREY, ls='--', lw=1.2)
ax.axhline(noise_shifted, color=BLUE, ls='--', lw=1.2)
tr = ax.get_yaxis_transform()
ax.text(0.995, noise_shifted, f'CPU seed noise, moved case {noise_shifted:.3f}', transform=tr, va='bottom', ha='right', fontsize=9, color=BLUE)
ax.text(0.995, noise_origin, f'CPU seed noise, origin {noise_origin:.3f}', transform=tr, va='top', ha='right', fontsize=9, color=MUTED)
ax.set_yscale('log')
ax.set_ylim(0.002, 0.4)
ax.set_xticks(list(x), [f'{label}\nkernel {kernel[v]:.1f} s' for v, label in VARIANTS])
ax.set_ylabel('relative difference from the CPU run\n(sum |GPU - CPU| / sum |CPU|, same fixed seed)')
ax.grid(axis='y', color=GRID, which='both', lw=0.6)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc='upper left', fontsize=9.5)
ax.set_title('Single-precision trial, B00 (24 h), RTX 5080', loc='left', weight='bold', color=INK, pad=12)
fig.text(0.01, 0.005, 'Kernel: mean GPU kernel time of the two cases at 4,096 particles per launch (the earlier default).\n'
         'State fields, the double output accumulators, the step-limit line and the random-number conversions are unchanged in every variant.', fontsize=8.5, color=MUTED)
fig.tight_layout(rect=(0, 0.06, 1, 1))
for ext in ('png', 'svg'):
    fig.savefig(HERE / f'pr77_precision.{ext}', dpi=200 if ext == 'png' else None, bbox_inches='tight', facecolor='white')
plt.close(fig)
numbers = {'relative_vs_cpu': {v: {'origin': rel[v][0], 'shifted': rel[v][1]} for v, _ in VARIANTS},
           'kernel_s_mean_of_cases': kernel, 'noise_origin': noise_origin, 'noise_shifted': noise_shifted}
(HERE / 'precision_numbers.json').write_text(json.dumps(numbers, indent=1), encoding='utf-8')
print(json.dumps(numbers))
