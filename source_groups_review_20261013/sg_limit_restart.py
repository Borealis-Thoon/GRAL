from pathlib import Path
import argparse, importlib.util, json, os, re, shutil, time, struct, zipfile
p=argparse.ArgumentParser();p.add_argument('--work-dir',required=True,type=Path);p.add_argument('--qa-dir',required=True,type=Path);p.add_argument('--dotnet',default='dotnet');a=p.parse_args();root=a.work_dir;qa=a.qa_dir
sp=importlib.util.spec_from_file_location('validation',Path(__file__).resolve().parent/'sg_limit_validation.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
run=root/'restart_pulse_run';run.mkdir(exist_ok=True);env=os.environ.copy();env.update(TEMP=str(root/'run/tmp'),TMP=str(root/'run/tmp'),DOTNET_CLI_HOME=str(root/'run/dotnet_home'));rows=[];start=time.perf_counter()

def alloff(folder):
 q=folder/'emissions_timeseries.txt';lines=q.read_text().splitlines();n=len(lines[0].split(';'))-2
 for i in range(2,len(lines)):lines[i]=';'.join(lines[i].split(';')[:2]+['0']*n)
 q.write_text('\n'.join(lines)+'\n');q=folder/'synthetic_case.json';d=json.loads(q.read_text());d['emission_factors']=[[1]*n]+[[0]*n for _ in range(d['situations']-1)];m.save(q,d)

for name,variant,rep in [('legacy_area','baseline',0),('legacy_area','fixed',0),('count108_area','fixed',0),('count108_area','fixed',1),('count255_area','fixed',0),('count255_area','fixed',1)]:
 c=next(c for c in m.cases() if c['id']==name);key=f'{name}_{variant}_{rep}';prefix=run/(key+'_prefix')
 if not prefix.exists():shutil.copytree(root/'inputs'/name,prefix)
 (prefix/'KeepAndReadTransientTempFiles.dat').write_text('2\n');alloff(prefix)
 dll=root/'source'/variant/'src/bin/Release/net10.0/GRAL.dll'
 for phase in ['prefix','resume']:
  if phase=='prefix':folder=prefix;check=dict(c,situations=3)
  else:
   folder=run/(key+'_resume')
   if not folder.exists():m.make_input(dict(c,situations=4),folder,root/'inputs'/name)
   (folder/'KeepAndReadTransientTempFiles.dat').unlink(missing_ok=True);check=dict(c,situations=2,allow_zero_groups=True);alloff(folder)
   files=list(prefix.glob('Transient_Concentrations*.tmp'));assert len(files)==1
   with zipfile.ZipFile(files[0]) as z:
    data=z.read(z.namelist()[0]);assert struct.unpack_from('<ii',data,48)==(2,len(c['ids']))
   shutil.copy2(files[0],folder/files[0].name)
  if (folder/'console.log').exists():code=0;out=(folder/'console.log').read_bytes().decode('utf-8').replace('\r\r\n','\n').replace('\r\n','\n');err=(folder/'stderr.log').read_text(encoding='utf-8');elapsed=None
  else:
   code,out,err,elapsed=m.process([a.dotnet,str(dll),str(folder)],folder,env,30);(folder/'console.log').write_text(out,encoding='utf-8');(folder/'stderr.log').write_text(err,encoding='utf-8')
  assert code==0 and 'GRAL simulations finished at:' in (folder/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig'),out+err
  problem=folder/'Problemreport_GRAL.txt';assert not problem.exists() or not problem.read_text(encoding='utf-8-sig').strip()
  payload,sums=m.payloads(folder,check)
  if phase=='resume':assert 'Reading Transient_Concentrations.tmp successful!' in out;assert all(k.startswith(('3:','4:')) for k in payload),payload
  final=list(map(float,re.findall(r'Summarized emission rates per source group in kg\s*\n[^\n]*SG:[^\n]*\n([^\n]+)',out)[-1].split()));factors=json.loads((folder/'synthetic_case.json').read_text())['emission_factors'];expect=[sum(f[g] for f in factors)*30/3600 for g in range(len(c['ids']))];assert len(final)==len(expect);assert all(abs(x-y)<=.00011+.006*abs(y) for x,y in zip(final,expect))
  rows.append(dict(case=name,variant=variant,repeat=rep,phase=phase,status='pass',wall_s=elapsed,payload_sha256=payload,output_sums=sums,fresh_mass_kg=final,zero_concentration_groups=[g for g,v in sums.items() if v==0]));print('[RESTART]',key,phase,'pass',flush=True)
for phase in ['prefix','resume']:
 a0=next(r for r in rows if r['case']=='legacy_area' and r['variant']=='baseline' and r['phase']==phase);a1=next(r for r in rows if r['case']=='legacy_area' and r['variant']=='fixed' and r['phase']==phase);assert a0['payload_sha256']==a1['payload_sha256']
 for name in ['count108_area','count255_area']:
  rr=[r for r in rows if r['case']==name and r['phase']==phase];assert rr[0]['payload_sha256']==rr[1]['payload_sha256']
m.save(qa/'sg_limit_restart.json',dict(status='pass',main_runs=len(rows),elapsed_s=time.perf_counter()-start,records=rows,legacy_baseline_fixed_equal=True,high_group_repeats_equal=True,scope='Same ordered IDs retained across checkpoint and resume; situations3 and4 run after the fully written intermediate situation2 checkpoint. Emission pulse only in situation1 (no later fresh-emission accumulation during checkpoint writing). Interval2 with3 prefix situations ensures existing writer is joined before exit; final-situation checkpoint writer joining and concurrent EmissionPerSG snapshot remain separate limitations. This is SG read/resume compatibility under an emission-OFF condition, not general uninterrupted/restart equivalence. SG30 and224 may have no remaining concentration in the 255-group resume window; their output entries must still exist.'))
