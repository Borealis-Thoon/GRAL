"""Check Main input/output protocol and validator rejection paths, without GRAL execution."""
import importlib.util,json,math,os,struct,sys,tempfile,zipfile
from pathlib import Path
job=Path(__file__).resolve().parents[2];sys.path.insert(0,str(job/'reproduce'))
import main_inputs as inp
import validate_main as check
results=[]
with tempfile.TemporaryDirectory(prefix='main_harness_',dir=job/'tmp') as scratch:
    scratch=Path(scratch);case=dict(id='harness',nx=10,ny=10,dx=20,dy=20,slices=1,mode='stationary',receptors=False,deposition=False,odour=False)
    def fixture(label,values,header=(-3,0,0,20.,20.,10,10),members=2,receptor=None):
        folder=scratch/label;folder.mkdir()
        with zipfile.ZipFile(folder/'00001.grz','w') as archive:
            for index in range(members):archive.writestr(f'00001-{index+1}.con',struct.pack('<iiiffii',*header)+struct.pack('<'+str(len(values))+'f',*values))
        if receptor is not None:(folder/'ReceptorConcentrations.dat').write_bytes(receptor)
        return folder
    good=[1.]+[0.]*99
    probes=[('valid_dense_v03',good,{},True),('reject_nan',[float('nan')]+[0.]*99,{},False),('reject_infinity',[float('inf')]+[0.]*99,{},False),('reject_negative',[-1.]+[0.]*99,{},False),('reject_all_zero',[0.]*100,{},False),('reject_wrong_header',good,{'header':(-2,0,0,20.,20.,10,10)},False),('reject_wrong_origin',good,{'header':(-3,1,0,20.,20.,10,10)},False),('reject_wrong_resolution',good,{'header':(-3,0,0,10.,20.,10,10)},False),('reject_wrong_payload_width',[1.]*99,{},False),('reject_missing_source_group',good,{'members':1},False),('valid_utf16_receptor',good,{'receptor':'Header\n1\t2\n'.encode('utf-16')},True),('valid_utf8_receptor',good,{'receptor':'Header\n1\t2\n'.encode('utf-8')},True),('reject_nan_receptor',good,{'receptor':'Header\nNaN\t2\n'.encode('utf-16')},False)]
    for label,values,kw,wanted in probes:
        folder=fixture(label,values,**kw)
        try:payload,counts,nvalues,grids=check.outputs(folder,case,[1]);accepted=True
        except AssertionError:accepted=False
        assert accepted==wanted,(label,accepted,wanted)
        results.append(dict(check=label,pass_status=True))
with tempfile.TemporaryDirectory(prefix='main_watchdog_',dir=job/'tmp') as scratch:
    owned=[]
    try:check.process([sys.executable,'-c','import time; time.sleep(5)'],Path(scratch),os.environ.copy(),.2,owned)
    except TimeoutError:pass
    else:raise AssertionError('Owned PID watchdog did not time out')
    assert len(owned)==1 and owned[0]['timed_out'] and owned[0]['exit_code'] is not None
    results.append(dict(check='owned_pid_watchdog_terminates_timed_out_child',pass_status=True))
prepared=json.loads((job/'qa/main_preparation.json').read_text(encoding='utf-8-sig'))
assert prepared['conditions']==18
for case in inp.cases():
    folder=job/'inputs/synthetic_cases'/case['id'];manifest=json.loads((folder/'input_manifest.json').read_text(encoding='utf-8-sig'))
    for name,value in manifest.items():assert inp.sha(folder/name)==value['sha256']
    grid=(folder/'GRAL.geb').read_text().splitlines();controls=(folder/'in.dat').read_text().splitlines()
    assert list(map(float,grid[7:11]))==[0,200,0,200]
    assert int(grid[3])*float(grid[0])==200 and int(grid[4])*float(grid[1])==200
    assert len(controls[9].split())==int(grid[5])
    if case['terrain']:
        lines=(folder/'ggeom.asc').read_text().splitlines();n,ny,nz=map(int,lines[0].split()[:3])
        assert (n,ny,nz)==(20,20,12) and len(lines)==15
        assert len(lines[0].split())==3+(n+1)+(ny+1)+(nz+1)
        assert len(lines[1].split())==n*ny and len(lines[8].split())==n*ny*nz
        assert len(lines[-1].split())==(n+1)*(ny+1)*(nz+1)
        for wnd in folder.glob('*.wnd'):
            raw=wnd.read_bytes();assert struct.unpack_from('<5i',raw)==(-1,n,ny,nz,20)
            assert len(raw)==20+6*n*ny*nz
    results.append(dict(check='input_manifest_and_protocol_'+case['id'],pass_status=True))
summary=dict(status='pass',checks_passed=len(results),checks=results,main_model_execution=False,limits=['Harness protocol checks complement real Main regression; they do not validate physical model equations.'])
inp.save(job/'qa/main_harness_checks.json',summary)
print('[HARNESS] '+str(len(results))+' pass')
