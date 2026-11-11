"""Judge the RTX 5080 CUDA plan (plan_cuda.json) run by run against the expectations of the CUDA inventory.
Usage: analyze_cuda_runs.py <cuda_runs dir> <suite dir> <out json>
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

RUNS, SUITE, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
REF_B00 = Path(r'D:\INU_Modeling_Work\jobs\20261103_gral_gpu_final_validation\runs\final448_001\targets\B00_fixed00_gpu\Computation')


def info(case, label):
    p = RUNS / case / label / 'run_info.json'
    return json.loads(p.read_text(encoding='utf8')) if p.exists() else None


def diff(a, b):
    keys = set(a) | set(b)
    return sorted(k for k in keys if a.get(k) != b.get(k))


def metrics(case, label):
    """Cumulative runtime metrics of the run: result_server_metrics of the last situation (as a one-element list)."""
    p = RUNS / case / label / 'logs' / 'gpu_metrics.jsonl'
    if not p.exists():
        return []
    lines = [json.loads(l) for l in p.read_text(encoding='utf8').splitlines() if l.strip()]
    return [lines[-1].get('result_server_metrics', {})] if lines else []


def grz_members(comp):
    res = {}
    for p in sorted(comp.glob('*.grz')):
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                res[p.name + '/' + n] = hashlib.sha256(z.read(n)).hexdigest()
    return res


R = {}
# item 1: repeatability of the integer sums over repeats, launch shapes and watchdog launch sizing
C1 = ['frozen_B00_fixed00', 'transient_area_drydep', 'wet_nodrift', 'wet_drift_all', 'steady_pgt_terrain_primary', 'odour_all_sources',
      'transient_all_sources', 'tunnel_entrance', 'vertical_conc']
item1 = {}
for c in C1:
    base = info(c, 'r1')
    row = {'r1_rc': base['rc'], 'r1_outputs': len(base['outputs']), 'r1_fallback': base['fallback_lines']}
    for lab in ('r2', 'c4096b256', 'c1000', 'mk50', 'mk0'):
        i = info(c, lab)
        row[lab] = {'rc': i['rc'], 'fallback': len(i['fallback_lines']), 'differing': len(diff(base['outputs'], i['outputs']))}
    m = {lab: metrics(c, lab) for lab in ('r1', 'mk50', 'mk0')}
    row['launches'] = {lab: [x.get('kernel_launches') for x in v] for lab, v in m.items()}
    row['adaptive'] = {lab: [(x.get('adaptive_launch'), x.get('adaptive_part_min'), x.get('adaptive_part_max')) for x in v] for lab, v in m.items()}
    row['repro_flag'] = sorted({str(x.get('reproducible_sums')) for x in m['r1']})
    item1[c] = row
R['item1_repeatability'] = item1

# item 2: float sums (REPRO=0) on B00 against the 6057195 study reference, and atomic-order control
off1, off2 = info('frozen_B00_fixed00', 'off1'), info('frozen_B00_fixed00', 'off2')
ref = grz_members(REF_B00)
off1_grz = {k: v for k, v in off1['outputs'].items() if '.grz/' in k}
r1_grz = {k: v for k, v in info('frozen_B00_fixed00', 'r1')['outputs'].items() if '.grz/' in k}
R['item2_b00_float_sums'] = {
    'ref_members': len(ref), 'off1_members': len(off1_grz),
    'off1_vs_reference_differing': len(diff(ref, off1_grz)), 'off1_vs_off2_differing': len(diff(off1['outputs'], off2['outputs'])),
    'repro_r1_vs_reference_differing': len(diff(ref, r1_grz)),
    'off1_repro_flag': sorted({str(x.get('reproducible_sums')) for x in metrics('frozen_B00_fixed00', 'off1')}),
    'kernel_ms_off1': sum(x.get('kernel_device_ms', 0) for x in metrics('frozen_B00_fixed00', 'off1')),
    'kernel_ms_r1': sum(x.get('kernel_device_ms', 0) for x in metrics('frozen_B00_fixed00', 'r1')),
    'wall_off1': off1['wall_s'], 'wall_r1': info('frozen_B00_fixed00', 'r1')['wall_s']}
ctrl = {}
for c in ('wet_drift_all', 'steady_rot_receptors51'):
    a, b = info(c, 'off_c65536'), info(c, 'off_c4096')
    ctrl[c] = {'off_c65536_vs_off_c4096_differing': len(diff(a['outputs'], b['outputs'])), 'members': len(a['outputs'])}
    if c == 'steady_rot_receptors51':
        ctrl[c]['repro_r1_vs_c4096_differing'] = len(diff(info(c, 'r1')['outputs'], info(c, 'c4096')['outputs']))
R['item2_atomic_order_control'] = ctrl

# item 4: carry path (threshold 2^34) gives the same bytes; error 6 stops the run
carry = {}
for c in ('frozen_B00_fixed00', 'transient_area_drydep', 'wet_drift_all', 'steady_pgt_terrain_primary', 'odour_all_sources'):
    i = info(c, 'carry')
    carry[c] = {'rc': i['rc'], 'differing_vs_r1': len(diff(info(c, 'r1')['outputs'], i['outputs']))}
e6 = info('transient_area_drydep', 'err6')
carry['err6'] = {'rc': e6['rc'], 'fallback': e6['fallback_lines'][:2],
                 'stdout_tail': (RUNS / 'transient_area_drydep' / 'err6' / 'logs' / 'stdout.log').read_bytes().decode('utf8', 'replace')[-600:]}
R['item4_carry'] = carry

# item 5: CUBIN path
cub = {}
for c in ('frozen_B00_fixed00', 'wet_drift_all'):
    a, b = info(c, 'cubin1'), info(c, 'cubin2')
    cub[c] = {'rc': (a['rc'], b['rc']), 'device_line': a['device_line'], 'cubin1_vs_cubin2': len(diff(a['outputs'], b['outputs'])),
              'cubin1_vs_ptx_r1': len(diff(info(c, 'r1')['outputs'], a['outputs'])),
              'cache': [sorted({str(x.get('cache_status')) for x in metrics(c, lab)}) for lab in ('cubin1', 'cubin2')]}
R['item5_cubin'] = cub

# item 7 / 9: backend selection and startup fallback (transient_area; cpu_ref = CPU run with the same fixed seed)
cpu = info('transient_area', 'cpu_ref')
be = {}
for lab in ('be_default', 'be_cuda_spaces', 'be_nvidia', 'be_hip', 'be_hip_fb', 'dev5',
            'fb_repro2', 'fb_manifest', 'fb_nvrtc_empty', 'fb_block64', 'fb_maxkernel_abc', 'fb_old_runtime'):
    i = info('transient_area', lab)
    be[lab] = {'rc': i['rc'], 'device': i['device_line'], 'fallback': [l[:220] for l in i['fallback_lines'][:2]],
               'gpu_lines': [l[:200] for l in i.get('gpu_lines', [])[:3]],
               'outputs': len(i['outputs']), 'differing_vs_cpu': len(diff(cpu['outputs'], i['outputs'])),
               'differing_vs_default': len(diff(info('transient_area', 'be_default')['outputs'], i['outputs']))}
R['item7_9_backend_and_fallback'] = be

# item 11: SPECIALIZE ignored on CUDA
sb = info('transient_all_sources', 'spec_bogus')
R['item11_specialize'] = {'rc': sb['rc'], 'fallback': sb['fallback_lines'], 'differing_vs_r1': len(diff(info('transient_all_sources', 'r1')['outputs'], sb['outputs'])),
                          'specialization_keys': sorted({k for x in metrics('transient_all_sources', 'spec_bogus') for k in x if 'special' in k})}
# item 15: GPU / CPU fallback / GPU in one run
a, b = info('neg_eki_calm', 'r1'), info('neg_eki_calm', 'r2')
R['item15_mixed'] = {'rc': (a['rc'], b['rc']), 'fallback': a['fallback_lines'][:1], 'r1_vs_r2': len(diff(a['outputs'], b['outputs']))}
OUT.write_text(json.dumps(R, indent=1, ensure_ascii=False), encoding='utf8')
print('written')
