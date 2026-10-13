from pathlib import Path
import json,math,shutil
ROOT=Path(__file__).resolve().parent/"transient"
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def input_case(case,folder):
 if folder.exists():raise FileExistsError(folder)
 shutil.copytree(ROOT/'template',folder)
 for p in list(folder.iterdir()):
  if p.suffix=='.json' or p.name in ('cadastre.dat','point.dat','line.dat','portals.dat'):p.unlink()
 lines=(folder/'in.dat').read_text().splitlines();lines[0]=str(case['budget']/case['duration']);lines[1]=str(case['duration']);lines[2]='0';lines[7]='Y'
 (folder/'in.dat').write_text('\n'.join(lines)+'\n')
 dx=case['dx'];grid=[dx,dx,'2,1.1',200//dx,200//dx,1,','.join(str(i+1) for i in range(case['groups'])),0,200,0,200]
 (folder/'GRAL.geb').write_text('\n'.join(map(str,grid))+'\n')
 (folder/'Max_Proc.txt').write_text(str(case['workers'])+'\n')
 weather=[(9,case['wind_m_s'],case['stability'])]*case['situations']
 (folder/'meteopgt.all').write_text('10,1,10\nwind_dir,wind_speed,stability,frequency\n'+'\n'.join(f'{d},{s},{sc},1' for d,s,sc in weather)+'\n')
 (folder/'mettimeseries.dat').write_text('\n'.join(f'01.01.2022 {h:02d} {s} {d} {sc}' for h,(d,s,sc) in enumerate(weather))+'\n')
 factors=[]
 for h in range(case['situations']):
  f=[1.]*case['groups']
  if case['pattern']=='alloff' and h>=1:f=[0.]*case['groups']
  if case['pattern']=='pulse':f=[10. if h==0 else .1]*case['groups']
  if case['pattern']=='largeoff' and h>=1:f[0]=0
  factors.append(f)
 (folder/'emissions_timeseries.txt').write_text('date;hour;'+';'.join(str(i+1) for i in range(case['groups']))+'\n'+'\n'.join(f'01.01.2022;{h:02d};'+';'.join(map(str,f)) for h,f in enumerate(factors))+'\n')
 declared={};rates=[0.]*case['groups'];content={};kinds=['point','portal','line','area'] if case['kind']=='mixed' else [case['kind']]
 for i in range(case['sources']):
  kind=kinds[i%len(kinds)];x=45+(i%8)*14;y=55+(i//8)*18;sg=1+i%case['groups'];er=case['ratio'] if sg==1 else 1;rates[sg-1]+=er
  if kind=='point':row=[x,y,2,er,0,0,0,1,1,293,sg]
  elif kind=='portal':row=[x,y,x+6,y,1,3,er,0,0,0,sg]
  elif kind=='line':row=[i+1,0,sg,x,y,1,x+10,y+4,2,2,-2,0,0,er*1000/math.sqrt(117),0,0,0,0,0]
  else:row=[x,y,2,8,8,2,er,0,0,0,sg]
  content.setdefault(kind,[]).append(','.join(map(str,row)));declared[kind]=declared.get(kind,0)+1
 for kind,rows in content.items():
  fn={'point':'point.dat','portal':'portals.dat','line':'line.dat','area':'cadastre.dat'}[kind]
  header=5 if kind=='line' else 1 if kind=='area' else 2
  (folder/fn).write_text('\n'.join(['header']*header+rows)+'\n')
 detail=dict(case,weather=weather,emission_factors=factors,nominal_rates_kg_h=rates,source_counts=declared,expected_fresh_mass_kg=[rate*sum(f[g] for f in factors)*case['duration']/3600 for g,rate in enumerate(rates)],domain_m=[0,200,0,200])
 save(folder/'synthetic_case.json',detail);return detail
