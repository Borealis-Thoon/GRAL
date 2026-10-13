from pathlib import Path
import argparse,importlib.util,json,os,re,shutil,time,zipfile,struct,hashlib,statistics
import numpy as np
ROOT=Path(__file__).resolve().parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
import field_support as f
import transient_support as r
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def cases():
 rows=[]
 def add(name,workers=4,**kw):
  c=dict(id=name,dx=20,budget=3000,kind='point',sources=2,groups=2,pattern='steady',workers=workers,ratio=1,duration=30,situations=3,wind_m_s=.5,stability=4,slices=1,mode='transient',mb=256);c.update(kw);rows.append(c)
 add('one_worker',1)
 add('four_workers',4)
 add('twentyfour_workers',24)
 add('mixed_groups',4,kind='mixed',sources=8,groups=8)
 add('mixed_groups_24',24,kind='mixed',sources=8,groups=8)
 add('pulse_stable',4,kind='area',sources=8,groups=8,pattern='pulse',wind_m_s=.25,stability=6)
 add('large_source_off',4,kind='point',sources=2,groups=2,pattern='largeoff',ratio=99,wind_m_s=1,stability=2)
 add('many_selected_few_allocated',4,sources=2,groups=8)
 add('nine_slices_enabled',4,dx=5,kind='area',sources=8,groups=8,slices=9)
 add('nine_slices_budget_fallback',24,dx=5,kind='area',sources=8,groups=8,slices=9,mb=1)
 add('decay',4,decay=True)
 add('odour',4,odour=True)
 add('terrain',4,mode='terrain',kind='area',sources=2,groups=2,situations=1)
 add('stationary_concentrated',4,mode='stationary',situations=1,duration=120,wind_m_s=.25,stability=6)
 return rows

def prepare_case(c,d):
 if c['mode']=='transient':
  detail=r.input_case(c,d);n=200//c['dx'];shape=dict(nx=n,ny=n,dx=c['dx'],sg=c['groups'],slices=c['slices'],situations=c['situations'])
  if c['slices']!=1:
   p=d/'GRAL.geb';lines=p.read_text().splitlines();lines[5]=str(c['slices']);p.write_text('\n'.join(lines)+'\n');p=d/'in.dat';lines=p.read_text().splitlines();lines[9]=' '.join(str(2+4*i) for i in range(c['slices']));p.write_text('\n'.join(lines)+'\n')
 else:
  cfg=dict(id='parallel_concentrated' if c['mode']=='stationary' and c.get('concentrated',True) else c['id'],particles=c['budget'],kind=c['kind'],sources=c['sources'],sg=c['groups'],length=c.get('length',800 if c['mode']=='stationary' else 400),flow=c.get('flow',40),conc=c.get('conc',40),slices=c['slices'],tau=c['duration'],speed=c['wind_m_s'],sc=c['stability'],hot=False,workers=c['workers'],terrain=c['mode']=='terrain')
  detail=f.configure(cfg,d);shape=dict(nx=detail['nx'],ny=detail['ny'],dx=cfg['conc'],sg=c['groups'],slices=c['slices'],situations=1)
 if c.get('decay'):(d/'Pollutant.txt').write_text('NOX\n0\n0\n0.005\n2:0.02\n')
 if c.get('odour'):(d/'Pollutant.txt').write_text('odour\n0\n0\n0\n')
 save(d/'worker_case.json',dict(c,shape=shape,source_description=detail));return shape,detail

def output(d,shape):
 values={};hashes={};weather=list(d.glob('*.grz'));assert len(weather)==shape['situations'],(len(weather),shape)
 for p in sorted(weather):
  with zipfile.ZipFile(p) as z:
   members=[n for n in z.namelist() if n.endswith('.con')];assert len(members)==shape['sg']*shape['slices'],(len(members),shape)
   for name in z.namelist():
    raw=z.read(name);key=p.name+':'+name;hashes[key]=hashlib.sha256(raw).hexdigest()
    if name.endswith('.con'):
     h=struct.unpack_from('<iiiffii',raw);assert h==(-3,0,0,float(shape['dx']),float(shape['dx']),shape['nx'],shape['ny']);assert len(raw)==28+4*shape['nx']*shape['ny'];v=np.frombuffer(raw[28:],dtype='<f4').copy();assert np.isfinite(v).all() and (v>=0).all();values[key]=v
 assert sum(float(v.sum()) for v in values.values())>0
 return values,hashes

def main():
 p=argparse.ArgumentParser();p.add_argument('--repeat',type=int,default=3);p.add_argument('--run-name',default='main');p.add_argument('--cases',nargs='+');p.add_argument('--max-seconds',type=int,default=360);args=p.parse_args();run=ROOT/args.run_name;run.mkdir();(run/'tmp').mkdir();env=os.environ.copy();env.update(TEMP=str(run/'tmp'),TMP=str(run/'tmp'));env.pop('GRAL_WORKER_CONCENTRATION_MB',None)
 variants=['f64','off','on'];dlls={'f64':ROOT/'source/f64/src/bin/Release/net10.0/GRAL.dll','off':ROOT/'repo/src/bin/Release/net10.0/GRAL.dll','on':ROOT/'repo/src/bin/Release/net10.0/GRAL.dll'};records=[];pairs=[];repeatdiffs=[];conditions=[];start=time.perf_counter();selected=[c for c in cases() if not args.cases or c['id'] in args.cases]
 for c in selected:
  d=run/'inputs'/c['id'];d.parent.mkdir(exist_ok=True);shape,detail=prepare_case(c,d);conditions.append(dict(c,shape=shape));first={}
  for rep in range(args.repeat):
   current={};rotation=(rep+selected.index(c))%3
   for v in variants[rotation:]+variants[:rotation]:
    if time.perf_counter()-start>args.max_seconds:raise TimeoutError('suite budget')
    folder=run/'runs'/f'{c["id"]}_{v}_{rep}';folder.parent.mkdir(exist_ok=True);shutil.copytree(d,folder);e=env.copy()
    if v=='on':e['GRAL_WORKER_CONCENTRATION_MB']=str(c['mb'])
    result=f.process(dlls[v],folder,e,timeout=60);text=(folder/'console.log').read_text(encoding='utf-8',errors='replace');core=folder/'Logfile_GRALCore.txt';problem=folder/'Problemreport_GRAL.txt';assert result['exit_code']==0 and core.exists() and 'GRAL simulations finished at:' in core.read_text(encoding='utf-8-sig') and not(problem.exists() and problem.read_text().strip()),text[-3000:]
    allocation=[int(n) for n in re.findall(r'Using a total of (\d+) particles',text)];assert allocation,(c['id'],'allocation absent')
    sources={}
    for kind,label in {'point':'point sources','area':'area source partitions','line':'line source segments','portal':'tunnel portals'}.items():
     a=re.findall(r'Total number of '+label+r': (\d+)',text);sources[kind]=int(a[0]) if a else 0;assert sources[kind]==detail['source_counts'].get(kind,0),(c['id'],sources,detail['source_counts'])
    if c['mode']=='terrain':assert 'FLOW FIELD COMPUTATION WITH TOPOGRAPHY' in text and 'Reading GRAMM wind field:' in text
    logs=re.findall(r'Worker concentration buffers: ([^\r\n]+)',text)
    if v=='on':
     assert len(logs)==c['situations'],logs
     if c['workers']==1:assert all(s.startswith('shared (driver)') for s in logs)
     elif c['mb']==1:assert all(s.startswith('shared (budget') for s in logs)
     else:assert all(s.startswith('enabled') for s in logs),logs
    else:assert not logs,(v,logs)
    if c['mode']=='transient':
     m=re.findall(r'Summarized emission rates per source group in kg\s*\n[^\n]*SG:[^\n]*\n([^\n]+)',text);assert m;actual=list(map(float,m[-1].split()));expected=detail['expected_fresh_mass_kg'];assert len(actual)==len(expected);assert all(abs(x-y)<=.00011+.006*abs(y) for x,y in zip(actual,expected)),(actual,expected)
    a,h=output(folder,shape);current[v]=(a,h)
    if v in first:repeatdiffs.append(dict(case=c['id'],variant=v,repeat=rep,all_payload_equal=first[v][1]==h,**f.diff(first[v][0],a)))
    else:first[v]=(a,h)
    result.update(case=c['id'],variant=v,repeat=rep,nominal_particles=c['budget'],actual_particles=allocation,workers=c['workers'],source_counts=sources,buffer_log=logs,payload_hashes=h);records.append(result);save(run/'progress.json',dict(status='running',completed=len(records),planned=len(selected)*len(variants)*args.repeat,last=c['id']+' '+v));print('[MAIN]',len(records),c['id'],v,rep,flush=True)
   for v in ['off','on']:
    delta=f.diff(current['f64'][0],current[v][0]);pairs.append(dict(case=c['id'],variant=v,repeat=rep,all_payload_equal=current['f64'][1]==current[v][1],**delta))
    if c['workers']==1:assert current['f64'][1]==current[v][1],(c['id'],v,'one-worker mismatch')
 summaries=[]
 for c in selected:
  baseline=[r['wall_s'] for r in records if r['case']==c['id'] and r['variant']=='f64']
  for v in variants:
   rr=[r for r in records if r['case']==c['id'] and r['variant']==v];t=[r['wall_s'] for r in rr];summaries.append(dict(case=c['id'],variant=v,median_s=statistics.median(t),min_s=min(t),max_s=max(t),median_ratio=statistics.median(t)/statistics.median(baseline),peak_working_set=max(r['memory']['PeakWorkingSetSize'] for r in rr),sampled_peak_private=max(r['memory']['PrivateUsage'] for r in rr)))
 result=dict(status='pass',conditions=conditions,main_runs=len(records),records=records,paired_comparisons=pairs,repeat_differences=repeatdiffs,summaries=summaries,elapsed_s=time.perf_counter()-start,scope='Shared sums remain the default. Enabled worker sums change double addition grouping; multiworker differences are compared with the baseline repeat spread. Working-set and private-memory observations include the whole engine, not only the bounded buffers.')
 save(run/'summary.json',result);save(run/'progress.json',dict(status='complete',completed=len(records),planned=len(selected)*len(variants)*args.repeat));print('[PASS]',len(records),'Main runs',flush=True)
if __name__=='__main__':main()
