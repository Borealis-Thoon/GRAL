"""Reconstruct six pinned source variants from upstream and the included patches."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--repository',default='https://github.com/GralDispersionModel/GRAL.git')
    args=parser.parse_args();evidence=args.evidence.resolve();dest=args.destination.resolve()
    if dest.exists():raise FileExistsError('Use a new destination')
    spec=json.loads((evidence/'source_manifests/variants.json').read_text(encoding='utf-8'))
    dest.mkdir(parents=True);repository=dest/'upstream_git'
    subprocess.run(['git','clone','--no-checkout','--no-hardlinks',args.repository,str(repository)],check=True,timeout=180)
    base=spec['baseline_commit']
    check=subprocess.run(['git','-C',str(repository),'cat-file','-e',base+'^{commit}'],capture_output=True)
    if check.returncode:subprocess.run(['git','-C',str(repository),'fetch','origin',base],check=True,timeout=180)
    records={}
    for variant,meta in spec['variants'].items():
        directory=dest/'source'/variant;directory.mkdir(parents=True)
        for relative in meta['source_files']:
            path=Path(relative)
            if path.is_absolute() or '..' in path.parts or path.parts[0]!='src':raise ValueError('Unexpected source path')
            data=subprocess.check_output(['git','-C',str(repository),'show',base+':'+relative],timeout=30).replace(b'\r\n',b'\n')
            output=directory/path;output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
        subprocess.run(['git','init','--quiet',str(directory)],check=True,timeout=30)
        if meta.get('patch'):
            subprocess.run(['git','-C',str(directory),'apply','--check',str(evidence/meta['patch'])],check=True,timeout=30)
            subprocess.run(['git','-C',str(directory),'apply',str(evidence/meta['patch'])],check=True,timeout=30)
        hashes={}
        for relative,expected in meta['source_files'].items():
            path=directory/relative;data=path.read_bytes().replace(b'\r\n',b'\n');path.write_bytes(data)
            digest=hashlib.sha256(data).hexdigest()
            if digest!=expected:raise AssertionError('Reconstructed source differs: '+variant+'/'+relative)
            hashes[relative]=digest
        records[variant]={'status':'pass','files_verified':len(hashes),'source_files':hashes}
    for folder in ['inputs','reproduce']:
        shutil.copytree(evidence/folder,dest/folder)
    (dest/'qa').mkdir()
    (dest/'qa/source_reconstruction.json').write_text(json.dumps({'status':'pass','baseline_commit':base,'variants':records},indent=2),encoding='utf-8')
    print('[PASS] six variants; 85 SHA-256 matches each')
if __name__=='__main__':main()
