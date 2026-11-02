"""Synthetic input contracts for the new GPU modes; no model runs."""
import tempfile
import unittest
from pathlib import Path
import fixtures
import functional_matrix
from support import runtime_helpers
from unittest.mock import patch


class NewModeFixtures(unittest.TestCase):
    def test_quiet_gate_records_two_five_second_samples(self):
        clock = [0.0]
        counter = [0]
        def sleep(seconds): clock[0] += seconds
        def read():
            counter[0] += 100
            return counter[0], counter[0]
        result = runtime_helpers.quiet_gate(required_seconds=10, now=lambda: clock[0], sleep=sleep, read=read)
        self.assertEqual(result['rule']['window_seconds'], 10)
        self.assertEqual(len(result['samples']), 2)
        self.assertEqual(sum(row['duration_s'] for row in result['samples']), 10)

    def test_functional_comparator_receives_manifest_groups(self):
        manifest = {'config': {}, 'hours': 4, 'source_groups': [1, 2, 3, 4]}
        with patch.object(functional_matrix.compare, 'compare_outputs', return_value={}) as compare:
            functional_matrix.compare_case(Path('a'), Path('b'), manifest)
            self.assertEqual(compare.call_args.kwargs['expected_groups'], (1, 2, 3, 4))

    def test_all_sources_cohorts_have_four_independent_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            for case, steady in (('transient_all_sources', False), ('steady_all_sources', True)):
                root = Path(tmp)/case
                manifest = fixtures.prepare(root, case, particles_per_hour=360000)
                comp = root/'Computation'
                self.assertEqual(manifest['source_groups'], [1, 2, 3, 4])
                self.assertEqual(manifest['particles_per_hour'], 360000)
                self.assertEqual(manifest['workers'], 16)
                self.assertEqual(manifest['config'].get('steady', False), steady)
                self.assertEqual(manifest['factors'], [(1, 1, 1, 1)]*4)
                for filename in ('cadastre.dat', 'line.dat', 'point.dat', 'portals.dat'):
                    self.assertTrue((comp/filename).is_file())
                self.assertEqual((comp/'cadastre.dat').read_text().splitlines()[1].split(',')[10], '1')
                self.assertEqual((comp/'line.dat').read_text().splitlines()[5].split(',')[2], '2')
                self.assertEqual((comp/'point.dat').read_text().splitlines()[2].split(',')[10], '3')
                self.assertEqual((comp/'portals.dat').read_text().splitlines()[2].split(',')[10], '4')

    def test_time_varying_point_and_portal_series_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'varying'
            manifest = fixtures.prepare(root, 'point_portal_timeseries', hours=4)
            comp = root/'Computation'
            expected = {
                'TimeSeriesPointSourceTemp.txt': ('point_temp', [0, 20, 80, 40]),
                'TimeSeriesPointSourceVel.txt': ('point_vel', [0.05, 0.2, 6, 0.05]),
                'TimeSeriesPortalSourceTemp.txt': ('portal_temp', [0, 10, 20, 5]),
                'TimeSeriesPortalSourceVel.txt': ('portal_vel', [0.05, 0.2, 8, 2]),
            }
            for filename, (column, values) in expected.items():
                rows = (comp/filename).read_text().splitlines()
                self.assertEqual(rows[0].split(','), ['Date', 'Hour', column])
                self.assertEqual(len(rows), 5)
                self.assertEqual([float(row.split(',')[2]) for row in rows[1:]], values)
            point = (comp/'point.dat').read_text().splitlines()[2].split(',')
            portal = (comp/'portals.dat').read_text().splitlines()[2].split(',')
            self.assertEqual(point[7], '0:5:90')
            for row, names in ((point, ('point_temp', 'point_vel')), (portal, ('portal_temp', 'portal_vel'))):
                self.assertIn('Temp@_'+names[0], row)
                self.assertIn('Vel@_'+names[1], row)
            self.assertEqual(manifest['source_series_units'], {'point_temperature': 'degC', 'portal_temperature': 'delta_degC', 'velocity': 'm/s'})

    def test_gpu_cases_have_paired_inputs_and_expected_sources(self):
        cases = {
            'steady_area': ('cadastre.dat',),
            'steady_line': ('line.dat',),
            'steady_point': ('point.dat',),
            'steady_portal': ('portals.dat',),
            'point': ('point.dat',),
            'point_buoyant': ('point.dat',),
            'portal': ('portals.dat',),
            'mixed_point_area': ('point.dat', 'cadastre.dat'),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for case, files in cases.items():
                with self.subTest(case=case):
                    a, b = Path(tmp)/f'{case}_cpu', Path(tmp)/f'{case}_gpu'
                    ma, mb = fixtures.prepare(a, case), fixtures.prepare(b, case)
                    self.assertEqual(ma['input_sha256'], mb['input_sha256'])
                    self.assertEqual(ma['workers'], 16)
                    self.assertEqual(ma['config']['dispatch'], 'gpu')
                    for name in files:
                        self.assertTrue((a/'Computation'/name).is_file())
                    self.assertEqual((a/'Computation'/'in.dat').read_text().splitlines()[2],
                                     '1' if case.startswith('steady_') else '0')
            cold = (Path(tmp)/'point_cpu'/'Computation'/'point.dat').read_text().splitlines()[2].split(',')
            hot = (Path(tmp)/'point_buoyant_cpu'/'Computation'/'point.dat').read_text().splitlines()[2].split(',')
            self.assertNotEqual(cold[7:10], hot[7:10])


if __name__ == '__main__':
    unittest.main()
