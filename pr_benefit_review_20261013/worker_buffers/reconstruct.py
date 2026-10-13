"""Reconstruct #64 and #64+#73 on the recorded V2701 base from a local Git repository."""
from pathlib import Path
import argparse, hashlib, io, json, subprocess, tarfile
import apply_patch_helper as h

ROOT=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,required=True);args=parser.parse_args()
    manifest=json.loads((ROOT/'source_manifest.json').read_text())
    archive=subprocess.check_output(['git','-C',str(args.repo),'archive',manifest['base'],'src'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        original={m.name:h.norm(tar.extractfile(m).read()) for m in tar.getmembers() if m.isfile()}
    for variant,topics in [('before',['pr64']),('after',['pr64','worker'])]:
        data=original.copy()
        for topic in topics:
            meta=manifest['topics'][topic];patch=(ROOT/'patches'/meta['file']).read_bytes()
            assert hashlib.sha256(patch).hexdigest()==meta['sha256']
            h.apply(data,h.norm(patch))
        hashes={p:hashlib.sha256(s.encode()).hexdigest() for p,s in data.items()}
        assert hashes==manifest['hashes'][variant],variant
        for path,text in data.items():
            p=ROOT/'sources'/variant/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(text.encode())
        print('[SOURCE]',variant,len(hashes),'hashes verified')
if __name__=='__main__':main()
