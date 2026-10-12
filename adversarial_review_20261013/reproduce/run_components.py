"""Rebuild the pinned component sources and rerun the small review fixtures."""
from pathlib import Path
import argparse,json,os,re,shutil,time
from validate_main import process
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root",type=Path,required=True)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--dotnet",default="dotnet")
    args=parser.parse_args();package=args.package_root.resolve();run=args.run_dir.resolve()
    dotnet=Path(shutil.which(args.dotnet) or args.dotnet).resolve()
    if not dotnet.is_file():raise FileNotFoundError("Use a verified .NET executable")
    if run.exists():raise FileExistsError("Use a new --run-dir")
    numbers=[59,60,62,63,66,67,68,69]
    for n in numbers:
        if not (package/f"source_components/pr{n}/src/GRAL.csproj").is_file():raise FileNotFoundError("Prepare with --include-components first")
    run.mkdir(parents=True)
    for name in ("logs","qa","tmp","cache"): (run/name).mkdir()
    shutil.copytree(package/"source_components",run/"source")
    for name in ("nan_opt","residual_reference","residual_seed"):shutil.copytree(package/"reproduce"/name,run/name)
    env=os.environ.copy();env.update(DOTNET_CLI_HOME=str(run/"cache/dotnet"),NUGET_PACKAGES=str(run/"cache/nuget"),TEMP=str(run/"tmp"),TMP=str(run/"tmp"),DOTNET_NOLOGO="1",DOTNET_CLI_UI_LANGUAGE="en")
    started=time.monotonic();pids=[];builds={}
    def execute(args,label,timeout=180):
        remaining=900-(time.monotonic()-started)
        if remaining<=0:raise TimeoutError("The 15-minute component limit expired")
        code,out,err=process([str(dotnet),*map(str,args)],run,env,min(timeout,remaining),pids)
        (run/"logs"/(label+".log")).write_text(out+err,encoding="utf-8")
        if code:raise RuntimeError(label+" failed; see its log")
        return out+err
    def build(project,label):
        log=execute(["build",project,"-c","Release","-t:Rebuild","-v:minimal","--nologo","/p:TreatWarningsAsErrors=true"],label)
        warnings=re.search(r"(\d+) Warning\(s\)",log);errors=re.search(r"(\d+) Error\(s\)",log)
        if not warnings or not errors or int(warnings[1]) or int(errors[1]):raise AssertionError("Strict build result missing or nonzero: "+label)
        builds[label]={"warnings":0,"errors":0}
    for n in numbers:build(run/f"source/pr{n}/src/GRAL.csproj",f"pr{n}_build")
    for folder,project in [("nan_opt","Review.csproj"),("residual_reference","DraftChecks.csproj"),("residual_seed","SeedChecks.csproj")]:build(run/folder/project,folder+"_build")
    dll=lambda n:run/f"source/pr{n}/src/bin/Release/net10.0/GRAL.dll"
    execute([run/"nan_opt/bin/Release/net10.0/Review.dll",*[dll(n) for n in [66,67,68,69,59]],run/"qa/nan_opt.json"],"nan_opt")
    for n in [62,63]:execute([run/"residual_reference/bin/Release/net10.0/DraftChecks.dll",dll(n),run/f"qa/pr{n}.json"],f"pr{n}")
    execute([run/"residual_seed/bin/Release/net10.0/SeedChecks.dll",dll(60),run/"qa/seed"],"seed")
    results={p.name:json.loads(p.read_text(encoding="utf-8")) for p in (run/"qa").glob("*.json")}
    if any(r.get("status")!="pass" for r in results.values()):raise AssertionError("A component result did not pass")
    seed=json.loads((run/"qa/seed/candidate_seed_checks.json").read_text(encoding="utf-8"))
    if seed.get("status")!="pass":raise AssertionError("Seed fixture did not pass")
    (run/"qa/reproduction_summary.json").write_text(json.dumps({"status":"pass","strict_builds":builds,"results":results,"seed":seed,"scope":"Component methods only; no Main execution","elapsed_s":time.monotonic()-started},indent=2),encoding="utf-8")
    (run/"qa/process_ownership.json").write_text(json.dumps(pids,indent=2),encoding="utf-8")
    print("[PASS] component fixtures")
if __name__=="__main__":main()
