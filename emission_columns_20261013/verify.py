from pathlib import Path
import argparse,subprocess,json,os,shutil,time,hashlib,zipfile,struct,math,re
import transient_support as ts
ROOT=Path(__file__).resolve().parent

def save(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def execute(cmd,cwd,log,env,timeout=90):
 start=time.perf_counter();log.parent.mkdir(parents=True,exist_ok=True)
 with log.open('w',encoding='utf-8') as f:
  proc=subprocess.Popen(list(map(str,cmd)),cwd=cwd,stdout=f,stderr=subprocess.STDOUT,env=env)
  try:rc=proc.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   proc.kill();proc.wait();raise
 return dict(exit_code=rc,wall_s=time.perf_counter()-start)

def build(src,out,dotnet,env):
 log=out.parent/(out.name+'_build.log')
 result=execute([dotnet,'build',src/'GRAL.csproj','-c','Release','-o',out,'-p:TreatWarningsAsErrors=true','-p:UseSharedCompilation=false','--nologo'],src,log,env,timeout=120)
 text=log.read_text(encoding='utf-8');assert result['exit_code']==0,text
 assert '0 Warning(s)' in text and '0 Error(s)' in text,text
 return dict(**result,warnings=0,errors=0)

def payloads(folder):
 result={};total=0.;count=0
 for archive in sorted(folder.glob('*.grz')):
  with zipfile.ZipFile(archive) as z:
   for name in z.namelist():
    raw=z.read(name);result[archive.name+':'+name]=hashlib.sha256(raw).hexdigest()
    if name.endswith('.con'):
     assert len(raw)>=28 and (len(raw)-28)%4==0
     v=struct.unpack('<'+'f'*((len(raw)-28)//4),raw[28:]);assert all(math.isfinite(x) and x>=0 for x in v)
     total+=sum(v);count+=len(v)
 return dict(hashes=result,total=total,values=count,archives=len(list(folder.glob('*.grz'))))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--baseline-source',type=Path,required=True);ap.add_argument('--candidate-source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--dotnet',default='dotnet');a=ap.parse_args();out=a.out.resolve();out.mkdir(exist_ok=False);start=time.perf_counter()
 env=os.environ.copy();(out/'tmp').mkdir();env.update(TEMP=str(out/'tmp'),TMP=str(out/'tmp'),DOTNET_CLI_UI_LANGUAGE='en');env.pop('GRAL_WORKER_CONCENTRATION_MB',None)
 builds={};components={};sources={'baseline':a.baseline_source.resolve(),'candidate':a.candidate_source.resolve()}
 for variant,source in sources.items():
  builds[variant]=build(source,out/'build'/variant,a.dotnet,env)
  f=out/'fixtures'/variant;f.mkdir(parents=True)
  shutil.copy2(ROOT/'ReaderFixture.cs',f/'ReaderFixture.cs');shutil.copy2(source/'ReadEmissionTimeSeries.cs',f/'ReadEmissionTimeSeries.cs')
  (f/'Fixture.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><TreatWarningsAsErrors>true</TreatWarningsAsErrors><UseSharedCompilation>false</UseSharedCompilation></PropertyGroup></Project>')
  b=execute([a.dotnet,'build','-c','Release','--nologo'],f,out/'build'/f'{variant}_fixture_build.log',env,120);assert b['exit_code']==0
  log=(out/'build'/f'{variant}_fixture_build.log').read_text();assert '0 Warning(s)' in log and '0 Error(s)' in log;builds[variant+'_fixture']=dict(**b,warnings=0,errors=0)
  resultfile=out/'results'/f'{variant}_reader.json';resultfile.parent.mkdir(exist_ok=True)
  r=execute([a.dotnet,f/'bin/Release/net10.0/Fixture.dll',out/'fixture_inputs'/variant,variant,resultfile],f,out/'logs'/f'{variant}_fixture.log',env);assert r['exit_code']==0,(out/'logs'/f'{variant}_fixture.log').read_text();components[variant]=json.loads(resultfile.read_text())
 defs=[('matched',20,100,'point',[1,2],[],False),('reordered',10,1000,'mixed',[2,1],[],False),('selected_absent',40,3000,'area',[1],[],False),('extra_first',20,1000,'point',[99,1,2],[99],True),('extra_middle',10,3000,'mixed',[1,99,2],[99],True),('extra_last',40,100,'area',[1,2,99],[99],True),('many_extra',20,3000,'mixed',[98,99,1,97,2],[97,98,99],True),('missing_value',20,1000,'point',[99,1,2],[99],True)]
 records=[];comparisons=[]
 for idx,(name,dx,budget,kind,header,unused,defect) in enumerate(defs):
  c=dict(id=name,dx=dx,budget=budget,kind=kind,sources=4 if kind=='mixed' else 2,groups=2,pattern='steady',workers=1,ratio=1,duration=30,situations=3,wind_m_s=.5,stability=4)
  d=out/'inputs'/name;d.parent.mkdir(exist_ok=True);detail=ts.input_case(c,d)
  factors=[[.5,1.5],[0,2],[2,.25]];canonical=[x for x in header if x not in unused]
  if name=='missing_value':factors[0][1]=1
  def text_for(cols):
   rows=[]
   for h in range(3):
    vals=[str(factors[h][sg-1]) if sg in [1,2] else '9' for sg in cols]
    if name=='missing_value' and h==0:vals=vals[:-1]
    rows.append(f'01.01.2022;{h:02d};'+';'.join(vals))
   return 'date;hour;'+';'.join(map(str,cols))+'\n'+'\n'.join(rows)+'\n'
  for rep in range(2):
   results={}
   for variant,layout in [('baseline','canonical'),('baseline','supplied'),('candidate','canonical'),('candidate','supplied')]:
    assert time.perf_counter()-start<840,'suite budget'
    folder=out/'runs'/f'{name}_{variant}_{layout}_{rep}';folder.parent.mkdir(exist_ok=True);shutil.copytree(d,folder)
    (folder/'emissions_timeseries.txt').write_text(text_for(canonical if layout=='canonical' else header))
    r=execute([a.dotnet,out/'build'/variant/'GRAL.dll'],folder,folder/'console.log',env,60)
    log=(folder/'console.log').read_text(encoding='utf-8',errors='replace');core=folder/'Logfile_GRALCore.txt';finished=core.exists() and 'GRAL simulations finished at:' in core.read_text(encoding='utf-8-sig',errors='replace');reader_ok='Reading emissions_timeseries.txt successful' in log
    p=payloads(folder)
    if not(variant=='baseline' and layout=='supplied' and defect):assert r['exit_code']==0 and finished and reader_ok and p['archives']==3 and p['total']>0,(name,variant,layout,log[-2000:])
    if variant=='baseline' and layout=='supplied' and defect:assert not reader_ok and 'Index was outside the bounds of the array.' in log,(name,log)
    allocation=list(map(int,re.findall(r'Using a total of (\d+) particles',log)));assert allocation and all(100<=x<=3000 for x in allocation),allocation
    record=dict(case=name,dx=dx,budget=budget,actual_particles=allocation,source_kind=kind,variant=variant,layout=layout,repeat=rep,known_defect=defect,finished=finished,reader_complete=reader_ok,**r,**p);records.append(record);results[(variant,layout)]=record
    save(out/'progress.json',dict(completed=len(records),planned=64));print('[MAIN]',len(records),name,variant,layout,rep,flush=True)
   control=results[('baseline','canonical')]['hashes']
   for key in [('candidate','canonical'),('candidate','supplied')]:assert results[key]['hashes']==control,(name,key,'payload mismatch')
   if not defect:assert results[('baseline','supplied')]['hashes']==control
   comparisons.append(dict(case=name,repeat=rep,candidate_supplied_matches_baseline_canonical=True,candidate_canonical_matches_baseline_canonical=True,baseline_supplied_matches_baseline_canonical=results[('baseline','supplied')]['hashes']==control,known_defect=defect))
  save(out/'results/main.json',dict(status='running',records=records,comparisons=comparisons))
 for name,*_ in defs:
  for variant in ['baseline','candidate']:
   for layout in ['canonical','supplied']:
    rr=[r for r in records if r['case']==name and r['variant']==variant and r['layout']==layout];assert rr[0]['hashes']==rr[1]['hashes'],(name,variant,layout,'repeat mismatch')
 save(out/'results/main.json',dict(status='pass',conditions=8,repeats=2,main_runs=len(records),records=records,comparisons=comparisons,elapsed_s=time.perf_counter()-start))
 figure=[]
 for variant in ['baseline','candidate']:
  r=next(x for x in components[variant]['records'] if x['name']=='figure_selected_one')
  for hour,(actual,expected) in enumerate(zip(r['actual'],r['expected'])):figure.append(dict(variant=variant,hour=hour,actual=actual[0],expected=expected[0],completed=r['complete']))
 save(out/'results/figure_data.json',dict(selected_groups=[1],header_groups=[2,1],rows=figure))
 save(out/'results/summary.json',dict(status='pass',builds=builds,component_cases=13,component_assertions={k:v['assertions'] for k,v in components.items()},main_runs=len(records),main_conditions=8,main_repeats=2,baseline_fault_runs=10,elapsed_s=time.perf_counter()-start))
 print('[PASS]',len(records),'Main runs',flush=True)
if __name__=='__main__':main()
