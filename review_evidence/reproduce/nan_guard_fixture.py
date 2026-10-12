from pathlib import Path
import argparse,hashlib,json,os,subprocess,time

def run_fixture(job,dotnet,build_sources=True):
    job=Path(job).resolve();env=os.environ.copy()
    for name,value in {'DOTNET_CLI_HOME':job/'cache/dotnet_nan_guard','NUGET_PACKAGES':job/'cache/nuget','TEMP':job/'tmp','TMP':job/'tmp'}.items():env[name]=str(value)
    env.update(DOTNET_CLI_UI_LANGUAGE='en-US',DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1')
    operations=[];started=time.monotonic()
    def process(cmd,label):
        proc=subprocess.Popen([str(x) for x in cmd],cwd=job,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        try:raw,_=proc.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
            proc.communicate();raise RuntimeError(label+' timed out')
        text=raw.decode('utf-8',errors='replace');(job/'logs'/('nan_guard_'+label+'.log')).write_text(text,encoding='utf-8')
        if proc.returncode:raise RuntimeError(label+' failed; inspect the log')
        operations.append({'label':label,'exit_code':proc.returncode,'strict_build':label.endswith('build'),'zero_warning_error':('0 Warning(s)' in text and '0 Error(s)' in text) if label.endswith('build') else None})
    for variant in ['nan_guard_state','nan_guard_storage']:
        meta=json.loads((job/'qa'/f'{variant}_source_manifest.json').read_text('utf-8'))
        for f in meta['source_files']:
            path=job/'source'/variant/f['path']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=f['sha256']:raise RuntimeError('Source differs: '+str(path))
    for script in ['nan_guard_extract_fixture.py','nan_guard_extract_wet_fixture.py','nan_guard_extract_report_fixture.py','nan_guard_extract_expiry_fixture.py']:
        process([os.sys.executable,'-X','utf8','-B',job/'reproduce'/script,],script.removesuffix('.py'))
    if build_sources:
        for variant in ['warning_free_baseline','nan_guard_state','nan_guard_storage']:
            process([dotnet,'build',job/'source'/variant/'src/GRAL.csproj','-c','Release','-t:Rebuild','-v:minimal','--nologo','/p:TreatWarningsAsErrors=true'],variant+'_build')
    process([dotnet,'build',job/'tests/nan_guard/NaNGuardFixture.csproj','-c','Release','-t:Rebuild','-v:minimal','--nologo','/p:TreatWarningsAsErrors=true'],'fixture_build')
    binaries=[job/'source'/v/'src/bin/Release/net10.0/GRAL.dll' for v in ['warning_free_baseline','nan_guard_state','nan_guard_storage']]
    process([dotnet,job/'tests/nan_guard/bin/Release/net10.0/NaNGuardFixture.dll',*binaries,job/'qa/nan_guard_component_summary.json'],'component')
    meta={'status':'pass','operations':operations,'elapsed_seconds':time.monotonic()-started,'main_runs':0,'source_sha_verified':170,'scope':'Component-only reproduction. Main normal-condition validation is performed by the separate common runner.'}
    (job/'qa/nan_guard_fixture_reproduction.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print('[PASS] nan_guard_component')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,default=Path(__file__).resolve().parent.parent);p.add_argument('--dotnet',default=r'C:\Program Files\dotnet\dotnet.exe');p.add_argument('--skip-source-builds',action='store_true')
    a=p.parse_args();run_fixture(a.job,a.dotnet,not a.skip_source_builds)
