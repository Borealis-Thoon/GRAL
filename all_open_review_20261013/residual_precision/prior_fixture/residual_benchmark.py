from pathlib import Path
import argparse, csv, hashlib, io, json, math, os, re, shutil, statistics, struct, subprocess, sys, time, zipfile
ROOT=Path(__file__).resolve().parent
JOB=ROOT.parents[1]
REPO=ROOT/'repo'
TEMPLATE=ROOT/'template'
QA=JOB/'qa'
BASE='891225b2f9dbbcda7f5ef6e9ef6db65e64845108'
PREVIOUS='324dd08161bb2a4a4d02a43f33e2a7f4ebd0eff7'
HEADS={'baseline':BASE,'pr62':'e44523982fb88a8d1cc8929bc650b8b1719be14f','pr63':'370084ba3d933e8cf444b33af93a34db41ba91fe'}
DOTNET='dotnet'

def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def git(*args, binary=False):
 return subprocess.check_output(['git','-C',str(REPO),*args],text=not binary)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def cases():
 rows=[]
 def add(ident,dx=20,budget=1000,kind='point',sources=2,groups=2,pattern='steady',workers=1,ratio=1):
  rows.append(dict(id=ident,dx=dx,budget=budget,kind=kind,sources=sources,groups=groups,pattern=pattern,workers=workers,ratio=ratio,duration=30,situations=5,wind_m_s=.25,stability=6))
 add('steady_20m_n1000')
 add('steady_20m_n100',budget=100)
 add('steady_40m_n1000',dx=40)
 add('steady_10m_n3000',dx=10,budget=3000)
 add('many_sources_20m_n3000',sources=32,budget=3000,groups=8)
 add('line_20m_n1000',kind='line',sources=8)
 add('area_20m_n1000',kind='area',sources=8)
 add('mixed_20m_n1000',kind='mixed',sources=8,groups=8)
 add('pulse_20m_n1000',pattern='pulse')
 add('alloff_20m_n1000',pattern='alloff')
 add('largeoff_20m_n100',budget=100,pattern='largeoff',ratio=99)
 add('largeoff_40m_n1000',dx=40,pattern='largeoff',ratio=99)
 add('largeoff_20m_n1000',pattern='largeoff',ratio=99)
 add('largeoff_10m_n3000',dx=10,budget=3000,pattern='largeoff',ratio=99)
 add('largeoff_20m_n1000_w4',pattern='largeoff',ratio=99,workers=4)
 return rows

def input_case(case,folder):
 if folder.exists():raise FileExistsError(folder)
 shutil.copytree(ROOT/'template',folder)
 for p in list(folder.iterdir()):
  if p.suffix=='.json' or p.name in ('cadastre.dat','point.dat','line.dat','portals.dat'):p.unlink()
 lines=(folder/'in.dat').read_text().splitlines();lines[0]=str(case['budget']/case['duration']);lines[1]=str(case['duration']);lines[2]='0';lines[7]='Y'
 (folder/'in.dat').write_text('\n'.join(lines)+'\n')
 dx=case['dx'];grid=[dx,dx,'2,1.1',200//dx,200//dx,1,','.join(str(i+1) for i in range(case['groups'])),0,200,0,200]
 (folder/'GRAL.geb').write_text('\n'.join(map(str,grid))+'\n')
 (folder/'Max_Proc.txt').write_text(str(case['workers'])+'\n')
 weather=[(9,case['wind_m_s'],case['stability'])]*case['situations']
 (folder/'meteopgt.all').write_text('10,1,10\nwind_dir,wind_speed,stability,frequency\n'+'\n'.join(f'{d},{s},{sc},1' for d,s,sc in weather)+'\n')
 (folder/'mettimeseries.dat').write_text('\n'.join(f'01.01.2022 {h:02d} {s} {d} {sc}' for h,(d,s,sc) in enumerate(weather))+'\n')
 factors=[]
 for h in range(case['situations']):
  f=[1.]*case['groups']
  if case['pattern']=='alloff' and h>=1:f=[0.]*case['groups']
  if case['pattern']=='pulse':f=[10. if h==0 else .1]*case['groups']
  if case['pattern']=='largeoff' and h>=1:f[0]=0
  factors.append(f)
 (folder/'emissions_timeseries.txt').write_text('date;hour;'+';'.join(str(i+1) for i in range(case['groups']))+'\n'+'\n'.join(f'01.01.2022;{h:02d};'+';'.join(map(str,f)) for h,f in enumerate(factors))+'\n')
 declared={};rates=[0.]*case['groups'];content={};kinds=['point','portal','line','area'] if case['kind']=='mixed' else [case['kind']]
 for i in range(case['sources']):
  kind=kinds[i%len(kinds)];x=45+(i%8)*14;y=55+(i//8)*18;sg=1+i%case['groups'];er=case['ratio'] if sg==1 else 1;rates[sg-1]+=er
  if kind=='point':row=[x,y,2,er,0,0,0,1,1,293,sg]
  elif kind=='portal':row=[x,y,x+6,y,1,3,er,0,0,0,sg]
  elif kind=='line':row=[i+1,0,sg,x,y,1,x+10,y+4,2,2,-2,0,0,er*1000/math.sqrt(117),0,0,0,0,0]
  else:row=[x,y,2,8,8,2,er,0,0,0,sg]
  content.setdefault(kind,[]).append(','.join(map(str,row)));declared[kind]=declared.get(kind,0)+1
 for kind,rows in content.items():
  fn={'point':'point.dat','portal':'portals.dat','line':'line.dat','area':'cadastre.dat'}[kind]
  header=5 if kind=='line' else 1 if kind=='area' else 2
  (folder/fn).write_text('\n'.join(['header']*header+rows)+'\n')
 detail=dict(case,weather=weather,emission_factors=factors,nominal_rates_kg_h=rates,source_counts=declared,expected_fresh_mass_kg=[rate*sum(f[g] for f in factors)*case['duration']/3600 for g,rate in enumerate(rates)],domain_m=[0,200,0,200])
 save(folder/'synthetic_case.json',detail);return detail

DIAG=r'''using System;
using System.Diagnostics;
using System.Globalization;
namespace GRAL_2001 {
internal static class ResidualReviewDiagnostics {
 public static Stopwatch Planner;
 public static Stopwatch Driver;
 static long eligible, nominal, selected;
 static double mass;
 public static void BeforePlan() {
  eligible=0;nominal=0;selected=0;mass=0;
  for(int i=1;i<=Program.NII;i++)for(int j=1;j<=Program.NJJ;j++)for(int k=1;k<=Program.NKK_Transient;k++)for(int g=0;g<Program.SourceGroups.Count;g++) {
   double c=Program.Conz4d[i][j][k][g];
   if(c<Program.TransConcThreshold)continue;
   double m=c*(Program.DXK*Program.DYK*Program.DZK_Trans[k]/Program.GridVolume)/Program.TAUS;
   eligible++;mass+=m;
   nominal+=(long)Math.Min(100000,Math.Max(1,Math.Floor(Math.Floor(m/Program.ParticleMassMean)/10)+1));
  }
  Planner=Stopwatch.StartNew();
 }
 public static void AfterPlan() {
  Planner.Stop();
  for(int i=1;i<=Program.NII;i++)for(int j=1;j<=Program.NJJ;j++)for(int k=1;k<=Program.NKK_Transient;k++)for(int g=0;g<Program.SourceGroups.Count;g++) {
   double c=Program.Conz4d[i][j][k][g];if(c<Program.TransConcThreshold)continue;
   double m=c*(Program.DXK*Program.DYK*Program.DZK_Trans[k]/Program.GridVolume)/Program.TAUS;
   selected+=ZeitschleifeNonSteadyState.ReviewSplit(m);
  }
  Driver=Stopwatch.StartNew();
 }
 public static void AfterDriver() {
  Driver.Stop();
  Console.WriteLine(string.Format(CultureInfo.InvariantCulture,"[RESIDUAL_REVIEW] situation={0};eligible={1};nominal_children={2};selected_children={3};planner_ms={4:R};driver_ms={5:R};retained_scaled_mass={6:R};grid_entries={7};budget={8:R};reference={9:R};k={10:R}",Program.IWET,eligible,nominal,selected,Planner.Elapsed.TotalMilliseconds,Driver.Elapsed.TotalMilliseconds,mass,(long)Program.NII*Program.NJJ*Program.NKK_Transient*Program.SourceGroups.Count,Program.TAUS*Program.TPS,ZeitschleifeNonSteadyState.ReviewReference(),ZeitschleifeNonSteadyState.ReviewK()));
 }
}
}
'''

def prepare():
 if TEMPLATE.resolve()!=(ROOT/'template').resolve():shutil.copytree(TEMPLATE,ROOT/'template')
 manifests={};patches={}
 for variant,head in HEADS.items():
  target=ROOT/'source'/variant;target.mkdir(parents=True)
  raw=git('archive','--format=zip',BASE,'src',binary=True)
  with zipfile.ZipFile(io.BytesIO(raw)) as z:z.extractall(target)
  if variant!='baseline':
   patch=git('diff','--binary',PREVIOUS,head,'--','src',binary=True)
   (ROOT/f'{variant}.patch').write_bytes(patch)
   subprocess.run(['git','apply','--unsafe-paths',str(ROOT/f'{variant}.patch')],cwd=target,check=True)
   patches[variant]=digest(ROOT/f'{variant}.patch')
  manifests[variant]={str(p.relative_to(target)).replace('\\','/'):digest(p) for p in sorted((target/'src').iterdir()) if p.is_file()}
  diagnostic=ROOT/'source'/(variant+'_diag');shutil.copytree(target,diagnostic)
  p=diagnostic/'src/Program.cs';t=p.read_text(encoding='utf-8-sig')
  if variant=='pr63':t=t.replace('ZeitschleifeNonSteadyState.PlanResidual();','ResidualReviewDiagnostics.BeforePlan();\n                        ZeitschleifeNonSteadyState.PlanResidual();\n                        ResidualReviewDiagnostics.AfterPlan();')
  else:t=t.replace('ParallelTransientParticleDriver(0, cellNr);','ResidualReviewDiagnostics.BeforePlan();\n                        ResidualReviewDiagnostics.AfterPlan();\n                        ParallelTransientParticleDriver(0, cellNr);')
  t=t.replace('ParallelTransientParticleDriver(0, cellNr);','ParallelTransientParticleDriver(0, cellNr);\n                        ResidualReviewDiagnostics.AfterDriver();');p.write_text(t,encoding='utf-8')
  p=diagnostic/'src/Zeitschleife_nonsteadystate.cs';t=p.read_text(encoding='utf-8-sig');ref='Program.ParticleMassMean' if variant=='baseline' else 'ParticleManagement.ParticleMassActive';split='ResidualSplitCount(m)' if variant=='pr63' else f'(int)Math.Min(100000, Math.Max(1, Math.Floor(Math.Floor(m/{ref})/10)+1))';k='residualSplitK' if variant=='pr63' else '10'
  t=t.replace('private const float Pi2F',f'public static int ReviewSplit(double m) => {split};\n        public static double ReviewReference() => {ref};\n        public static double ReviewK() => {k};\n        private const float Pi2F');p.write_text(t,encoding='utf-8')
  (diagnostic/'src/ResidualReviewDiagnostics.cs').write_text(DIAG,encoding='utf-8')
 save(ROOT/'source_manifest.json',dict(baseline=BASE,topic_heads=HEADS,source_files=manifests,patch_sha256=patches,diagnostic_scope='timing and scans in separate diagnostic copies only'))
 for case in cases():input_case(case,ROOT/'inputs'/case['id'])
 save(QA/'residual_design.json',dict(status='prepared_not_executed',cases=cases(),pristine_variants=3,repeats=3,diagnostic_runs=45,normal_runs=135,timeout_per_run_s=60,total_limit_s=600,limitations=['End-to-end wall time includes startup, input and output; diagnostic planner/driver times come from separate instrumented runs.','Concentration differences measure numerical sensitivity, not accuracy against observations.','Multi-worker diagnostic output is not required to be byte-identical because floating-point accumulation order varies.','Automatic selection is a proposal, not an implemented code change.']))
 print('[PREPARED] 15 conditions; 135 pristine + 45 diagnostic Main runs')

def process(cmd,cwd,env,timeout=60):
 started=time.perf_counter();p=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
 try:out,err=p.communicate(timeout=timeout)
 except subprocess.TimeoutExpired:
  subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW);out,err=p.communicate();raise TimeoutError(str(cwd))
 return p.returncode,out.decode('utf-8','replace'),err.decode('utf-8','replace'),time.perf_counter()-started

def outputs(folder,case):
 payload={};values=[]
 for path in sorted(folder.glob('*.grz')):
  with zipfile.ZipFile(path) as z:
   for name in sorted(z.namelist()):
    raw=z.read(name);payload[path.name+':'+name]=hashlib.sha256(raw).hexdigest()
    if name.endswith('.con'):
     hdr=struct.unpack_from('<iiiffii',raw);assert hdr==(-3,0,0,float(case['dx']),float(case['dx']),200//case['dx'],200//case['dx']),hdr
     assert len(raw)==28+4*(200//case['dx'])**2
     v=struct.unpack_from('<'+str((len(raw)-28)//4)+'f',raw,28);assert all(math.isfinite(x) and x>=0 for x in v);values.extend(v)
 assert len(payload)==case['groups']*case['situations'],(len(payload),case)
 assert sum(values)>0
 return payload,values

def run(run_name='run',reuse_builds=False):
 run=ROOT/run_name;run.mkdir()
 env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(run/'dotnet_home'),NUGET_PACKAGES=str(run/'nuget'),TEMP=str(run/'tmp'),TMP=str(run/'tmp'),DOTNET_CLI_UI_LANGUAGE='en',DOTNET_NOLOGO='1')
 (run/'tmp').mkdir();started=time.perf_counter();builds={}
 for variant in [v+s for v in HEADS for s in ('','_diag')]:
  if reuse_builds:
   dll=ROOT/'source'/variant/'src/bin/Release/net10.0/GRAL.dll'
   assert dll.is_file()
   builds[variant]=dict(reused_previously_strict_built=True,dll_sha256=digest(dll));continue
  target=ROOT/'source'/variant/'src';code,out,err,elapsed=process([DOTNET,'build',str(target/'GRAL.csproj'),'-c','Release','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true'],target,env,180)
  (run/f'build_{variant}.log').write_text(out+err,encoding='utf-8');assert code==0 and '0 Warning(s)' in out and '0 Error(s)' in out,out+err
  builds[variant]=dict(warnings=0,errors=0,elapsed_s=elapsed)
 records=[];numerics={};payloads={};baseline_records={}
 def one(case,variant,rep,diag):
  if time.perf_counter()-started>600:raise TimeoutError('Total budget 600s')
  key=f'{case["id"]}_{variant}_{rep}'+('_diag' if diag else '')
  folder=run/key;shutil.copytree(ROOT/'inputs'/case['id'],folder)
  actual_variant=variant+('_diag' if diag else '')
  dll=ROOT/'source'/actual_variant/'src/bin/Release/net10.0/GRAL.dll'
  code,out,err,elapsed=process([DOTNET,str(dll),str(folder)],folder,env,60)
  (folder/'console.log').write_text(out,encoding='utf-8');(folder/'stderr.log').write_text(err,encoding='utf-8')
  assert code==0 and 'GRAL simulations finished at:' in (folder/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig'),key+out[-3000:]+err
  problem=folder/'Problemreport_GRAL.txt';assert not problem.exists() or not problem.read_text(encoding='utf-8-sig').strip()
  allocation=list(map(int,re.findall(r'Using a total of (\d+) particles',out)));assert len(allocation)==1
  actual_sources={}
  for kind,description in {'point':'point sources','portal':'tunnel portals','line':'line source segments','area':'area source partitions'}.items():
   found=re.findall(r'Total number of '+description+r': (\d+)',out);actual_sources[kind]=int(found[0]) if found else 0
  assert actual_sources=={k:json.loads((folder/'synthetic_case.json').read_text())['source_counts'].get(k,0) for k in actual_sources},(key,actual_sources)
  payload,values=outputs(folder,case)
  fresh=re.findall(r'Summarized emission rates per source group in kg\s*\n[^\n]*SG:[^\n]*\n([^\n]+)',out);assert fresh,key
  fresh=list(map(float,fresh[-1].split()));detail=json.loads((folder/'synthetic_case.json').read_text());assert len(fresh)==case['groups']
  assert all(math.isclose(a,b,rel_tol=.006,abs_tol=.00011) for a,b in zip(fresh,detail['expected_fresh_mass_kg'])),(key,fresh,detail['expected_fresh_mass_kg'])
  diagnostic=[]
  if diag:
   for line in re.findall(r'\[RESIDUAL_REVIEW\] ([^\r\n]+)',out):diagnostic.append({k:float(v) for k,v in [entry.split('=') for entry in line.split(';')]})
   assert len(diagnostic)==case['situations']
  record=dict(case=case['id'],variant=variant,repeat=rep,diagnostic=diag,wall_s=elapsed,actual_particles=allocation[0],actual_sources=actual_sources,source_groups=case['groups'],fresh_mass_kg=fresh,output_sum=sum(values),output_max=max(values),float_count=len(values),payload_sha256=payload,diagnostics=diagnostic)
  keypair=(case['id'],variant)
  if not diag:
   numerics[(case['id'],variant,rep)]=values;payloads[(case['id'],variant,rep)]=payload
  elif case['workers']==1:assert payload==payloads[(case['id'],variant,0)],'Diagnostic instrumentation changed deterministic output '+key
  records.append(record);save(QA/'residual_progress.json',dict(status='running',completed=len(records),last=key,elapsed_s=time.perf_counter()-started))
  print(f'[RUN] {len(records)} {key} {elapsed:.3f}s',flush=True)
 # Interleaved cyclic variant order avoids a systematic warm-up/order advantage.
 for case in cases():
  for rep in range(3):
   vs=list(HEADS);vs=vs[rep:]+vs[:rep]
   for variant in vs:one(case,variant,rep,False)
  for variant in HEADS:one(case,variant,0,True)
 comparisons=[];summaries=[]
 for case in cases():
  for variant in HEADS:
   selected=[r for r in records if r['case']==case['id'] and r['variant']==variant and not r['diagnostic']]
   timings=[r['wall_s'] for r in selected];base=[r['wall_s'] for r in records if r['case']==case['id'] and r['variant']=='baseline' and not r['diagnostic']]
   diag=next(r for r in records if r['case']==case['id'] and r['variant']==variant and r['diagnostic'])
   summaries.append(dict(case=case['id'],variant=variant,wall_median_s=statistics.median(timings),wall_min_s=min(timings),wall_max_s=max(timings),relative_to_baseline=statistics.median(timings)/statistics.median(base),actual_particles=selected[0]['actual_particles'],eligible_entries_sum=sum(d['eligible'] for d in diag['diagnostics']),nominal_children_sum=sum(d['nominal_children'] for d in diag['diagnostics']),selected_children_sum=sum(d['selected_children'] for d in diag['diagnostics']),planner_ms=sum(d['planner_ms'] for d in diag['diagnostics']),driver_ms=sum(d['driver_ms'] for d in diag['diagnostics']),planner_infeasible_situations=sum(d['eligible']>d['budget'] for d in diag['diagnostics']),deterministic_repeats_equal=all(r['payload_sha256']==selected[0]['payload_sha256'] for r in selected)))
   if case['workers']==1:assert summaries[-1]['deterministic_repeats_equal']
   for rep in range(3):
    a=numerics[(case['id'],'baseline',rep)];b=numerics[(case['id'],variant,rep)];assert len(a)==len(b)
    comparisons.append(dict(case=case['id'],variant=variant,repeat=rep,relative_l1=sum(abs(x-y) for x,y in zip(a,b))/sum(a),sum_ratio=sum(b)/sum(a),max_ratio=max(b)/max(a),exact_payload=payloads[(case['id'],'baseline',rep)]==payloads[(case['id'],variant,rep)]))
 save(QA/'residual_records.json',records);save(QA/'residual_numeric_comparisons.json',comparisons);save(QA/'residual_summary.json',dict(status='pass',baseline=BASE,builds=builds,main_executions=len(records),pristine_runs=9*len(cases()),diagnostic_runs=3*len(cases()),elapsed_s=time.perf_counter()-started,conditions=cases(),summaries=summaries,limitations=['Single-machine short synthetic tests; walltime includes startup and IO.','Three fixed-seed repeats estimate runtime scatter, not stochastic scientific uncertainty.','Automatic switching remains proposed.','Mass checks cover fresh emissions and unchanged splitting formula; concentration sums are not a full domain mass balance.']))
 with (QA/'residual_summary.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=summaries[0]);w.writeheader();w.writerows(summaries)
 print('[PASS] residual suite',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--work-dir',type=Path,default=ROOT);p.add_argument('--source-repo',type=Path);p.add_argument('--template-root',type=Path);p.add_argument('--qa-dir',type=Path);p.add_argument('--dotnet',default=DOTNET);p.add_argument('--weather-only',action='store_true');p.add_argument('--floor-only',action='store_true');p.add_argument('--reuse-builds',action='store_true');p.add_argument('--run-name',default='run');a=p.parse_args()
 ROOT=a.work_dir.resolve();ROOT.mkdir(parents=True,exist_ok=True);REPO=(a.source_repo or ROOT/'repo').resolve();TEMPLATE=(a.template_root or ROOT/'template').resolve();QA=(a.qa_dir or ROOT/'qa').resolve();QA.mkdir(parents=True,exist_ok=True);DOTNET=a.dotnet
 if a.weather_only:
  reference=cases();weather=[]
  for state,speed,stability in [('neutral',2,4),('unstable',1,2)]:
   for ident in ['steady_20m_n1000','largeoff_20m_n1000']:
    c=dict(next(v for v in reference if v['id']==ident));c.update(id=ident+'_'+state,wind_m_s=speed,stability=stability);weather.append(c)
  cases=lambda:weather
  for case in cases():input_case(case,ROOT/'inputs'/case['id'])
 if a.floor_only:
  c=dict(next(v for v in cases() if v['id']=='many_sources_20m_n3000'));c.update(id='many_sources_10m_requested100',dx=10,budget=100);cases=lambda:[c];input_case(c,ROOT/'inputs'/c['id'])
 if a.prepare:prepare()
 elif a.execute:run(a.run_name,a.reuse_builds)
 else:raise SystemExit('Use --prepare or --execute')
