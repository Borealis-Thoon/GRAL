"""Small deterministic synthetic GRAL inputs; no production geography or GRAMM outputs."""
from __future__ import annotations
import hashlib,json,math,shutil
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def cases():
    result=[]
    def add(ident,kind,budget,dx,weather,**kw):
        value=dict(id=ident,kind=kind,budget=budget,mode='stationary',sources_per_kind=2,dx=dx,dy=dx,nx=200//dx,ny=200//dx,slices=1,receptors=False,deposition=False,odour=False,hot_stack=False,terrain=False,buildings=False,weather=weather)
        value.update(kw);result.append(value)
    add('point_n100_20m','point',100,20,[(9,1,4)])
    add('point_hot_n1000_10m','point',1000,10,[(18,2.5,2)],hot_stack=True,slices=9)
    add('point_n3000_40m','point',3000,40,[(27,.5,6)])
    add('portal_n100_40m','portal',100,40,[(36,2.5,2)])
    add('portal_n1000_20m','portal',1000,20,[(27,1,4)])
    add('line_n3000_10m','line',3000,10,[(9,.5,6)])
    add('line_n100_20m','line',100,20,[(18,1,4)])
    add('area_n1000_40m','area',1000,40,[(36,2.5,2)])
    add('area_n3000_20m','area',3000,20,[(27,.5,6)])
    add('mixed_n100_10m','mixed',100,10,[(9,1,4)],sources_per_kind=1)
    add('mixed_transient_n100_40m','mixed',100,40,[(27,.5,6),(18,.5,6),(9,.5,6)],mode='transient',sources_per_kind=1)
    add('mixed_transient_n1000_20m','mixed',1000,20,[(9,2.5,2),(18,.5,6),(27,1,4)],mode='transient')
    add('mixed_transient_n3000_10m','mixed',3000,10,[(36,1,4),(27,2.5,2),(18,.5,6)],mode='transient')
    add('mixed_deposition_receptors','mixed',1000,20,[(18,2.5,2)],deposition=True,receptors=True)
    add('mixed_odour_9slices','mixed',1000,20,[(27,1,4)],slices=9,odour=True)
    add('flat_buildings_n1000','point',1000,20,[(9,1,4)],buildings=True,slices=9)
    add('terrain_hot_n100','point',100,20,[(9,2.5,2)],terrain=True,hot_stack=True,slices=9)
    add('terrain_stable_building_n1000','point',1000,20,[(18,.5,6),(27,.5,6),(9,.5,6)],terrain=True,buildings=True,slices=9,mode='transient')
    return result

def terrain_inputs(folder,case):
    # Authoritative reader order: ReadGRAMMGeb, ReadGgeomAsc ASCII, WindfieldRead compact.
    n=20;nz=12;dx=20;west=-100;south=-100;dz=10
    terrain=lambda x,y: .02*(x-west)+.005*(y-south)
    header=[n,n,nz]+[i*dx for i in range(n+1)]+[j*dx for j in range(n+1)]+[k*dz for k in range(nz+1)]
    ah=[terrain(west+(i+.5)*dx,south+(j+.5)*dx) for j in range(n) for i in range(n)]
    zsp=[terrain(west+(i+.5)*dx,south+(j+.5)*dx)+(k+.5)*dz for k in range(nz) for j in range(n) for i in range(n)]
    ahe=[terrain(west+i*dx,south+j*dx)+k*dz for k in range(nz+1) for j in range(n+1) for i in range(n+1)]
    lines=[' '.join(map(str,header)),' '.join(map(str,ah))]+['0']*6+[' '.join(map(str,zsp)),' '.join(map(str,[dx]*n)),' '.join(map(str,[dx]*n)),'0','0',f'{west} {south} 0',' '.join(map(str,ahe))]
    (folder/'ggeom.asc').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (folder/'GRAMM.geb').write_text(f'{n}\n{n}\n{nz}\n{west}\n{west+n*dx}\n{south}\n{south+n*dx}\n',encoding='utf-8')
    # These are synthetic prescribed constant vectors; no GRAMM simulation is asserted.
    import struct
    for index,(direction,speed,sc) in enumerate(case['weather'],1):
        angle=math.radians(270-direction*10);u=round(speed*math.cos(angle)*100);v=round(speed*math.sin(angle)*100)
        raw=struct.pack('<5i',-1,n,n,nz,dx)+struct.pack('<3h',u,v,0)*(n*n*nz)
        (folder/f'{index:05d}.wnd').write_bytes(raw)
    case['synthetic_terrain_recipe']=dict(generation='entirely_generated_by_this_fixture',coarse_domain_m=[west,west+n*dx,south,south+n*dx],coarse_cells=[n,n,nz],coarse_dx_m=dx,vertical_spacing_m=dz,terrain_equation_m='0.02*(x+100) + 0.005*(y+100)',wind_field='constant prescribed horizontal vector; zero vertical component; compact cm/s quantization',no_gramm_model_execution=True,formats_from=['ReadGeometryAndDomains.cs:ReadGRAMMGeb','ReadGgeomAsc.cs:ASCII branch','Windfield_Reader.cs:compact -1 format'])

def configure(template,folder,raw_case):
    if folder.exists():raise FileExistsError(folder)
    shutil.copytree(template,folder);case=dict(raw_case)
    for name in ('cadastre.dat','point.dat','portals.dat','line.dat','input_manifest.json','fixture_spec.json','synthetic_case.json','Receptor.dat','Pollutant.txt'):
        p=folder/name
        if p.exists():p.unlink()
    lines=(folder/'in.dat').read_text(encoding='utf-8').splitlines();lines[0]=str(case['budget']/30);lines[2]='0' if case['mode']=='transient' else '1';lines[4]='1' if case['receptors'] else '0';lines[12]='1' if case['buildings'] else '0'
    grid=(folder/'GRAL.geb').read_text(encoding='utf-8').splitlines()
    grid[0]=str(case['dx']);grid[1]=str(case['dy']);grid[3]=str(case['nx']);grid[4]=str(case['ny']);grid[5]=str(case['slices'])
    slice_heights=[2+4*i for i in range(case['slices'])] if case['slices']>1 else [2]
    lines[9]=' '.join(map(str,slice_heights))
    (folder/'in.dat').write_text('\n'.join(lines)+'\n',encoding='utf-8');(folder/'GRAL.geb').write_text('\n'.join(grid)+'\n',encoding='utf-8')
    (folder/'Max_Proc.txt').write_text('1\n',encoding='utf-8')
    (folder/'meteopgt.all').write_text('10,1,10\nwind_dir,wind_speed,stability,frequency\n'+'\n'.join(f'{d},{speed},{sc},1' for d,speed,sc in case['weather'])+'\n',encoding='utf-8')
    (folder/'mettimeseries.dat').write_text('\n'.join(f'01.01.2022 {h:02d} {speed} {d} {sc}' for h,(d,speed,sc) in enumerate(case['weather']))+'\n',encoding='utf-8')
    factors=[(1,1),(0,0),(.5,2)][:len(case['weather'])]
    (folder/'emissions_timeseries.txt').write_text('date;hour;1;2\n'+'\n'.join(f'01.01.2022;{h:02d};{a};{b}' for h,(a,b) in enumerate(factors))+'\n',encoding='utf-8')
    if case['receptors']:(folder/'Receptor.dat').write_text('2\n1,90,90,2,Near\n2,130,90,2,Far\n',encoding='utf-8')
    if case['odour']:(folder/'Pollutant.txt').write_text('odour\n',encoding='utf-8')
    if case['buildings']:(folder/'buildings.dat').write_text('100 80 0 8\n100 100 0 8\n100 120 0 8\n',encoding='utf-8')
    kinds=('point','portal','line','area') if case['kind']=='mixed' else (case['kind'],)
    declared={};rates=[0.,0.]
    for kind in kinds:
        rows=[]
        for i in range(case['sources_per_kind']):
            x=60+(i%8)*12;y=60+(i//8)*12;sg=1+(i%2)
            if case['kind']=='mixed':sg=1+((kinds.index(kind)+i)%2)
            er=1;rates[sg-1]+=er
            if kind=='point':row=[x,y,20 if case['hot_stack'] else 2,er,0,0,0,3 if case['hot_stack'] else 1,1,400 if case['hot_stack'] else 293,sg]
            elif kind=='portal':row=[x,y,x+6,y,1,3,er,0,0,0,sg]
            elif kind=='line':row=[i+1,0,sg,x,y,1,x+10,y+4,2,2,-2,0,0,1000/math.sqrt(117),0,0,0,0,0]
            else:row=[x,y,2,8,8,2,er,0,0,0,sg]
            if case['deposition']:row += [100,100,30,0,.02,.02,.02,1]
            rows.append(','.join(map(str,row)))
        filename={'point':'point.dat','portal':'portals.dat','line':'line.dat','area':'cadastre.dat'}[kind];headers=5 if kind=='line' else 1 if kind=='area' else 2
        (folder/filename).write_text('\n'.join(['header']*headers+rows)+'\n',encoding='utf-8');declared[kind]=len(rows)
    if case['terrain']:terrain_inputs(folder,case)
    case.update(domain_m=[0,200,0,200],situation_duration_s=30,workers=1,source_counts=declared,fixed_seed=True,slice_heights_m=slice_heights,source_group_base_rates_kg_h=rates,emission_factors=factors,interpretation='Each weather situation integrates 30 seconds. Hour labels index inputs; no radiation-resolving meteorology is claimed.')
    save(folder/'synthetic_case.json',case)
    manifest={p.name:dict(size=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.iterdir()) if p.is_file() and p.name!='input_manifest.json'}
    save(folder/'input_manifest.json',manifest)
    return case
