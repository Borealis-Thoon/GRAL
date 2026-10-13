"""Reconstruct the tested source and runners without changing the supplied repository."""
from pathlib import Path
import argparse,hashlib,io,json,shutil,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parent

def normalized_hash(path):
 return hashlib.sha256(path.read_text(encoding='utf-8-sig').replace('\r\n','\n').encode()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--source-repo',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True);args=p.parse_args()
 work=args.work_dir.resolve();work.mkdir(parents=True,exist_ok=False)
 manifest=json.loads((ROOT/'source_manifest.json').read_text());base=manifest['base']
 raw=subprocess.check_output(['git','-C',str(args.source_repo.resolve()),'archive','--format=zip',base,'src'])
 target=work/'source/f64';target.mkdir(parents=True)
 with zipfile.ZipFile(io.BytesIO(raw)) as z:z.extractall(target)
 subprocess.run(['git','apply','--unsafe-paths',str(ROOT/'double_accumulation_prerequisite.patch')],cwd=target,check=True)
 shutil.copytree(target,work/'repo')
 subprocess.run(['git','apply','--unsafe-paths',str(ROOT/'worker_accumulation.patch')],cwd=work/'repo',check=True)
 for variant,folder in [('f64',target/'src'),('candidate',work/'repo/src')]:
  actual={p.name:normalized_hash(p) for p in sorted(folder.iterdir()) if p.is_file()}
  assert actual==manifest['files'][variant],variant+' source mismatch'
 for name in ['run_component.py','run_main.py','run_performance.py','prepare_driver_probe.py','field_support.py','transient_support.py']:
  shutil.copyfile(ROOT/name,work/name)
 for name in ['field','transient','fixture']:shutil.copytree(ROOT/name,work/name)
 subprocess.run([sys.executable,'-B',str(work/'prepare_driver_probe.py')],check=True)
 result=dict(status='pass',base=base,prerequisite_head=manifest['prerequisite_head'],source_files_checked=sum(len(v) for v in manifest['files'].values()),normalization=manifest['normalization'],patches={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['double_accumulation_prerequisite.patch','worker_accumulation.patch']})
 (work/'prepare_receipt.json').write_text(json.dumps(result,indent=2)+'\n')
 print('[PREPARED]',result['source_files_checked'],'source files')
if __name__=='__main__':main()