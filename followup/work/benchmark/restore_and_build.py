"""Restore the four locked GRAL variants in a fresh evidence directory."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess
ROOT=Path(__file__).resolve().parents[2]
BASE="e3336e8e901d5f49f20fa3a954a08463517bf61d"
DEV="7d4366a6ac16f58a5d28f166e272e59247362630"

def run(args,cwd=None,timeout=120):
    result=subprocess.run(list(map(str,args)),cwd=cwd,capture_output=True,timeout=timeout)
    text=(result.stdout+result.stderr).decode("utf-8",errors="replace")
    if result.returncode: raise RuntimeError(text)
    return text

def main():
    p=argparse.ArgumentParser();p.add_argument("--git",default="git");p.add_argument("--dotnet",default=r"C:\Program Files\dotnet\dotnet.exe");a=p.parse_args()
    assert not (ROOT/"build").exists(), "Use a fresh evidence directory."
    dest=ROOT/"work"/"restored";dest.mkdir(parents=True,exist_ok=False)
    repo=dest/"upstream"
    run([a.git,"clone","--no-checkout","--single-branch","--branch","ConcurrentDictionary","https://github.com/GralDispersionModel/GRAL.git",repo])
    for sha in [BASE,DEV]: run([a.git,"fetch","origin",sha],repo)
    source_lock=json.loads((ROOT/"qa"/"source_lock.json").read_text())
    outputs=[]
    for variant in ["float","double","dictionary","dictionary_fixed"]:
        target=dest/variant
        run([a.git,"worktree","add","--detach",target,DEV if variant.startswith("dictionary") else BASE],repo)
        patch={"double":"pr64_on_current.patch","dictionary_fixed":"dictionary_fixed.patch"}.get(variant)
        if patch: run([a.git,"apply",ROOT/"qa"/patch],target)
        expected=(json.loads((ROOT/"qa"/"dictionary_fixed_source_lock.json").read_text())["tracked_source_sha256"] if variant=="dictionary_fixed" else source_lock["variants"][variant]["sources"])
        assert all(hashlib.sha256((target/k).read_bytes()).hexdigest()==v for k,v in expected.items()),variant
        cmd=[a.dotnet,"build",target/"src"/"GRAL.csproj","-c","Release","--nologo","--disable-build-servers","-o",ROOT/"build"/variant]
        if variant!="dictionary": cmd.append("/p:TreatWarningsAsErrors=true")
        log=run(cmd,target)
        (dest/(variant+".build.log")).write_text(log,encoding="utf-8")
        outputs.append({"variant":variant,"sha256":hashlib.sha256((ROOT/"build"/variant/"GRAL.dll").read_bytes()).hexdigest()})
        print("[BUILD]",variant,flush=True)
    (dest/"builds.json").write_text(json.dumps(outputs,indent=2)+"\n")
if __name__=="__main__":main()
