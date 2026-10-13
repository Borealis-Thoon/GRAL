from pathlib import Path
import argparse,subprocess,io,zipfile,json,hashlib,shutil
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);args=ap.parse_args()
manifest=json.loads((ROOT/'source_manifest.json').read_text());base=manifest['base']
for variant in ['f64','parallel']:
 dest=ROOT/'sources'/variant
 if dest.exists():raise FileExistsError(dest)
 dest.mkdir(parents=True)
 raw=subprocess.check_output(['git','-C',str(args.repo),'archive','--format=zip',base,'src'])
 with zipfile.ZipFile(io.BytesIO(raw)) as z:z.extractall(dest)
 subprocess.run(['git','apply',str(ROOT/'patches/f64.patch')],cwd=dest,check=True)
 if variant=='parallel':shutil.copy2(ROOT/'candidate/ProgramFunctions.cs',dest/'src/ProgramFunctions.cs')
 actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((dest/'src').iterdir()) if p.is_file()}
 assert actual==manifest['hashes'][variant],variant+' source hash mismatch'
 print('[SOURCE]',variant,len(actual))
