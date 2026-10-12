"""Strict builds and fixed-seed real Main regression for independent GRAL patches."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,os,re,shutil,signal,struct,subprocess,sys,time,zipfile
from pathlib import Path
from main_inputs import cases,configure,save,sha
BASE='warning_free_baseline'
SCOPES={
 'nan_guard_state':['src/ProgramFunctions.cs','src/Program.cs','src/Zeitschleife.cs','src/Zeitschleife_nonsteadystate.cs'],
 'nan_guard_storage':['src/Transient_Concentration.cs','src/Program.cs'],
 'opt1_stack':['src/Zeitschleife.cs'],
 'opt1_vertical':['src/Intwind.cs','src/Zeitschleife.cs','src/Zeitschleife_nonsteadystate.cs'],
}
RNG_PATTERN=r'(?:DeterministicRng|Random\.Shared\.NextDouble|NextDouble)\([^;\n]*?\)|(?:m_z|m_w)\s*=\s*(?:36969|18000)[^;]*;'

def source_hashes(folder):
 return {p.relative_to(folder).as_posix():sha(p) for p in sorted((folder/'src').iterdir()) if p.is_file()}
def inspect(package,variants,scopes):
 reference=json.loads((package/'inputs/baseline_source_manifest.json').read_text(encoding='utf-8-sig'))
 expected=reference['source_files'][BASE];actual=source_hashes(package/'source'/BASE)
 if actual!=expected or len(actual)!=85:raise AssertionError('Current baseline source85 SHA-256 differs')
 oldtexts={name:(package/'source'/BASE/name).read_text(encoding='utf-8-sig') for name in actual if name.endswith('.cs')}
 manifests={BASE:actual};changed={};rng_guard={}
 for variant in variants:
  if variant==BASE:continue
  if variant not in scopes:raise AssertionError('Explicit source scope required: '+variant)
  hashes=source_hashes(package/'source'/variant)
  if set(hashes)!=set(actual):raise AssertionError('Source file set differs: '+variant)
  changes=[name for name in actual if actual[name]!=hashes[name]]
  if not changes or not set(changes)<=set(scopes[variant]):raise AssertionError('Changed source outside allowlist: '+variant+repr(changes))
  for name,old in oldtexts.items():
   new=(package/'source'/variant/name).read_text(encoding='utf-8-sig')
   if re.findall(RNG_PATTERN,old)!=re.findall(RNG_PATTERN,new):raise AssertionError('RNG call/update sequence changed: '+variant+'/'+name)
  # Unchanged writers and source initialization are additionally named in the receipt.
  protected=[name for name in actual if name.startswith('src/Write') or name in ('src/Anfangko.cs','src/DepositionComputation.cs')]
  if not all(hashes[name]==actual[name] for name in protected):raise AssertionError('Protected output/start-coordinate file differs')
  manifests[variant]=hashes;changed[variant]=changes;rng_guard[variant]=dict(all_source_rng_call_sequences_equal=True,protected_sha256_files=protected)
 return dict(baseline_commit=reference['baseline_commit'],source_files=manifests,allowed_scopes=scopes,changed_files=changed,rng_guard=rng_guard)

def csvwrite(path,rows):
 if not rows:return
 with path.open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def process(command,cwd,env,timeout,pid_records):
 kwargs={'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)} if os.name=='nt' else {'start_new_session':True}
 started=time.perf_counter();p=subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kwargs)
 record=dict(pid=p.pid,command=command,cwd=str(cwd),timeout_s=timeout);pid_records.append(record)
 try:out,err=p.communicate(timeout=timeout)
 except subprocess.TimeoutExpired:
  if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=15)
  else:os.killpg(p.pid,signal.SIGKILL)
  out,err=p.communicate(timeout=10);record.update(timed_out=True,exit_code=p.returncode,elapsed_s=time.perf_counter()-started)
  raise TimeoutError('Owned PID exceeded limit: '+str(p.pid)+' '+str(cwd))
 record.update(timed_out=False,exit_code=p.returncode,elapsed_s=time.perf_counter()-started)
 return p.returncode,out.decode('utf-8',errors='replace'),err.decode('utf-8',errors='replace')

def outputs(folder,case,expected_situations,checkpoint_required=True):
 payload={};nvalues=0;nonzero=0;counts=dict(concentration=0,deposition=0,odour=0,checkpoints=0,receptors=0);grids=[]
 for path in sorted(folder.glob('*.grz')):
  with zipfile.ZipFile(path) as archive:
   for name in sorted(archive.namelist()):
    raw=archive.read(name);payload[path.name+':'+name]=hashlib.sha256(raw).hexdigest()
    kind=next((kind for ending,kind in [('.con','concentration'),('.dep','deposition'),('.odr','odour')] if name.endswith(ending)),None)
    if kind is None:continue
    if len(raw)<28:raise AssertionError('Missing V03 header: '+name)
    header,x,y,dx,dy,nx,ny=struct.unpack_from('<iiiffii',raw)
    if (header,x,y,nx,ny)!=(-3,0,0,case['nx'],case['ny']) or dx!=case['dx'] or dy!=case['dy']:raise AssertionError('Actual dense V03 dynamic grid differs: '+name)
    n=nx*ny*(4 if kind=='odour' else 1)
    if len(raw)!=28+n*4:raise AssertionError('Actual float payload size differs: '+name)
    values=struct.unpack_from('<'+str(n)+'f',raw,28)
    if not all(math.isfinite(v) and v>=0 for v in values):raise AssertionError('Finite nonnegative float payload failed: '+name)
    counts[kind]+=1;nvalues+=n;nonzero+=sum(v>0 for v in values);grids.append(dict(name=name,kind=kind,nx=nx,ny=ny,dx_m=dx,dy_m=dy))
 for path in sorted(folder.glob('Transient_Concentrations*.tmp')):
  with zipfile.ZipFile(path) as archive:
   for name in sorted(archive.namelist()):
    raw=archive.read(name);payload[path.name+':'+name]=hashlib.sha256(raw).hexdigest();counts['checkpoints']+=1
 for name in ('ReceptorConcentrations.dat','Receptor_Timeseries_Transient.txt'):
  path=folder/name
  if path.exists():
   payload[name]=sha(path);counts['receptors']+=1
   raw_text=path.read_bytes();text_encoding='utf-16' if raw_text.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
   for token in re.split(r'[\s;,]+',raw_text.decode(text_encoding)):
    try:value=float(token)
    except ValueError:continue
    if not math.isfinite(value):raise AssertionError('Nonfinite receptor value: '+name)
 expected=case['slices']*2*len(expected_situations)
 if counts['concentration']!=expected:raise AssertionError(f'Concentration count {counts["concentration"]} != {expected}')
 if case['mode']=='transient' and checkpoint_required and counts['checkpoints']!=1:raise AssertionError('Residual checkpoint missing')
 if case['receptors'] and not counts['receptors']:raise AssertionError('Receptor missing')
 if case['deposition'] and not counts['deposition']:raise AssertionError('Deposition missing')
 if case['odour'] and not counts['odour']:raise AssertionError('Odour missing')
 if nonzero==0:raise AssertionError('Configured outputs are all zero')
 return payload,counts,nvalues,grids

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--run-dir',type=Path)
 parser.add_argument('--dotnet',default=r'C:\Program Files\dotnet\dotnet.exe');parser.add_argument('--variants',nargs='+',default=list(SCOPES))
 parser.add_argument('--scope-file',type=Path);parser.add_argument('--cases',nargs='+');parser.add_argument('--repeat',type=int,default=2)
 parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--execute',action='store_true');parser.add_argument('--skip-restart',action='store_true')
 args=parser.parse_args();package=args.package_root.resolve();selected=cases()
 if args.cases:
  unknown=set(args.cases)-{c['id'] for c in selected}
  if unknown:raise ValueError('Unknown synthetic case: '+repr(unknown))
  selected=[c for c in selected if c['id'] in args.cases]
 if args.repeat<1 or args.repeat>2:raise ValueError('Use one or two bounded repeats')
 scopes=dict(SCOPES)
 if args.scope_file:scopes.update(json.loads(args.scope_file.read_text(encoding='utf-8-sig')))
 if args.prepare_only:
  prepared=[]
  for rawcase in selected:
   folder=package/'inputs/synthetic_cases'/rawcase['id'];prepared.append(configure(package/'inputs/template',folder,rawcase))
  save(package/'qa/main_preparation.json',dict(status='prepared_not_executed',conditions=len(prepared),conditions_detail=prepared,limits=['No model or performance execution has occurred.','Terrain and wind input are entirely synthetic; no GRAMM model run is asserted.']))
  print('[PREPARED] '+str(len(prepared))+' cases',flush=True);return
 if not args.execute:raise ValueError('Model execution requires explicit --execute after source finalization')
 if not args.run_dir:raise ValueError('Fresh --run-dir is required')
 run=args.run_dir.resolve()
 if run.exists():raise FileExistsError('Use a fresh isolated run directory')
 variants=[BASE]+[v for v in args.variants if v!=BASE]
 if len(set(variants))!=len(variants):raise ValueError('Duplicate variant')
 manifest=inspect(package,variants,scopes);run.mkdir(parents=True)
 for name in ('logs','tmp','cache','qa','source','inputs','virtual_runs','restart'):(run/name).mkdir()
 save(run/'qa/main_source_manifest.json',manifest)
 env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(run/'cache/dotnet'),NUGET_PACKAGES=str(run/'cache/nuget'),TEMP=str(run/'tmp'),TMP=str(run/'tmp'),DOTNET_CLI_UI_LANGUAGE='en',DOTNET_NOLOGO='1')
 dotnet=str(Path(args.dotnet).resolve())
 if not Path(dotnet).is_file():raise FileNotFoundError('Verified .NET CLI required')
 started=time.perf_counter();pids=[];builds={};dlls={};records=[];data={};conditions=[];restart_records=[]
 def limit(seconds):
  remaining=900-(time.perf_counter()-started)
  if remaining<=0:raise TimeoutError('Whole suite exceeded 900 seconds')
  return min(seconds,remaining)
 def run_main(variant,folder,case,rid,repeat,expected_situations,expect_load=False,check_fresh=True):
  before=time.perf_counter();code,out,err=process([dotnet,str(dlls[variant]),str(folder)],folder,env,limit(60),pids)
  (folder/'console.log').write_text(out,encoding='utf-8');(folder/'stderr.log').write_text(err,encoding='utf-8')
  core=folder/'Logfile_GRALCore.txt';problem=folder/'Problemreport_GRAL.txt'
  if code or not core.exists() or 'GRAL simulations finished at:' not in core.read_text(encoding='utf-8-sig') or (problem.exists() and problem.read_text(encoding='utf-8-sig').strip()):raise AssertionError('Actual Main completion failed: '+rid+'\n'+out[-4000:]+err)
  allocation=list(map(int,re.findall(r'Using a total of (\d+) particles',out)))
  if len(allocation)!=1 or not 100<=allocation[0]<=3000 or allocation[0]!=case['budget']:raise AssertionError('Actual particle allocation differs: '+rid+repr(allocation))
  weather=[(float(s),int(d),int(sc)) for s,d,sc in re.findall(r'Init meteo:\s+wind speed \[m/s\]: ([0-9.]+)\s+direction \[deg\]: ([0-9]+)\s+Stability class \[-\]: ([0-9]+)',out)]
  wanted_weather=[(case['weather'][s-1][1],case['weather'][s-1][0]*10,case['weather'][s-1][2]) for s in expected_situations]
  if weather!=wanted_weather:raise AssertionError('Actual meteorology differs: '+rid+repr(weather)+' != '+repr(wanted_weather))
  weather_numbers=list(map(int,re.findall(r'Weather number: (\d+)',out)))
  expected_announcements=expected_situations+[max(expected_situations)+1]
  if weather_numbers!=expected_announcements:raise AssertionError('Weather announcements differ: '+rid+repr(weather_numbers))
  if expect_load and 'Reading Transient_Concentrations.tmp successful!' not in out:raise AssertionError('Actual checkpoint was not loaded: '+rid)
  sourcepatterns=dict(point='point sources',portal='tunnel portals',line='line source segments',area='area source partitions');sourcecounts={}
  for kind,description in sourcepatterns.items():
   found=re.findall(r'Total number of '+description+r': (\d+)',out);sourcecounts[kind]=int(found[0]) if found else 0;declared=case['source_counts'].get(kind,0)
   if (sourcecounts[kind]<declared if case['deposition'] else sourcecounts[kind]!=declared):raise AssertionError('Actual source count differs: '+kind+' '+rid)
  fresh_mass=None
  if case['mode']=='transient':
   if 'Reading emissions_timeseries.txt successful' not in out:raise AssertionError('Emission schedule was not read')
   if check_fresh:
    reported=re.findall(r'Summarized emission rates per source group in kg\s*\n[^\n]*SG:[^\n]*\n([^\n]+)',out)
    if not reported:raise AssertionError('Fresh emission diagnostic missing')
    fresh_mass=list(map(float,reported[-1].split()));expected_mass=[case['source_group_base_rates_kg_h'][g]*math.fsum(case['emission_factors'][s-1][g] for s in expected_situations)*30/3600 for g in (0,1)]
    if len(fresh_mass)!=2 or not all(math.isclose(a,b,rel_tol=.005,abs_tol=.0001) for a,b in zip(fresh_mass,expected_mass)):raise AssertionError('Cumulative fresh mass differs '+rid+repr(fresh_mass)+' != '+repr(expected_mass))
  if case['terrain']:
   if 'FLOW FIELD COMPUTATION WITH TOPOGRAPHY' not in out or 'Reading GRAMM wind field:' not in out or 'Reading GRAMM orography file ggeom.asc' not in out:raise AssertionError('Actual terrain/GRAMM input path not exercised')
  if case['buildings'] and ('Reading building file buildings.dat' not in out or not re.search(r'Total number of blocked cells in 2D: [1-9]',out)):raise AssertionError('Actual building path not exercised')
  guard_text=out+'\n'+core.read_text(encoding='utf-8-sig')
  rejected_states=list(map(int,re.findall(r'Rejected (\d+) non-finite particle states',guard_text)))
  skipped_writes=list(map(int,re.findall(r'Skipped (\d+) non-finite residual writes',guard_text)))
  if any(rejected_states) or any(skipped_writes):raise AssertionError('Guard rejected finite-state Main input: '+rid+repr((rejected_states,skipped_writes)))
  payload,counts,nvalues,grids=outputs(folder,case,list(range(1,max(expected_situations)+1)) if expect_load else expected_situations,checkpoint_required=not expect_load)
  names=['exit_zero','completion_marker','empty_problem_report','actual_particles_in_100_to_3000','actual_allocation_equals_configured_budget','actual_source_type_counts','actual_meteorology','actual_weather_sequence','dynamic_dense_v03_grid','finite_nonnegative_float_payloads','expected_concentration_count','expected_auxiliary_outputs','nonzero_output','within_60_second_main_limit','normal_guard_diagnostics_zero_or_unreported']
  if case['mode']=='transient':names.append('actual_emission_schedule_read')
  if fresh_mass is not None:names.append('cumulative_fresh_mass_matches_schedule')
  if expect_load:names.append('actual_checkpoint_read_and_resume_sequence')
  if case['terrain']:names.append('actual_synthetic_terrain_wind_input_path')
  if case['buildings']:names.append('actual_building_path')
  record=dict(run_id=rid,case=case['id'],variant=variant,repeat=repeat,elapsed_s=time.perf_counter()-before,actual_particles=allocation[0],actual_weather=weather,actual_weather_numbers=weather_numbers,actual_source_counts=sourcecounts,counts=counts,float_values_checked=nvalues,payload_sha256=payload,fresh_mass_kg=fresh_mass,checks={name:True for name in names},checks_passed=len(names),restart_loaded=expect_load,actual_grid_headers=grids,normal_guard_diagnostics=dict(rejected_particle_states_reported=rejected_states,skipped_residual_writes_reported=skipped_writes,zero_or_unreported=True))
  records.append(record)
  save(run/'qa/main_progress.json',dict(status='running',completed_main_runs=len(records),completed_main_checks=sum(r['checks_passed'] for r in records),last_run=rid,strict_builds=builds,elapsed_s=time.perf_counter()-started))
  return record
 try:
  for variant in variants:
   target=run/'source'/variant;shutil.copytree(package/'source'/variant,target,ignore=shutil.ignore_patterns('bin','obj'))
   code,out,err=process([dotnet,'build',str(target/'src/GRAL.csproj'),'-c','Release','-t:Rebuild','-v:minimal','--nologo','/p:TreatWarningsAsErrors=true'],target/'src',env,limit(180),pids);log=out+err;(run/'logs'/f'{variant}_build.log').write_text(log,encoding='utf-8')
   warnings=re.search(r'(\d+) Warning\(s\)',log);errors=re.search(r'(\d+) Error\(s\)',log)
   if code or not warnings or not errors or int(warnings.group(1)) or int(errors.group(1)):raise AssertionError('Strict build failed '+variant+'\n'+log)
   builds[variant]=dict(warnings=0,errors=0);dlls[variant]=next(p for p in (target/'src/bin/Release/net10.0').glob('*.dll') if p.stem.lower()=='gral');print('[BUILD] '+variant+' 0 0',flush=True)
  for rawcase in selected:
   template=run/'inputs'/rawcase['id'];case=configure(package/'inputs/template',template,rawcase);conditions.append(case)
   for variant in variants:
    for repeat in range(1,args.repeat+1):
     rid=case['id']+'_'+variant+'_r'+str(repeat);folder=run/'virtual_runs'/rid;shutil.copytree(template,folder)
     record=run_main(variant,folder,case,rid,repeat,list(range(1,len(case['weather'])+1)));data[(case['id'],variant,repeat)]=record
     print('[MAIN] '+str(len(records))+'/'+str(len(selected)*len(variants)*args.repeat)+' '+rid,flush=True)
  comparisons=[];repeats=[]
  for case in conditions:
   for variant in variants:
    if args.repeat==2:
     a=data[(case['id'],variant,1)];b=data[(case['id'],variant,2)]
     if a['payload_sha256']!=b['payload_sha256']:raise AssertionError('Fixed-seed repeat differs: '+case['id']+' '+variant)
     repeats.append(dict(case=case['id'],variant=variant,payloads_equal=True,payloads=len(a['payload_sha256'])))
   for variant in variants[1:]:
    for repeat in range(1,args.repeat+1):
     a=data[(case['id'],BASE,repeat)];b=data[(case['id'],variant,repeat)]
     if a['payload_sha256']!=b['payload_sha256']:raise AssertionError('Baseline/candidate payload differs: '+case['id']+' '+variant)
     comparisons.append(dict(case=case['id'],variant=variant,repeat=repeat,actual_particles=a['actual_particles'],payloads=len(a['payload_sha256']),payloads_equal=True,changed_payloads=0,max_absolute_concentration_difference=0,relative_l1=0))
  if not args.skip_restart:
   restart_case=next((c for c in conditions if c['id']=='mixed_transient_n1000_20m'),None)
   if restart_case:
    restart_data={}
    for variant in variants:
     for repeat in range(1,args.repeat+1):
      folder=run/'restart'/f'{variant}_r{repeat}';shutil.copytree(run/'inputs'/restart_case['id'],folder)
      original=(folder/'mettimeseries.dat').read_bytes();(folder/'mettimeseries.dat').write_bytes(b'\n'.join(original.splitlines()[:2])+b'\n')
      prefix=run_main(variant,folder,restart_case,f'restart_prefix_{variant}_r{repeat}',repeat,[1,2])
      checkpoint=next(folder.glob('Transient_Concentrations*.tmp'))
      with zipfile.ZipFile(checkpoint) as archive:
       raw=archive.read(archive.namelist()[0]);checkpoint_situation=struct.unpack_from('<i',raw,48)[0]
      if checkpoint_situation!=2:raise AssertionError('Prefix checkpoint situation differs')
      checkpoint_payload_sha=hashlib.sha256(raw).hexdigest();(folder/'mettimeseries.dat').write_bytes(original);(folder/'KeepAndReadTransientTempFiles.dat').unlink()
      resumed=run_main(variant,folder,restart_case,f'restart_resume_{variant}_r{repeat}',repeat,[3],expect_load=True,check_fresh=False)
      item=dict(variant=variant,repeat=repeat,prefix_checkpoint_situation=checkpoint_situation,prefix_checkpoint_payload_sha256=checkpoint_payload_sha,resume_weather_numbers=resumed['actual_weather_numbers'],actual_checkpoint_loaded=True,resumed_payload_sha256=resumed['payload_sha256']);restart_records.append(item);restart_data[(variant,repeat)]=item
      print('[RESTART] '+variant+' r'+str(repeat)+' loaded',flush=True)
    for item in restart_records:
     reference=restart_data[(BASE,item['repeat'])]
     if item['prefix_checkpoint_payload_sha256']!=reference['prefix_checkpoint_payload_sha256'] or item['resumed_payload_sha256']!=reference['resumed_payload_sha256']:raise AssertionError('Baseline/candidate actual resume differs: '+item['variant'])
     item['baseline_prefix_and_resume_payloads_equal']=True
     if args.repeat==2:
      if item['resumed_payload_sha256']!=restart_data[(item['variant'],1)]['resumed_payload_sha256']:raise AssertionError('Fixed-seed resumed repeat differs: '+item['variant'])
      item['fixed_seed_resume_repeats_equal']=True
  final=inspect(package,variants,scopes)
  if final['source_files']!=manifest['source_files']:raise AssertionError('Original source changed during suite')
  for variant in variants:
   if source_hashes(run/'source'/variant)!=manifest['source_files'][variant]:raise AssertionError('Compiled copy source differs: '+variant)
  summary=dict(status='pass',source_files_per_variant=85,baseline_commit=manifest['baseline_commit'],variants=variants,strict_builds=builds,conditions=len(conditions),main_runs=len(records),main_checks_passed=sum(r['checks_passed'] for r in records),single_worker_repeat_pairs=len(repeats),baseline_candidate_pairs=len(comparisons),compared_payload_pairs=sum(c['payloads'] for c in comparisons),actual_restart_pairs=len(restart_records),checkpoint_read_runs=sum(r['restart_loaded'] for r in records),concentration_payloads=sum(r['counts']['concentration'] for r in records),checkpoint_payloads=sum(r['counts']['checkpoints'] for r in records),float_values_checked=sum(r['float_values_checked'] for r in records),elapsed_s=time.perf_counter()-started,conditions_detail=conditions,comparisons=comparisons,repeat_results=repeats,restart=restart_records,runs=records,limits=['Fixed-seed byte equality is required only for these controlled single-worker cases.','Hourly labels index 30-second situations; they do not assert hourly physical integration.','This balanced coverage is not a full factorial sensitivity design.','Terrain geometry and prescribed winds are wholly synthetic and not a GRAMM model validation.','No physical truth oracle or production-domain speedup claim.','Checkpoint tests require baseline/candidate resumed payload equality; continuous/resumed engine-state equality is not asserted.','Only the Main suite is counted here; worker-owned injected-NaN and optimization component checks are separate.'])
  save(run/'qa/main_validation_summary.json',summary);csvwrite(run/'qa/main_output_comparison.csv',comparisons);save(run/'qa/main_process_ownership.json',pids)
  save(run/'qa/main_progress.json',dict(status='pass',completed_main_runs=len(records),completed_main_checks=summary['main_checks_passed'],strict_builds=builds,elapsed_s=summary['elapsed_s']))
  print('[PASS] '+str(len(records))+' Main; '+str(summary['main_checks_passed'])+' checks',flush=True)
 except BaseException as exc:
  save(run/'qa/main_failure.json',dict(status='fail',type=type(exc).__name__,message=str(exc),completed_main_runs=len(records),elapsed_s=time.perf_counter()-started,strict_builds=builds))
  save(run/'qa/main_partial_runs.json',records);save(run/'qa/main_process_ownership.json',pids);raise
if __name__=='__main__':main()
