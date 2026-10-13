from pathlib import Path
import importlib.util,json,os,time,shutil,re,zipfile,hashlib,struct,argparse
import numpy as np
B=Path(__file__).resolve().parent;J=B;F=B;R=B
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
f=module('f_fixture',F/'synthetic_fixture.py');r=None
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def payloads(d,situations,sg,slices,nx,ny,dx):
 hashes={};values=0;nonzero=0
 grzs=list(d.glob('*.grz'));assert len(grzs)==situations,(len(grzs),situations)
 for p in sorted(grzs):
  with zipfile.ZipFile(p) as z:
   members=[n for n in z.namelist() if n.endswith('.con')];assert len(members)==sg*slices
   for n in members:
    raw=z.read(n);header=struct.unpack_from('<iiiffii',raw);assert header==(-3,0,0,float(dx),float(dx),nx,ny),(n,header);assert len(raw)==28+4*nx*ny;a=np.frombuffer(raw[28:],dtype='<f4');assert np.isfinite(a).all() and (a>=0).all();values+=len(a);nonzero+=int(np.count_nonzero(a));hashes[p.name+':'+n]=hashlib.sha256(raw).hexdigest()
 assert nonzero>0
 return dict(hashes=hashes,values=values,nonzero=nonzero)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--topic',choices=['parallel'],default='parallel');ap.add_argument('--repeat',type=int,default=3);ap.add_argument('--dense-only',action='store_true');args=ap.parse_args();run=B/('main_'+args.topic+('_dense4_verified' if args.dense_only else ''));run.mkdir(exist_ok=False);(run/'tmp').mkdir();env=os.environ.copy();env.update(TEMP=str(run/'tmp'),TMP=str(run/'tmp'));start=time.perf_counter();records=[];pairs=[];conditions=[]
 cases=[c for c in f.cases() if c['id'] in ['small_point','terrain_area','many_sources','dense_output_grid','parallel_concentrated']];variants=['f64','parallel']
 if args.dense_only:cases=[dict(next(c for c in cases if c['id']=='dense_output_grid'),id='dense_output_grid_w4',workers=4)]
 for c0 in cases:
  template=run/'inputs'/c0['id'];template.parent.mkdir(exist_ok=True)
  c=f.configure(c0,template);shape=dict(situations=1,sg=c['sg'],slices=c['slices'],nx=c['nx'],ny=c['ny'],dx=c['conc'])
  conditions.append(dict(c,output_shape=shape));first={}
  for rep in range(args.repeat):
   pair={}
   for v in variants[(rep%2):]+variants[:(rep%2)]:
    if time.perf_counter()-start>750:raise TimeoutError('750s suite cap')
    d=run/'runs'/f'{c["id"]}_{v}_{rep+1}';d.parent.mkdir(exist_ok=True);shutil.copytree(template,d);result=f.process(B/'sources'/v/'src/bin/Release/net10.0/GRAL.dll',d,env,timeout=60);text=(d/'console.log').read_text(errors='replace');core=d/'Logfile_GRALCore.txt';problem=d/'Problemreport_GRAL.txt';assert result['exit_code']==0 and core.exists() and 'GRAL simulations finished at:' in core.read_text(encoding='utf-8-sig') and not(problem.exists() and problem.read_text().strip()),text[-3000:]
    counts=[int(x) for x in re.findall(r'Using a total of (\d+) particles',text)];assert len(counts)==shape['situations'],counts
    p=payloads(d,**shape);pair[v]=p
    if v in first:assert first[v]==p['hashes'],'repeat differs'
    else:first[v]=p['hashes']
    result.update(case=c['id'],variant=v,repeat=rep+1,particle_counts=counts,output_values=p['values'],nonzero_values=p['nonzero'],payload_hashes=p['hashes']);records.append(result);save(run/'progress.json',dict(status='running',runs=len(records),last=dict(case=c['id'],variant=v,repeat=rep+1)));print('[MAIN]',args.topic,len(records),c['id'],v,rep+1,flush=True)
   assert pair[variants[0]]['hashes']==pair[variants[1]]['hashes'],'candidate payload differs';pairs.append(dict(case=c['id'],repeat=rep+1,status='byte_identical',members=len(pair[variants[0]]['hashes'])))
 save(run/'summary.json',dict(status='pass',topic=args.topic,conditions=conditions,variants=variants,repeat=args.repeat,main_runs=len(records),matched_pairs=len(pairs),pairs=pairs,records=records,elapsed_s=time.perf_counter()-start,scope='Fixed-seed one-worker real Main output payloads; warm method performance is reported separately. These short cold-process runs do not establish a production speedup.'))
 print('[PASS]',args.topic,len(records),'Main runs',flush=True)
if __name__=='__main__':main()
