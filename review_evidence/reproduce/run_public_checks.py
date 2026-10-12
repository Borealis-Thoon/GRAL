"""Reproduce the public review checks in a fresh writable working copy."""
from __future__ import annotations
import argparse,contextlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
from validate_main import BASE,SCOPES,inspect,process,save,source_hashes

VARIANTS=[BASE,*SCOPES]
def inspect_public(package):
    manifest=inspect(package,VARIANTS,SCOPES)
    for variant in ('nan_guard_state','nan_guard_storage'):
        expected={r['path']:r['sha256'] for r in json.loads((package/'qa'/f'{variant}_source_manifest.json').read_text(encoding='utf-8-sig'))['source_files']}
        assert manifest['source_files'][variant]==expected
    opt=json.loads((package/'qa/opt1_source_manifest.json').read_text(encoding='utf-8-sig'))
    for variant in ('opt1_stack','opt1_vertical'):
        assert manifest['source_files'][variant]=={'src/'+r['path']:r['candidate_sha256'] for r in opt[variant]}
    count=0
    for path in package.rglob('*.json'):
        if any(part in ('bin','obj','cache','work') for part in path.relative_to(package).parts):continue
        json.loads(path.read_text(encoding='utf-8-sig'));count+=1
    return dict(status='pass',source_files_verified=425,json_files_parsed=count,source_manifest=manifest)

def neighbors():
    if os.name=='nt':
        command="Get-CimInstance Win32_Process -Filter \"Name='dotnet.exe' OR Name='GRAL.exe' OR Name='GRAMM.exe'\" | Select-Object Name,ProcessId | ConvertTo-Json -Compress"
        result=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        data=json.loads(result.stdout) if result.stdout.strip() else []
        return data if isinstance(data,list) else [data]
    rows=[]
    if Path('/proc').is_dir():
        for path in Path('/proc').glob('[0-9]*/comm'):
            try:name=path.read_text().strip().lower()
            except (OSError,PermissionError):continue
            if name in ('dotnet','gral','gramm'):rows.append(dict(name=name,pid=int(path.parent.name)))
    return rows

@contextlib.contextmanager
def timing_lock(path):
    path.parent.mkdir(parents=True,exist_ok=True);handle=path.open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            handle.seek(0)
            if not handle.read(1):handle.write(b'0');handle.flush()
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:handle.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--run-dir',type=Path)
    parser.add_argument('--mode',choices=['inspect','nan','opt1','benchmark','paired','profile'],required=True)
    parser.add_argument('--dotnet',default='dotnet');parser.add_argument('--execute',action='store_true');parser.add_argument('--timing-lock',type=Path)
    args=parser.parse_args();package=args.package_root.resolve();checked=inspect_public(package)
    if args.mode=='inspect':print(json.dumps({k:v for k,v in checked.items() if k!='source_manifest'}));return
    if not args.execute or not args.run_dir:raise ValueError('Checks require --execute and a fresh --run-dir')
    run=args.run_dir.resolve()
    if run.exists() or run==package or package in run.parents:raise ValueError('Use a fresh run folder outside the public package')
    dotnet=str(Path(args.dotnet).resolve()) if Path(args.dotnet).is_file() else shutil.which(args.dotnet)
    if not dotnet:raise FileNotFoundError('A verified .NET 10 SDK executable is required')
    shutil.copytree(package,run)
    for name in ('logs','tmp','cache'):(run/name).mkdir(exist_ok=True)
    env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(run/'cache/dotnet'),NUGET_PACKAGES=str(run/'cache/nuget'),TEMP=str(run/'tmp'),TMP=str(run/'tmp'),DOTNET_CLI_UI_LANGUAGE='en',DOTNET_NOLOGO='1',DOTNET_CLI_USE_MSBUILD_SERVER='0',MSBUILDDISABLENODEREUSE='1')
    started=time.perf_counter();pids=[];operations=[];dlls={}
    def invoke(command,label,seconds=180):
        remaining=900-(time.perf_counter()-started)
        if remaining<=0:raise TimeoutError('Whole reproduction window exceeded 900 seconds')
        code,out,err=process(command,run,env,min(seconds,remaining),pids);text=out+err;(run/'logs'/f'public_{label}.log').write_text(text,encoding='utf-8')
        if code:raise RuntimeError(label+' failed; inspect its log')
        operations.append(dict(label=label,exit_code=code));return text
    def build(project,label):
        text=invoke([dotnet,'build',str(project),'-c','Release','-t:Rebuild','-v:minimal','--nologo','/p:TreatWarningsAsErrors=true','/p:UseSharedCompilation=false','/nodeReuse:false'],label)
        warnings=re.search(r'(\d+) Warning\(s\)',text);errors=re.search(r'(\d+) Error\(s\)',text)
        if not warnings or not errors or int(warnings.group(1)) or int(errors.group(1)):raise AssertionError('Strict build is not zero warning/error: '+label)
        found=[p for p in (project.parent/'bin/Release/net10.0').glob('*.dll') if p.stem.lower()==project.stem.lower() or (project.stem=='GRAL' and p.stem.lower()=='gral')]
        if len(found)!=1:raise AssertionError('Built DLL name is ambiguous: '+str(project))
        return found[0]
    try:
        if args.mode=='profile':
            invoke([sys.executable,'-X','utf8','-B',str(run/'reproduce/profile_opt1_hits.py'),'--package-root',str(run)],'profile_prepare',60)
            invoke([sys.executable,'-X','utf8','-B',str(run/'reproduce/validate_main.py'),'--package-root',str(run),'--run-dir',str(run/'profile_main'),'--dotnet',dotnet,'--variants','opt1_vertical_profile','--scope-file',str(run/'qa/opt1_profile_scope.json'),'--cases','terrain_hot_n100','terrain_stable_building_n1000','--skip-restart','--execute'],'profile_main',850)
            invoke([sys.executable,'-X','utf8','-B',str(run/'reproduce/profile_opt1_hits.py'),'--package-root',str(run),'--summarize',str(run/'profile_main')],'profile_summary',60)
        else:
            selected=[BASE,'nan_guard_state','nan_guard_storage'] if args.mode=='nan' else [BASE,'opt1_stack','opt1_vertical']
            if args.mode=='nan':
                for name in ('nan_guard_extract_fixture.py','nan_guard_extract_wet_fixture.py','nan_guard_extract_report_fixture.py','nan_guard_extract_expiry_fixture.py'):
                    invoke([sys.executable,'-X','utf8','-B',str(run/'reproduce'/name)],name.removesuffix('.py'),60)
            for variant in selected:dlls[variant]=build(run/'source'/variant/'src/GRAL.csproj',variant+'_build')
            if args.mode=='nan':
                fixture=build(run/'tests/nan_guard/NaNGuardFixture.csproj','nan_fixture_build')
                invoke([dotnet,str(fixture),*(str(dlls[v]) for v in selected),str(run/'qa/nan_guard_component_summary.json')],'nan_component',180)
            elif args.mode=='opt1':
                fixture=build(run/'tests/opt1/fixture/Opt1Fixture.csproj','opt1_fixture_build')
                invoke([dotnet,str(fixture),'correctness',*(str(dlls[v]) for v in selected),str(run/'qa/opt1_correctness.json')],'opt1_component',180)
            else:
                kind='benchmark' if args.mode=='benchmark' else 'paired';project='Opt1Benchmark' if kind=='benchmark' else 'Opt1PairedBenchmark'
                fixture=build(run/f'tests/opt1/{kind}/{project}.csproj',kind+'_build')
                invoke([dotnet,'build-server','shutdown'],'build_server_shutdown',60)
                lock=args.timing_lock.resolve() if args.timing_lock else run/'tmp/public_timing.lock'
                with timing_lock(lock):
                    before=neighbors()
                    if before:raise RuntimeError('Active GRAL/GRAMM/dotnet processes prevent isolated timing: '+repr(before))
                    arguments=[str(dlls[v]) for v in selected] if kind=='benchmark' else [str(dlls[BASE]),str(dlls['opt1_vertical'])]
                    invoke([dotnet,str(fixture),*arguments,str(run/'qa'/f'opt1_{kind}.json')],kind,180)
                    save(run/'qa'/f'public_{kind}_isolation.json',dict(status='pass',timing_lock=str(lock),neighbors_before=before,neighbors_after=neighbors(),scope='Freshly compiled DLLs; optional shared timing lock; no active GRAL/GRAMM/dotnet before measured fixture.'))
        final=inspect_public(run)
        assert final['source_manifest']['source_files']==checked['source_manifest']['source_files']
        save(run/'qa/public_reproduction_receipt.json',dict(status='pass',mode=args.mode,source_files_verified=425,operations=operations,elapsed_s=time.perf_counter()-started,process_ownership=pids,limits=['These are new reproduction outputs. Original measured binary hashes and machine timings are provenance, not expected reproduction constants.']))
        print('[PASS] '+args.mode)
    except BaseException as exc:
        save(run/'qa/public_reproduction_failure.json',dict(status='fail',mode=args.mode,error=str(exc),operations=operations,process_ownership=pids));raise
if __name__=='__main__':main()
