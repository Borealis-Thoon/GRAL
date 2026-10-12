"""Prepare test-only call/hit counters for the final vertical-search DLL; never publish instrumented source."""
import argparse,json,hashlib,shutil,re
from pathlib import Path
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+"\n",encoding="utf-8")
def main():
 p=argparse.ArgumentParser();p.add_argument("--package-root",type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument("--summarize",type=Path);a=p.parse_args();r=a.package_root
 if a.summarize:
  summary=json.loads((a.summarize/"qa/main_validation_summary.json").read_text(encoding="utf-8"));assert summary["status"]=="pass";rows=[]
  for d in sorted((a.summarize/"virtual_runs").iterdir()):
   if "opt1_vertical_profile" not in d.name:continue
   text=(d/"console.log").read_text(encoding="utf-8")
   records=re.findall(r"\[OPT1_PROFILE\] weather=(\d+) nkk=(\d+) calls=(\d+) hits=(\d+)",text)
   assert records
   for weather,nkk,calls,hits in records:
    calls=int(calls);hits=int(hits);assert 0<=hits<=calls
    rows.append(dict(run=d.name,weather=int(weather),nkk=int(nkk),calls=calls,hits=hits,hit_ratio=hits/calls if calls else None))
  save(r/"qa/opt1_actual_cache_hits.json",dict(status="pass",instrumented_main_runs=4,total_main_runs=summary["main_runs"],payload_pairs_equal=summary["compared_payload_pairs"],records=rows,calls=sum(x["calls"] for x in rows),hits=sum(x["hits"] for x in rows),limits=["Test-only counters alter timing; no runtime speed claim.","These are two synthetic terrain projects, not a production workload distribution.","Cache hit fractions do not prove overall model speedup."]))
  print("[PROFILE] "+str(len(rows))+" weather records");return
 src=r/"source/opt1_vertical";dst=r/"source/opt1_vertical_profile";assert not dst.exists();(dst/"src").mkdir(parents=True)
 for f in (src/"src").iterdir():
  if f.is_file():shutil.copy2(f,dst/"src"/f.name)
 f=dst/"src/Intwind.cs";text=f.read_text(encoding="utf-8-sig")
 old="        internal struct WindSearch";assert text.count(old)==1;text=text.replace(old,"        internal static long ProfileCalls;\n        internal static long ProfileHits;\n\n"+old)
 old="            if (search.Levels != Program.HOKART || search.Count != Program.NKK)";assert text.count(old)==1;text=text.replace(old,"            System.Threading.Interlocked.Increment(ref ProfileCalls);\n"+old)
 old="            if (search.Index > 0 && float.IsFinite(Height) && Height == search.Height)\n            {\n                return search.Index;";assert text.count(old)==1
 text=text.replace(old,old.replace("                return search.Index;","                System.Threading.Interlocked.Increment(ref ProfileHits);\n                return search.Index;"));f.write_text(text,encoding="utf-8")
 f=dst/"src/Program.cs";text=f.read_text(encoding="utf-8-sig");old="                    ParallelParticleDriver(1, NTEILMAX + 1);";assert text.count(old)==1
 add='\n                    Console.WriteLine("[OPT1_PROFILE] weather=" + IWET + " nkk=" + NKK + " calls=" + System.Threading.Interlocked.Exchange(ref Zeitschleife.ProfileCalls, 0) + " hits=" + System.Threading.Interlocked.Exchange(ref Zeitschleife.ProfileHits, 0));'
 f.write_text(text.replace(old,old+add),encoding="utf-8")
 save(r/"qa/opt1_profile_scope.json",{"opt1_vertical_profile":["src/Intwind.cs","src/Program.cs","src/Zeitschleife.cs","src/Zeitschleife_nonsteadystate.cs"]})
 save(r/"qa/opt1_profile_source_manifest.json",{"status":"prepared_test_only","source_files":{x.name:sha(x) for x in (dst/"src").iterdir() if x.is_file()},"final_source_sha256":{x.name:sha(x) for x in (src/"src").iterdir() if x.is_file()},"public_source_unchanged":True})
 print("[PREPARED] test-only counters")
if __name__=="__main__":main()

