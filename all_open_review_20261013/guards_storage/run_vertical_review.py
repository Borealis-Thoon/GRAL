from pathlib import Path
import importlib.util,json,os,statistics,subprocess,time,shutil,hashlib,re
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--work-dir',type=Path,required=True);ap.add_argument('--qa-dir',type=Path,required=True);ap.add_argument('--dotnet',default='dotnet');args=ap.parse_args()
W=args.work_dir.resolve();Q=args.qa_dir.resolve();Q.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('field_support',W/'field_support.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.DOTNET=Path(args.dotnet)
R=W/'vertical_run';R.mkdir(exist_ok=False)
env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(R/'cache'),TEMP=str(R/'tmp'),TMP=str(R/'tmp'),DOTNET_CLI_UI_LANGUAGE='en');(R/'tmp').mkdir()
variants=['baseline','current','height_first'];start=time.perf_counter();builds={};records=[]
for v in variants:
 p=subprocess.run([str(f.DOTNET),'build',str(W/'source'/v/'src/GRAL.csproj'),'-c','Release','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true'],capture_output=True,env=env,timeout=90)
 s=(p.stdout+p.stderr).decode('utf-8',errors='replace');(Q/f'vertical_build_{v}.log').write_text(s,encoding='utf-8');assert p.returncode==0 and '0 Warning(s)' in s and '0 Error(s)' in s,s
 builds[v]={'warnings':0,'errors':0};print('[BUILD]',v,flush=True)
cases=[]
for name,kind,slices,speed,sc,hot in [('terrain_area','area',1,.5,6,False),('terrain_hot_points','point',9,2.5,2,True)]:
 cases.append(dict(id=name,terrain=True,particles=100000,kind=kind,sources=26,sg=26,length=1200,flow=20,conc=20,slices=slices,tau=120,speed=speed,sc=sc,hot=hot,workers=1))
for case in cases:
 template=R/'inputs'/case['id'];template.parent.mkdir(exist_ok=True);case=f.configure(case,template);reference=None
 for rep in range(6):
  order=variants[rep%3:]+variants[:rep%3]
  for v in order:
   assert time.perf_counter()-start<235,'whole suite cap'
   d=R/'runs'/f"{case['id']}_{v}_{rep}";d.parent.mkdir(exist_ok=True);shutil.copytree(template,d)
   dll=W/'source'/v/'src/bin/Release/net10.0/GRAL.dll';rec=f.process(dll,d,env,timeout=25)
   log=(d/'console.log').read_text(encoding='utf-8',errors='replace');problem=d/'Problemreport_GRAL.txt'
   assert rec['exit_code']==0 and 'GRAL simulations finished at:' in (d/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig') and not(problem.exists() and problem.read_text().strip()),log[-2000:]
   arrays,hashes=f.payloads(d,case)
   if reference is None:reference=hashes
   assert hashes==reference,(case['id'],v,rep)
   assert 'FLOW FIELD COMPUTATION WITH TOPOGRAPHY' in log and 'Reading GRAMM wind field:' in log
   actual=int(re.search(r'Using a total of (\d+) particles',log).group(1))
   rec.update(case=case['id'],variant=v,repeat=rep,measured=rep>0,actual_particles=actual,payloads=len(hashes),hashes=hashes)
   records.append(rec);f.save(Q/'vertical_progress.json',{'executions':len(records),'last':{k:rec[k] for k in ['case','variant','repeat','wall_s']}})
   print('[MAIN]',len(records),case['id'],v,rep,round(rec['wall_s'],4),flush=True)
summaries=[]
for c in cases:
 b=statistics.median(r['wall_s'] for r in records if r['case']==c['id'] and r['variant']=='baseline' and r['measured'])
 for v in variants:
  rs=[r for r in records if r['case']==c['id'] and r['variant']==v and r['measured']];median=statistics.median(r['wall_s'] for r in rs)
  summaries.append(dict(case=c['id'],variant=v,median_wall_s=median,wall_s=[r['wall_s'] for r in rs],median_cpu_s=statistics.median(r['cpu_s'] for r in rs),median_peak_working_bytes=statistics.median(r['memory']['PeakWorkingSetSize'] for r in rs),percent_change_vs_baseline=100*(median/b-1),payload_pairs=sum(r['payloads'] for r in rs)))
result=dict(status='pass',base='891225b2f9dbbcda7f5ef6e9ef6db65e64845108',pr69_head='7c23fe92803a019c1535af7f02fcc6b2e940f2ee',builds=builds,main_executions=len(records),timed_executions=30,warmups=6,cases=cases,summaries=summaries,records=records,elapsed_s=time.perf_counter()-start,method='One worker, fixed seeds, 26 sources/groups, 100000 requested particles, two prescribed terrain fields. Each case has one excluded warmup per variant, then five interleaved repetitions. Whole-process wall time includes initialization and output. The one-line height-first alternative is evaluated independently of all other PRs.')
f.save(Q/'vertical_review.json',result)
print('[PASS]',len(records),'Main',flush=True)
