"""Figures for the GRAL PR #77 description (parity, speed, native seeds).

Reads only the frozen analysis outputs listed in SOURCES and writes PNG + SVG
next to this script. Run with the modeling-tools Python (matplotlib 3.11).
"""
import csv
import json
import statistics
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

JOBS = Path(r'<jobs>')
OUT = Path(__file__).resolve().parent
SOURCES = {
    'main_blocks': JOBS / '20261103_gral_gpu_final_validation/analysis/final448_001/fixed_blocks.csv',
    'main_speed': JOBS / '20261103_gral_gpu_final_validation/analysis/final448_001/fixed_timing_speedups.csv',
    'main_runs': JOBS / '20261103_gral_gpu_final_validation/analysis/final448_001/timing_runs.csv',
    'crossover': JOBS / '20261104_gral_gpu_pr_integration/crossover/crossover_report.json',
    'matrix': JOBS / '20261103_gral_gpu_final_validation/planning/proposed_matrix.json',
    'supp': JOBS / '20261104_gral_gpu_supplement56/analysis/out_supp56_001/analysis.json',
    'suite': JOBS / '20261104_gral_gpu_feature_suite/runs/final_eceb2eb/report.json',
    'seeds': JOBS / '20261104_gral_gpu_pr_integration/crossover/hash_check_report.json',
}
INK, MUTED, GRID = '#1f2d3d', '#5b6b7b', '#d9e1e8'
BLUE, ORANGE, GREEN, GREY = '#2f6f9f', '#d9822b', '#3a8f5c', '#9aa5b1'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5, 'axes.edgecolor': GRID,
                     'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': INK,
                     'axes.spines.top': False, 'axes.spines.right': False})


def save(fig, name):
    for ext in ('png', 'svg'):
        fig.savefig(OUT / f'{name}.{ext}', dpi=200 if ext == 'png' else None, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def parity():
    main = [float(r['A_over_B']) for r in csv.DictReader(open(SOURCES['main_blocks'], encoding='utf8'))]
    supp_doc = json.loads(SOURCES['supp'].read_text(encoding='utf8'))
    supp = [b['A_over_B'] for g in supp_doc['scientific_results'] + supp_doc['receptor_results']
            for b in g['fixed_blocks'] if b.get('A_over_B') is not None]
    suite_doc = json.loads(SOURCES['suite'].read_text(encoding='utf8'))
    cases = suite_doc['cases']
    suite, identical = [], 0
    for c in cases.values():
        if c.get('statistical'):
            continue  # native-seed case; A is not a fixed-seed difference
        for v in (c.get('A_over_B') or {}).values():
            if v.get('A_over_B') is None:
                continue
            if v['A_over_B'] == 0:
                identical += 1
            else:
                suite.append(v['A_over_B'])
    n_cases = sum(1 for c in cases.values() if not c.get('statistical'))
    rows = [(f'Main study\n{len(main)} seed blocks', main, BLUE),
            (f'Supplement\n{len(supp)} seed blocks', supp, GREEN),
            (f'Feature suite, final code\n{n_cases} fixed-seed cases', suite, ORANGE)]
    fig, ax = plt.subplots(figsize=(8.6, 3.4))
    rng = np.random.default_rng(7)
    for i, (label, vals, color) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.scatter(vals, y + rng.uniform(-0.18, 0.18, len(vals)), s=13, color=color, alpha=0.55, linewidths=0)
        ax.text(max(vals) * 1.6, y, f'max {max(vals):.1e}', va='center', color=MUTED, fontsize=9)
    ax.axvline(1, color='#b23b3b', lw=1.6)
    ax.text(0.85, 2.48, 'A/B = 1: CPU seed-to-seed noise', color='#b23b3b', ha='right', va='center', fontsize=9.5)
    ax.axvspan(1, 10, color='#f6e3e3', zorder=0)
    ax.set_xscale('log')
    ax.set_xlim(1e-6, 10)
    ax.set_ylim(-0.6, 2.7)
    ax.set_yticks(range(len(rows)), [r[0] for r in reversed(rows)])
    ax.set_xlabel('A / B   (CPU-GPU difference, same seed  ÷  CPU-CPU difference, two seeds)')
    ax.grid(axis='x', color=GRID, lw=0.6)
    ax.set_title('Fixed-seed GPU output stays far inside CPU run-to-run noise', loc='left', color=INK, fontsize=12, pad=10)
    if identical:
        ax.text(1.2e-6, -0.48, f'{identical} further outputs with A = 0 (zero on both backends or CPU fallback) are not plotted',
                color=MUTED, fontsize=8.5)
    save(fig, 'pr77_parity')
    return {'main_max': max(main), 'main_n': len(main), 'supp_max': max(supp), 'supp_n': len(supp),
            'suite_max': max(suite), 'suite_n': len(suite), 'suite_identical': identical}


def speed():
    matrix = json.loads(SOURCES['matrix'].read_text(encoding='utf8'))
    labels = {
        'B00': 'reference (10 m grid, 360k particles/h)', 'C01': '5 m concentration grid', 'F02': '25 m flow grid',
        'P03': '90k particles/h', 'P04': '1.44M particles/h', 'W05': 'low wind, stable', 'W06': 'higher wind, unstable',
        'T07': 'flat terrain', 'S08': 'area sources', 'S09': 'line sources', 'S10': 'point sources',
        'S11': 'portal sources', 'D12': '48 hours', 'R13': 'CUDA block 256', 'I14': '5 m grid + 1.44M particles/h',
        'I15': '25 m flow grid + flat terrain'}
    assert set(labels) == {c['id'] for c in matrix['configurations']}
    # Contention: other jobs shared the machine. A pair counts as contended when its CPU or GPU time is more
    # than 1.5x the fastest run of that backend among the configuration's 14 runs.
    fastest = {}
    for r in csv.DictReader(open(SOURCES['main_runs'], encoding='utf8')):
        key = (r['configuration'], r['backend'])
        v = float(r['process_start_to_exit_s'])
        fastest[key] = min(fastest.get(key, v), v)
    clean, busy = {}, {}
    for r in csv.DictReader(open(SOURCES['main_speed'], encoding='utf8')):
        if r['boundary'] == 'process_start_to_exit_s':
            c = r['configuration']
            slowed = float(r['cpu_s']) > 1.5 * fastest[(c, 'cpu')] or float(r['gpu_s']) > 1.5 * fastest[(c, 'gpu')]
            target = busy if slowed else clean
            target.setdefault(r['configuration'], []).append(float(r['speedup_cpu_over_gpu']))
    order = sorted(clean, key=lambda k: statistics.median(clean[k]))
    fig, ax = plt.subplots(figsize=(8.6, 5.8))
    y = np.arange(len(order))
    ax.barh(y, [statistics.median(clean[k]) for k in order], color=BLUE, height=0.62, label='median, uncontended pairs')
    for yi, k in zip(y, order):
        ax.scatter(clean[k], np.full(len(clean[k]), yi), s=16, color=INK, zorder=3)
        if k in busy:
            ax.scatter(busy[k], np.full(len(busy[k]), yi), s=22, facecolors='none', edgecolors=ORANGE, zorder=3)
        ax.text(0.12, yi, f'{statistics.median(clean[k]):.1f}x', va='center', ha='left', fontsize=9, color='white',
                fontweight='bold', zorder=4)
    ax.scatter([], [], s=16, color=INK, label='uncontended pair')
    ax.scatter([], [], s=22, facecolors='none', edgecolors=ORANGE, label='pair slowed by other jobs')
    ax.set_yticks(y, [f'{k}  {labels[k]}' for k in order], fontsize=9.5)
    ax.axvline(1, color=GREY, lw=1, ls='--')
    ax.text(1.05, len(order) - 0.4, '1x', color=MUTED, fontsize=8.5)
    ax.set_xlabel('CPU time / GPU time, process start to exit')
    ax.grid(axis='x', color=GRID, lw=0.6)
    ax.legend(loc='lower right', fontsize=8.5, frameon=True, facecolor='white', edgecolor=GRID)
    cv = [v for vs in clean.values() for v in vs]
    bv = [v for vs in busy.values() for v in vs]
    ax.set_title(f'GPU speedup: RTX 5080 vs 16 threads (8 cores) of a Ryzen 9 9950X3D\n'
                 f'median {statistics.median(cv):.1f}x over {len(cv)} uncontended pairs', loc='left', color=INK,
                 fontsize=12, pad=10)
    save(fig, 'pr77_speed')
    return {'clean_median': statistics.median(cv), 'clean_n': len(cv), 'clean_min': min(cv), 'clean_max': max(cv),
            'busy_median': statistics.median(bv), 'busy_n': len(bv), 'all_median': statistics.median(cv + bv),
            'clean_per_config': {k: statistics.median(v) for k, v in clean.items()}}


def seeds():
    doc = json.loads(SOURCES['seeds'].read_text(encoding='utf8'))
    cross = json.loads(SOURCES['crossover'].read_text(encoding='utf8'))['configs']
    groups = [('cpu_native', 'CPU', BLUE), ('cpu_ctrl', 'CPU\nrepeat', '#6b9ac4'),
              ('cpu_gpustyle', 'CPU,\nold GPU\nseeding', '#8c6bb1'),
              ('gpu_native_old', 'GPU\nbefore', ORANGE), ('gpu_hash', 'GPU\nnow', GREEN)]
    configs = [c for c in ('B00', 'W05', 'true_flat') if c in doc]
    fig, axes = plt.subplots(1, len(configs), figsize=(9.4, 3.6), sharey=True)
    out = {}
    for ax, c in zip(np.atleast_1d(axes), configs):
        d = dict(doc[c]['layer1_aggregate'])
        assert cross[c]['layer1_aggregate']['cpu_native']['maximum'] == d['cpu_native']['maximum']
        d['cpu_gpustyle'] = cross[c]['layer1_aggregate']['cpu_gpustyle']
        ref = statistics.mean(d['cpu_native']['maximum'])
        for i, (key, label, color) in enumerate(groups):
            vals = [v / ref for v in d[key]['maximum']]
            ax.scatter(np.full(len(vals), i) + np.linspace(-0.12, 0.12, len(vals)), vals, s=22, color=color, zorder=3)
            out.setdefault(c, {})[key] = [round(v, 4) for v in vals]
        ax.axhline(1, color=GREY, lw=0.8, ls='--')
        ax.set_xticks(range(len(groups)), [g[1] for g in groups], fontsize=8.3)
        ax.set_title({'B00': 'B00 reference', 'W05': 'W05 low wind', 'true_flat': 'flat, constant emission'}[c],
                     fontsize=10, color=INK)
        ax.grid(axis='y', color=GRID, lw=0.6)
    np.atleast_1d(axes)[0].set_ylabel('run maximum ÷ mean of the\n6 CPU run maxima')
    fig.suptitle('Native seeds, run maxima of 6 runs each. Old GPU seeding: master + particle number; GPU now: hashed',
                 x=0.01, ha='left', color=INK, fontsize=11)
    fig.tight_layout()
    save(fig, 'pr77_native_seeds')
    return out


if __name__ == '__main__':
    summary = {'parity': parity(), 'speed': speed(), 'seeds': seeds(),
               'sources': {k: v.relative_to(JOBS).as_posix() for k, v in SOURCES.items()}}
    (OUT / 'figure_numbers.json').write_text(json.dumps(summary, indent=1), encoding='utf8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'seeds'}, indent=1)[:2500])
