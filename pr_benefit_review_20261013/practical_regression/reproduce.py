from pathlib import Path
import argparse,hashlib,json,math,os,re,shutil,struct,subprocess,time,zipfile
P=Path(__file__).resolve().parent
a=argparse.ArgumentParser();a.add_argument('--work',type=Path,required=True);a.add_argument('--prepare-only',action='store_true');a.add_argument('--dotnet',default='dotnet');args=a.parse_args()
W=args.work.resolve();W.mkdir(parents=True,exist_ok=False)
manifest=json.loads((P/'source_manifest.json').read_text());previous=json.loads((P/'validation.json').read_text())
for variant,files in manifest['hashes'].items():
 for name,expected in files.items():
  source=P/'source'/variant/name;assert hashlib.sha256(source.read_bytes()).hexdigest()==expected,name
  target=W/'source'/variant/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
if args.prepare_only:print('[SOURCE]',sum(map(len,manifest['hashes'].values())),'hashes verified');raise SystemExit(0)
env=os.environ.copy();(W/'tmp').mkdir();env.update(TEMP=str(W/'tmp'),TMP=str(W/'tmp'),DOTNET_CLI_HOME=str(W/'dotnet'),DOTNET_CLI_UI_LANGUAGE='en',DOTNET_NOLOGO='1');env.pop('GRAL_WORKER_CONCENTRATION_MB',None)
def command(argv,d,timeout):
 t=time.perf_counter();p=subprocess.Popen(argv,cwd=d,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:out,err=p.communicate(timeout=timeout)
 except subprocess.TimeoutExpired:
  p.kill();p.communicate();raise
 assert p.returncode==0,(argv,out[-2000:],err[-2000:])
 return (out+err).decode('utf-8','replace'),time.perf_counter()-t
for variant in manifest['hashes']:
 d=W/'source'/variant/'src';out,_=command([args.dotnet,'build',str(d/'GRAL.csproj'),'-c','Release','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true'],W,180)
 (W/f'build_{variant}.log').write_text(out,encoding='utf-8');assert '0 Warning(s)' in out and '0 Error(s)' in out
records=[];reference={};pairs=0;started=time.perf_counter()
for entry in previous['records']:
 assert time.perf_counter()-started<600
 case=entry['case'];variant=entry['variant'];version=variant.split('_')[0];rep=entry['repeat']
 d=W/'runs'/f'{case}_{variant}_{rep}';shutil.copytree(P/'inputs'/(case+('_extra' if variant.endswith('_extra') else '')),d)
 out,elapsed=command([args.dotnet,str(W/'source'/version/'src/bin/Release/net10.0/GRAL.dll'),str(d)],d,60)
 (d/'console.log').write_text(out,encoding='utf-8');assert 'GRAL simulations finished at:' in (d/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig')
 problem=d/'Problemreport_GRAL.txt';assert not problem.exists() or not problem.read_text(encoding='utf-8-sig').strip()
 hashes=[];values=[]
 for f in sorted(d.glob('*.grz')):
  with zipfile.ZipFile(f) as z:
   for name in sorted(z.namelist()):
    raw=z.read(name);hashes.append(hashlib.sha256(raw).hexdigest());values.extend(struct.unpack('<'+str((len(raw)-28)//4)+'f',raw[28:]))
 assert len(hashes)==entry['groups']*entry['situations'] and all(math.isfinite(v) and v>=0 for v in values) and sum(values)>0
 if case in reference:assert hashes==reference[case],(case,variant);pairs+=len(hashes)
 else:reference[case]=hashes
 allocated=list(map(int,re.findall(r'Using a total of (\d+) particles',out)));assert allocated==[entry['allocated_particles']]
 fresh=re.findall(r'Summarized emission rates per source group in kg\s*\n[^\n]*SG:[^\n]*\n([^\n]+)',out);assert fresh
 actual=list(map(float,fresh[-1].split()));expected=json.loads((d/'synthetic_case.json').read_text())['expected_fresh_mass_kg']
 assert len(actual)==len(expected) and all(math.isclose(x,y,rel_tol=.006,abs_tol=.00011) for x,y in zip(actual,expected))
 records.append(dict(entry,wall_s=elapsed));print('[MAIN]',len(records),case,variant,flush=True)
(W/'results.json').write_text(json.dumps(dict(status='pass',main_runs=len(records),identical_payload_pairs=pairs,records=records),indent=2)+'\n',encoding='utf-8')
print('[PASS]',len(records),'runs;',pairs,'identical payload comparisons')
