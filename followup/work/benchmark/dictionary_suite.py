from pathlib import Path
import argparse,json,os,re,shutil,statistics,hashlib,struct,time,zipfile,gc
import numpy as np
import field_support as f
import run_validation as old
J=Path(__file__).resolve().parents[2]
f.ROOT=Path(__file__).resolve().parent
f.DOTNET=Path(r'C:\Program Files\dotnet\dotnet.exe')
def cases():
 d=json.loads((J/'qa/test_design.json').read_text()); out=[dict(d['common'],**c) for c in d['primary_cases']]
 out += [dict(d['common'],id='buildings_mixed_t4',pps=500,tau=300,sources=32,sg=8,kind='mixed',buildings=6,flow=20,conc=10),dict(d['common'],id='hot_stack_t1',pps=1000,tau=300,sources=8,sg=8,hot=True,sc=2,speed=2.5,workers=1),dict(d['common'],id='transient_three_t1',pps=100,tau=120,kind='mixed',sources=8,sg=2,workers=1,transient=True),dict(d['common'],id='sg108_boundary',pps=100,tau=30,sources=108,sg=108,workers=1,expected_boundary=True),dict(d['common'],id='dry_deposition_t1',pps=100,tau=120,sources=2,sg=2,workers=1,deposition=True)]
 out += [dict(d['common'],id=f'sg{n}_boundary',pps=100,tau=30,sources=n,sg=n,workers=1,expected_boundary=True) for n in [101,102]]
 out += [dict(d['common'],id='labels_1_99_100_255',pps=100,tau=60,sources=4,sg=4,workers=1,labels=[1,99,100,255]),dict(d['common'],id='labels_1_257',pps=100,tau=60,sources=2,sg=2,workers=1,labels=[1,257])]
 out += [dict(d["common"],id="missing_receptor_diagnostic",pps=100,tau=120,sources=2,sg=2,workers=1,missing_receptor=True)]
 out += [dict(d["common"],id="labels_1_99_100_101",pps=100,tau=60,sources=4,sg=4,workers=1,labels=[1,99,100,101]),dict(d["common"],id="labels_1_102",pps=100,tau=60,sources=2,sg=2,workers=1,labels=[1,102])]
 out += [dict(d['common'],id='sparse_sg99_fine1_t4',sources=99,sg=99,length=2400,flow=40,conc=10,slices=1)]
 return out
def configure(c,d):
 c=old.configure(c,d)
 if c.get('labels'):
  p=d/'GRAL.geb';rows=p.read_text().splitlines();rows[6]=','.join(map(str,c['labels']));p.write_text('\n'.join(rows)+'\n')
  p=d/'point.dat';rows=p.read_text().splitlines()
  for i in range(len(rows)-2):
   a=rows[i+2].split(',');a[10]=str(c['labels'][i%len(c['labels'])]);rows[i+2]=','.join(a)
  p.write_text('\n'.join(rows)+'\n')
 if c.get('distributed'):
  p=d/'point.dat';lines=p.read_text().splitlines()
  for i in range(len(lines)-2):
   a=lines[i+2].split(',');a[0]=str(40+(i%4)*90);a[1]=str(40+(i//4)*90);lines[i+2]=','.join(a)
  p.write_text('\n'.join(lines)+'\n')
 if c.get('deposition'):
  p=d/'point.dat';lines=p.read_text().splitlines();lines=lines[:2]+[x+',100,100,30,1000,0.005,0,0,1' for x in lines[2:]];p.write_text('\n'.join(lines)+'\n')
 if c.get('missing_receptor'):
  p=d/'in.dat';lines=p.read_text().splitlines();lines[4]='1';p.write_text('\n'.join(lines)+'\n');assert not (d/'Receptor.dat').exists()
 c['total_output_slots']=c['nx']*c['ny']*c['slices']*c['sg'];f.save(d/'case.json',c)
 return c
def decode(d,c):
 vals={};hashes={};sums={};issues=[];nonzero=0;con_count=dep_count=dep_nonzero=0
 for p in sorted(d.glob('*.grz')):
  with zipfile.ZipFile(p) as z:
   for n in sorted(z.namelist()):
    if not n.endswith(('.con','.dep')):continue
    b=z.read(n);h,x,y,dx,dy,nx,ny=struct.unpack_from('<iiiffii',b)
    assert (h,x,y,nx,ny)==(-3,0,0,c['nx'],c['ny']) and dx==dy==c['conc'] and len(b)==28+nx*ny*4,(p,n)
    v=np.frombuffer(b[28:],dtype='<f4').copy();assert np.isfinite(v).all() and (v>=0).all(),(p,n)
    key=p.name+':'+n;vals[key]=v;hashes[key]=hashlib.sha256(b).hexdigest()
    if n.endswith('.con'):
     con_count+=1;sums[p.name]=sums.get(p.name,0.0)+float(v.sum(dtype=np.float64));nonzero+=int(np.count_nonzero(v))
    else:dep_count+=1;dep_nonzero+=int(np.count_nonzero(v))
 expected=c['slices']*c['sg']*c['situations']
 if con_count!=expected:issues.append(f'con_count_{con_count}_expected_{expected}')
 if c.get('deposition'):
  if dep_count!=c['sg']*c['situations']:issues.append('deposition_count')
  if not dep_nonzero:issues.append('deposition_zero')
 if not nonzero:issues.append('no_concentration')
 if c.get('transient') and sums.get('00002.grz',0)==0:issues.append('residual_only_situation_zero')
 return vals,{'payload_hashes':hashes,'situation_sums':sums,'nonzero_values':nonzero,'deposition_fields':dep_count,'deposition_nonzero':dep_nonzero,'output_values':sum(v.size for v in vals.values()),'occupied_fraction':nonzero/(c['total_output_slots']*c['situations']),'issues':issues}
def compare(a,b):
 if a.keys()!=b.keys() or not a:return {'comparable':False}
 total=changed=0;absdiff=refsum=maxabs=0.0
 for k in a:
  x=a[k];y=b[k];total+=x.size;changed+=int(np.count_nonzero(x!=y));diff=np.abs(x.astype(np.float64)-y);absdiff+=float(diff.sum());refsum+=float(np.abs(x.astype(np.float64)).sum());maxabs=max(maxabs,float(diff.max(initial=0)))
 return {'comparable':True,'fields':len(a),'values':total,'changed_values':changed,'exact':changed==0,'sum_abs':absdiff,'reference_sum':refsum,'relative_l1':absdiff/refsum if refsum else 0.0,'max_abs':maxabs}
def main():
 p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--cases',nargs='+');p.add_argument('--variants',nargs='+',default=['float','double','dictionary','dictionary_fixed']);p.add_argument('--repeats',type=int,default=3);p.add_argument('--timeout',type=float,default=120);a=p.parse_args()
 out=J/'results'/a.tag;out.mkdir(parents=True);assert not (out/'records.json').exists()
 env=os.environ.copy();env.update(TEMP=str(J/'tmp'),TMP=str(J/'tmp'),DOTNET_CLI_UI_LANGUAGE='en',DOTNET_CLI_TELEMETRY_OPTOUT='1');env.pop('GRAL_WORKER_CONCENTRATION_MB',None)
 plan=[c for c in cases() if not a.cases or c['id'] in a.cases];assert plan
 records=[];comparisons=[];conditions=[];start=time.perf_counter()
 f.save(out/'plan.json',{'cases':plan,'variants':a.variants,'warmups':1,'measured_repeats':a.repeats,'process_limit_s':a.timeout,'chunk_limit_s':840,'order':'rotating','harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'binary_sha256':{v:hashlib.sha256((J/'build'/v/'GRAL.dll').read_bytes()).hexdigest() for v in a.variants}})
 for ci,raw in enumerate(plan):
  c=configure(raw,out/'inputs'/raw['id']);conditions.append(c);first={}
  for rep in range(a.repeats+1):
   rotate=(ci+rep)%len(a.variants);order=a.variants[rotate:]+a.variants[:rotate];current={}
   for v in order:
    assert time.perf_counter()-start<840,'chunk budget reached'
    d=out/'runs'/f'{c["id"]}_{v}_{rep}';shutil.copytree(out/'inputs'/c['id'],d)
    row={'case':c['id'],'variant':v,'repeat':rep,'measured':rep>0,'status':'pass'}
    try:
     rec=f.process(J/'build'/v/'GRAL.dll',d,env,min(a.timeout,840-(time.perf_counter()-start)));row.update(rec)
     log=(d/'console.log').read_text(encoding='utf-8',errors='replace');corepath=d/'Logfile_GRALCore.txt';core=corepath.read_text(encoding='utf-8-sig',errors='replace') if corepath.exists() else '';problem=d/'Problemreport_GRAL.txt'
     issues=[]
     if rec['exit_code']!=0:issues.append('nonzero_exit')
     if 'GRAL simulations finished at:' not in core:issues.append('incomplete')
     if problem.exists() and problem.read_text(encoding='utf-8-sig',errors='replace').strip():issues.append('problem_report')
     counts=list(map(int,re.findall(r'Using a total of (\d+) particles',log)));row['actual_particles']=counts;row['actual_particles_per_s']=[n/c['tau'] for n in counts]
     if len(counts)!=1 or not .9*c['particles']<=counts[0]<=1.1*c['particles']:issues.append('particle_count')
     if 'GRAL Deterministic Mode' not in log:issues.append('seed_not_fixed')
     if len(re.findall(r'Init meteo:',log))!=c['situations']:issues.append('weather_count')
     if c.get('terrain') and ('FLOW FIELD COMPUTATION WITH TOPOGRAPHY' not in log or 'Reading GRAMM wind field:' not in log):issues.append('terrain_path_missing')
     if c.get('buildings') and f"Total number of blocked cells in 2D: {c['buildings']}" not in log:issues.append('building_path_missing')
     row['actual_source_counts']={}
     for kind,label in {'point':'point sources','area':'area source partitions','portal':'tunnel portals','line':'line source segments'}.items():
      match=re.findall('Total number of '+label+r': (\d+)',log);num=int(match[0]) if match else 0;row['actual_source_counts'][kind]=num
      if num!=c['source_counts'].get(kind,0):issues.append('source_count_'+kind)
     values,stats=decode(d,c);row.update(stats);issues+=row.pop('issues');row['issues']=issues
     if c.get('deposition'):
      row['deposition_files']=[str(p.relative_to(d)) for p in d.rglob('*.dep')]
      withzip=[]
      for zp in d.glob('*.grz'):
       with zipfile.ZipFile(zp) as z:withzip += [str(zp.name)+':'+n for n in z.namelist() if n.endswith('.dep')]
      row['deposition_files']+=withzip
      if not row['deposition_files']:row['issues'].append('deposition_missing')
     if issues:row['status']='fail'
     current[v]=values
     if v in first:comparisons.append(dict(case=c['id'],kind='repeat',reference=v,variant=v,repeat=rep,**compare(first[v],values)))
     elif values:first[v]=values
    except Exception as ex:
     row['status']='error';row['error']=type(ex).__name__+': '+str(ex)
    records.append(row);f.save(out/'records.json',records);f.save(out/'comparisons.json',comparisons)
    print('[RUN]',a.tag,len(records),c['id'],v,rep,row['status'],round(row.get('wall_s',0),3),row.get('issues',row.get('error','')),flush=True)
   for reference in ['float','double']:
    if reference in current:
     for v in a.variants:
      if v!=reference and v in current:comparisons.append(dict(case=c['id'],kind='paired',reference=reference,variant=v,repeat=rep,**compare(current[reference],current[v])))
   f.save(out/'comparisons.json',comparisons)
  first.clear();current.clear();gc.collect()
 f.save(out/'conditions.json',conditions)
 f.save(out/'completion.json',{'completed':True,'runs':len(records),'failed':sum(r['status']!='pass' for r in records),'elapsed_s':time.perf_counter()-start})
 print('[DONE]',a.tag,len(records),flush=True)
if __name__=='__main__':main()
