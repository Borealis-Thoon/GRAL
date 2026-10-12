"""Fetch pinned public GRAL sources and reconstruct the reviewed compositions."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, io, json, shutil, subprocess, tarfile
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def git(args,cwd,timeout=180):
    p=subprocess.run(["git","-c","credential.helper=","-c","core.autocrlf=false","-c","core.eol=lf",*args],cwd=cwd,capture_output=True,timeout=timeout)
    if p.returncode: raise RuntimeError(p.stderr.decode("utf-8",errors="replace"))
    return p.stdout
def extract(repo,commit,dest):
    dest.mkdir(parents=True)
    data=git(["archive","--format=tar",commit],repo)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            p=PurePosixPath(member.name)
            if not member.isfile() or p.is_absolute() or ".." in p.parts: continue
            if not (member.name.startswith("src/") or member.name in ("License.md","Contributing.md")):continue
            target=dest.joinpath(*p.parts);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--work-root",type=Path,required=True)
    parser.add_argument("--include-components",action="store_true")
    args=parser.parse_args();evidence=args.evidence_root.resolve();work=args.work_root.resolve()
    if work.exists():raise FileExistsError("Use a new --work-root")
    provenance=json.loads((evidence/"integration/provenance.json").read_text(encoding="utf-8"))
    expected=json.loads((evidence/"integration/source_manifest.json").read_text(encoding="utf-8"))
    for item in provenance["patches"].values():
        if sha(evidence/item["path"])!=item["sha256"]:raise AssertionError("Patch SHA-256 differs")
    work.mkdir(parents=True);repo=work/"public_upstream";repo.mkdir()
    git(["init","--quiet"],repo)
    git(["fetch","--no-tags","--depth","1",provenance["upstream_repository"],provenance["baseline_commit"]],repo)
    baseline=git(["rev-parse","FETCH_HEAD"],repo).decode().strip()
    if baseline!=provenance["baseline_commit"]:raise AssertionError("Public baseline commit differs")
    package=work/"package";package.mkdir()
    shutil.copytree(evidence/"integration/inputs",package/"inputs")
    shutil.copytree(evidence/"reproduce",package/"reproduce")
    receipt={"status":"pass","baseline_commit":baseline,"public_fetch":True,"variants":{},"components":{}}
    for name,item in provenance["patches"].items():
        dest=package/"source"/name
        extract(repo,baseline,dest)
        # Keep patch application inside this snapshot even when work-root is in another Git checkout.
        git(["init","--quiet"],dest)
        for source in (dest/"src").iterdir():
            if source.is_file():source.write_bytes(source.read_bytes().replace(b"\r\n",b"\n"))
        patch=(evidence/item["path"]).resolve()
        git(["apply","--check",str(patch)],dest)
        git(["apply",str(patch)],dest)
        for source in (dest/"src").iterdir():
            if source.is_file() and sha(source)!=expected["sources"][name][source.name]:
                original_lf=source.read_bytes().replace(b"\r\n",b"\n")
                crlf=original_lf.replace(b"\n",b"\r\n")
                if hashlib.sha256(crlf).hexdigest()!=expected["sources"][name][source.name]:raise AssertionError("Source content differs: "+source.name)
                source.write_bytes(crlf)
        actual={p.name:sha(p) for p in sorted((dest/"src").iterdir()) if p.is_file()}
        if actual!=expected["sources"][name] or len(actual)!=85:raise AssertionError("Source85 SHA-256 differs: "+name)
        receipt["variants"][name]={"files":85,"mismatches":0,"sha256":actual,"patch_sha256":sha(patch)}
    if args.include_components:
        numbers=[59,60,62,63,66,67,68,69]
        commits=[provenance["source_heads"][str(n)]["head"] for n in numbers]
        git(["fetch","--no-tags","--depth","1",provenance["fork_repository"],*commits],repo)
        for n,commit in zip(numbers,commits):
            dest=package/"source_components"/("pr"+str(n));extract(repo,commit,dest)
            actual={p.relative_to(dest).as_posix():sha(p) for p in sorted((dest/"src").iterdir()) if p.is_file()}
            if len(actual)!=85:raise AssertionError("Component source file count differs")
            receipt["components"][str(n)]={"commit":commit,"source_files":actual}
    (work/"source_reconstruction.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print("[PASS] public source reconstruction: 85 files per composition")
if __name__=="__main__":main()
