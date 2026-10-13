from pathlib import Path
import subprocess,sys,os,re,json,time,hashlib
ROOT=Path(__file__).resolve().parent;DOTNET=Path(os.environ.get("DOTNET_EXE",r"C:\Program Files\dotnet\dotnet.exe"));run=ROOT/'component_final';run.mkdir();(run/'tmp').mkdir();env=os.environ.copy();env.update(TEMP=str(run/'tmp'),TMP=str(run/'tmp'),DOTNET_CLI_HOME=str(run/'dotnet_home'),NUGET_PACKAGES=str(run/'nuget'),DOTNET_NOLOGO='1',DOTNET_CLI_UI_LANGUAGE='en');start=time.perf_counter()
def save(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def process(cmd,cwd,limit=180):
 p=subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,capture_output=True,timeout=limit);text=(p.stdout+p.stderr).decode('utf-8','replace');assert p.returncode==0,text;return text
builds={}
for name,project in [('f64',ROOT/'source/f64/src/GRAL.csproj'),('candidate',ROOT/'repo/src/GRAL.csproj'),('fixture',ROOT/'fixture/Fixture.csproj'),('probe_f64',ROOT/'probe/f64/src/GRAL.csproj'),('probe_candidate',ROOT/'probe/candidate/src/GRAL.csproj'),('driver_fixture',ROOT/'driver_fixture/DriverFixture.csproj')]:
 text=process([DOTNET,'build',project,'-c','Release','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true'],project.parent);(run/f'build_{name}.log').write_text(text,encoding='utf-8');assert '0 Warning(s)' in text and '0 Error(s)' in text;builds[name]=dict(warnings=0,errors=0);print('[BUILD]',name,flush=True)
fixtures=[]
for setting in ['0','1','-1','invalid','999']:
 d=run/('fixture_'+setting);d.mkdir();text=process([DOTNET,ROOT/'fixture/bin/Release/net10.0/Fixture.dll',ROOT/'repo/src/bin/Release/net10.0/GRAL.dll',setting],d,30);(d/'console.log').write_text(text,encoding='utf-8');record=json.loads(re.search(r'\[FIXTURE\] (.+)',text)[1]);expected=268435456 if setting=='999' else 1048576 if setting=='1' else 0;assert record['budget_bytes']==expected;fixtures.append(dict(setting=setting,**record));print('[FIXTURE]',setting,record['assertions'],flush=True)
drivers=[]
for variant,setting in [('f64','0'),('candidate','0'),('candidate','1')]:
 for workers in [1,4,24]:
  for lower,upper in [(1,101),(7,108),(1,3001)]:
   key=f'{variant}_{setting}_{workers}_{lower}_{upper}';d=run/key;d.mkdir();text=process([DOTNET,ROOT/'driver_fixture/bin/Release/net10.0/DriverFixture.dll',ROOT/'probe'/variant/'src/bin/Release/net10.0/GRAL.dll',setting,workers,lower,upper],d,30);(d/'console.log').write_text(text,encoding='utf-8');record=json.loads(re.search(r'\[DRIVER\] (.+)',text)[1]);drivers.append(dict(variant=variant,setting=setting,**record));print('[DRIVER]',key,'pass',flush=True)
result=dict(status='pass',builds=builds,fixtures=fixtures,driver_probes=drivers,driver_probe_executions=len(drivers),elapsed_s=time.perf_counter()-start,driver_scope='Real ParallelParticleDriver with trajectory body replaced in separate diagnostic copies by exactly-once and dyadic-contribution probes. No timings are used as engine performance evidence.')
save(run/'summary.json',result);print('[PASS] component suite',flush=True)
