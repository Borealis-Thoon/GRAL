"""Restore five pinned GRAL variants inside a fresh evidence directory."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, time
ROOT=Path(__file__).resolve().parents[2]
BASE='e3336e8e901d5f49f20fa3a954a08463517bf61d'
DEV='7d4366a6ac16f58a5d28f166e272e59247362630'
PATCHES={
 'double':['pr64_on_current.patch'],
 'dictionary_fixed':['dictionary_fixed.patch'],
 'output_index':['dictionary_fixed.patch','output_index.patch'],
 'static_update':['dictionary_fixed.patch','static_update.patch'],
 'combined':['dictionary_fixed.patch','output_index.patch','static_update.patch'],
}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(args,cwd,env,deadline,limit=120):
 remaining=min(limit,deadline-time.monotonic())
 if remaining<=0:raise TimeoutError('Restoration batch budget exhausted')
 proc=subprocess.Popen(list(map(str,args)),cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
 try:out,_=proc.communicate(timeout=remaining)
 except subprocess.TimeoutExpired:
  if os.name=='nt':subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=10)
  else:proc.kill()
  proc.communicate();raise
 text=out.decode('utf-8',errors='replace')
 if proc.returncode:raise RuntimeError(text)
 return text

def main():
 p=argparse.ArgumentParser();p.add_argument('--git',default='git');p.add_argument('--dotnet',default='dotnet');p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
 root=a.root.resolve();assert (root/'qa/followup_source_lock.json').is_file(),'Use a fresh extracted followup evidence directory.'
 dest=root/'work/restored_followup'
 assert not dest.exists() and not (root/'build').exists(),'Restoration requires new source and build directories; existing data is never replaced.'
 dest.mkdir(parents=True,exist_ok=False);(root/'tmp').mkdir(exist_ok=True)
 env=os.environ.copy();env.update(TEMP=str(root/'tmp'),TMP=str(root/'tmp'),DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_CLI_UI_LANGUAGE='en')
 deadline=time.monotonic()+840;repo=dest/'upstream';lock=json.loads((root/'qa/followup_source_lock.json').read_text(encoding='utf-8-sig'))
 for filename,digest in lock['patch_sha256'].items():assert sha(root/'qa'/filename)==digest,filename
 run([a.git,'clone','--no-checkout','--single-branch','--branch','ConcurrentDictionary','https://github.com/GralDispersionModel/GRAL.git',repo],root,env,deadline)
 for commit in [BASE,DEV]:run([a.git,'fetch','origin',commit],repo,env,deadline)
 outputs=[]
 for variant,patches in PATCHES.items():
  target=dest/variant
  run([a.git,'worktree','add','--detach',target,BASE if variant=='double' else DEV],repo,env,deadline)
  for patch in patches:run([a.git,'apply',root/'qa'/patch],target,env,deadline)
  expected=lock['variants'][variant]['sources']
  mismatches=[name for name,digest in expected.items() if sha(target/name)!=digest]
  assert not mismatches,(variant,mismatches)
  result={'variant':variant,'source_files_verified':len(expected),'strict_build':False}
  if not a.prepare_only:
   log=run([a.dotnet,'build',target/'src/GRAL.csproj','-c','Release','--nologo','--disable-build-servers','/p:TreatWarningsAsErrors=true','-o',root/'build'/variant],target,env,deadline)
   (dest/(variant+'.build.log')).write_text(log,encoding='utf-8')
   result.update(strict_build=True,binary_sha256=sha(root/'build'/variant/'GRAL.dll'))
  outputs.append(result);print('[SOURCE]' if a.prepare_only else '[BUILD]',variant,flush=True)
 (dest/'restoration.json').write_text(json.dumps({'variants':outputs,'batch_limit_s':840,'models_run':False},indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
