"""Matched cold-process GRAL timing, memory and output-repeat comparisons on synthetic fields."""
from pathlib import Path
import argparse,array,ctypes,ctypes.wintypes as wt,hashlib,json,math,os,re,shutil,statistics,struct,subprocess,time,zipfile
import numpy as np
ROOT=Path(__file__).resolve().parent
VARIANTS=['baseline','f64','opt68_69','f64_opt68_69']
DOTNET=Path(r'C:\Program Files\dotnet\dotnet.exe')
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def cases():
 return [
 dict(id='small_point',particles=3000,kind='point',sources=2,sg=2,length=400,flow=40,conc=40,slices=1,tau=30,speed=1,sc=4,hot=False,workers=1),
 dict(id='hot_stacks',particles=100000,kind='point',sources=26,sg=26,length=1200,flow=20,conc=20,slices=9,tau=120,speed=1,sc=4,hot=True,workers=1),
 dict(id='terrain_area',terrain=True,particles=30000,kind='area',sources=26,sg=26,length=1200,flow=20,conc=20,slices=1,tau=120,speed=.5,sc=6,hot=False,workers=1),
 dict(id='many_sources',particles=20000,kind='mixed',sources=512,sg=64,length=1200,flow=40,conc=40,slices=1,tau=60,speed=2.5,sc=2,hot=False,workers=1),
 dict(id='dense_output_grid',particles=3000,kind='area',sources=64,sg=64,length=1000,flow=40,conc=10,slices=9,tau=30,speed=1,sc=4,hot=False,workers=1),
 dict(id='parallel_concentrated',particles=100000,kind='point',sources=8,sg=2,length=1200,flow=20,conc=20,slices=1,tau=120,speed=.5,sc=6,hot=False,workers=4),
 ]
def terrain_inputs(d,c):
 n=c['length']//40+10;nz=20;dx=40;west=-200;south=-200;dz=20
 terrain=lambda x,y:.01*(x-west)+.003*(y-south)
 header=[n,n,nz]+[i*dx for i in range(n+1)]+[j*dx for j in range(n+1)]+[k*dz for k in range(nz+1)]
 ah=[terrain(west+(i+.5)*dx,south+(j+.5)*dx) for j in range(n) for i in range(n)]
 zsp=[terrain(west+(i+.5)*dx,south+(j+.5)*dx)+(k+.5)*dz for k in range(nz) for j in range(n) for i in range(n)]
 ahe=[terrain(west+i*dx,south+j*dx)+k*dz for k in range(nz+1) for j in range(n+1) for i in range(n+1)]
 lines=[' '.join(map(str,header)),' '.join(map(str,ah))]+['0']*6+[' '.join(map(str,zsp)),' '.join(map(str,[dx]*n)),' '.join(map(str,[dx]*n)),'0','0',f'{west} {south} 0',' '.join(map(str,ahe))]
 (d/'ggeom.asc').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 (d/'GRAMM.geb').write_text(f'{n}\n{n}\n{nz}\n{west}\n{west+n*dx}\n{south}\n{south+n*dx}\n',encoding='utf-8')
 (d/'00001.wnd').write_bytes(struct.pack('<5i',-1,n,n,nz,dx)+struct.pack('<3h',-round(c['speed']*100),0,0)*(n*n*nz))
 c['synthetic_terrain_recipe']=dict(coarse_grid=[n,n,nz],coarse_dx=dx,coarse_dz=dz,terrain='0.01*(x+200)+0.003*(y+200)',wind='uniform westward, zero vertical, prescribed input; no GRAMM model run')

def configure(c,d):
 shutil.copytree(ROOT/'template',d)
 for p in d.iterdir():
  if p.name not in ['in.dat','micro_vert_layers.txt']:p.unlink()
 n=c['length']//c['conc']
 (d/'GRAL.geb').write_text('\n'.join(map(str,[c['flow'],c['flow'],'2,1.1',n,n,c['slices'],','.join(map(str,range(1,c['sg']+1))),0,c['length'],0,c['length']]))+'\n',encoding='utf-8')
 a=(d/'in.dat').read_text().splitlines();a[0]=str(c['particles']/c['tau']);a[1]=str(c['tau']);a[2]='1';a[4]='0';a[9]=' '.join(map(str,[2+4*i for i in range(c['slices'])]));a[12]='0';a[-1]='1';(d/'in.dat').write_text('\n'.join(a)+'\n',encoding='utf-8')
 (d/'Max_Proc.txt').write_text(str(c['workers'])+'\n',encoding='utf-8')
 (d/'meteopgt.all').write_text(f"10,1,10\nwind_dir,wind_speed,stability,frequency\n9,{c['speed']},{c['sc']},1\n",encoding='utf-8')
 kinds=['point','area','line','portal'] if c['kind']=='mixed' else [c['kind']]
 rows={k:[] for k in kinds};source_counts={}
 for i in range(c['sources']):
  kind=kinds[i%len(kinds)];sg=1+i%c['sg'];x=200+(i%16)*8;y=200+((i//16)%16)*8
  if c['id']=='parallel_concentrated':x=y=400
  er=1.0
  if kind=='point':v=[x,y,20 if c['hot'] else 2,er,0,0,0,3 if c['hot'] else 1,1,400 if c['hot'] else 293,sg]
  elif kind=='area':v=[x,y,2,8,8,2,er,0,0,0,sg]
  elif kind=='line':v=[i+1,0,sg,x,y,1,x+10,y+4,2,2,-2,0,0,1000/math.sqrt(117),0,0,0,0,0]
  else:v=[x,y,x+6,y,1,3,er,0,0,0,sg]
  rows[kind].append(','.join(map(str,v)))
 for k,rs in rows.items():
  name={'point':'point.dat','area':'cadastre.dat','line':'line.dat','portal':'portals.dat'}[k]
  head=5 if k=='line' else 1 if k=='area' else 2
  (d/name).write_text('\n'.join(['header']*head+rs)+'\n',encoding='utf-8');source_counts[k]=len(rs)
 c=dict(c,nx=n,ny=n,source_counts=source_counts,vertical_flow_layers=40)
 if c.get('terrain'):terrain_inputs(d,c)
 save(d/'case.json',c);return c
class PMC(ctypes.Structure):
 _fields_=[('cb',wt.DWORD),('PageFaultCount',wt.DWORD)]+[(x,ctypes.c_size_t) for x in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage']]
psapi=ctypes.WinDLL('psapi',use_last_error=True);psapi.GetProcessMemoryInfo.argtypes=[wt.HANDLE,ctypes.POINTER(PMC),wt.DWORD];psapi.GetProcessMemoryInfo.restype=wt.BOOL
kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetProcessTimes.argtypes=[wt.HANDLE]+[ctypes.POINTER(wt.FILETIME)]*4;kernel.GetProcessTimes.restype=wt.BOOL
def sample(handle):
 m=PMC();m.cb=ctypes.sizeof(m)
 if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(m),m.cb):return None
 return {x:int(getattr(m,x)) for x in ['PeakWorkingSetSize','PeakPagefileUsage','PrivateUsage','WorkingSetSize']}
def cpu(handle):
 ts=[wt.FILETIME() for _ in range(4)]
 if not kernel.GetProcessTimes(handle,*[ctypes.byref(t) for t in ts]):return None
 return sum((t.dwHighDateTime<<32)+t.dwLowDateTime for t in ts[2:])/1e7

def process(dll,folder,env,timeout=90):
 with (folder/'console.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
  start=time.perf_counter();p=subprocess.Popen([str(DOTNET),str(dll),str(folder)],cwd=folder,env=env,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
  peaks={k:0 for k in ['PeakWorkingSetSize','PeakPagefileUsage','PrivateUsage','WorkingSetSize']};samples=0
  while p.poll() is None:
   s=sample(p._handle)
   if s:
    peaks={k:max(peaks[k],s[k]) for k in peaks};samples+=1
   if time.perf_counter()-start>timeout:
    subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=10);raise TimeoutError(folder)
   time.sleep(.01)
  elapsed=time.perf_counter()-start;final=sample(p._handle);cpu_s=cpu(p._handle)
  if final:peaks={k:max(peaks[k],final[k]) for k in peaks}
  return dict(exit_code=p.returncode,wall_s=elapsed,cpu_s=cpu_s,pid=p.pid,memory=peaks,memory_samples=samples,memory_after_exit_api_succeeded=final is not None)

def payloads(folder,c):
 values={};hashes={}
 for p in sorted(folder.glob('*.grz')):
  with zipfile.ZipFile(p) as z:
   for n in sorted(z.namelist()):
    if not n.endswith('.con'):continue
    raw=z.read(n);h,x,y,dx,dy,nx,ny=struct.unpack_from('<iiiffii',raw)
    assert (h,x,y,nx,ny)==(-3,0,0,c['nx'],c['ny'])
    assert dx==c['conc'] and dy==c['conc'] and len(raw)==28+nx*ny*4
    a=np.frombuffer(raw[28:],dtype='<f4').copy();assert np.isfinite(a).all() and (a>=0).all()
    name=p.name+':'+n;values[name]=a;hashes[name]=hashlib.sha256(raw).hexdigest()
 assert len(values)==c['slices']*c['sg'],(len(values),c)
 assert sum(np.count_nonzero(a) for a in values.values())>0
 return values,hashes

def diff(a,b):
 assert a.keys()==b.keys()
 changed=0;l1=0.;ref=0.;maxabs=0.;maxrel=0.;total=0
 for k in a:
  x=a[k].astype('float64');y=b[k].astype('float64');d=np.abs(x-y);changed+=int(np.count_nonzero(d));total+=len(x);l1+=float(d.sum());ref+=float(np.abs(x).sum());maxabs=max(maxabs,float(d.max()));pos=np.maximum(np.abs(x),np.abs(y));good=pos>0
  if good.any():maxrel=max(maxrel,float((d[good]/pos[good]).max()))
 return dict(changed_cells=changed,total_cells=total,relative_l1=l1/ref if ref else 0,max_absolute=maxabs,max_relative_cell=maxrel)

