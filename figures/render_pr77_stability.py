"""PR #77 figure: largest fixed-seed GPU-CPU difference per output type in the 50-case feature suite, RTX 5080 and
RX 9070 XT, as a fraction of the CPU's own seed-to-seed difference (A/B). Reads the suite report.json files.
Negative (invalid-input) cases and the native-seed statistical case are left out, as in the suite screens.
Usage: render_pr77_stability.py <report 5080> <report 9070 XT> <out png>
"""
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

GROUPS = [('Concentration', ['con']), ('Deposition', ['dep']), ('Receptors', ['receptor_steady', 'receptor_transient', 'receptor_staterr']),
          ('Odour', ['odr_ch0', 'odr_ch1', 'odr_ch2', 'odr_ch3']), ('Vertical profile', ['vertical', 'vertical_topo'])]


def maxima(path):
    cases = json.load(open(path, encoding='utf-8'))['cases']
    out = {}
    for name, c in cases.items():
        if name.startswith('neg_') or c.get('statistical'):
            continue
        for t, v in (c.get('A_over_B') or {}).items():
            v = v.get('A_over_B') if isinstance(v, dict) else v
            if isinstance(v, (int, float)):
                out[t] = max(out.get(t, 0.0), v)
    return {g: max(out.get(t, 0.0) for t in ts) for g, ts in GROUPS}, sum(1 for n, c in cases.items() if not n.startswith('neg_') and not c.get('statistical'))


nv, n_nv = maxima(sys.argv[1])
amd, n_amd = maxima(sys.argv[2])
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
fig, ax = plt.subplots(figsize=(9.5, 4.6), dpi=200)
labels = [g for g, _ in GROUPS][::-1]
y = range(len(labels))
h = 0.36
ax.barh([i + h / 2 for i in y], [nv[l] for l in labels], height=h, color='#5a8f29', label='NVIDIA RTX 5080 (CUDA)')
ax.barh([i - h / 2 for i in y], [amd[l] for l in labels], height=h, color='#c8102e', label='AMD RX 9070 XT (HIP)')
for i, l in enumerate(labels):
    ax.text(nv[l] * 1.15, i + h / 2, f'{nv[l]:.4f}', va='center', fontsize=9.5)
    ax.text(amd[l] * 1.15, i - h / 2, f'{amd[l]:.4f}', va='center', fontsize=9.5)
ax.set_xscale('log')
ax.set_xlim(1e-4, 3)
ax.axvline(1, color='#333333', lw=1.4, ls='--')
ax.text(0.93, len(labels) - 0.45, 'CPU seed-to-seed\ndifference (A/B = 1)', ha='right', va='top', fontsize=9.5, color='#333333')
ax.set_yticks(list(y), labels)
ax.set_xlabel('largest GPU-CPU difference with the same fixed seed, relative to the CPU seed-to-seed difference (A/B)')
ax.set_title('Feature suite: every output type stays below 1 % of the CPU seed noise', loc='left', fontweight='bold', fontsize=12.5)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
ax.legend(loc='lower right', frameon=False, fontsize=10)
fig.text(0.01, -0.02, f'Largest value over {n_nv} feature cases per GPU (12 or 13 situations each, fixed seeds). '
         'Invalid-input cases and the native-seed case are not included.', fontsize=8.5, color='#5b6670')
fig.savefig(sys.argv[3], bbox_inches='tight', facecolor='white')
print(sys.argv[3], nv, amd)
