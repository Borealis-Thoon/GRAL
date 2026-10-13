from pathlib import Path
import argparse,subprocess,io,zipfile,hashlib,json,shutil
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,default=ROOT/'repo');args=parser.parse_args();REPO=args.repo.resolve()
BASE='891225b2f9dbbcda7f5ef6e9ef6db65e64845108'
TOPICS={'f64':'003b00e60ebe9f0c5acc7377ed155c3271b4d8c9','o68':'b4ffec5e2ab55d3ec3717ed37d04938837e00120','o69':'7c23fe92803a019c1535af7f02fcc6b2e940f2ee'}
VARIANTS={'baseline':[],'f64':['f64'],'opt68_69':['o68','o69'],'f64_opt68_69':['f64','o68','o69']}
def run(*a,**kw):return subprocess.check_output(a,**kw)
(ROOT/'patches').mkdir(exist_ok=True)
for n,h in TOPICS.items():
 patch=ROOT/'patches'/f'{n}.patch'
 if not patch.exists():patch.write_bytes(run('git','-C',str(REPO),'diff',h+'^',h,'--','src'))
manifest={}
for name,patches in VARIANTS.items():
 dest=ROOT/'sources'/name
 if dest.exists():raise FileExistsError(dest)
 dest.mkdir(parents=True)
 raw=run('git','-C',str(REPO),'archive','--format=zip',BASE,'src')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:z.extractall(dest)
 for patch in patches:
  subprocess.run(['git','apply','--unsafe-paths',str(ROOT/'patches'/f'{patch}.patch')],cwd=dest,check=True)
 manifest[name]={p.relative_to(dest).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((dest/'src').iterdir()) if p.is_file()}
if not (ROOT/'template').is_dir():raise FileNotFoundError('Bundled synthetic template directory required')
if (ROOT/'source_manifest.json').exists():
 expected=json.loads((ROOT/'source_manifest.json').read_text(encoding='utf-8'))
 assert expected['base']==BASE and expected['topics']==TOPICS and expected['hashes']==manifest,'Reconstructed source manifest differs'
(ROOT/'source_manifest.json').write_text(json.dumps({'base':BASE,'topics':TOPICS,'variants':VARIANTS,'hashes':manifest},indent=2)+'\n',encoding='utf-8')
print('prepared 4 variants')
