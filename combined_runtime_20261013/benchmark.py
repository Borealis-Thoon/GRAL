"""Cold-process integration checks on four synthetic stationary fields."""
from pathlib import Path
import argparse,csv,hashlib,itertools,json,os,re,shutil,statistics,subprocess,time
import numpy as np
import field_support as f
ROOT=Path(__file__).resolve().parent
VARIANTS=['current','reviewed','combined_off','combined_on']
SOURCE={'current':'current','reviewed':'reviewed','combined_off':'combined','combined_on':'combined'}
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def cases():
 return [
 dict(id='concentrated_100k_w4',particles=100000,kind='point',sources=2,sg=2,length=800,flow=40,conc=40,slices=1,tau=120,speed=.25,sc=6,hot=False,workers=4,concentrated=True),
 dict(id='concentrated_1m_unstable_w24',particles=1000000,kind='point',sources=2,sg=2,length=800,flow=40,conc=40,slices=1,tau=120,speed=.25,sc=2,hot=False,workers=24,concentrated=True),
 dict(id='wide_9slice_8sg_100k_w24',particles=100000,kind='area',sources=8,sg=8,length=1200,flow=40,conc=10,slices=9,tau=60,speed=1,sc=4,hot=False,workers=24),
 dict(id='small_3k_w1',particles=3000,kind='point',sources=2,sg=2,length=400,flow=40,conc=40,slices=1,tau=30,speed=1,sc=4,hot=False,workers=1),
 ]
def configure(c,d):
 cfg=dict(c);cfg['id']='parallel_concentrated' if c.get('concentrated') else c['id'];detail=f.configure(cfg,d);detail.update(id=c['id'])
 save(d/'case.json',detail);return detail

def verify():
 m=json.loads((ROOT/'source_manifest.json').read_text())
 for v,expected in m['hashes'].items():
  actual={p.relative_to(ROOT/'sources'/v).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'sources'/v/'src').rglob('*') if p.is_file() and not any(s in ['obj','bin'] for s in p.parts)}
  assert actual==expected,(v,'source mismatch')
 return sum(len(d) for d in m['hashes'].values())
def build(run,env):
 out={}
 for v in ['current','reviewed','combined']:
  cmd=[str(f.DOTNET),'build',str(ROOT/'sources'/v/'src/GRAL.csproj'),'-c','Release','-t:Rebuild','-v:minimal','--nologo','/p:TreatWarningsAsErrors=true']
  p=subprocess.run(cmd,capture_output=True,env=env,timeout=180);log=(p.stdout+p.stderr).decode('utf-8',errors='replace');(run/f'build_{v}.log').write_text(log,encoding='utf-8')
  assert p.returncode==0 and re.search(r'\b0 Warning\(s\)',log) and re.search(r'\b0 Error\(s\)',log),log
  dll=ROOT/'sources'/v/'src/bin/Release/net10.0/GRAL.dll';out[v]=dict(warnings=0,errors=0,dll_sha256=hashlib.sha256(dll.read_bytes()).hexdigest());print('[BUILD]',v,flush=True)
 return out

def aggregate(a):
 return dict(concentration_cell_sum=sum(float(v.astype('float64').sum()) for v in a.values()),max_concentration=max(float(v.max()) for v in a.values()),nonzero_cells=sum(int(np.count_nonzero(v)) for v in a.values()),cells=sum(len(v) for v in a.values()))
def compare(a,b):
 x=aggregate(a);y=aggregate(b);d=f.diff(a,b);d.update(reference_sum=x['concentration_cell_sum'],candidate_sum=y['concentration_cell_sum'],signed_relative_sum=(y['concentration_cell_sum']/x['concentration_cell_sum']-1) if x['concentration_cell_sum'] else None,reference_max=x['max_concentration'],candidate_max=y['max_concentration']);return d

def main():
 p=argparse.ArgumentParser();p.add_argument('--dotnet',type=Path,default=f.DOTNET);p.add_argument('--run-name',default='main');p.add_argument('--repeat',type=int,default=5);p.add_argument('--cases',nargs='+');p.add_argument('--build-only',action='store_true');p.add_argument('--skip-build',action='store_true');p.add_argument('--pilot',action='store_true');p.add_argument('--max-seconds',type=float,default=900);args=p.parse_args();f.DOTNET=args.dotnet.resolve()
 assert args.repeat>=5 or args.pilot or args.build_only
 run=ROOT/args.run_name;run.mkdir(exist_ok=False);(run/'tmp').mkdir();env=os.environ.copy();env.update(TEMP=str(run/'tmp'),TMP=str(run/'tmp'),DOTNET_CLI_HOME=str(ROOT/'cache'),NUGET_PACKAGES=str(ROOT/'nuget'),DOTNET_NOLOGO='1',DOTNET_CLI_UI_LANGUAGE='en');env.pop('GRAL_WORKER_CONCENTRATION_MB',None)
 checked=verify();builds={} if args.skip_build else build(run,env)
 if args.build_only:save(run/'summary.json',dict(status='built',source_hashes_checked=checked,builds=builds));return
 selected=[c for c in cases() if not args.cases or c['id'] in args.cases];assert selected and (not args.cases or set(args.cases)=={c['id'] for c in selected})
 records=[];pairs=[];spreads=[];conditions=[];started=time.perf_counter();planned=len(selected)*4*args.repeat
 for ci,c0 in enumerate(selected):
  d=run/'inputs'/c0['id'];d.parent.mkdir(exist_ok=True);c=configure(c0,d);conditions.append(c);history={v:[] for v in VARIANTS}
  for rep in range(args.repeat):
   current={};rotation=(rep+ci)%4;order=VARIANTS[rotation:]+VARIANTS[:rotation]
   for position,v in enumerate(order):
    remaining=args.max_seconds-(time.perf_counter()-started);assert remaining>0,'suite cap reached'
    folder=run/'runs'/f'{c["id"]}_{v}_{rep+1}';folder.parent.mkdir(exist_ok=True);shutil.copytree(d,folder);e=env.copy()
    if v=='combined_on':e['GRAL_WORKER_CONCENTRATION_MB']='256'
    r=f.process(ROOT/'sources'/SOURCE[v]/'src/bin/Release/net10.0/GRAL.dll',folder,e,timeout=min(90,remaining));text=(folder/'console.log').read_text(encoding='utf-8',errors='replace');core=folder/'Logfile_GRALCore.txt';problem=folder/'Problemreport_GRAL.txt'
    assert r['exit_code']==0 and core.exists() and 'GRAL simulations finished at:' in core.read_text(encoding='utf-8-sig') and not(problem.exists() and problem.read_text().strip()),text[-4000:]
    actual=list(map(int,re.findall(r'Using a total of (\d+) particles',text)));assert len(actual)==1 and abs(actual[0]-c['particles'])<=c['sources'],(c,actual)
    counts={}
    for k,label in {'point':'point sources','area':'area source partitions','portal':'tunnel portals','line':'line source segments'}.items():
     n=re.findall(r'Total number of '+label+r': (\d+)',text);counts[k]=int(n[0]) if n else 0;assert counts[k]==c['source_counts'].get(k,0),(c,counts)
    logs=re.findall(r'Worker concentration buffers: ([^\r\n]+)',text)
    if v=='combined_on':
     assert len(logs)==1 and logs[0].startswith('shared (driver)' if c['workers']==1 else 'enabled'),logs
    else:assert not logs,(v,logs)
    guards=re.findall(r'(?:Rejected|Skipped) (\d+) non-finite',text);assert not any(int(x) for x in guards),(v,guards)
    a,h=f.payloads(folder,c);current[v]=a;history[v].append(a);disp=re.findall(r'Dispersion \[s\]: ([\d.]+)',text)
    r.update(case=c['id'],variant=v,repeat=rep+1,order_position=position+1,requested_particles=c['particles'],actual_particles=actual[0],workers=c['workers'],actual_source_counts=counts,buffer_log=logs,guard_reports=guards,reported_dispersion_s=float(disp[-1]) if disp else None,payload_hashes=h,**aggregate(a));records.append(r)
    save(run/'progress.json',dict(status='running',completed=len(records),planned=planned,last={k:r[k] for k in ['case','variant','repeat','wall_s']},elapsed_s=time.perf_counter()-started));print('[MAIN]',len(records),c['id'],v,rep+1,round(r['wall_s'],3),flush=True)
   for left,right in itertools.combinations(VARIANTS,2):pairs.append(dict(case=c['id'],reference=left,candidate=right,repeat=rep+1,**compare(current[left],current[right])))
   if c['workers']==1:
    assert compare(current['reviewed'],current['combined_off'])['changed_cells']==0 and compare(current['reviewed'],current['combined_on'])['changed_cells']==0,'serial reviewed path changed'
  for v in VARIANTS:
   for (i,a),(j,b) in itertools.combinations(enumerate(history[v],1),2):spreads.append(dict(case=c['id'],variant=v,repeat_a=i,repeat_b=j,**compare(a,b)))
 summaries=[];timing=[]
 for c in conditions:
  for v in VARIANTS:
   rs=[r for r in records if r['case']==c['id'] and r['variant']==v];t=[r['wall_s'] for r in rs];spread=[r for r in spreads if r['case']==c['id'] and r['variant']==v]
   summaries.append(dict(case=c['id'],variant=v,n=len(t),median_wall_s=statistics.median(t),min_wall_s=min(t),max_wall_s=max(t),median_cpu_s=statistics.median(r['cpu_s'] for r in rs),median_peak_working_bytes=statistics.median(r['memory']['PeakWorkingSetSize'] for r in rs),max_peak_working_bytes=max(r['memory']['PeakWorkingSetSize'] for r in rs),median_peak_commit_bytes=statistics.median(r['memory']['PeakPagefileUsage'] for r in rs),max_repeat_relative_l1=max((r['relative_l1'] for r in spread),default=0),max_repeat_absolute_difference=max((r['max_absolute'] for r in spread),default=0),min_cell_sum=min(r['concentration_cell_sum'] for r in rs),max_cell_sum=max(r['concentration_cell_sum'] for r in rs),min_max_concentration=min(r['max_concentration'] for r in rs),max_max_concentration=max(r['max_concentration'] for r in rs)))
  for left,right in itertools.combinations(VARIANTS,2):
   a=[r['wall_s'] for r in records if r['case']==c['id'] and r['variant']==left];b=[r['wall_s'] for r in records if r['case']==c['id'] and r['variant']==right];ratio=[y/x for x,y in zip(a,b)];timing.append(dict(case=c['id'],reference=left,candidate=right,median_wall_ratio=statistics.median(b)/statistics.median(a),median_paired_wall_ratio=statistics.median(ratio),paired_wall_ratio_min=min(ratio),paired_wall_ratio_max=max(ratio),median_time_change_percent=100*(statistics.median(b)/statistics.median(a)-1)))
 result=dict(status='pass',main_runs=len(records),repeat=args.repeat,source_hashes_checked=checked,builds=builds,conditions=conditions,records=records,comparisons=pairs,repeat_comparisons=spreads,summaries=summaries,timing_comparisons=timing,elapsed_s=time.perf_counter()-started,limits=['Synthetic stationary fields; these measurements do not establish production-domain speedups or transient residual behavior.','Cold process wall time includes startup, JIT, flow initialization and output. Five cyclically interleaved repeats are not a fully position-balanced design.','Current upstream already contains merged PRs 59, 60, 61 and 65. PRs 62 and 63 are deliberately excluded.','Concentration cell sum is a numerical output diagnostic, not atmospheric total mass. Each output slice and selected source group is included.','Worker buffers are off by default. Enabled buffers change the grouping of double additions. The tests measure output differences and independent repeat spread.','OS peak working-set and process-commit counters include the whole engine; PrivateUsage is a sampled 10 ms maximum.'])
 verify();save(run/'summary.json',result)
 for name,rows in [('runs',[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in records]),('comparisons',pairs),('repeat_comparisons',spreads),('summary',summaries),('timing',timing)]:
  with (run/(name+'.csv')).open('w',newline='',encoding='utf-8') as out:w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 save(run/'progress.json',dict(status='complete',completed=len(records),planned=planned));print('[PASS]',len(records),'Main runs',flush=True)
if __name__=='__main__':main()
