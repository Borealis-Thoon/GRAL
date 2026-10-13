from pathlib import Path
import argparse,hashlib,io,json,os,statistics,subprocess,tarfile,time,shutil
HERE=Path(__file__).resolve().parent
COMMITS={'baseline':'f2bd495cde6d060be2e451320c102090c157d7df','transfer':'514bd97aad89dc49bae83cf2f5d7ed59fe3523bd','buffers':'175bf603dc5d132a14a651df7397ce3ae9ff1df5'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);a=ap.parse_args();work=a.work.resolve();work.mkdir(parents=True,exist_ok=False);out=work/'results';out.mkdir();tmp=work/'tmp';tmp.mkdir();env=os.environ.copy();env.update(TEMP=str(tmp),TMP=str(tmp),DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_CLI_UI_LANGUAGE='en');dotnet=os.environ.get('GRAL_DOTNET','dotnet');start=time.monotonic()
 def run(args,cwd=work,timeout=60):
  if time.monotonic()-start>240:raise TimeoutError('240 second suite cap')
  p=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
  if p.returncode:raise RuntimeError(p.stdout+'\n'+p.stderr)
  return p
 for label,commit in COMMITS.items():
  raw=subprocess.run(['git','-C',str(a.repo),'archive',commit,'src'],check=True,capture_output=True).stdout;dest=work/label;dest.mkdir()
  with tarfile.open(fileobj=io.BytesIO(raw)) as archive:archive.extractall(dest,filter='data')
 # #74 is a single progress-interval guard on the #73 driver.
 p=work/'buffers/src/ProgramFunctions.cs';s=p.read_text(encoding='utf-8-sig');old='int percent10 = (int)(Program.NTEILMAX * 0.1F);';assert s.count(old)==1;p.write_text(s.replace(old,'int percent10 = Math.Max(1, (int)(Program.NTEILMAX * 0.1F));'),encoding='utf-8')
 # Keep actual queue/interval/prepare/merge logic; replace the physics body with the diagnostic visit/sum hook.
 p=work/'buffers/src/Zeitschleife.cs';s=p.read_text(encoding='utf-8-sig');signature='internal static void CalculateWithWorkerBuffer(int nteil, double[] workerConcentration)';start_body=s.index('{',s.index(signature));depth=1;i=start_body+1
 while depth:
  if s[i]=='{':depth+=1
  elif s[i]=='}':depth-=1
  i+=1
 p.write_text(s[:start_body]+'{\n            WorkerDriverProbe.Visit(nteil, workerConcentration);\n        }'+s[i:],encoding='utf-8');shutil.copy2(HERE/'WorkerDriverProbe.cs',work/'buffers/src/WorkerDriverProbe.cs')
 for name in ['driver_fixture','transfer_fixture']:shutil.copytree(HERE/name,work/name)
 projects=[work/f'{n}/src/GRAL.csproj' for n in COMMITS]+[work/'driver_fixture/DriverFixture.csproj',work/'transfer_fixture/Component.csproj']
 for index,project in enumerate(projects):
  p=run([dotnet,'build',str(project),'-c','Release','-p:TreatWarningsAsErrors=true','--nologo']);(out/f'build_{index}.log').write_text(p.stdout+p.stderr,encoding='utf-8');assert '0 Warning(s)' in p.stdout and '0 Error(s)' in p.stdout
 records=[];fixture=work/'driver_fixture/bin/Release/net10.0/DriverFixture.dll';engine=work/'buffers/src/bin/Release/net10.0/GRAL.dll'
 for mb in ['0','1']:
  for workers in [1,4,24]:
   for count in range(1,11):
    for repeat in [1,2]:
     p=run([dotnet,str(fixture),str(engine),mb,str(workers),'1',str(count+1)],timeout=15);line=p.stdout.split('[DRIVER] ',1)[1].splitlines()[0];row=json.loads(line);row.update(budget_mb=int(mb),repeat=repeat);records.append(row)
 (out/'combined_driver.json').write_text(json.dumps(dict(status='pass',runs=len(records),records=records),indent=2)+'\n')
 records=[];fixture=work/'transfer_fixture/bin/Release/net10.0/Component.dll';configs=[(63,32,1,64),(64,32,1,64),(4,512,1,64),(512,256,1,1)]
 for ci,(nx,ny,ns,sg) in enumerate(configs):
  for workers in [4,24]:
   for repeat in [1,2]:
    for variant in (['baseline','transfer'] if (ci+repeat)%2 else ['transfer','baseline']):
     pth=out/f'transfer_{nx}_{ny}_{workers}_{repeat}_{variant}.json';run([dotnet,str(fixture),str(work/f'{variant}/src/bin/Release/net10.0/GRAL.dll'),'transfer',str(nx),str(ny),str(ns),str(sg),str(workers),str(pth)],timeout=30);row=json.loads(pth.read_text());row.update(variant=variant,repeat=repeat,median_ms=statistics.median(row['elapsed_ms_per_transfer'][2:]));records.append(row)
 (out/'transfer_boundary.json').write_text(json.dumps(dict(status='pass',runs=len(records),records=records,elapsed_s=time.monotonic()-start),indent=2)+'\n');print('[PASS]',120,'driver',len(records),'transfer')
if __name__=='__main__':main()

