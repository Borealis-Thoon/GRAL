"""Build the reconstructed sources and run the bounded component checks."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,sys,time
from validate_main import process

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-root',type=Path,required=True)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--dotnet',default='dotnet')
    args=parser.parse_args();package=args.package_root.resolve();run=args.run_dir.resolve()
    if run.exists():raise FileExistsError('Use a new component run directory')
    receipt=json.loads((package/'qa/source_reconstruction.json').read_text(encoding='utf-8'))
    for variant,meta in receipt['variants'].items():
        for relative,expected in meta['source_files'].items():
            if hashlib.sha256((package/'source'/variant/relative).read_bytes()).hexdigest()!=expected:raise AssertionError('Prepared source changed')
    run.mkdir(parents=True)
    for folder in ['qa','logs','tmp','cache','tests','reproduce']:(run/folder).mkdir()
    for variant in ['upstream_current','nan_guard_state','nan_guard_storage','pr62','pr63']:
        target='warning_free_baseline' if variant=='upstream_current' else variant
        shutil.copytree(package/'source'/variant/'src',run/'source'/target/'src')
    for name,folder in [('common','nan_guard'),('state_boundaries','state_boundaries'),('storage','storage'),('residual','residual')]:shutil.copytree(package/'reproduce'/name,run/'tests'/folder)
    for f in (package/'reproduce/extractors').glob('*.py'):shutil.copy2(f,run/'reproduce'/f.name)
    generated={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in (run/'tests/nan_guard').glob('Extracted*.cs')}
    env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(run/'cache/dotnet'),NUGET_PACKAGES=str(run/'cache/nuget'),TEMP=str(run/'tmp'),TMP=str(run/'tmp'),DOTNET_CLI_UI_LANGUAGE='en',DOTNET_NOLOGO='1')
    dotnet=Path(shutil.which(args.dotnet) or args.dotnet).resolve()
    if not dotnet.is_file():raise FileNotFoundError('Verified .NET executable required')
    started=time.monotonic();pids=[];builds={}
    def execute(args,label):
        remaining=900-(time.monotonic()-started)
        if remaining<=0:raise TimeoutError('Component run exceeded 15 minutes')
        code,out,err=process(list(map(str,args)),run,env,min(180,remaining),pids)
        (run/'logs'/(label+'.log')).write_text(out+err,encoding='utf-8')
        if code:raise RuntimeError(label+' failed; inspect its log')
        return out+err
    for name in ['nan_guard_extract_fixture.py','nan_guard_extract_wet_fixture.py','nan_guard_extract_report_fixture.py','nan_guard_extract_expiry_fixture.py']:
        execute([sys.executable,'-X','utf8','-B',run/'reproduce'/name],name)
    for name,expected in generated.items():
        if hashlib.sha256((run/'tests/nan_guard'/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=expected:raise AssertionError('Extracted source block changed: '+name)
    def build(project,label):
        log=execute([dotnet,'build',project,'-c','Release','-t:Rebuild','-v:minimal','--nologo','/p:TreatWarningsAsErrors=true'],label)
        if not re.search(r'\b0 Warning\(s\)',log) or not re.search(r'\b0 Error\(s\)',log):raise AssertionError('Nonzero or missing strict build result')
        builds[label]={'warnings':0,'errors':0}
    variants=['warning_free_baseline','nan_guard_state','nan_guard_storage','pr62','pr63']
    for name in variants:build(run/'source'/name/'src/GRAL.csproj',name+'_build')
    projects={'nan_guard':'NaNGuardFixture','state_boundaries':'StateBoundaries','storage':'StorageReview','residual':'DraftChecks'}
    for name,project in projects.items():build(run/'tests'/name/(project+'.csproj'),name+'_build')
    dll=lambda name:run/'source'/name/'src/bin/Release/net10.0/GRAL.dll'
    fixture=lambda name:run/'tests'/name/'bin/Release/net10.0'/(projects[name]+'.dll')
    execute([dotnet,fixture('nan_guard'),dll('warning_free_baseline'),dll('nan_guard_state'),dll('nan_guard_storage'),run/'qa/common.json'],'common')
    execute([dotnet,fixture('state_boundaries'),dll('nan_guard_state'),run/'qa/state_boundaries.json'],'state_boundaries')
    execute([dotnet,fixture('storage'),dll('warning_free_baseline'),dll('nan_guard_storage'),run/'qa/storage.json'],'storage')
    for name in ['pr62','pr63']:execute([dotnet,fixture('residual'),dll(name),run/'qa'/(name+'.json')],name)
    results={name:json.loads((run/'qa'/(name+'.json')).read_text(encoding='utf-8')) for name in ['common','state_boundaries','storage','pr62','pr63']}
    if any(result.get('status')!='pass' for result in results.values()):raise AssertionError('A fixture failed')
    counts={name:result.get('checks_passed',result.get('checks')) for name,result in results.items()}
    expected={'common':1917,'state_boundaries':98325,'storage':16314,'pr62':10,'pr63':62}
    if counts!=expected:raise AssertionError('Fixture check counts differ: '+repr(counts))
    (run/'qa/component_reproduction.json').write_text(json.dumps({'status':'pass','builds':builds,'check_counts':counts,'extracted_blocks_match':True,'elapsed_s':time.monotonic()-started,'scope':'Component tests only. Mid-step guard paths use freshly extracted production blocks and fixture facades; initial entry and storage tests call actual DLL methods.'},indent=2),encoding='utf-8')
    (run/'qa/process_ownership.json').write_text(json.dumps(pids,indent=2),encoding='utf-8')
    print('[PASS] '+repr(counts))
if __name__=='__main__':main()
