from pathlib import Path
import argparse,hashlib,io,itertools,json,math,os,shutil,struct,subprocess,tarfile,zipfile
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
W=a.work.resolve();W.mkdir(parents=True,exist_ok=False);m=json.loads((ROOT/'source_manifest.json').read_text());old=json.loads((ROOT/'validation.json').read_text())
env=os.environ.copy();(W/'tmp').mkdir();env.update(DOTNET_CLI_UI_LANGUAGE='en',DOTNET_NOLOGO='1',DOTNET_CLI_HOME=str(W/'dotnet'),TEMP=str(W/'tmp'),TMP=str(W/'tmp'));env.pop('GRAL_WORKER_CONCENTRATION_MB',None)
def command(args,**kw):return subprocess.run(args,check=True,capture_output=True,env=env,timeout=180,**kw)
raw=command(['git','-C',str(a.repo.resolve()),'archive',m['upstream'],'src']).stdout
for variant in ['before','after']:
 d=W/variant;d.mkdir()
 with tarfile.open(fileobj=io.BytesIO(raw)) as t:
  for member in t.getmembers():
   if member.isfile():
    dest=(d/member.name).resolve();assert dest.is_relative_to(d);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(t.extractfile(member).read().decode('utf-8-sig').replace('\r\n','\n'),encoding='utf-8',newline='\n')
 command(['git','apply','--whitespace=nowarn',str(ROOT/f'{variant}.patch')],cwd=d)
 for name,expected in m['hashes'][variant].items():
  path=d/name;path.write_text(path.read_text(encoding='utf-8-sig'),encoding='utf-8',newline='\n')
  assert hashlib.sha256((d/name).read_bytes()).hexdigest()==expected,name
 if a.prepare_only:continue
 b=command(['dotnet','build',str(d/'src/GRAL.csproj'),'-c','Release','-v:minimal','--nologo','/p:TreatWarningsAsErrors=true'])
 (W/f'build_{variant}.log').write_bytes(b.stdout+b.stderr)
 assert b'0 Warning(s)' in b.stdout and b'0 Error(s)' in b.stdout
if a.prepare_only:
 print('[SOURCE]',sum(len(x) for x in m['hashes'].values()),'source hashes matched');raise SystemExit(0)
records=[];values={}
for case in old['cases']:
 for rep in range(5 if case['workers']>1 else 2):
  for variant in ['before','after']:
   d=W/'runs'/f'{case["id"]}_{variant}_{rep+1}';shutil.copytree(ROOT/'inputs'/case['id'],d)
   env.pop('GRAL_WORKER_CONCENTRATION_MB',None)
   if case['workers']>1:env['GRAL_WORKER_CONCENTRATION_MB']='256'
   r=command(['dotnet',str(W/variant/'src/bin/Release/net10.0/GRAL.dll'),str(d)],cwd=d);(d/'console.log').write_bytes(r.stdout+r.stderr)
   assert 'GRAL simulations finished at:' in (d/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig')
   problem=d/'Problemreport_GRAL.txt';assert not(problem.exists() and problem.read_text().strip())
   data=[];hashes={}
   for zpath in sorted(d.glob('*.grz')):
    with zipfile.ZipFile(zpath) as z:
     for name in sorted(z.namelist()):
      raw=z.read(name);hashes[zpath.name+':'+name]=hashlib.sha256(raw).hexdigest();assert name.endswith('.con')
      data.extend(struct.unpack('<'+str((len(raw)-28)//4)+'f',raw[28:]))
   assert len(hashes)==case['groups']*case['situations'] and all(math.isfinite(v) and v>=0 for v in data)
   key=(case['id'],variant,rep+1);values[key]=data;records.append({'case':case['id'],'variant':variant,'repeat':rep+1,'payloads':hashes})
   print('[MAIN]',len(records),flush=True)
comparisons=[]
for c in old['cases']:
 for (ka,va),(kb,vb) in itertools.combinations([(k,v) for k,v in values.items() if k[0]==c['id']],2):
  delta=[abs(x-y) for x,y in zip(va,vb)];changed=sum(x!=y for x,y in zip(va,vb))
  if c['workers']==1:assert changed==0
  comparisons.append({'case':c['id'],'a':list(ka[1:]),'b':list(kb[1:]),'changed_cells':changed,'relative_l1':sum(delta)/max(sum(va),1e-30),'max_absolute':max(delta)})
(W/'results.json').write_text(json.dumps({'main_runs':len(records),'records':records,'numeric_comparisons':comparisons},indent=2)+'\n',encoding='utf-8')
print('[COMPLETE]',len(records),'runs; compare parallel within-build and between-build differences in results.json')
