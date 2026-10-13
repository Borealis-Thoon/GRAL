from pathlib import Path
import argparse,hashlib,importlib.util,json,os,re,shutil,statistics,struct,time
R=Path(__file__).resolve().parent

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('f_harness',R/'helpers/main_harness.py');sg=module('sg_harness',R/'helpers/transient_harness.py')
a=argparse.ArgumentParser();a.add_argument('--suite',choices=['met'],default='met');a.add_argument('--repeat',type=int,default=5);a.add_argument('--cases',nargs='+');a.add_argument('--tag',default='');args=a.parse_args();assert args.repeat>=5
run=R/('small_main_'+args.suite+args.tag);run.mkdir();(run/'tmp').mkdir();env=os.environ.copy();env.update(TEMP=str(run/'tmp'),TMP=str(run/'tmp'),DOTNET_CLI_HOME=str(run/'cache'));start=time.perf_counter();records=[];comparisons=[];conditions=[]
base=dict(kind='area',sources=4,sg=2,length=1200,flow=20,conc=20,slices=1,tau=120,speed=.5,sc=2,hot=False,workers=1,vertical=40)
met=[dict(base,id='zr_30k',particles=30000,zr=True),dict(base,id='unstable_small',particles=3000),dict(base,id='unstable_100k',particles=100000),dict(base,id='unstable_terrain',particles=30000,terrain=True),dict(base,id='unstable_hot_mixed',particles=30000,kind='mixed',sources=16,hot=True,speed=2),dict(base,id='stable_100k',particles=100000,sc=6),dict(base,id='sonic_30k',particles=30000,sonic=True),dict(base,id='transient_unstable',transient=True,particles=3000)]
variants=['met_baseline','met_variance']
selected=met
if args.cases:selected=[c for c in selected if c['id'] in args.cases]
for ci,c0 in enumerate(selected):
 d=run/'inputs'/c0['id'];d.parent.mkdir(exist_ok=True)
 if c0.get('transient'):
  c=dict(id=c0['id'],kind='area',ids=[1,2],budget=3000,dx=20,duration=30,situations=3,workers=1,stationary=False,decay=False,transient=True,source_counts={'area':2})
  sg.make_input(c,d,R/'transient_template')
  (d/'meteopgt.all').write_text('10,1,10\nwind_dir,wind_speed,stability,frequency\n9,.5,2,1\n9,1,4,1\n9,.5,2,1\n')
  (d/'mettimeseries.dat').write_text('01.01.2022 00 .5 9 2\n01.01.2022 01 1 9 4\n01.01.2022 02 .5 9 2\n')
 else:
  c=m.configure(c0,d)
  if c.get('buildings'):(d/'buildings.dat').write_text('180 200 0 6\n180 220 0 10\n')
  if c.get('zr'):
   lines=(d/'in.dat').read_text().splitlines();lines[3]='0';(d/'in.dat').write_text('\n'.join(lines)+'\n');(d/'inputzr.dat').write_text('1\n10\n0 .2 -50 800 .3 -1 0\n')
  if c.get('sonic'):
   lines=(d/'in.dat').read_text().splitlines();lines[3]='3';(d/'in.dat').write_text('\n'.join(lines)+'\n');(d/'sonic.dat').write_text('10\n1 90 .2 .3 .3 .2 -50 0 0 300\n')
 conditions.append(c);first={}
 for rep in range(args.repeat):
  current={}
  for v in variants if (rep+ci)%2==0 else variants[::-1]:
   assert time.perf_counter()-start<840
   f=run/'runs'/f'{c["id"]}_{v}_{rep}';f.parent.mkdir(exist_ok=True);shutil.copytree(d,f)
   result=m.process(R/'bin'/v/'GRAL.dll',f,env,90);out=(f/'console.log').read_text(encoding='utf-8');log=(f/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig')
   assert result['exit_code']==0 and 'GRAL simulations finished at:' in log,(f,out[-2000:])
   p=f/'Problemreport_GRAL.txt';assert not p.exists() or not p.read_text().strip(),f
   counts=[int(x) for x in re.findall(r'Using a total of (\d+) particles',out)];assert counts
   actual_sources={}
   for kind,label in {'point':'point sources','area':'area source partitions','portal':'tunnel portals','line':'line source segments'}.items():
    z=re.findall('Total number of '+label+r': (\d+)',out);actual_sources[kind]=int(z[0]) if z else 0;assert actual_sources[kind]==c['source_counts'].get(kind,0),(c,actual_sources)
   if c.get('terrain'):assert 'FLOW FIELD COMPUTATION WITH TOPOGRAPHY' in out and 'Reading GRAMM wind field:' in out
   if c.get('buildings'):assert 'Total number of blocked cells in 2D: 2' in out
   if c.get('zr'):assert 'Observational heights: 10.00m' in out
   if c.get('sonic'):assert 'Observational heights: 10.00' in out
   if c.get('transient'):h,sums=sg.payloads(f,c)
   else:values,h=m.payloads(f,c)
   if v in first:assert first[v]==h,(c['id'],v,rep)
   else:first[v]=h
   current[v]=h
   geometry=struct.unpack('<3i',(f/'GRAL_geometries.txt').read_bytes()[:12]) if (f/'GRAL_geometries.txt').exists() else None
   result.update(case=c['id'],variant=v,repeat=rep,actual_particles=counts,source_counts=actual_sources,payload_hashes=h,geometry_nkk_njj_nii=geometry);records.append(result);m.save(run/'records.json',records);print('[MAIN]',len(records),c['id'],v,round(result['wall_s'],3),flush=True)
  assert current[variants[0]]==current[variants[1]],c['id'];comparisons.append(dict(case=c['id'],repeat=rep,equal=True))
summary=[]
for c in conditions:
 bs=[r for r in records if r['case']==c['id'] and r['variant']==variants[0]];cs=[r for r in records if r['case']==c['id'] and r['variant']==variants[1]];b=[r['wall_s'] for r in bs];h=[r['wall_s'] for r in cs]
 summary.append(dict(case=c['id'],baseline_median_s=statistics.median(b),candidate_median_s=statistics.median(h),median_runtime_ratio=statistics.median(h)/statistics.median(b),paired_median_runtime_ratio=statistics.median(y/x for x,y in zip(b,h)),baseline_range_s=[min(b),max(b)],candidate_range_s=[min(h),max(h)],cpu_runtime_ratio=statistics.median(r['cpu_s'] for r in cs)/statistics.median(r['cpu_s'] for r in bs)))
m.save(run/'summary.json',dict(status='pass',suite=args.suite,main_runs=len(records),conditions=conditions,records=records,comparisons=comparisons,summaries=summary,elapsed_s=time.perf_counter()-start));print('[PASS]',len(records),flush=True)
