"""Merge independent topic edits in baseline line coordinates, preserving unchanged bytes."""
from __future__ import annotations
import argparse,difflib,hashlib,json,shutil
from pathlib import Path

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
def main():
    a=argparse.ArgumentParser();a.add_argument("--package-root",type=Path,default=Path(__file__).resolve().parents[1]);a.add_argument("--topics",nargs="+",required=True);a.add_argument("--execute",action="store_true");args=a.parse_args()
    root=args.package_root.resolve();base=root/"source/warning_free_baseline";target=root/"source/combined_candidate"
    baseline=json.loads((root/"inputs/baseline_source_manifest.json").read_text(encoding="utf-8-sig"))["source_files"]["warning_free_baseline"]
    actual={p.relative_to(base).as_posix():sha(p) for p in (base/"src").iterdir() if p.is_file()}
    assert actual==baseline and len(actual)==85
    edits={};topic_hashes={}
    for topic_order,topic in enumerate(args.topics):
        folder=root/"source"/topic;hashes={p.relative_to(folder).as_posix():sha(p) for p in (folder/"src").iterdir() if p.is_file()}
        assert set(hashes)==set(actual);topic_hashes[topic]=hashes
        for name in actual:
            if actual[name]==hashes[name]: continue
            old=(base/name).read_text(encoding="utf-8-sig").splitlines();new=(folder/name).read_text(encoding="utf-8-sig").splitlines()
            for tag,i,j,u,v in difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes():
                if tag!="equal": edits.setdefault(name,[]).append((i,j,new[u:v],topic_order,topic))
    merged={};metadata={}
    for name,items in edits.items():
        items.sort(key=lambda x:(x[0],x[1],x[3]))
        for idx,item in enumerate(items):
            for other in items[idx+1:]:
                i,j,_,_,_=item;k,l,_,_,_=other
                if j>i and l>k and max(i,k)<min(j,l): raise AssertionError("Overlapping replacements: "+name+repr(((item[0],item[1],item[4]),(other[0],other[1],other[4]))))
                if j>i and k==l and i<k<j: raise AssertionError("Insertion inside replacement: "+name)
        old=(base/name).read_text(encoding="utf-8-sig").splitlines();result=[];cursor=0
        for i,j,new,order,topic in items:
            if i<cursor: raise AssertionError("Unexpected edit ordering: "+name)
            result.extend(old[cursor:i]);result.extend(new);cursor=j
        result.extend(old[cursor:]);raw=(base/name).read_bytes();eol="\r\n" if b"\r\n" in raw else "\n";bom=b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"";merged[name]=bom+(eol.join(result)+(eol if raw.endswith(b"\n") else "")).encode("utf-8")
        metadata[name]=[dict(base_start=i,base_end=j,new_lines=len(new),topic=topic) for i,j,new,order,topic in items]
    plan=dict(status="prepared_not_executed",topics=args.topics,baseline_files=85,changed_files=sorted(merged),edits=metadata,topic_source_sha256=topic_hashes)
    save(root/"qa/combined_integration_plan.json",plan)
    if not args.execute:print("[PREPARED] "+str(len(merged))+" files");return
    if target.exists():raise FileExistsError("Fresh combined_candidate is required")
    (target/"src").mkdir(parents=True)
    for name in actual:
        dest=target/name;dest.write_bytes(merged[name] if name in merged else (base/name).read_bytes())
    hashes={p.relative_to(target).as_posix():sha(p) for p in (target/"src").iterdir() if p.is_file()}
    assert len(hashes)==85 and all(hashes[k]==actual[k] for k in actual if k not in merged)
    # Two independent diagnostics must survive the shared Program.cs insertion.
    text=(target/"src/Program.cs").read_text(encoding="utf-8-sig")
    assert "Rejected {nonFiniteParticleCount}" in text or "non-finite particle states" in text
    assert "non-finite residual writes" in text
    plan.update(status="pass",combined_source_sha256=hashes,unchanged_files_verified=85-len(merged))
    save(root/"qa/combined_integration_manifest.json",plan);save(root/"qa/combined_scope.json",{"combined_candidate":sorted(merged)})
    print("[MERGED] 85 files; "+str(len(merged))+" changed")
if __name__=="__main__":main()

