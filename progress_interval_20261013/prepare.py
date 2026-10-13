from pathlib import Path
import argparse,subprocess,shutil
p=argparse.ArgumentParser();p.add_argument('--source-repo',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True);a=p.parse_args()
source=a.source_repo.resolve();work=a.work_dir.resolve();bundle=Path(__file__).resolve().parent
if work.exists():raise SystemExit('Choose a new work directory')
work.mkdir(parents=True)
subprocess.run(['git','clone','--shared','--no-checkout',str(source),str(work/'repo')],check=True)
subprocess.run(['git','-C',str(work/'repo'),'checkout','--detach','891225b2f9dbbcda7f5ef6e9ef6db65e64845108'],check=True)
shutil.copy2(bundle/'reproduce.py',work/'reproduce.py');shutil.copy2(bundle/'source_manifest.json',work/'source_manifest_reference.json')
print('Prepared '+str(work))
