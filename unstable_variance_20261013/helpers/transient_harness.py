from pathlib import Path
import hashlib,json,math,re,shutil,struct,zipfile
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def make_input(c,folder,template):
 shutil.copytree(template,folder)
 for p in list(folder.iterdir()):
  if p.suffix=='.json' or p.name in ('cadastre.dat','point.dat','line.dat','portals.dat'):p.unlink()
 lines=(folder/'in.dat').read_text().splitlines();lines[0]=str(c['budget']/c['duration']);lines[1]=str(c['duration']);lines[2]='1' if c['stationary'] else '0';lines[7]='Y'
 (folder/'in.dat').write_text('\n'.join(lines)+'\n');dx=c['dx'];ids=c['ids']
 (folder/'GRAL.geb').write_text('\n'.join(map(str,[dx,dx,'2,1.1',200//dx,200//dx,1,','.join(map(str,ids)),0,200,0,200]))+'\n')
 (folder/'Max_Proc.txt').write_text(str(c['workers'])+'\n')
 weather=[(9,.5,4)]*c['situations'];(folder/'meteopgt.all').write_text('10,1,10\nwind_dir,wind_speed,stability,frequency\n'+'\n'.join(f'{d},{s},{sc},1' for d,s,sc in weather)+'\n')
 (folder/'mettimeseries.dat').write_text('\n'.join(f'01.01.2022 {h:02d} {s} {d} {sc}' for h,(d,s,sc) in enumerate(weather))+'\n')
 factors=[[1 if h==0 else .5 if g%2 else 0 for g in range(len(ids))] for h in range(c['situations'])]
 (folder/'emissions_timeseries.txt').write_text('date;hour;'+';'.join(map(str,ids))+'\n'+'\n'.join(f'01.01.2022;{h:02d};'+';'.join(map(str,f)) for h,f in enumerate(factors))+'\n')
 rows=[]
 for i,sg in enumerate(ids):
  x=25+(i%16)*10;y=25+(i//16)*10;er=1;kind=c['kind']
  if kind=='point':row=[x,y,2,er,0,0,0,1,1,293,sg]
  elif kind=='portal':row=[x,y,x+6,y,1,3,er,0,0,0,sg]
  elif kind=='line':row=[i+1,0,sg,x,y,1,x+10,y+4,2,2,-2,0,0,er*1000/math.sqrt(117),0,0,0,0,0]
  else:row=[x,y,2,8,8,2,er,0,0,0,sg]
  rows.append(','.join(map(str,row)))
 fn={'point':'point.dat','portal':'portals.dat','line':'line.dat','area':'cadastre.dat'}[kind];header=5 if kind=='line' else 1 if kind=='area' else 2
 (folder/fn).write_text('\n'.join(['header']*header+rows)+'\n')
 if c['decay']:(folder/'Pollutant.txt').write_text('NOX\n0\n0\n0.001\n'+'\t'.join(f'{sg}:{.005*(i+1)}' for i,sg in enumerate(ids))+'\n')
 save(folder/'synthetic_case.json',dict(c,emission_factors=factors));return factors

def payloads(folder,c):
 data={};sums={g:0. for g in c['ids']}
 for archive in sorted(folder.glob('*.grz')):
  with zipfile.ZipFile(archive) as z:
   for name in sorted(z.namelist()):
    if not name.endswith('.con'):continue
    match=re.fullmatch(r'(\d{5})-1(\d{2,3})\.con',name);assert match,name;g=int(match[2]);assert g in c['ids'],name
    raw=z.read(name);h=struct.unpack_from('<iiiffii',raw);assert h==(-3,0,0,float(c['dx']),float(c['dx']),200//c['dx'],200//c['dx']),h
    assert len(raw)==28+4*(200//c['dx'])**2
    v=struct.unpack_from('<'+str((len(raw)-28)//4)+'f',raw,28);assert all(math.isfinite(x) and x>=0 for x in v);sums[g]+=sum(v)
    data[f'{int(match[1])}:{c["ids"].index(g)}']=hashlib.sha256(raw).hexdigest()
 assert len(data)==len(c['ids'])*c['situations'],(len(data),c['id']);assert (sum(sums.values())>0 if c.get('allow_zero_groups',False) else all(x>0 for x in sums.values())),sums
 return data,sums
