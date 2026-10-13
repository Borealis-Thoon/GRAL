from pathlib import Path
import argparse, subprocess, zipfile, io, shutil, hashlib, json

BASE='891225b2f9dbbcda7f5ef6e9ef6db65e64845108'
p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parent; work=a.work_dir.resolve();work.mkdir(parents=True,exist_ok=False)
base=work/'source/baseline';base.mkdir(parents=True)
with zipfile.ZipFile(io.BytesIO(subprocess.check_output(['git','-C',str(a.repo),'archive','--format=zip',BASE,'src']))) as z:z.extractall(base)
for v in ['pr68','pr69','pr72']:
 dest=work/'source'/v;shutil.copytree(base,dest)
 subprocess.run(['git','apply','--ignore-space-change',str(root/(v+'.patch'))],cwd=dest,check=True)
shutil.copytree(root/'template',work/'template');shutil.copy2(root/'field_support.py',work/'field_support.py')
files={str(f.relative_to(work)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((work/'source').rglob('*')) if f.is_file()}
(work/'source_manifest.json').write_text(json.dumps({'base':BASE,'files':files},indent=2)+'\n',encoding='utf-8')
print('[PREPARED]',len(files))
