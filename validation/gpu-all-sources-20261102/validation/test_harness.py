"""Offline contract tests; no model or research data is used."""
import struct
import tempfile
import unittest
from unittest.mock import patch
import io
import threading
import zipfile
from pathlib import Path

import fixtures
import compare
import run_matrix
import prepare_overlay
import run_study


class FixtureTests(unittest.TestCase):
    def test_representative_sources_and_fixed_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in fixtures.CASES:
                root = Path(tmp) / name
                manifest = fixtures.prepare(root, name)
                self.assertEqual(manifest['hours'], 4)
                self.assertEqual(manifest['workers'], 16)
                self.assertEqual(manifest['particles_per_hour'], 36000)
                self.assertEqual(len((root / 'Computation' / 'mettimeseries.dat').read_text().splitlines()), 5)
                self.assertEqual((root / 'Computation' / 'Max_Proc.txt').read_text(), '16\n')
                self.assertEqual(manifest['grid_cells'], [50, 50])
            comp = Path(tmp) / 'line_horizontal' / 'Computation'
            line = (comp / 'line.dat').read_text().splitlines()[5].split(',')
            self.assertEqual(len(line), 14)
            self.assertEqual(line[9:11], ['20', '5'])
            self.assertEqual(len((Path(tmp) / 'receptors51' / 'Computation' / 'Receptor.dat').read_text().splitlines()), 52)

    def test_input_pair_identical_and_seed_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'
            ma = fixtures.prepare(a, 'area_line_switch')
            mb = fixtures.prepare(b, 'area_line_switch')
            self.assertEqual(fixtures.input_hashes(a), fixtures.input_hashes(b))
            self.assertEqual(ma['factors'], mb['factors'])
            self.assertNotIn('seed', '\n'.join(p.name for p in a.rglob('*')))

    def test_refuse_overwrite_and_invalid_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'case'
            fixtures.prepare(root, 'area')
            with self.assertRaises(FileExistsError):
                fixtures.prepare(root, 'area')
            with self.assertRaises(ValueError):
                fixtures.prepare(Path(tmp) / 'other', 'area', particles_per_hour=0)
            with self.assertRaises(ValueError):
                fixtures.prepare(Path(tmp) / 'other', 'area', workers=32)


class ComparisonTests(unittest.TestCase):
    @staticmethod
    def sparse(values):
        return struct.pack('<i', -1) + b''.join(struct.pack('<iif', x, y, v) for x, y, v in values)

    def test_sparse_dense_and_nonfinite(self):
        sparse = compare.read_grid(self.sparse([(2010, 2010, 2), (2030, 2010, 0)]))
        dense = compare.read_grid(struct.pack('<iiiffii', -3, 2000, 2000, 20, 20, 2, 1) + struct.pack('<2f', 2, 0))
        self.assertEqual(sparse, dense)
        for bad in (self.sparse([(1, 1, float('nan'))]), self.sparse([(1, 1, -1)]), self.sparse([(1, 1, 1), (1, 1, 2)])):
            with self.assertRaises(ValueError):
                compare.read_grid(bad)

    def test_metric_zero_policy_and_bias(self):
        row = compare.metrics([0, 1, 3], [0, 2, 3])
        self.assertAlmostEqual(row['nmae'], 0.25)
        self.assertAlmostEqual(row['normalized_bias'], 0.25)
        self.assertEqual(row['fac2_positive_reference'], 1)
        self.assertEqual(row['zero_reference_positive_candidate'], 0)
        self.assertIsNone(compare.metrics([0], [1])['nmae'])
        self.assertEqual(compare.metrics([0], [0])['nmae'], 0)

    def test_archives_all_members_and_exact_hour_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'
            a.mkdir(); b.mkdir()
            for folder in (a, b):
                with zipfile.ZipFile(folder / '00001.grz', 'w') as z:
                    z.writestr('00001-101.con', self.sparse([(1, 1, 2)]))
                    z.writestr('00001-01.dep', self.sparse([(1, 1, 0.5)]))
            result = compare.compare_outputs(a, b, hours=1)
            self.assertTrue(result['raw_members_equal'])
            self.assertEqual(len(result['members']), 2)
            with self.assertRaises(ValueError):
                compare.compare_outputs(a, b, hours=1, expected_groups=(1,2,3), deposition=True)
            with self.assertRaises(ValueError):
                compare.compare_outputs(a, b, hours=1, required_receptors=('Receptor_Timeseries_Transient.txt',))
            (b / '00002.grz').write_bytes((b / '00001.grz').read_bytes())
            with self.assertRaises(ValueError):
                compare.compare_outputs(a, b, hours=1)

    def test_fallback_does_not_silently_relax_raw_equality(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a', Path(tmp) / 'b'
            a.mkdir(); b.mkdir()
            for folder, value in ((a, 1), (b, 1.01)):
                with zipfile.ZipFile(folder / '00001.grz', 'w') as z:
                    z.writestr('00001-101.con', self.sparse([(1, 1, value)]))
            result = compare.compare_outputs(a, b, hours=1)
            self.assertFalse(result['raw_members_equal'])
            self.assertGreater(result['members'][0]['nmae'], 0)

    def test_real_receptor_footer_is_diagnostic_not_concentration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'Receptor_Timeseries_Transient.txt'
            text='Rec/SourceGroup\tR1/SG: 1\t\nX\t2520\nY\t2420\nZ\t1.5\nDate/time\t[ug/m3]\n'
            text+='2020-01-01 1:00:00\t7.0578e+000\t\n2020-01-01 2:00:00\t8.2556e+000\t\n \n\nEst. statistical error [%] SimulationSpan:(1_2)\t1.9%\t\n'
            path.write_text(text,encoding='utf-16')
            _,labels,values,footer=compare.receptors(path,2)
            self.assertEqual(len(labels),2)
            self.assertEqual(values,[[7.0578],[8.2556]])
            self.assertEqual(footer['statistical_error_percent'],[1.9])
            path.write_text(text+'2020-01-01 3:00:00\t1\n',encoding='utf-16')
            with self.assertRaises(ValueError): compare.receptors(path,2)


class RunnerTests(unittest.TestCase):
    def test_environment_scrubs_stale_gpu_and_seed_variables(self):
        env = run_matrix.clean_environment({'PATH': 'x', 'INU_GPU_EXPERIMENTAL': '1', 'INU_OTHER': 'x', 'GRAL_BENCH_SEED_OFFSET': '42'})
        self.assertEqual(env, {'PATH': 'x'})

    def test_six_offsets_change_only_designated_seed_math(self):
        states=[]
        for offset in (0,100000,200000,300000,400000,500000):
            first=521288629+200+((1+offset)<<2)
            second=2232121+((1+offset)<<1)
            row=dict(IWET=1,WindVelGral=2,WindDirGral=0,Seed1=first,Seed2=second,fixed_mode=True)
            check=run_matrix.validate_seed_rows([row],offset,True)
            states.append(check['states'][0])
            with self.assertRaises(ValueError): run_matrix.validate_seed_rows([row],offset+1,True)
        self.assertEqual(len(set(states)),6)

    def test_fallback_requires_reason_and_no_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = 'INU GPU dispatch: CPU fallback: unsupported point sources\n'
            self.assertEqual(run_matrix.check_dispatch(root, good, 'fallback')['path'], 'cpu_fallback')
            with self.assertRaises(ValueError):
                run_matrix.check_dispatch(root, 'nothing', 'fallback')
            (root / 'gpu_metrics.jsonl').write_text('{}\n')
            with self.assertRaises(ValueError):
                run_matrix.check_dispatch(root, good, 'fallback')

    def test_telemetry_alignment(self):
        rows = [{'timestamp': 'a', 'elapsed_s': 1., 'tree_rss_bytes': 100},
                {'timestamp': 'b', 'elapsed_s': 2., 'tree_rss_bytes': 200},
                {'timestamp': 'c', 'elapsed_s': 3., 'tree_rss_bytes': 300}]
        result = run_matrix.summarize_situations(rows, [{'situation': 1, 'start_s': .5, 'end_s': 2.5}])
        self.assertEqual(result[0]['telemetry_samples'], 2)
        self.assertEqual(result[0]['peak_tree_rss_bytes'], 200)

    def test_nan_mass_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = Path(tmp)
            (comp/'Logfile_GRALCore.txt').write_text('GRAL simulations finished at: now')
            text = 'Weather number: 1 -\nSummarized emission rates per source group in kg\n1 2 3\nNaN 1 1\n'
            with self.assertRaisesRegex(ValueError, 'nonfinite'):
                run_matrix.validate_completion(comp, text, dict(hours=1,config={},expected_emitted_mass_kg=[1,1,1]))

    def test_gpu_query_invalid_numeric_fails_collector(self):
        class FakeQuery:
            stdout = io.StringIO('0, NaN, 30, 20\n')
            def poll(self): return 0
            def wait(self, timeout): return 0
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = run_matrix.Telemetry.__new__(run_matrix.Telemetry)
            telemetry.logs = Path(tmp); telemetry.stop = threading.Event()
            telemetry.gpu_ready = threading.Event(); telemetry.errors = []
            telemetry.origin = run_matrix.time.perf_counter()
            with patch.object(run_matrix.subprocess, 'Popen', return_value=FakeQuery()):
                telemetry.gpu()
            self.assertTrue(telemetry.stop.is_set())
            self.assertTrue(telemetry.errors)
            self.assertIn('nonfinite', telemetry.errors[0])

    def test_access_denied_skip_requires_exit_evidence(self):
        telemetry=run_matrix.Telemetry.__new__(run_matrix.Telemetry)
        telemetry.model_finished=threading.Event()
        class Psutil:
            @staticmethod
            def pid_exists(pid): return True
        class Process:
            pid=42
            def is_running(self): return True
        telemetry.psutil=Psutil()
        self.assertFalse(telemetry.exited_process(Process()))
        telemetry.model_finished.set()
        self.assertTrue(telemetry.exited_process(Process()))

    def test_gpu_query_launch_failure_is_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = run_matrix.Telemetry.__new__(run_matrix.Telemetry)
            telemetry.logs = Path(tmp); telemetry.stop = threading.Event()
            telemetry.gpu_ready = threading.Event(); telemetry.errors = []
            telemetry.origin = run_matrix.time.perf_counter()
            with patch.object(run_matrix.subprocess, 'Popen', side_effect=OSError('missing NVIDIA tool')):
                telemetry.gpu()
            self.assertTrue(telemetry.errors)
            self.assertTrue(telemetry.stop.is_set())

    def test_terminal_banner_is_only_allowed_without_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            comp = Path(tmp)
            (comp/'Logfile_GRALCore.txt').write_text('GRAL simulations finished at: now')
            text = 'Weather number: 1 -\nWeather number: 2 -\nUsing a total of 100 particles\n'
            with self.assertRaisesRegex(ValueError,'terminal situation banner'):
                run_matrix.validate_completion(comp,text,dict(hours=1,config={},expected_emitted_mass_kg=[1,1,1]))


class OverlayTests(unittest.TestCase):
    def test_patch_only_designated_rng_and_observer_hooks(self):
        source = ('LogLevel = CheckCommandLineArguments(args);\n'
                  '                String WindfieldPath = ReadWindfeldTXT();\n'
                  'RnGSeed = new DeterministicRandomGenerator(IWET, WindVelGral, WindDirGral);\n'
                  '                } //skipped situation if no entry in meteopgt.all could be found in transient GRAL mode\n'
                  'FinishGral:\n')
        result = prepare_overlay.patch_program(source)
        self.assertIn('checked(IWET + benchmarkSeedOffset)', result)
        self.assertIn('benchmarkTelemetry?.RecordSeed(IWET', result)
        self.assertIn('benchmarkTelemetry?.CompleteSituation(IWET', result)
        self.assertIn('benchmarkTelemetry?.SituationStarted(IWET)', result)
        self.assertNotIn('IWET +=', result)
        with self.assertRaises(ValueError):
            prepare_overlay.patch_program(result)


class StudyTests(unittest.TestCase):
    def test_actual_seed_formula_and_fixed_input_are_mandatory(self):
        def record(offset=100000):
            return dict(seed_offset=offset,backend='cpu',hours=1,result=dict(observer=dict(status='pass',seed_rows=[
                dict(IWET=1,TAUS=3600,WindVelGral=2,WindDirGral=0,fixed_mode=True,
                     Seed1=521288629+200+4*(1+offset),Seed2=2232121+2*(1+offset))])))
        run_study.validate_prefixes([record()])
        wrong=record();wrong['result']['observer']['seed_rows'][0]['Seed1']=521288833
        with self.assertRaisesRegex(ValueError,'actual seed'): run_study.validate_prefixes([wrong])
        wrong=record();wrong['result']['observer']['seed_rows'][0]['WindDirGral']=270
        with self.assertRaisesRegex(ValueError,'actual wind'): run_study.validate_prefixes([wrong])


if __name__ == '__main__':
    unittest.main(verbosity=2)
