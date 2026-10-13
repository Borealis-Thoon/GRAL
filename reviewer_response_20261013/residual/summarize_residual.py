from pathlib import Path
import csv,hashlib,json,math,re,shutil,struct,zipfile
import argparse
p=argparse.ArgumentParser();p.add_argument('--work-dir',type=Path,required=True);p.add_argument('--base-qa',type=Path,required=True);p.add_argument('--weather-qa',type=Path,required=True);p.add_argument('--floor-qa',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
ROOT=a.work_dir.resolve();QA=a.output_dir.resolve();QA.mkdir(parents=True,exist_ok=True)
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
all_records=[];all_rows=[];all_cases=[];all_comparisons=[];all_diagnostics=[];checks=dict(source_files=0,dense_payloads=0,float_values=0,weather_inputs=0,diagnostic_pristine_pairs=0,repeat_pairs=0)
base_manifest=json.loads((ROOT/'source_manifest.json').read_text())
for variant,files in base_manifest['source_files'].items():
 for name,expected in files.items():assert sha(ROOT/'source'/variant/name)==expected;checks['source_files']+=1
for qa,run_name in [(a.base_qa,'run'),(a.weather_qa,'weather_run'),(a.floor_qa,'floor_run')]:
 summary=json.loads((qa/'residual_summary.json').read_text());records=json.loads((qa/'residual_records.json').read_text());comp=json.loads((qa/'residual_numeric_comparisons.json').read_text())
 cases={c['id']:c for c in summary['conditions']};all_cases+=list(cases.values())
 data={}
 for r in records:
  c=cases[r['case']];key=f'{r["case"]}_{r["variant"]}_{r["repeat"]}'+('_diag' if r['diagnostic'] else '')
  folder=ROOT/run_name/key;per_situation={};payload={}
  weather=[(float(v),int(d),int(sc)) for v,d,sc in re.findall(r'Init meteo:\s+wind speed \[m/s\]: ([0-9.]+)\s+direction \[deg\]: ([0-9]+)\s+Stability class \[-\]: ([0-9]+)',(folder/'console.log').read_text())]
  assert len(weather)==c['situations'] and all(v==(c['wind_m_s'],90,c['stability']) for v in weather);checks['weather_inputs']+=1
  for file in sorted(folder.glob('*.grz')):
   situation=int(file.stem);per_situation[situation]=[]
   with zipfile.ZipFile(file) as z:
    for name in sorted(z.namelist()):
     raw=z.read(name);assert name.endswith('.con');n=(200//c['dx'])**2
     assert len(raw)==28+4*n
     header=struct.unpack_from('<iiiffii',raw);assert header==(-3,0,0,float(c['dx']),float(c['dx']),200//c['dx'],200//c['dx'])
     values=struct.unpack_from('<'+str(n)+'f',raw,28);assert all(math.isfinite(v) and v>=0 for v in values)
     per_situation[situation]+=values;payload[file.name+':'+name]=hashlib.sha256(raw).hexdigest();checks['dense_payloads']+=1;checks['float_values']+=n
  assert payload==r['payload_sha256'];assert set(per_situation)==set(range(1,6))
  data[(r['case'],r['variant'],r['repeat'],r['diagnostic'])]=(per_situation,payload)
  r.update(requested_particle_budget=c['budget'],configured_workers=c['workers'],grid_spacing_m=c['dx'],declared_sources=c['sources'],weather=dict(wind_m_s=c['wind_m_s'],stability_class=c['stability']))
  for d in r['diagnostics']:
   all_diagnostics.append(dict(case=r['case'],variant=r['variant'],**d,mean_scaled_child_mass=d['retained_scaled_mass']/d['selected_children'] if d['selected_children'] else None))
 for c in cases.values():
  for v in ('baseline','pr62','pr63'):
   if c['workers']==1:
    assert data[(c['id'],v,0,True)][1]==data[(c['id'],v,0,False)][1];checks['diagnostic_pristine_pairs']+=1
    for rep in (1,2):assert data[(c['id'],v,rep,False)][1]==data[(c['id'],v,0,False)][1];checks['repeat_pairs']+=1
   for rep in range(3):
    a=data[(c['id'],'baseline',rep,False)][0];b=data[(c['id'],v,rep,False)][0]
    av=[x for k in range(2,6) for x in a[k]];bv=[x for k in range(2,6) for x in b[k]];assert len(av)==len(bv)
    match=next(r for r in comp if r['case']==c['id'] and r['variant']==v and r['repeat']==rep)
    match.update(after_first_situation_relative_l1=sum(abs(x-y) for x,y in zip(av,bv))/sum(av),after_first_situation_sum_ratio=sum(bv)/sum(av))
 for row in summary['summaries']:
  c=cases[row['case']];row.update(requested_particle_budget=c['budget'],configured_workers=c['workers'],grid_spacing_m=c['dx'],declared_sources=c['sources'],source_groups=c['groups'],wind_m_s=c['wind_m_s'],stability_class=c['stability'],emission_pattern=c['pattern'])
 all_records+=records;all_rows+=summary['summaries'];all_comparisons+=comp
assert len(all_records)==240 and len(all_cases)==20
result=dict(status='pass',baseline=base_manifest['baseline'],conditions=20,pristine_main_runs=180,diagnostic_main_runs=60,total_main_runs=240,strict_engine_builds=6,build_warnings=0,build_errors=0,requested_particles=sorted(set(c['budget'] for c in all_cases)),actual_particles=sorted(set(r['actual_particles'] for r in all_records)),checks=checks,condition_details=all_cases,summaries=all_rows,limits=['End-to-end timings are three fresh-process repeats. Startup and IO dominate these short runs.','Planner and driver timings are from separate diagnostic builds. The extra scans warm caches, so phase timings do not establish a production break-even threshold.','Fixed-seed repeats do not estimate sampling uncertainty. Concentration differences have no independent accuracy oracle.','Actual source-minimum particle allocation can exceed the requested budget. The current planner uses TAUS*TPS as its target.','Fresh-emission mass checks do not establish a full-domain mass balance.','Auto mode is a proposal; no PR implementation was changed.'])
save(QA/'residual_combined_summary.json',result);save(QA/'residual_combined_records.json',all_records);save(QA/'residual_combined_comparisons.json',all_comparisons);save(QA/'residual_diagnostics.json',all_diagnostics)
for name,rows in [('residual_combined_summary',all_rows),('residual_combined_comparisons',all_comparisons),('residual_diagnostics',all_diagnostics)]:
 with (QA/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

print(json.dumps({'status':'pass','conditions':20,'main_runs':240,'checks':checks}))
