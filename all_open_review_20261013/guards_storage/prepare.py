from pathlib import Path
import argparse,subprocess,zipfile,io,shutil
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--work-dir',type=Path,required=True);a=ap.parse_args()
root=Path(__file__).resolve().parent;work=a.work_dir.resolve();work.mkdir(parents=True,exist_ok=False)
base=work/'source/baseline';base.mkdir(parents=True)
data=subprocess.check_output(['git','-C',str(a.repo),'archive','--format=zip','891225b2f9dbbcda7f5ef6e9ef6db65e64845108','src'])
with zipfile.ZipFile(io.BytesIO(data)) as archive:archive.extractall(base)
for name in ['current','height_first']:
 dest=work/'source'/name;shutil.copytree(base,dest)
 subprocess.run(['git','apply','--ignore-space-change',str(root/'pr69_functional.patch')],cwd=dest,check=True)
 if name=='height_first':subprocess.run(['git','apply','--ignore-space-change',str(root/'height_first_alternative.patch')],cwd=dest,check=True)
shutil.copy2(root/'field_support.py',work/'field_support.py');shutil.copytree(root/'template',work/'template')
print('[PREPARED] baseline current height_first')
