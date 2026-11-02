"""Generate constant synthetic GRAL inputs; no user data or absolute paths."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from geometry_fixture import validate_geometry, write_geometry


CASES = {
    'area': {'sources': 'area', 'dispatch': 'gpu'},
    'area_receptor1': {'sources': 'area', 'dispatch': 'gpu', 'receptors': 1},
    'line_horizontal': {'sources': 'line_horizontal', 'dispatch': 'gpu'},
    'line_vertical': {'sources': 'line_vertical', 'dispatch': 'gpu'},
    'area_line_switch': {'sources': 'area_line', 'dispatch': 'gpu', 'switch': True},
    'supported_primary': {'sources': 'supported_primary', 'dispatch': 'gpu'},
    'transient_all_sources': {'sources': 'all_sources', 'dispatch': 'gpu'},
    'steady_all_sources': {'sources': 'all_sources', 'dispatch': 'gpu', 'steady': True},
    'steady_area': {'sources': 'area', 'dispatch': 'gpu', 'steady': True},
    'steady_line': {'sources': 'line_horizontal', 'dispatch': 'gpu', 'steady': True},
    'steady_point': {'sources': 'point', 'dispatch': 'gpu', 'steady': True},
    'steady_portal': {'sources': 'portal', 'dispatch': 'gpu', 'steady': True},
    'point': {'sources': 'point', 'dispatch': 'gpu'},
    'point_buoyant': {'sources': 'point_buoyant', 'dispatch': 'gpu'},
    'point_cold_momentum': {'sources': 'point_cold_momentum', 'dispatch': 'gpu'},
    'point_portal_timeseries': {'sources': 'point_portal_timeseries', 'dispatch': 'gpu', 'source_series': True},
    'portal': {'sources': 'portal', 'dispatch': 'gpu'},
    'mixed_point_area': {'sources': 'mixed_point_area', 'dispatch': 'gpu'},
    'dry_deposition': {'sources': 'area', 'dispatch': 'fallback', 'deposition': True},
    'decay': {'sources': 'area', 'dispatch': 'fallback', 'decay': True},
    'buildings': {'sources': 'area', 'dispatch': 'fallback', 'buildings': True},
    'flat': {'sources': 'area', 'dispatch': 'fallback', 'flat': True},
    'receptors51': {'sources': 'area', 'dispatch': 'fallback', 'receptors': 51},
    'nonfixed_seed': {'sources': 'area', 'dispatch': 'fallback', 'nonfixed_seed': True},
}
GRID = dict(nx=24, ny=20, nz=16, dx_m=250, dy_m=250, first_dz_m=20.,
            vertical_stretch=1.3, terrain_height_m=0., west_m=0, south_m=0)


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def input_hashes(root: Path) -> dict:
    return {str(p.relative_to(root)).replace('\\', '/'): sha(p)
            for top in ('Computation', 'Weather') for p in sorted((root / top).rglob('*')) if p.is_file()}


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding='ascii', newline='\n')


def source_files(comp: Path, kind: str, deposition: bool) -> list[float]:
    area, point, lines, portals = [], [], [], []
    for group in ((1, 2, 3, 4) if kind == 'all_sources' else (1, 2, 3)):
        area_rate = .5 if kind in ('area_line', 'mixed_point_area') else 1
        if kind in ('area', 'area_line', 'mixed_point_area') or (kind in ('supported_primary', 'all_sources') and group == 1):
            row = f'2500,2500,2,100,100,1,{area_rate},0,0,0,{group}'
            # Documented deposition suffix: size fractions, diameter, density,
            # deposition velocity, sedimentation velocity, mode and coarse fraction.
            if deposition:
                row += ',100,100,30,1000,0.03,0,0,1'
            area.append(row)
        if kind in ('point', 'point_buoyant', 'point_cold_momentum', 'point_portal_timeseries', 'mixed_point_area') or (kind == 'all_sources' and group == 3):
            rate = .5 if kind == 'mixed_point_area' else 1
            velocity, temperature = ((10, 373) if kind == 'point_buoyant' else
                                     (10, 273) if kind == 'point_cold_momentum' else
                                     ('0:5:90', 293) if kind == 'point_portal_timeseries' else (0, 293))
            suffix = ',Temp@_point_temp,Vel@_point_vel' if kind == 'point_portal_timeseries' else ''
            point.append(f'2500,2500,2,{rate},0,0,0,{velocity},1,{temperature},{group}{suffix}')
        if kind in ('line_horizontal', 'line_vertical', 'area_line') or (kind == 'supported_primary' and group in (2, 3)) or (kind == 'all_sources' and group == 2):
            x1, y1, z1, x2, y2, z2 = ((2500, 2500, 2, 2500, 2500, 12)
                                      if kind == 'line_vertical' or (kind == 'supported_primary' and group == 3)
                                      else (2450, 2500, 2, 2550, 2500, 2))
            length = math.dist((x1, y1, z1), (x2, y2, z2))
            rate = (.5 if kind == 'area_line' else 1) * 1000 / length
            lines.append(f'{group},synthetic,{group},{x1},{y1},{z1},{x2},{y2},{z2},20,5,0,0,{rate:g}')
        if kind in ('portal', 'point_portal_timeseries') or (kind == 'all_sources' and group == 4):
            suffix = ',Temp@_portal_temp,Vel@_portal_vel' if kind == 'point_portal_timeseries' else ''
            portals.append(f'2500,2495,2500,2505,0,5,1,0,0,0,{group},0,2{suffix}')
    if area:
        write(comp / 'cadastre.dat', 'x,y,z,dx,dy,dz,emission,unused,unused,unused,SG\n' + '\n'.join(area) + '\n')
    if point:
        write(comp / 'point.dat', 'x,y,z,emission,unused,unused,unused,velocity,diameter,temperature,SG\nvirtual sources; kg/h\n' + '\n'.join(point) + '\n')
    if lines:
        write(comp / 'line.dat', 'virtual LINE sources\nconstant synthetic values\nkg/h/km\nno research data\nid,name,SG,x1,y1,z1,x2,y2,z2,width,height,unused,unused,emission\n' + '\n'.join(lines) + '\n')
    if portals:
        write(comp / 'portals.dat', 'x1,y1,x2,y2,z1,z2,emission,unused,unused,unused,SG,deltaT,velocity\nvirtual sources; kg/h\n' + '\n'.join(portals) + '\n')
    return [2., 2., 2.] if kind == 'point_portal_timeseries' else [1.] * (4 if kind == 'all_sources' else 3)


def prepare(root: Path, case: str, *, hours: int = 4, particles_per_hour: int = 36000,
            workers: int = 16, schedule: str = 'case') -> dict:
    if case not in CASES or hours < 1 or particles_per_hour < 1 or workers != 16:
        raise ValueError('invalid case, hour count, particle budget or worker count')
    if schedule not in ('case', 'sparse', 'constant'):
        raise ValueError('unknown schedule')
    config = dict(CASES[case])
    if config.get('switch') and hours != 4 and schedule == 'case':
        raise ValueError('switch smoke is defined for four hours')
    root.mkdir(parents=True, exist_ok=False)
    comp, weather = root / 'Computation', root / 'Weather'
    comp.mkdir(); weather.mkdir()
    geometry = None
    if not config.get('flat'):
        write_geometry(comp / 'ggeom.asc', GRID)
        geometry = validate_geometry(comp / 'ggeom.asc', GRID)
        write(comp / 'GRAMM.geb', '24\n20\n16\n0\n6000\n0\n5000\n')
        write(comp / 'windfeld.txt', '../Weather\n')
        wind = struct.pack('<iiiii', -1, 24, 20, 16, 250) + struct.pack('<hhh', 200, 0, 0) * (24 * 20 * 16)
        stability = struct.pack('<iiiif', -1, 24, 20, 16, 250.) + struct.pack('<h', 4) * (24 * 20)
        for index in range(1, (hours if config.get('steady') else 1) + 1):
            (weather / f'{index:05d}.wnd').write_bytes(wind)
            (weather / f'{index:05d}.scl').write_bytes(stability)
    groups = [1, 2, 3, 4] if config['sources'] == 'all_sources' else [1, 2, 3]
    write(comp / 'GRAL.geb', '20\n20\n5,1.15\n50\n50\n1\n' + ','.join(map(str, groups)) + '\n2000\n3000\n2000\n3000\n')
    receptors = config.get('receptors', 0)
    control = [format(particles_per_hour / 3600, '.12g'), '3600', '1' if config.get('steady') else '0',
               '4', '1' if receptors else '0', '0.1', '37', 'Y', 'NO2', '1.5', '2', '1', '0', '0',
               'compressed', 'nokeystroke', 'ASCiiResults 0', '0', '0', '0', '0',
               '0' if config.get('nonfixed_seed') else '1']
    write(comp / 'in.dat', '\n'.join(control) + '\n')
    write(comp / 'Max_Proc.txt', f'{workers}\n')
    source_rates = source_files(comp, config['sources'], config.get('deposition', False))
    if config.get('source_series'):
        series = {
            'TimeSeriesPointSourceTemp.txt': ('point_temp', (0, 20, 80, 40)),
            'TimeSeriesPointSourceVel.txt': ('point_vel', (0.05, 0.2, 6, 0.05)),
            'TimeSeriesPortalSourceTemp.txt': ('portal_temp', (0, 10, 20, 5)),
            'TimeSeriesPortalSourceVel.txt': ('portal_vel', (0.05, 0.2, 8, 2)),
        }
        for filename, (column, values) in series.items():
            write(comp / filename, 'Date,Hour,' + column + '\n' + ''.join(
                f'{1+h//24:02d}.01,{1+h%24},{values[h%len(values)]}\n' for h in range(hours)))
    factors = ([(3, 0, 0), (0, 0, 0), (0, 3, 0), (0, 0, 3)] if config.get('switch') and schedule == 'case'
               else [tuple([len(groups)] + [0]*(len(groups)-1)) if schedule == 'sparse' else tuple([1]*len(groups))] * hours)
    write(comp / 'meteopgt.all', '10,1,0\ndirection,speed,stability,frequency\n' +
          '27,2,4,1\n' * (hours if config.get('steady') else 1))
    # Keep a real unused trailing row so upstream final-row modulation rules do
    # not erase the last measured switching hour. Explicit SITUATIONS limits run.
    write(comp / 'mettimeseries.dat', ''.join(f'{1+h//24:02d}.01 {1+h%24} 2 27 4\n' for h in range(hours+1)))
    write(comp / 'emissions_timeseries.txt', 'Date;Hour;' + ';'.join(map(str, groups)) + '\n' + ''.join(
        f'{1+h//24:02d}.01;{1+h%24};' + ';'.join(map(str, row)) + '\n' for h, row in enumerate(factors+[factors[-1]])))
    if receptors:
        write(comp / 'Receptor.dat', str(receptors) + '\n' + ''.join(
            f'{i+1},{2520+(i%10)*20},{2420+(i//10)*20},1.5,R{i+1}\n' for i in range(receptors)))
    if config.get('decay'):
        write(comp / 'Pollutant.txt', 'NO2\n0\n0\n0.0001\n')
    if config.get('buildings'):
        write(comp / 'buildings.dat', '2700,2700,0,5\n')
    manifest = dict(schema=1, case=case, config=config, hours=hours, input_rows=hours+1, workers=workers,
                    particles_per_hour=particles_per_hour, particles_per_second=particles_per_hour/3600,
                    grid_cells=[50, 50], gral_domain_m=[2000, 3000, 2000, 3000],
                    factors=factors, source_groups=groups, source_emission_kg_h=source_rates,
                    expected_emitted_mass_kg=[sum(row[i] for row in factors)*source_rates[i] for i in range(len(groups))],
                    emission_check_scope='transient emitted mass; steady frequencies have different accounting',
                    geometry_qa=geometry, synthetic_only=True, schedule=schedule,
                    source_series_units=({'point_temperature': 'degC', 'portal_temperature': 'delta_degC', 'velocity': 'm/s'}
                                         if config.get('source_series') else None),
                    seed_control='none in inputs; external benchmark overlay only',
                    input_sha256=input_hashes(root))
    (root / 'input_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--case', choices=CASES, required=True)
    p.add_argument('--hours', type=int, default=4)
    p.add_argument('--particles-per-hour', type=int, default=36000)
    p.add_argument('--schedule', choices=('case', 'sparse', 'constant'), default='case')
    args = p.parse_args()
    prepare(args.out, args.case, hours=args.hours, particles_per_hour=args.particles_per_hour, schedule=args.schedule)
    print('[PREPARED]', args.case)


if __name__ == '__main__':
    main()
