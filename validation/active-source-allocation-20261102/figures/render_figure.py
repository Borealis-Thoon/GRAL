from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def parse(path, patched):
    raw = path.read_bytes()
    text = raw.decode('utf-8-sig')
    assert re.search(r'Number of weather situations:\s*24', text)
    factors = re.findall(r'Source group:\s*(\d+) Mean emission factor:\s*([\d.]+)', text)
    assert factors == [('1', '3'), ('2', '0'), ('3', '0')]
    assert 'Total emission [kg/h]: 3.000 (  SG 1[kg/h]: 1.000  SG 2[kg/h]: 1.000  SG 3[kg/h]: 1.000 )' in text
    initial = text.split('Transient GRAL mode.', 1)[0]
    initial_values = [int(v) for _, v in re.findall(r'PS\s+(\d+)\s*:\s*(\d+)', initial)]
    assert initial_values == [36, 36, 36]
    blocks = re.split(r'Weather number:\s*(\d+)', text)
    situations = {int(blocks[i]): blocks[i + 1] for i in range(1, len(blocks), 2)}
    assert all(hour in situations for hour in range(1, 25))
    values = initial_values
    if patched:
        for hour in range(1, 25):
            allocation = re.findall(r'PS\s+(\d+)\s*:\s*(\d+)', situations[hour])
            assert allocation == [('1', '108')]
            assert 'Using a total of 108 particles' in situations[hour]
        values = [108, 0, 0]
    assert re.search(r'Summarized emission rates per source group in kg\s+SG:.*?\n\s*7\.20e\+001\s+0\.00e\+000\s+0\.00e\+000', text, re.S)
    return values, hashlib.sha256(raw).hexdigest()


def main():
    if not __debug__:
        raise RuntimeError('Run without -O so that the log validation checks remain enabled.')
    parser = argparse.ArgumentParser(description='Render the sparse-source allocation example from GRAL logs.')
    parser.add_argument('--baseline-log', required=True, type=Path)
    parser.add_argument('--patched-log', required=True, type=Path)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    logs = {'Baseline': args.baseline_log, 'Patched': args.patched_log}
    values, hashes = {}, {}
    for name, path in logs.items():
        values[name], hashes[name] = parse(path, name == 'Patched')
    assert values == {'Baseline': [36, 36, 36], 'Patched': [108, 0, 0]}
    rows = [{'scenario': name, 'source_group': group, 'allocated_particles': value,
             'emission_factor': [3, 0, 0][group - 1]}
            for name, entries in values.items() for group, value in enumerate(entries, 1)]
    with (out / 'allocation_data.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    data = {'description': 'Allocation per hourly situation for equal-base point sources',
            'weather_situations': 24, 'particle_budget_per_hour': 108,
            'base_emission_kg_per_hour_each': [1, 1, 1], 'emission_factors': [3, 0, 0],
            'total_emission_kg_over_24_hours': [72, 0, 0],
            'allocation': values, 'source_logs': {k: v.name for k, v in logs.items()},
            'source_sha256': hashes,
            'interpretation': 'Baseline uses initial allocation; patched allocation is logged for every hourly situation.'}
    (out / 'allocation_data.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

    with plt.rc_context({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none',
                         'font.size': 12, 'axes.edgecolor': '#777777'}):
        fig, ax = plt.subplots(figsize=(10, 4.5), facecolor='white')
        fig.subplots_adjust(left=.19, right=.96, top=.70, bottom=.25)
        fig.text(.08, .91, 'Particle allocation with one active source group',
                 fontsize=18, fontweight='bold', color='#172b3a')
        fig.text(.08, .82, '24 hourly situations  |  Factors: SG 1 = 3, SG 2 = 0, SG 3 = 0',
                 fontsize=12, color='#405360')
        for y, name in [(1, 'Baseline'), (0, 'Patched')]:
            left = 0
            for i, width in enumerate(values[name]):
                if not width:
                    continue
                ax.barh(y, width, left=left, height=.53,
                        color='#17689a' if i == 0 else '#e2e7ea',
                        edgecolor='#ffffff' if i == 0 else '#687985',
                        hatch=None if i == 0 else ('///' if i == 1 else '\\\\\\'), linewidth=1)
                ax.text(left + width / 2, y, f'SG {i + 1}: {width}', ha='center', va='center',
                        color='white' if i == 0 else '#172b3a', fontsize=12, fontweight='bold',
                        bbox={'facecolor': '#17689a' if i == 0 else '#e2e7ea', 'edgecolor': 'none', 'pad': 2})
                left += width
        ax.set_yticks([1, 0], ['Baseline', 'Patched'], fontweight='bold')
        ax.set_xlim(0, 108)
        ax.set_xticks([0, 36, 72, 108])
        ax.set_xlabel('Allocated particles per hour', labelpad=8)
        ax.tick_params(axis='y', length=0, pad=12)
        ax.tick_params(axis='x', colors='#405360')
        for side in ('top', 'right', 'left'):
            ax.spines[side].set_visible(False)
        fig.text(.08, .075, 'Allocation example, not a runtime comparison.  Total emissions: 3 kg/h in both runs.',
                 fontsize=10.5, color='#405360')
        for ext in ('png', 'svg'):
            fig.savefig(out / f'particle_allocation.{ext}', dpi=200, facecolor='white')
        plt.close(fig)
    qa = {'python': sys.version, 'matplotlib': matplotlib.__version__, 'command': f'"{sys.executable}" "{Path(__file__)}"',
          'status': 'pass', 'checks': ['Both logs contain 24 weather situations and factors 3,0,0',
          'Baseline initial allocation is 36,36,36', 'Patched logs 108 for SG 1 in each of 24 situations',
          'Each log reports 72,0,0 kg over 24 hours', 'SVG and PNG created'],
          'alt_text': 'Two stacked bars each total 108 particles per hour. Baseline allocates 36 each to source groups 1, 2 and 3; patched allocates all 108 to active source group 1. Emissions total 3 kg per hour in both runs.'}
    (out / 'qa.json').write_text(json.dumps(qa, indent=2) + '\n', encoding='utf-8')
    print('PASS: extracted data and rendered PNG/SVG')


if __name__ == '__main__':
    main()
