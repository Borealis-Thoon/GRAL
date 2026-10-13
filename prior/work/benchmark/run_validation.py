from pathlib import Path
import argparse, hashlib, json, math, os, re, shutil, statistics, struct, subprocess, time, zipfile
import numpy as np
import field_support as f
BUNDLE=Path(__file__).resolve().parent
ROOT=BUNDLE
VARIANTS=['baseline','wall_guard','source_type']
SOURCE_NAMES={name:name for name in VARIANTS}

def cases():
 b=dict(pps=1000,tau=600,kind='mixed',sources=32,sg=8,length=1200,flow=20,conc=20,slices=1,speed=1,sc=4,hot=False,workers=1,buildings=0,adaptive=0,transient=False)
 def c(ident,**kw):return dict(b,id=ident,**kw)
 # Grid, meteorology, emission type, obstacle density and worker setting vary independently.
 return [c('flat_neutral_100ps_t1',pps=100,tau=1200,kind='point',sources=8,flow=40),
 c('flat_convective_mixed_1000ps_t2',workers=2,sc=2,speed=2.5,sources=64,conc=10),
 c('terrain_stable_area_1000ps_t8',terrain=True,kind='area',sources=26,sg=26,workers=8,sc=6,speed=.5),
 c('flat_medium_8000ps_t8',pps=8000,tau=600,length=2400,sources=256,sg=26,workers=8,sc=4),
 c('flat_sparse_buildings_t2',pps=500,tau=300,workers=2,buildings=3,kind='point',sources=16),
 c('flat_dense_buildings_adaptive_t8',pps=500,tau=300,workers=8,buildings=36,adaptive=3,sc=2),
 c('terrain_buildings_adaptive_t1',pps=500,tau=300,terrain=True,buildings=3,adaptive=3,sc=6,speed=.5),
 c('transient_flat_mixed_t1',pps=100,tau=120,transient=True,kind='mixed',sources=8,sg=2),
 c('transient_terrain_buildings_t2',pps=100,tau=120,transient=True,terrain=True,buildings=3,workers=2,kind='mixed',sources=8,sg=2,speed=.5,sc=6)]

def configure(raw,d):
 c=dict(raw);c['particles']=c['pps']*c['tau'];c=f.configure(c,d)
 lines=(d/'in.dat').read_text().splitlines();lines[2]='0' if c['transient'] else '1';lines[12]='1' if c['buildings'] else '0';lines[17]=str(c['adaptive']);(d/'in.dat').write_text('\n'.join(lines)+'\n')
 # Blocks lie west of the source cluster so particles reach building walls.
 if c['buildings']:
  rows=[]
  for i in range(c['buildings']):
   x=140-(i%3)*c['flow'];y=180+(i//3)*c['flow'];rows.append(f'{x} {y} 0 {6+4*(i%3)}')
  (d/'buildings.dat').write_text('\n'.join(rows)+'\n')
 weather=[(9,c['speed'],c['sc'])]
 if c['transient']:weather=[(9,c['speed'],c['sc']),(18,.5,6),(27,2.5,2)]
 c['situations']=len(weather);c['weather']=weather
 (d/'meteopgt.all').write_text('10,1,10\nwind_dir,wind_speed,stability,frequency\n'+'\n'.join(f'{dr},{sp},{sc},1' for dr,sp,sc in weather)+'\n')
 if c['transient']:
  (d/'mettimeseries.dat').write_text('\n'.join(f'01.01.2022 {h:02d} {sp} {dr} {sc}' for h,(dr,sp,sc) in enumerate(weather))+'\n')
  factors=[1,0,.5];(d/'emissions_timeseries.txt').write_text('date;hour;'+';'.join(map(str,range(1,c['sg']+1)))+'\n'+'\n'.join(f'01.01.2022;{h:02d};'+';'.join([str(factors[h])]*c['sg']) for h in range(len(weather)))+'\n')
 if c.get('terrain'):
  spec=c['synthetic_terrain_recipe'];n=spec['coarse_grid'][0];nz=spec['coarse_grid'][2];dx=spec['coarse_dx']
  for i,(dr,sp,sc) in enumerate(weather,1):
   angle=math.radians(270-dr*10);u=round(sp*math.cos(angle)*100);v=round(sp*math.sin(angle)*100)
   (d/f'{i:05d}.wnd').write_bytes(struct.pack('<5i',-1,n,n,nz,dx)+struct.pack('<3h',u,v,0)*(n*n*nz))
 if c.get('terrain'):c['synthetic_terrain_recipe']['wind']='horizontal vectors from weather rows; zero vertical; prescribed input'
 f.save(d/'case.json',c);return c

def payloads(folder,c):
 values={}; hashes={}
 for p in sorted(folder.glob('*.grz')):
  with zipfile.ZipFile(p) as z:
   for n in sorted(z.namelist()):
    if not n.endswith('.con'):continue
    raw=z.read(n);h,x,y,dx,dy,nx,ny=struct.unpack_from('<iiiffii',raw)
    assert (h,x,y,nx,ny)==(-3,0,0,c['nx'],c['ny']) and dx==dy==c['conc'] and len(raw)==28+nx*ny*4
    a=np.frombuffer(raw[28:],dtype='<f4').copy();assert np.isfinite(a).all() and (a>=0).all()
    k=p.name+':'+n;values[k]=a;hashes[k]=hashlib.sha256(raw).hexdigest()
 assert len(values)==c['slices']*c['sg']*c['situations'],(folder,len(values),c['situations'])
 assert sum(np.count_nonzero(a) for a in values.values())>0
 if c['transient']:assert sum(np.count_nonzero(a) for k,a in values.items() if k.startswith('00002.grz:'))>0,'residual-only situation produced no concentration'
 return values,hashes

def compare(a,b):
 assert a.keys()==b.keys()
 return dict(exact=all(np.array_equal(a[k],b[k]) for k in a),fields=len(a),values=sum(x.size for x in a.values()),max_abs=max(float(np.max(np.abs(a[k]-b[k]))) for k in a),sum_abs=sum(float(np.sum(np.abs(a[k].astype(float)-b[k]))) for k in a),reference_sum=sum(float(np.sum(x.astype(float))) for x in a.values()))

def environment():
 env=os.environ.copy();(ROOT/'tmp').mkdir(exist_ok=True);env.update(DOTNET_CLI_HOME=str(ROOT/'cache'),TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'),DOTNET_CLI_UI_LANGUAGE='en');env.pop('GRAL_WORKER_CONCENTRATION_MB',None);return env

def prepare(source_root,dotnet):
 locks={}
 for v in VARIANTS:
  repo=source_root/SOURCE_NAMES[v];expected=json.loads((BUNDLE/'runtime_source_lock.json').read_text())[v];head=expected['head'];out=ROOT/'source'/v
  assert not out.exists(),out
  shutil.copytree(repo/'src',out/'src',ignore=shutil.ignore_patterns('bin','obj','.vscode'))
  actual={str(p.relative_to(out)).replace('\\','/'):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()}
  assert actual==expected['files'], ('source mismatch',v)
  locks[v]=dict(head=head,files=actual,hash_mode='SHA256 after CRLF-to-LF normalization')
 f.save(ROOT/'source_lock.json',locks)
 for v in VARIANTS:build(v,dotnet)
 # Diagnostic-only build: log wall flag vs actual CUTK before and after adaptive roughness.
 shutil.copytree(ROOT/'source/wall_guard',ROOT/'source/wall_probe',ignore=shutil.ignore_patterns('bin','obj'))
 p=ROOT/'source/wall_probe/src/Program.cs';s=p.read_text(encoding='utf-8-sig')
 marker='            // array declarations for prognostic and diagnostic flow field'
 probe='            Console.WriteLine("WALL_PROBE stage=loaded flag=" + Program.BuildingWallsExist + " positive=" + System.Linq.Enumerable.Sum(Program.CUTK, row => System.Linq.Enumerable.Count(row, h => h > 0)));\n\n'
 assert s.count(marker)==1;s=s.replace(marker,probe+marker)
 marker='            if (Program.UseFixedRndSeedVal)';probe='            Console.WriteLine("WALL_PROBE stage=adaptive flag=" + Program.BuildingWallsExist + " positive=" + System.Linq.Enumerable.Sum(Program.CUTK, row => System.Linq.Enumerable.Count(row, h => h > 0)) + " adaptive=" + Program.AdaptiveRoughnessMax);\n\n';assert s.count(marker)==1;s=s.replace(marker,probe+marker)
 p.write_text(s,encoding='utf-8-sig');build('wall_probe',dotnet)
 f.save(ROOT/'plan.json',dict(cases=cases(),variants=VARIANTS,source_lock='source_lock.json',performance=dict(warmups=1,measured_pairs=5,order='rotating',per_process_cap_s=120,per_chunk_cap_s=840),correctness='finite nonnegative complete concentration payloads; exact comparisons and native baseline repeat envelope retained'))

def build(v,dotnet):
 p=subprocess.run([dotnet,'build',str(ROOT/'source'/v/'src/GRAL.csproj'),'-c','Release','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true'],capture_output=True,env=environment(),timeout=120)
 text=(p.stdout+p.stderr).decode('utf-8',errors='replace');(ROOT/'qa').mkdir(exist_ok=True);(ROOT/'qa'/f'build_{v}.log').write_text(text,encoding='utf-8');assert p.returncode==0 and '0 Warning(s)' in text and '0 Error(s)' in text,text;print('[BUILD]',v,flush=True)

def execute(a):
 f.DOTNET=Path(a.dotnet);out=ROOT/'results'/a.tag;out.mkdir(parents=True,exist_ok=False);(out/'inputs').mkdir();(out/'runs').mkdir();start=time.perf_counter();records=[];comparisons=[];conditions=[];env=environment()
 selected=[c for c in cases() if not a.cases or c['id'] in a.cases];assert selected
 variants=['wall_probe'] if a.mode=='probe' else VARIANTS
 reps=1 if a.mode=='probe' else a.repeats+1
 for ci,raw in enumerate(selected):
  c=configure(raw,out/'inputs'/raw['id']);conditions.append(c);first={};first_baseline=None
  for rep in range(reps):
   order=variants[(rep+ci)%len(variants):]+variants[:(rep+ci)%len(variants)];current={}
   for v in order:
    assert time.perf_counter()-start<840,'chunk watchdog'
    d=out/'runs'/f'{c["id"]}_{v}_{rep}';shutil.copytree(out/'inputs'/c['id'],d)
    rec=f.process(ROOT/'source'/v/'src/bin/Release/net10.0/GRAL.dll',d,env,min(120,max(1,840-(time.perf_counter()-start))))
    log=(d/'console.log').read_text(encoding='utf-8',errors='replace');core=(d/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig',errors='replace');problem=d/'Problemreport_GRAL.txt'
    assert rec['exit_code']==0 and 'GRAL simulations finished at:' in core and not(problem.exists() and problem.read_text().strip()),(d,log[-4000:])
    counts=list(map(int,re.findall(r'Using a total of (\d+) particles',log)));assert len(counts)==1,(d,counts);assert len(re.findall(r'Init meteo:',log))==c['situations']
    assert .9*c['particles']<=counts[0]<=1.1*c['particles'],(c,counts)
    assert 'GRAL Deterministic Mode' in log
    source_counts={}
    for kind,label in {'point':'point sources','area':'area source partitions','portal':'tunnel portals','line':'line source segments'}.items():
     match=re.findall('Total number of '+label+r': (\d+)',log);source_counts[kind]=int(match[0]) if match else 0;assert source_counts[kind]==c['source_counts'].get(kind,0),(c,source_counts)
    if c.get('terrain'):assert 'FLOW FIELD COMPUTATION WITH TOPOGRAPHY' in log and 'Reading GRAMM wind field:' in log
    if c['buildings']:assert f"Total number of blocked cells in 2D: {c['buildings']}" in log
    if c['adaptive']:assert 'Using adaptive roughness length' in log
    wall=[]
    if a.mode=='probe':
     wall=re.findall(r'WALL_PROBE stage=(\w+) flag=(True|False) positive=(\d+)',log);assert len(wall)==2,(d,wall)
     assert all((fl=='True')==(int(n)>0)==bool(c['buildings']) and int(n)==c['buildings'] for stage,fl,n in wall),(c,wall)
    values,hashes=payloads(d,c);current[v]=values
    if v in first:comparisons.append(dict(case=c['id'],kind='within_variant_repeat',variant=v,repeat=rep,**compare(first[v],values)))
    else:first[v]=values
    rec.update(case=c['id'],variant=v,repeat=rep,measured=rep>0,actual_particles=counts,actual_particles_per_s=[n/c['tau'] for n in counts],source_counts=source_counts,payload_hashes=hashes,wall_probe=wall)
    records.append(rec);f.save(out/'progress.json',dict(records=records,comparisons=comparisons,conditions=conditions));print('[RUN]',len(records),c['id'],v,rep,round(rec['wall_s'],3),flush=True)
   if 'baseline' in current:
    for v in variants[1:]:comparisons.append(dict(case=c['id'],kind='paired',variant=v,repeat=rep,**compare(current['baseline'],current[v])))
 summaries=[]
 for c in conditions:
  for v in variants[1:]:
   bs={r['repeat']:r for r in records if r['case']==c['id'] and r['variant']=='baseline' and r['measured']};ps={r['repeat']:r for r in records if r['case']==c['id'] and r['variant']==v and r['measured']}
   saved=[100*(1-ps[k]['wall_s']/bs[k]['wall_s']) for k in sorted(bs)]
   summaries.append(dict(case=c['id'],variant=v,paired_saved_percent=saved,median_saved_percent=statistics.median(saved),faster_pairs=sum(x>0 for x in saved),pairs=len(saved),baseline_median_s=statistics.median(x['wall_s'] for x in bs.values()),patch_median_s=statistics.median(x['wall_s'] for x in ps.values())))
 f.save(out/'summary.json',dict(status='pass',cases=conditions,records=records,comparisons=comparisons,summaries=summaries,elapsed_s=time.perf_counter()-start,all_output_exact=all(x['exact'] for x in comparisons)))
 print('[DONE]',len(records),'exact',all(x['exact'] for x in comparisons),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--work-dir',type=Path,required=True);p.add_argument('mode',choices=['prepare','probe','run']);p.add_argument('--source-root',type=Path);p.add_argument('--dotnet',default='dotnet');p.add_argument('--tag',default='screen');p.add_argument('--cases',nargs='+');p.add_argument('--repeats',type=int,default=5);a=p.parse_args()
 ROOT=a.work_dir.resolve();ROOT.mkdir(parents=True,exist_ok=True);f.ROOT=BUNDLE
 if a.mode=='prepare':prepare(a.source_root.resolve(),a.dotnet)
 else:execute(a)