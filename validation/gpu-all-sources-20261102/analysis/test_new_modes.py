"""New-mode contracts; synthetic tests only, never launch GRAL."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'validation'))
from prepare_new_modes_study import design,COHORTS
from mode_contracts import validate_gpu_phase_counts

class NewModeTests(unittest.TestCase):
    def test_declared_44_run_design(self):
        rows=[r for c in COHORTS for r in design(Path('fixed-root'),c)]
        self.assertEqual(len(rows),44)
        self.assertEqual(len({r['run_id'] for r in rows}),44)
        for cohort in COHORTS:
            selected=[r for r in rows if r['cohort']==cohort]
            self.assertEqual(len(selected),22)
            self.assertEqual(len([r for r in selected if r['role']=='science']),12)
            self.assertEqual(len([r for r in selected if r['hours']==48]),6)

    def test_mode_specific_device_phase_counts(self):
        rows=[{'situation':i,'fresh_particles':10,'fresh_active_particles':10,
               'residual_particles':0,'residual_batches':0,'phase_counts':{'fresh':i*10,'residual':0},'result_server_metrics':{'kernel_launches':i,'kernel_device_ms':float(i)}} for i in range(1,5)]
        self.assertEqual(validate_gpu_phase_counts(rows,'steady_all_sources',4)['fresh_total'],40)
        changed=[dict(r) for r in rows];changed[1]['residual_particles']=1
        with self.assertRaises(ValueError):validate_gpu_phase_counts(changed,'steady_all_sources',4)
        transient=[dict(r,residual_particles=0 if i==0 else 2,residual_batches=0 if i==0 else 1,
                        phase_counts={'fresh':(i+1)*10,'residual':i*2}) for i,r in enumerate(rows)]
        self.assertEqual(validate_gpu_phase_counts(transient,'transient_all_sources',4)['residual_total'],6)
        transient[2]['phase_counts']['fresh']=999
        with self.assertRaises(ValueError):validate_gpu_phase_counts(transient,'transient_all_sources',4)

if __name__=='__main__':unittest.main()
