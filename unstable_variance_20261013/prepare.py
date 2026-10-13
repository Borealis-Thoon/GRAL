from pathlib import Path
import argparse,hashlib,io,json,os,shutil,subprocess,zipfile
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--repository',type=Path,required=True);p.add_argument('--prepare-only',action='store_true');a=p.parse_args();manifest=json.loads((R/'source_manifest.json').read_text());raw=subprocess.check_output(['git','-C',str(a.repository),'archive','--format=zip',manifest['base'],'src'])
for v in ['met_baseline','met_variance']:
 target=R/'sources'/v;target.mkdir(parents=True,exist_ok=False)
 with zipfile.ZipFile(io.BytesIO(raw)) as z:z.extractall(target)
 if v=='met_variance':
  for name in ['Zeitschleife.cs','Zeitschleife_nonsteadystate.cs']:
   f=target/'src'/name;s=f.read_text();old='            float blh = Program.BdLayHeight;';assert s.count(old)==1;s=s.replace(old,old+'\n            float cachedObLength = float.NaN, cachedUstern = float.NaN, cachedVariance = 0;')
   expr='Program.Pow2(Ustern) * Program.Pow2(1.15F + 0.1F * MathF.Pow(blh / (-ObLength), 0.67F)) * Program.Pow2(Program.StdDeviationW)';old='                        varw = '+expr+';';assert s.count(old)==1;s=s.replace(old,'                        if (ObLength != cachedObLength || Ustern != cachedUstern)\n                        {\n                            cachedVariance = '+expr+';\n                            cachedObLength = ObLength;\n                            cachedUstern = Ustern;\n                        }\n                        varw = cachedVariance;');f.write_bytes(s.replace('\n','\r\n').encode('utf-8'))
 actual={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((target/'src').iterdir()) if f.is_file()};assert actual==manifest['hashes'][v],v
print('[PASS] exact source hashes',flush=True)
if a.prepare_only:raise SystemExit
out=R/'reproduced_compiled';out.mkdir();env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(out/'cache'),DOTNET_CLI_UI_LANGUAGE='en',DOTNET_NOLOGO='1');dotnet=env.get('GRAL_DOTNET',shutil.which('dotnet') or 'dotnet')
for v in ['met_baseline','met_variance','fixture']:
 src=R/'sources'/v/'src'
 if v=='fixture':
  src=R/'fixture';shutil.copytree(R/'sources/met_variance/src',src,ignore=shutil.ignore_patterns('bin','obj'));shutil.copy2(R/'VarianceReview.cs',src/'VarianceReview.cs')
 dest=R/'bin'/v;cmd=[dotnet,'build',str(src/'GRAL.csproj'),'-c','Release','-o',str(dest),'-t:Rebuild','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true']
 if v=='fixture':cmd+=['/p:StartupObject=GRAL_2001.VarianceReview']
 q=subprocess.run(cmd,env=env,capture_output=True,timeout=120);log=(q.stdout+q.stderr).decode('utf-8','replace');(out/(v+'.log')).write_text(log);assert q.returncode==0 and '0 Warning(s)' in log and '0 Error(s)' in log,log
subprocess.run([dotnet,str(R/'bin/fixture/GRAL.dll'),str(out/'compiled.json')],env=env,check=True,timeout=120)
print('[PASS] build and extracted-expression checks',flush=True)
