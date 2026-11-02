"""Synthetic analytical checks. These do not validate model physics."""
import unittest
import json
import tempfile
import struct
import zipfile
from pathlib import Path
import numpy as np
from analyze_study import field_metrics, aggregate_groups, block_metrics, summarize, ratio, bootstrap_blocks, load_runs, load_fields, observer_boundary_seconds, validate_constant_inputs, gpu_device_intervals, fixed_seed_repeatability

class AnalysisTests(unittest.TestCase):
    def test_symmetric_normalization_and_bias(self):
        out = field_metrics(np.array([[[0.,2.]]]), np.array([[[0.,4.]]]))
        self.assertAlmostEqual(out['weighted_nmae'], 2/3)
        self.assertAlmostEqual(out['normalized_bias'], 2/3)
        self.assertAlmostEqual(out['mean_difference'], 1.)
        reverse = field_metrics(np.array([[[0.,4.]]]), np.array([[[0.,2.]]]))
        self.assertAlmostEqual(reverse['weighted_nmae'], out['weighted_nmae'])
        self.assertAlmostEqual(reverse['normalized_bias'], -out['normalized_bias'])

    def test_zeros_and_undefined_correlation(self):
        out = field_metrics(np.zeros((2,2,2)), np.zeros((2,2,2)))
        self.assertEqual(out['weighted_nmae'], 0.)
        self.assertEqual(out['zero_status'], 'both_zero')
        self.assertIsNone(out['spatial_pearson'])
        self.assertEqual(ratio(0,0), 0)
        self.assertTrue(np.isinf(ratio(1,0)))

    def test_invalid_fields(self):
        for invalid in (np.array([[[-1.]]]), np.array([[[np.nan]]])):
            with self.assertRaises(ValueError):
                field_metrics(invalid, np.zeros_like(invalid))
        with self.assertRaises(ValueError):
            field_metrics(np.zeros((1,2,2)), np.zeros((2,2,2)))

    def test_aggregate_sums_groups_before_metric(self):
        groups = {'1': np.array([[[1.,0.]]]), '2': np.array([[[0.,2.]]])}
        np.testing.assert_array_equal(aggregate_groups(groups)['aggregate'], [[[1.,2.]]])
        self.assertEqual(set(groups), {'1','2'})

    def test_disjoint_block_formulas(self):
        c = [np.full((2,2,2), float(v)) for v in [1,3,5,7,9,11]]
        g = [x + .1 for x in c]
        blocks = block_metrics(c,g)
        self.assertEqual(len(blocks),3)
        for item in blocks:
            self.assertAlmostEqual(item['A'], .1)
            self.assertAlmostEqual(item['B'], 2)
            self.assertAlmostEqual(item['D'], 2)
            self.assertAlmostEqual(item['R'], .05)
            self.assertAlmostEqual(item['V'], 1)
        self.assertEqual([x['seed_indices'] for x in blocks], [[0,1],[2,3],[4,5]])

    def test_zero_reference_blocks_are_not_finite_ratios(self):
        z=[np.zeros((1,1,1)) for _ in range(6)]
        rows=block_metrics(z,z)
        self.assertIsNone(rows[0]['V'])
        self.assertEqual(rows[0]['ratio_status'],'uninformative_zero')
        empty=bootstrap_blocks(rows)
        self.assertEqual(empty['R']['undefined_resamples'],27)
        self.assertEqual(empty['R']['infinite_resamples'],0)
        self.assertIsNone(empty['R']['estimate'])
        positive=bootstrap_blocks([{'A':1,'B':0,'D':2} for _ in range(3)])
        self.assertEqual(positive['R']['infinite_resamples'],27)
        self.assertEqual(positive['R']['undefined_resamples'],0)
        self.assertTrue(np.isinf(positive['R']['estimate']))

    def test_cuda_event_counter_deltas_do_not_use_host_named_timers(self):
        rows=[{'result_server_metrics':{'kernel_device_ms':value},'fresh_kernel_ms':999.,'residual_kernel_ms':999.} for value in (4.,9.,15.)]
        self.assertEqual(gpu_device_intervals(rows),[4.,5.,6.])
        self.assertEqual(gpu_device_intervals([rows[0],{},rows[2]]),[4.,None,None])
        with self.assertRaises(ValueError):gpu_device_intervals([rows[1],rows[0]])

    def test_fixed_seed_repeats_remain_dependent_and_detect_gpu_jitter(self):
        runs=[];fields={}
        for hours in (24,48):
            for repeat in range(3):
                for backend in ('cpu','gpu'):
                    name=f'{hours}_{repeat}_{backend}'
                    runs.append({'run_id':name,'hours':hours,'seed_offset':0,'repeat':repeat,'backend':backend,'pair_id':f'{hours}_{repeat}'})
                    value=1. if backend=='cpu' else 1.+repeat*.1
                    fields[name]={'1':np.full((hours,1,1),value)}
        output=fixed_seed_repeatability(runs,fields)
        self.assertTrue(output['comparisons_are_dependent'])
        self.assertEqual(output['independent_seed_count'],1)
        self.assertIsNone(output['acceptance_threshold'])
        for hours in ('24','48'):
            group=output['durations'][hours]['windows']['all_hours']['groups']['1']
            self.assertEqual(len(group['paired_cpu_gpu']),3)
            self.assertEqual(len(group['cpu_self_pairs']),3)
            self.assertEqual(len(group['gpu_self_pairs']),3)
            self.assertTrue(all(p['raw_array_equal'] for p in group['cpu_self_pairs']))
            self.assertTrue(all(not p['raw_array_equal'] for p in group['gpu_self_pairs']))
            self.assertAlmostEqual(group['paired_cpu_gpu'][1]['symmetric_weighted_nmae'],.1/1.05)
            self.assertAlmostEqual(group['paired_cpu_gpu'][1]['normalized_bias_candidate_minus_reference'],.1/1.05)
            self.assertEqual(output['durations'][hours]['windows']['hours_4_to_end']['first_hour'],4)

    def test_three_run_sample_sd(self):
        result = summarize([1.,2.,3.])
        self.assertEqual(result['n'],3)
        self.assertAlmostEqual(result['sample_sd'],1.)
        self.assertAlmostEqual(result['cv'],.5)
        self.assertEqual(result['median'],2)

    def test_bootstrap_enumerates_three_blocks(self):
        blocks = [{'A':.1,'B':2.,'D':2.} for _ in range(3)]
        out = bootstrap_blocks(blocks)
        self.assertEqual(out['resamples'],27)
        self.assertAlmostEqual(out['R']['estimate'],.05)
        self.assertAlmostEqual(out['R']['p95_upper'],.05)
        self.assertFalse(out['coverage_established'])

class CohortValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from synthetic_fixture import make_study
        cls.temp=tempfile.TemporaryDirectory(prefix='analysis_test_',dir=Path(__file__).parent)
        cls.manifest=make_study(Path(cls.temp.name)/'fixture')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_full_cohort_and_zero_filled_grids(self):
        _,runs=load_runs(self.manifest)
        self.assertEqual(len(runs),22)
        fields=load_fields(runs[0]['root']/'Computation',24)
        self.assertEqual(fields['1'].shape,(24,50,50))
        self.assertEqual(fields['1'][0,1,1],0)
        self.assertEqual(fields['1'][0,0,0],1.)
        self.assertEqual(fields['1'][0,24,24],.5)
        np.testing.assert_allclose(fields['aggregate'],fields['1']+fields['2']+fields['3']+fields['4'])
        self.assertEqual(runs[0]['steady_boundary_wall_s'],21.)
        self.assertNotEqual(runs[0]['steady_boundary_wall_s'],runs[0]['steady_wall_sum_s'])

    def test_sparse_physical_cell_centers_and_outside_rejection(self):
        comp=Path(self.temp.name)/'sparse';comp.mkdir(exist_ok=True)
        def create(x):
            with zipfile.ZipFile(comp/'00001.grz','w') as archive:
                for group in (1,2,3,4):
                    payload=struct.pack('<i',-1)+struct.pack('<iif',2010,2010,float(group))+struct.pack('<iif',x,2990,float(group)*2)
                    archive.writestr(f'00001-1{group:02d}.con',payload)
        create(2990)
        fields=load_fields(comp,1)
        self.assertEqual(fields['1'][0,0,0],1.)
        self.assertEqual(fields['1'][0,49,49],2.)
        for invalid_x in (3010,1990,2991):
            create(invalid_x)
            with self.assertRaises(ValueError):load_fields(comp,1)

    def test_dense_grid_header_and_values(self):
        comp=Path(self.temp.name)/'dense';comp.mkdir(exist_ok=True)
        def create(origin):
            with zipfile.ZipFile(comp/'00001.grz','w') as archive:
                for group in (1,2,3,4):
                    array=np.zeros((50,50),dtype='<f4');array[2,3]=float(group)
                    payload=struct.pack('<iiiffii',-3,origin,2000,20.,20.,50,50)+array.tobytes()
                    archive.writestr(f'00001-1{group:02d}.con',payload)
        create(2000)
        fields=load_fields(comp,1)
        self.assertEqual(fields['aggregate'][0,2,3],10.)
        create(2001)
        with self.assertRaises(ValueError):load_fields(comp,1)

    def test_boundary_frequency_and_constant_input_mutation_rejected(self):
        manifest=json.loads(self.manifest.read_text())
        root=Path(manifest['runs'][0]['path'])
        result=json.loads((root/'logs'/'result.json').read_text())
        result['observer']['raw_events'][0]['stopwatch_frequency']=0
        with self.assertRaises(ValueError):observer_boundary_seconds(result['observer'],24)
        path=root/'Computation'/'emissions_timeseries.txt';raw=path.read_text()
        try:
            path.write_text(raw.replace(';1;1;1',';1;2;1',1))
            with self.assertRaises(ValueError):validate_constant_inputs(root/'Computation',24)
        finally:path.write_text(raw)

    def test_missing_observer_and_telemetry_are_rejected(self):
        manifest=json.loads(self.manifest.read_text())
        root=Path(manifest['runs'][0]['path'])
        result_path=root/'logs'/'result.json';original=result_path.read_text()
        for mutate in (lambda r:r.update(observer={'status':'unavailable'}),
                       lambda r:r['observer'].update(raw_events=[]),
                       lambda r:r['observer']['situation_series'][0].update(telemetry_samples=0)):
            try:
                result=json.loads(original);mutate(result);result_path.write_text(json.dumps(result))
                with self.assertRaises(ValueError):load_runs(self.manifest)
            finally:result_path.write_text(original)
        path=root/'logs'/'gpu_telemetry.csv';raw=path.read_text()
        try:
            path.write_text('elapsed_s,device_memory_used_mib,query_error\n')
            with self.assertRaises(ValueError):load_runs(self.manifest)
        finally:path.write_text(raw)

if __name__ == '__main__':
    unittest.main()
