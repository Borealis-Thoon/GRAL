import difflib,json
from pathlib import Path
r=Path(__file__).resolve().parents[1]
base=r/"source/warning_free_baseline/src";result={}
for variant in ("nan_guard_state","nan_guard_storage","opt1_stack","opt1_vertical"):
 rows=[];patch=[]
 for p in sorted(base.iterdir()):
  if not p.is_file():continue
  q=r/"source"/variant/"src"/p.name
  old=p.read_text(encoding="utf-8-sig").splitlines();new=q.read_text(encoding="utf-8-sig").splitlines()
  if old==new:continue
  d=list(difflib.unified_diff(old,new,fromfile="a/src/"+p.name,tofile="b/src/"+p.name,lineterm=""))
  added=[l[1:] for l in d if l.startswith("+") and not l.startswith("+++")];removed=[l[1:] for l in d if l.startswith("-") and not l.startswith("---")]
  rows.append(dict(file="src/"+p.name,added_lines=len(added),deleted_lines=len(removed),changed_body_characters=sum(map(len,added+removed))))
  patch.extend(d)
 result[variant]=dict(files=rows,file_count=len(rows),added_lines=sum(x["added_lines"] for x in rows),deleted_lines=sum(x["deleted_lines"] for x in rows),changed_body_characters=sum(x["changed_body_characters"] for x in rows),lf_unified_patch_characters=len("\n".join(patch)+"\n"),definition="Added and removed line text, including indentation; excludes diff markers and all CR/LF characters.")
(r/"qa/topic_diff_character_counts.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:{n:v[n] for n in ("file_count","added_lines","deleted_lines","changed_body_characters","lf_unified_patch_characters")} for k,v in result.items()}))

