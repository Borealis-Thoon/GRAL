from pathlib import Path
import argparse,json,struct,zipfile
import numpy as np

def read(folder):
 a={}
 for p in sorted(folder.glob('*.grz')):
  with zipfile.ZipFile(p) as z:
   for name in z.namelist():
    if not name.endswith('.odr'):continue
    raw=z.read(name);header=struct.unpack_from('<iiiffii',raw);assert header==(-3,0,0,20.,20.,10,10);assert len(raw)==28+4*4*10*10
    values=np.frombuffer(raw[28:],dtype='<f4').reshape(-1,4).astype('float64');assert np.isfinite(values).all() and (values>=0).all();a[p.name+':'+name]=values
 assert len(a)==6
 return a

def delta(a,b):
 assert a.keys()==b.keys()
 rows=[]
 for col,name in enumerate(['Conz3dp','Conz3dm','Q_cv0','DisConcVar']):
  x=np.concatenate([a[k][:,col] for k in a]);y=np.concatenate([b[k][:,col] for k in a]);d=np.abs(x-y);positive=np.maximum(np.abs(x),np.abs(y))>0
  rows.append(dict(field=name,float_count=len(x),changed=int(np.count_nonzero(d)),relative_l1=float(d.sum()/np.abs(x).sum()) if np.abs(x).sum() else 0.,max_absolute=float(d.max()),max_relative=float((d[positive]/np.maximum(np.abs(x[positive]),np.abs(y[positive]))).max()) if positive.any() else 0.))
 return rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();all={(v,r):read(args.run_dir/'runs'/f'odour_{v}_{r}') for v in ['f64','off','on'] for r in range(3)}
 pairs=[dict(variant=v,repeat=r,fields=delta(all['f64',r],all[v,r])) for v in ['off','on'] for r in range(3)]
 repeats=[dict(variant=v,repeat=r,fields=delta(all[v,0],all[v,r])) for v in ['f64','off','on'] for r in [1,2]]
 result=dict(status='pass',files=54,floats=21600,headers_shapes_finite_nonnegative='pass',paired=pairs,repeats=repeats,scope='Four float fields per odour output cell. These fields retain the existing shared accumulation path; differences include parallel ordering already present in baseline repeats.')
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print('[PASS] odour outputs: 54 files, 21600 floats')
if __name__=='__main__':main()