from pathlib import Path
import subprocess,os,re,json,time
B=Path(__file__).resolve().parent;R=B/'build_logs';R.mkdir(exist_ok=True)
env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(B/'cache'),TEMP=str(B/'tmp'),TMP=str(B/'tmp'),DOTNET_NOLOGO='1',DOTNET_CLI_UI_LANGUAGE='en');(B/'tmp').mkdir(exist_ok=True)
records=[]
for v in ['f64','parallel','component']:
 p=B/'component/Component.csproj' if v=='component' else B/'sources'/v/'src/GRAL.csproj'
 r=subprocess.run([r'C:\Program Files\dotnet\dotnet.exe','build',str(p),'-c','Release','-t:Rebuild','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true'],env=env,capture_output=True,timeout=180)
 s=(r.stdout+r.stderr).decode('utf-8',errors='replace');(R/(v+'.log')).write_text(s);assert r.returncode==0 and re.search(r'\b0 Warning\(s\)',s) and re.search(r'\b0 Error\(s\)',s),s
 records.append(dict(variant=v,status='pass',warnings=0,errors=0));print('[BUILD]',v,flush=True)
(B/'build_summary.json').write_text(json.dumps(records,indent=2)+'\n')
