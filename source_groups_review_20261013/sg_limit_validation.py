from pathlib import Path
import argparse, hashlib, io, json, math, os, re, shutil, struct, subprocess, time, zipfile, csv
BASE='891225b2f9dbbcda7f5ef6e9ef6db65e64845108'
PATCHES={f'src/{name}':(b'new double[101]',b'new double[Program.SourceGroups.Count]') for name in ['ReadPointSources.cs','ReadLinieSources.cs','ReadTunnelportals.cs','ReadAreaSources.cs']}
PATCHES.update({'src/ProgramDeclarations.cs':(b'public static readonly double[] DecayRate = new double[102];',b'public static readonly double[] DecayRate = new double[byte.MaxValue + 1];'),'src/ReadPollutant.cs':(b'sg_number > 0 && sg_number < 100',b'sg_number > 0 && sg_number < Program.DecayRate.Length')})
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def process(cmd,cwd,env,timeout=60):
 t=time.perf_counter();p=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 try:o,e=p.communicate(timeout=timeout)
 except subprocess.TimeoutExpired:
  if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True)
  else:p.kill()
  o,e=p.communicate();return 124,o.decode('utf-8','replace'),e.decode('utf-8','replace')+'\n[WATCHDOG] process tree terminated at timeout\n',time.perf_counter()-t
 return p.returncode,o.decode('utf-8','replace'),e.decode('utf-8','replace'),time.perf_counter()-t

def cases():
 rows=[]
 def add(name,kind,ids,**kw):rows.append(dict(id=name,kind=kind,ids=ids,budget=2160,dx=20,duration=30,situations=3,workers=1,stationary=False,decay=False,**kw))
 for kind in ['point','portal','line','area']:
  add('legacy_'+kind,kind,[1,99])
  add('sparse_'+kind,kind,[99,100,101,102,108,255])
  add('count108_'+kind,kind,list(range(1,109)))
  add('mirror_'+kind,kind,list(range(1,7)))
 add('count99_area','area',list(range(1,100)))
 add('count101_area','area',list(range(1,102)))
 add('count255_area','area',list(range(1,256)))
 add('reversed_sparse_area','area',[255,108,102,101,100,99])
 add('decay_sparse_area','area',[99,100,101,102,108,255]);rows[-1]['decay']=True
 add('decay_mirror_area','area',list(range(1,7)));rows[-1]['decay']=True
 add('steady_sparse_area','area',[99,100,101,102,108,255]);rows[-1].update(stationary=True,situations=1)
 add('steady_mirror_area','area',list(range(1,7)));rows[-1].update(stationary=True,situations=1)
 return rows

def make_input(c,folder,template):
 shutil.copytree(template,folder)
 for p in list(folder.iterdir()):
  if p.suffix=='.json' or p.name in ('cadastre.dat','point.dat','line.dat','portals.dat'):p.unlink()
 lines=(folder/'in.dat').read_text().splitlines();lines[0]=str(c['budget']/c['duration']);lines[1]=str(c['duration']);lines[2]='1' if c['stationary'] else '0';lines[7]='Y'
 (folder/'in.dat').write_text('\n'.join(lines)+'\n');dx=c['dx'];ids=c['ids']
 (folder/'GRAL.geb').write_text('\n'.join(map(str,[dx,dx,'2,1.1',200//dx,200//dx,1,','.join(map(str,ids)),0,200,0,200]))+'\n')
 (folder/'Max_Proc.txt').write_text(str(c['workers'])+'\n')
 weather=[(9,.5,4)]*c['situations'];(folder/'meteopgt.all').write_text('10,1,10\nwind_dir,wind_speed,stability,frequency\n'+'\n'.join(f'{d},{s},{sc},1' for d,s,sc in weather)+'\n')
 (folder/'mettimeseries.dat').write_text('\n'.join(f'01.01.2022 {h:02d} {s} {d} {sc}' for h,(d,s,sc) in enumerate(weather))+'\n')
 factors=[[1 if h==0 else .5 if g%2 else 0 for g in range(len(ids))] for h in range(c['situations'])]
 (folder/'emissions_timeseries.txt').write_text('date;hour;'+';'.join(map(str,ids))+'\n'+'\n'.join(f'01.01.2022;{h:02d};'+';'.join(map(str,f)) for h,f in enumerate(factors))+'\n')
 rows=[]
 for i,sg in enumerate(ids):
  x=25+(i%16)*10;y=25+(i//16)*10;er=1;kind=c['kind']
  if kind=='point':row=[x,y,2,er,0,0,0,1,1,293,sg]
  elif kind=='portal':row=[x,y,x+6,y,1,3,er,0,0,0,sg]
  elif kind=='line':row=[i+1,0,sg,x,y,1,x+10,y+4,2,2,-2,0,0,er*1000/math.sqrt(117),0,0,0,0,0]
  else:row=[x,y,2,8,8,2,er,0,0,0,sg]
  rows.append(','.join(map(str,row)))
 fn={'point':'point.dat','portal':'portals.dat','line':'line.dat','area':'cadastre.dat'}[kind];header=5 if kind=='line' else 1 if kind=='area' else 2
 (folder/fn).write_text('\n'.join(['header']*header+rows)+'\n')
 if c['decay']:(folder/'Pollutant.txt').write_text('NOX\n0\n0\n0.001\n'+'\t'.join(f'{sg}:{.005*(i+1)}' for i,sg in enumerate(ids))+'\n')
 save(folder/'synthetic_case.json',dict(c,emission_factors=factors));return factors

CS=r'''using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Collections.Generic;
using System.Globalization;
using System.Text.Json;
class Fixture {
 static Type P; static Type R; static Type W;
 static object Get(string n)=>P.GetField(n,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static).GetValue(null);
 static void Set(string n,object v)=>P.GetField(n,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static).SetValue(null,v);
 static float[][][][] Field(int n) {var a=new float[3][][][];for(int i=0;i<3;i++){a[i]=new float[3][][];for(int j=0;j<3;j++){a[i][j]=new float[3][];for(int k=0;k<3;k++)a[i][j][k]=new float[n];}}return a;}
 static void Check(bool ok,string label){if(!ok)throw new Exception(label);}
 static void Main(string[] args) {
 CultureInfo.CurrentCulture=CultureInfo.InvariantCulture; var a=Assembly.LoadFrom(args[0]);P=a.GetType("GRAL_2001.Program");R=a.GetType("GRAL_2001.ProgramReaders");W=a.GetType("GRAL_2001.ProgramWriters");
 File.WriteAllText("Pollutant.txt","NOX\n0\n0\n0.001\n99:0.009\t100:0.010\t101:0.011\t102:0.012\t108:0.018\t255:0.025\t256:0.999\n");R.GetMethod("ReadPollutantTXT").Invoke(Activator.CreateInstance(R),null);
 var decay=(double[])Get("DecayRate");var dict=new Dictionary<int,double>();foreach(int g in new[]{1,99,100,101,102,108,255})if(g<decay.Length)dict[g]=decay[g];Check(decay[1]==.001&&decay[99]==.009,"legacy decay");
 if(args[1]=="fixed"){Check(decay.Length==256,"decay size");Check(decay[100]==.010&&decay[101]==.011&&decay[102]==.012&&decay[108]==.018&&decay[255]==.025,"high decay");}else{Check(decay.Length==102&&decay[100]==.001&&decay[101]==.001,"baseline high decay ignored");}
 var counts=new List<int>();foreach(int n in new[]{99,108,255,256}){
 foreach(string f in Directory.GetFiles(".","Transient_Concentrations*.tmp"))File.Delete(f);
 Set("NII",1);Set("NJJ",1);Set("NKK_Transient",2);Set("GralWest",0.0);Set("GralEast",20.0);Set("GralSouth",0.0);Set("GralNorth",20.0);Set("DXK",20f);Set("TransConcThreshold",.1f);
 var groups=new List<int>();for(int g=0;g<n;g++)groups.Add(g);Set("SourceGroups",groups);var f4=Field(n);var e=new double[n];for(int g=0;g<n;g++){e[g]=g+.125;for(int i=1;i<=2;i++)for(int j=1;j<=2;j++)f4[i][j][1][g]=(float)(i+j+g/512.0);}Set("Conz4d",f4);Set("EmissionPerSG",e);
 W.GetMethod("WriteTransientConcentration").Invoke(Activator.CreateInstance(W),new object[]{7});var file=Directory.GetFiles(".","Transient_Concentrations*.tmp")[0];using(var zip=ZipFile.OpenRead(file)){using(var stream=zip.Entries[0].Open()){using(var mem=new MemoryStream()){stream.CopyTo(mem);Check(BitConverter.ToInt32(mem.ToArray(),52)==n,"Int32 count");}}}
 Set("Conz4d",Field(n));Set("EmissionPerSG",new double[n]);int next=(int)R.GetMethod("ReadTransientConcentrations").Invoke(Activator.CreateInstance(R),new object[]{file});Check(next==8,"restart next");var actual=(float[][][][])Get("Conz4d");var rates=(double[])Get("EmissionPerSG");for(int g=0;g<n;g++){Check(rates[g]==e[g],"emission roundtrip");for(int i=1;i<=2;i++)for(int j=1;j<=2;j++)Check(actual[i][j][1][g]==f4[i][j][1][g],"concentration roundtrip");}counts.Add(n);
 }
 Console.WriteLine("[FIXTURE] "+JsonSerializer.Serialize(new{status="pass",variant=args[1],decay_length=decay.Length,decay_rates=dict,checkpoint_count_roundtrip=counts,checkpoint_note="256 is a count-format fixture using IDs 0..255, not a claim of 256 positive supported IDs"}));
 }
}'''

def prepare(a):
 root=a.work_dir;repo=a.source_repo
 raw=subprocess.check_output(['git','-C',str(repo),'archive','--format=zip',BASE,'src'])
 for variant in ['baseline','fixed']:
  target=root/'source'/variant;target.mkdir(parents=True)
  with zipfile.ZipFile(io.BytesIO(raw)) as z:z.extractall(target)
  if variant=='fixed':
   for name,(before,after) in PATCHES.items():
    p=target/name;b=p.read_bytes();assert b.count(before)==1,(name,b.count(before));p.write_bytes(b.replace(before,after))
 manifest={v:{str(p.relative_to(root/'source'/v)).replace('\\','/'):sha(p) for p in sorted((root/'source'/v/'src').iterdir()) if p.is_file()} for v in ['baseline','fixed']}
 save(root/'source_manifest.json',dict(base=BASE,files=manifest))
 bundled=Path(__file__).resolve().parent/'sg_limit.patch'
 if bundled.resolve()!=(root/'sg_limit.patch').resolve():shutil.copyfile(bundled,root/'sg_limit.patch')
 for c in cases():make_input(c,root/'inputs'/c['id'],a.template_root)
 f=root/'fixture';f.mkdir();(f/'Fixture.cs').write_text(CS,encoding='utf-8');(f/'Fixture.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><EnableDefaultCompileItems>true</EnableDefaultCompileItems></PropertyGroup></Project>\n')
 save(root/'design.json',dict(cases=cases(),repeats=2,main_planned=len(cases())*4,scope='Headless engine IDs 1..255; GUI and >255 IDs excluded.'))

def payloads(folder,c):
 data={};sums={g:0. for g in c['ids']}
 for archive in sorted(folder.glob('*.grz')):
  with zipfile.ZipFile(archive) as z:
   for name in sorted(z.namelist()):
    if not name.endswith('.con'):continue
    match=re.fullmatch(r'(\d{5})-1(\d{2,3})\.con',name);assert match,name;g=int(match[2]);assert g in c['ids'],name
    raw=z.read(name);h=struct.unpack_from('<iiiffii',raw);assert h==(-3,0,0,float(c['dx']),float(c['dx']),200//c['dx'],200//c['dx']),h
    assert len(raw)==28+4*(200//c['dx'])**2
    v=struct.unpack_from('<'+str((len(raw)-28)//4)+'f',raw,28);assert all(math.isfinite(x) and x>=0 for x in v);sums[g]+=sum(v)
    data[f'{int(match[1])}:{c["ids"].index(g)}']=hashlib.sha256(raw).hexdigest()
 assert len(data)==len(c['ids'])*c['situations'],(len(data),c['id']);assert (sum(sums.values())>0 if c.get('allow_zero_groups',False) else all(x>0 for x in sums.values())),sums
 return data,sums

def execute(a):
 root=a.work_dir;qa=a.qa_dir;run=root/'run';run.mkdir(exist_ok=True);env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(run/'dotnet_home'),NUGET_PACKAGES=str(run/'nuget'),TEMP=str(run/'tmp'),TMP=str(run/'tmp'),DOTNET_CLI_UI_LANGUAGE='en',DOTNET_NOLOGO='1');(run/'tmp').mkdir(exist_ok=True)
 started=time.perf_counter();builds={};records=json.loads((qa/'sg_limit_records.json').read_text()) if (qa/'sg_limit_records.json').exists() else [];errors=[];fixtures=[]
 for variant in ['baseline','fixed','fixture']:
  target=root/'fixture' if variant=='fixture' else root/'source'/variant/'src';proj=target/('Fixture.csproj' if variant=='fixture' else 'GRAL.csproj')
  code,out,err,elapsed=process([a.dotnet,'build',str(proj),'-c','Release','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true'],target,env,180);(run/f'build_{variant}.log').write_text(out+err,encoding='utf-8');assert code==0 and '0 Warning(s)' in out and '0 Error(s)' in out,out+err;builds[variant]=dict(warnings=0,errors=0,elapsed_s=elapsed)
 for variant in ['baseline','fixed']:
  folder=run/('fixture_'+variant);folder.mkdir(exist_ok=True);dll=root/'source'/variant/'src/bin/Release/net10.0/GRAL.dll'
  code,out,err,elapsed=process([a.dotnet,str(root/'fixture/bin/Release/net10.0/Fixture.dll'),str(dll),variant],folder,env);(folder/'console.log').write_text(out+err,encoding='utf-8');assert code==0,out+err;fixtures.append(json.loads(re.search(r'\[FIXTURE\] (.+)',out)[1]))
 for c in cases():
  for rep in range(2):
   for variant in (['baseline','fixed'] if rep==0 else ['fixed','baseline']):
    if time.perf_counter()-started>600:raise TimeoutError('600s budget')
    key=f'{c["id"]}_{variant}_{rep}'
    if any(r['case']==c['id'] and r['variant']==variant and r['repeat']==rep for r in records):continue
    folder=run/key
    if folder.exists():folder=run/(key+'_retry')
    shutil.copytree(root/'inputs'/c['id'],folder);dll=root/'source'/variant/'src/bin/Release/net10.0/GRAL.dll'
    expected=variant=='fixed' or (len(c['ids'])<=101 and max(c['ids'])<=101)
    code,out,err,elapsed=process([a.dotnet,str(dll),str(folder)],folder,env,30 if expected else 5);(folder/'console.log').write_text(out,encoding='utf-8');(folder/'stderr.log').write_text(err,encoding='utf-8')
    log=folder/'Logfile_GRALCore.txt';completed=code==0 and log.exists() and 'GRAL simulations finished at:' in log.read_text(encoding='utf-8-sig');problem=folder/'Problemreport_GRAL.txt';problem=problem.read_text(encoding='utf-8-sig').strip() if problem.exists() else ''
    expect_success=variant=='fixed' or (len(c['ids'])<=101 and max(c['ids'])<=101)
    rec=dict(case=c['id'],variant=variant,repeat=rep,return_code=code,completed=completed,expected_success=expect_success,wall_s=elapsed,nominal_particles=c['budget'],actual_particles=[int(v) for v in re.findall(r'Using a total of (\d+) particles',out)],groups=len(c['ids']),max_id=max(c['ids']),problem=problem,stderr=err,payload_sha256={},output_sums={})
    try:
     assert completed==expect_success,(key,completed,expect_success,out[-2000:],err)
     if completed:
      assert not problem,(key,problem);rec['payload_sha256'],rec['output_sums']=payloads(folder,c)
      if not c['stationary']:
       emitted=re.findall(r'Summarized emission rates per source group in kg\s*\n[^\n]*SG:[^\n]*\n([^\n]+)',out);assert emitted,key;actual=list(map(float,emitted[-1].split()));factors=json.loads((folder/'synthetic_case.json').read_text())['emission_factors'];expected=[sum(f[g] for f in factors)*c['duration']/3600 for g in range(len(c['ids']))];assert len(actual)==len(expected);assert all(math.isclose(x,y,rel_tol=.006,abs_tol=.00011) for x,y in zip(actual,expected)),(key,actual,expected);rec['fresh_mass_kg']=actual
     else:assert problem or err or 'Error' in out or 'error' in out,(key,'No failure diagnostic')
     rec['status']='pass'
    except Exception as ex:rec['status']='fail';errors.append(repr(ex))
    records.append(rec);save(qa/'sg_limit_progress.json',dict(status='running',completed=len(records),planned=len(cases())*4,last=key));print(f'[RUN] {len(records)} {key} {rec["status"]} completed={completed}',flush=True)
    save(qa/'sg_limit_records.json',records)
 checks=[]
 for c in cases():
  for variant in ['baseline','fixed']:
   rs=[r for r in records if r['case']==c['id'] and r['variant']==variant]
   if rs[0]['completed']:
    equal=rs[0]['payload_sha256']==rs[1]['payload_sha256'];checks.append(dict(case=c['id'],test='fixed_seed_repeat_'+variant,pass_=equal));assert equal,(c['id'],variant)
  b=next(r for r in records if r['case']==c['id'] and r['variant']=='baseline');f=next(r for r in records if r['case']==c['id'] and r['variant']=='fixed')
  if b['completed']:
   equal=b['payload_sha256']==f['payload_sha256'];checks.append(dict(case=c['id'],test='legacy_baseline_equal',pass_=equal));assert equal,c['id']
 for high,low in [(f'sparse_{k}',f'mirror_{k}') for k in ['point','portal','line','area']]+[('decay_sparse_area','decay_mirror_area'),('steady_sparse_area','steady_mirror_area')]:
  x=next(r for r in records if r['case']==high and r['variant']=='fixed');y=next(r for r in records if r['case']==low and r['variant']=='fixed');equal=x['payload_sha256']==y['payload_sha256'];checks.append(dict(case=high,test='high_low_id_payload_equal',pass_=equal));assert equal,(high,low)
 save(qa/'sg_limit_summary.json',dict(status='pass' if not errors else 'fail',base=BASE,builds=builds,fixtures=fixtures,main_runs=len(records),conditions=len(cases()),completed_runs=sum(r['completed'] for r in records),expected_baseline_failures=sum(not r['completed'] and not r['expected_success'] for r in records),checks=checks,errors=errors,elapsed_s=time.perf_counter()-started,limits=['No GUI compatibility claim for three-digit IDs.','No memory reduction or speedup claim; dense concentration arrays still scale with selected group count.','256-group checkpoint fixture tests Int32 count serialization only, not 256 positive supported IDs.','Synthetic runs are input/output regression tests, not atmospheric validation.']))
 with (qa/'sg_limit_results.csv').open('w',newline='',encoding='utf-8') as f:
  fields=['case','variant','repeat','status','return_code','completed','expected_success','nominal_particles','actual_particles','groups','max_id','wall_s'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in records)
 save(qa/'sg_limit_progress.json',dict(status='complete',completed=len(records),planned=len(cases())*4,errors=errors));assert not errors,errors
 print('[PASS] sg_limit',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source-repo',required=True,type=Path);p.add_argument('--work-dir',required=True,type=Path);p.add_argument('--template-root',required=True,type=Path);p.add_argument('--qa-dir',required=True,type=Path);p.add_argument('--dotnet',default='dotnet');p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true');a=p.parse_args();a.work_dir.mkdir(parents=True,exist_ok=True);a.qa_dir.mkdir(parents=True,exist_ok=True)
 if a.prepare:prepare(a)
 if a.execute:execute(a)
