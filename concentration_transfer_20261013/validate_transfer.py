from pathlib import Path
import subprocess,json,time,os,statistics
B=Path(__file__).resolve().parent;R=B/'component_final_results';R.mkdir(exist_ok=True);dotnet=r'C:\Program Files\dotnet\dotnet.exe';fixture=B/'component/bin/Release/net10.0/Component.dll';start=time.perf_counter();rows=[]
env=os.environ.copy();env.update(TEMP=str(B/'tmp'),TMP=str(B/'tmp'))
configs=[(3,3,0,2,w) for w in [1,4,24]]+[(12,12,1,2,w) for w in [1,4]]+[(63,32,1,64,w) for w in [4,24]]+[(64,32,1,64,w) for w in [4,24]]+[(116,84,9,108,w) for w in [1,4,24]]+[(230,166,9,108,w) for w in [1,4,24]]
for i,(nx,ny,ns,sg,workers) in enumerate(configs):
 for v in (['f64','parallel'] if i%2 else ['parallel','f64']):
  if time.perf_counter()-start>180:raise TimeoutError('180s cap')
  out=R/f'{nx}_{ny}_{ns}_{sg}_w{workers}_{v}.json';p=subprocess.run([dotnet,str(fixture),str(B/'sources'/v/'src/bin/Release/net10.0/GRAL.dll'),'transfer',str(nx),str(ny),str(ns),str(sg),str(workers),str(out)],cwd=R,env=env,capture_output=True,timeout=30);assert p.returncode==0,p.stderr.decode();r=json.loads(out.read_text());rows.append(dict(variant=v,**r));print('[FINAL]',nx,ny,ns,sg,workers,v,round(statistics.median(r['elapsed_ms_per_transfer'][2:]),4),flush=True)
(B/'final_component_summary.json').write_text(json.dumps(dict(status='pass',source_hashes=json.loads((B/'source_manifest.json').read_text())['hashes'],transfer_runs=len(rows),timed_configurations=12,empty_slice_configurations=3,checked_cast_and_reset_values=sum(r['checked_values'] for r in rows),records=rows,elapsed_s=time.perf_counter()-start),indent=2)+'\n');print('[PASS]',len(rows),'final runs',flush=True)
