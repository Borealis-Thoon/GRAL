from pathlib import Path
import argparse,hashlib,io,json,re,subprocess,tarfile
ROOT=Path(__file__).resolve().parent
BASE='891225b2f9dbbcda7f5ef6e9ef6db65e64845108'
VARIANTS={'current':[], 'reviewed':['pr64','pr66','pr67','pr68','pr69','pr70'], 'combined':['pr64','pr66','pr67','pr68','pr69','pr70','pr71','met','worker']}

def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
def sha(b):return hashlib.sha256(b).hexdigest()
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args])
def apply(text,patch):
    lines=patch.splitlines(keepends=True);i=0;path=None;events=[]
    while i<len(lines):
        line=lines[i]
        if line.startswith('+++ '):
            path=line[4:].strip();path=path[2:] if path.startswith('b/') else path;i+=1;continue
        if not line.startswith('@@ '):i+=1;continue
        header=line.rstrip();i+=1;body=[]
        while i<len(lines) and not lines[i].startswith(('@@ ','diff --git ','--- ')):
            if lines[i][:1] in ' +-':body.append(lines[i])
            elif not lines[i].startswith('\\'):break
            i+=1
        old=''.join(s[1:] for s in body if s[0]!='+');new=''.join(s[1:] for s in body if s[0]!='-')
        content=text.get(path,'');left=0;right=0
        if not old:
            assert path not in text,('new exists',path)
            text[path]=new;events.append(dict(file=path,hunk=header,context_trim=[0,0],mode='new'));continue
        if content.count(old)!=1:
            lead=next((n for n,s in enumerate(body) if s[0]!=' '),len(body))
            trail=next((n for n,s in enumerate(reversed(body)) if s[0]!=' '),len(body))
            found=[]
            for removed in range(1,lead+trail+1):
                for l in range(lead+1):
                    r=removed-l
                    if not 0<=r<=trail:continue
                    subset=body[l:len(body)-r if r else len(body)]
                    o=''.join(s[1:] for s in subset if s[0]!='+');n=''.join(s[1:] for s in subset if s[0]!='-')
                    if o and content.count(o)==1:found.append((l,r,o,n))
                if found:break
            assert found,('no unique context',path,header,old[:120])
            results={content.replace(o,n,1) for l,r,o,n in found};assert len(results)==1,('ambiguous trimmed context',path,header)
            left,right,old,new=found[0]
        text[path]=content.replace(old,new,1);events.append(dict(file=path,hunk=header,context_trim=[left,right],mode='unique context'))
    return events

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=ROOT/'objects');a=p.parse_args()
    tar=tarfile.open(fileobj=io.BytesIO(git(a.repo,'archive',BASE,'src')))
    original={m.name:norm(tar.extractfile(m).read()) for m in tar.getmembers() if m.isfile()}
    patchmeta=json.loads((ROOT/'patches/topics.json').read_text());all_events={};hashes={}
    for v,topics in VARIANTS.items():
        data=original.copy();events=[]
        for topic in topics:
            b=(ROOT/'patches'/patchmeta[topic]['file']).read_bytes();assert sha(b)==patchmeta[topic]['sha256'];events.extend(dict(topic=topic,**e) for e in apply(data,norm(b)))
        for path,s in data.items():
            out=ROOT/'sources'/v/path;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(s.encode('utf-8'))
        hashes[v]={path:sha(s.encode('utf-8')) for path,s in sorted(data.items())};all_events[v]=events
    manifest=dict(base=BASE,normalization='UTF-8 without BOM and LF',variants=VARIANTS,topics=patchmeta,hashes=hashes,hunks=all_events)
    dest=ROOT/'source_manifest.json'
    if dest.exists():assert json.loads(dest.read_text())==manifest,'source reconstruction differs'
    else:dest.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('[SOURCE]',sum(map(len,hashes.values())),'hashes')
    for v,events in all_events.items():
        for e in events:
            if any(e['context_trim']):print('[CONTEXT]',v,e)
if __name__=='__main__':main()
