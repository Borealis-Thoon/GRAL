from pathlib import Path
import argparse,importlib.util,os,json,hashlib,subprocess,time,shutil,re,statistics,csv

p=argparse.ArgumentParser();p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--qa-dir',type=Path,required=True);p.add_argument('--dotnet',default='dotnet');a=p.parse_args()
W=a.work_dir.resolve();Q=a.qa_dir.resolve();Q.mkdir(parents=True,exist_ok=True)
s=importlib.util.spec_from_file_location('field_support',W/'field_support.py');f=importlib.util.module_from_spec(s);s.loader.exec_module(f);f.DOTNET=Path(a.dotnet)
manifest=json.loads((W/'source_manifest.json').read_text());assert all(hashlib.sha256((W/x).read_bytes()).hexdigest()==h for x,h in manifest['files'].items())
R=W/'run';R.mkdir(exist_ok=False);(R/'tmp').mkdir()
env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(R/'cache'),TEMP=str(R/'tmp'),TMP=str(R/'tmp'),DOTNET_CLI_UI_LANGUAGE='en');env.pop('GRAL_WORKER_CONCENTRATION_MB',None)
variants=['baseline','pr68','pr69','pr72'];start=time.perf_counter();builds={};records=[]
for v in variants:
 p=subprocess.run([str(f.DOTNET),'build',str(W/'source'/v/'src/GRAL.csproj'),'-c','Release','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true'],capture_output=True,env=env,timeout=90)
 text=(p.stdout+p.stderr).decode('utf-8',errors='replace');(Q/f'build_{v}.log').write_text(text,encoding='utf-8');assert p.returncode==0 and '0 Warning(s)' in text and '0 Error(s)' in text,text
 builds[v]={'warnings':0,'errors':0};print('[BUILD]',v,flush=True)
cases=[
 dict(id='terrain_stable_100ps',terrain=True,pps=100,tau=120,kind='area',sources=26,sg=26,length=1200,flow=20,conc=20,slices=1,speed=.5,sc=6,hot=False,workers=1),
 dict(id='terrain_hot_1000ps',terrain=True,pps=1000,tau=180,kind='point',sources=64,sg=26,length=1200,flow=20,conc=10,slices=9,speed=2.5,sc=2,hot=True,workers=1),
 dict(id='flat_mixed_500ps',pps=500,tau=240,kind='mixed',sources=128,sg=26,length=1600,flow=40,conc=20,slices=1,speed=2.5,sc=2,hot=False,workers=1),
 dict(id='flat_area_1000ps',pps=1000,tau=300,kind='area',sources=64,sg=26,length=1600,flow=20,conc=10,slices=9,speed=1,sc=2,hot=False,workers=1),
]
for c in cases:c['particles']=c['pps']*c['tau']
for ci,case in enumerate(cases):
 template=R/'inputs'/case['id'];template.parent.mkdir(exist_ok=True);case=f.configure(case,template);cases[ci]=case;reference=None
 for rep in range(6):
  order=variants[rep%4:]+variants[:rep%4]
  for v in order:
   assert time.perf_counter()-start<720,'whole suite watchdog'
   d=R/'runs'/f"{case['id']}_{v}_{rep}";d.parent.mkdir(exist_ok=True);shutil.copytree(template,d)
   rec=f.process(W/'source'/v/'src/bin/Release/net10.0/GRAL.dll',d,env,timeout=60)
   log=(d/'console.log').read_text(encoding='utf-8',errors='replace');problem=d/'Problemreport_GRAL.txt'
   assert rec['exit_code']==0 and 'GRAL simulations finished at:' in (d/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig') and not(problem.exists() and problem.read_text().strip()),log[-2000:]
   arrays,hashes=f.payloads(d,case)
   if reference is None:reference=hashes
   assert hashes==reference,(case['id'],v,rep,'payload mismatch')
   if case.get('terrain'):assert 'FLOW FIELD COMPUTATION WITH TOPOGRAPHY' in log and 'Reading GRAMM wind field:' in log
   actual=int(re.search(r'Using a total of (\d+) particles',log).group(1));assert .95*case['particles']<=actual<=1.05*case['particles']
   assert all(r['actual_particles']==actual for r in records if r['case']==case['id'])
   rec.update(case=case['id'],variant=v,repeat=rep,measured=rep>0,configured_pps=case['pps'],duration_s=case['tau'],requested_particles=case['particles'],actual_particles=actual,actual_particles_per_s=actual/case['tau'],payloads=len(hashes),payload_manifest_sha256=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest())
   records.append(rec);f.save(Q/'hotloop_progress.json',{'executions':len(records),'last':rec,'records':records})
   print('[MAIN]',len(records),case['id'],v,rep,round(rec['wall_s'],4),flush=True)
summaries=[]
for c in cases:
 bs={r['repeat']:r for r in records if r['case']==c['id'] and r['variant']=='baseline' and r['measured']};b=statistics.median(r['wall_s'] for r in bs.values())
 for v in variants:
  rs=[r for r in records if r['case']==c['id'] and r['variant']==v and r['measured']];m=statistics.median(r['wall_s'] for r in rs)
  summaries.append(dict(case=c['id'],variant=v,median_wall_s=m,wall_s=[r['wall_s'] for r in rs],median_cpu_s=statistics.median(r['cpu_s'] for r in rs),median_peak_working_bytes=statistics.median(r['memory']['PeakWorkingSetSize'] for r in rs),percent_change_vs_baseline=100*(m/b-1),paired_percent_change=[100*(r['wall_s']/bs[r['repeat']]['wall_s']-1) for r in rs],payload_pairs=sum(r['payloads'] for r in rs)))
result=dict(status='pass',base=manifest['base'],heads={'pr68':'b4ffec5e2ab55d3ec3717ed37d04938837e00120','pr69':'7c23fe92803a019c1535af7f02fcc6b2e940f2ee','pr72':'bf99b2424264a194e0df6b3ded737b8c2e3d6990'},builds=builds,main_executions=len(records),timed_executions=80,warmups=16,cases=cases,summaries=summaries,records=records,elapsed_s=time.perf_counter()-start,method='Each functional PR is applied alone to the same upstream source. Fixed seeds, one worker. Each condition excludes one warmup for each variant and uses five interleaved timed repetitions, rotating the order. Whole-process time includes initialization and output. Exact concentration payloads, finite nonnegative values, requested and actual particle counts are checked on every run.')
f.save(Q/'hotloop_review.json',result)
keys=['case','variant','repeat','measured','configured_pps','duration_s','requested_particles','actual_particles','actual_particles_per_s','wall_s','cpu_s','payloads','payload_manifest_sha256']
with (Q/'hotloop_timings.csv').open('w',newline='',encoding='utf-8') as out:
 writer=csv.DictWriter(out,fieldnames=keys);writer.writeheader();writer.writerows({k:r[k] for k in keys} for r in records)
print('[PASS]',len(records),'Main',flush=True)
