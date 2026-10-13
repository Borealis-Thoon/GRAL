from pathlib import Path
import argparse, subprocess, shutil, os, json, re, hashlib, time, zipfile, struct, math, csv
ROOT=Path(__file__).resolve().parent
BASE='891225b2f9dbbcda7f5ef6e9ef6db65e64845108'
DOTNET=os.environ.get('DOTNET_EXE',r'C:\Program Files\dotnet\dotnet.exe')
PYTHON=__import__('sys').executable

def save(p,data):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def norm(p):return p.read_text(encoding='utf-8-sig').replace('\r\n','\n').encode()
def run(cmd,cwd,timeout=150):
 p=subprocess.Popen(list(map(str,cmd)),cwd=cwd,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 try:out,err=p.communicate(timeout=timeout)
 except subprocess.TimeoutExpired:
  subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=10);raise
 return p.returncode,(out+err).decode('utf-8',errors='replace')
def build(src,tag,probe=False):
 cmd=[DOTNET,'build',src/'GRAL.csproj','-c','Release','-t:Rebuild','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true']
 if probe:cmd+=['/p:StartupObject=GRAL_2001.ProgressProbe']
 code,log=run(cmd,src);(ROOT/'logs'/f'build_{tag}.log').write_text(log,encoding='utf-8')
 assert code==0 and '0 Warning(s)' in log and '0 Error(s)' in log,log
 print('[BUILD]',tag,flush=True)
 return src/'bin/Release/net10.0/GRAL.dll'

def prepare():
 repo=ROOT/'repo'; src=repo/'src'
 p=src/'ProgramFunctions.cs'; s=p.read_text(encoding='utf-8-sig'); old='int percent10 = (int)(Program.NTEILMAX * 0.1F);';new='int percent10 = Math.Max(1, (int)(Program.NTEILMAX * 0.1F));'
 assert s.count(old)==1;s=s.replace(old,new);p.write_bytes(s.replace('\n','\r\n').encode('utf-8'))
 (ROOT/'baseline').mkdir()
 files=subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','--name-only',BASE,'src']).decode().splitlines()
 for name in files:
  dest=ROOT/'baseline'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(subprocess.check_output(['git','-C',str(repo),'show',BASE+':'+name]))
 patch=subprocess.check_output(['git','-C',str(repo),'diff','--','src/ProgramFunctions.cs']);(ROOT/'progress_interval.patch').write_bytes(patch)
 save(ROOT/'source_manifest.json',{v:{p.relative_to(root).as_posix():hashlib.sha256(norm(p)).hexdigest() for p in root.rglob('*') if p.is_file()} for v,root in [('baseline',ROOT/'baseline/src'),('candidate',src)]})

PROBE=r'''using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Text.Json;
namespace GRAL_2001 {
public class ProgressProbe {
 public static int[] Visits = new int[1];
 public static void Visit(int index) { Interlocked.Increment(ref Visits[index]); }
 public static void Main(string[] args) {
  var output=Console.Out;Console.SetOut(TextWriter.Null);
  var records=new List<object>();
  var method=typeof(Program).GetMethod("ParallelParticleDriver",BindingFlags.NonPublic|BindingFlags.Static);
  foreach(bool fixedSeed in new[]{true,false}) foreach(int total in new[]{0,1,2,3,4,5,6,7,8,9,10,11,19,20,100,3000}) foreach(int workers in new[]{1,4,24}) for(int repeat=0;repeat<3;repeat++) {
   Program.NTEILMAX=total;Program.UseFixedRndSeedVal=fixedSeed;Program.pOptions.MaxDegreeOfParallelism=workers;Program.CancelToken=new CancellationTokenSource();Program.ISTATIONAER=Consts.StationaryMode;Program.IWETstartstop=new Program.IWetSpan(2,3);
   Visits=new int[total+1];method.Invoke(null,new object[]{1,total+1});
   int visited=0,duplicates=0;for(int i=1;i<=total;i++){if(Visits[i]>0)visited++;if(Visits[i]>1)duplicates++;}
   records.Add(new{fixed_seed=fixedSeed,total,workers,repeat,visited,duplicates,missing=total-visited,exactly_once=visited==total&&duplicates==0,visits=Visits});
  }
  File.WriteAllText(args[0],JsonSerializer.Serialize(records,new JsonSerializerOptions{WriteIndented=true}));Console.SetOut(output);Console.WriteLine("[PROBE] "+records.Count);
 }
}}
'''

def probes():
 records={}
 for tag in ['baseline','candidate']:
  src=ROOT/('baseline/src' if tag=='baseline' else 'repo/src');dst=ROOT/'probe'/tag/'src';shutil.copytree(src,dst,ignore=shutil.ignore_patterns('bin','obj'),dirs_exist_ok=True)
  p=dst/'ProgramFunctions.cs';s=p.read_text(encoding='utf-8-sig');assert s.count('Zeitschleife.Calculate(index);')==1 and s.count('Zeitschleife.Calculate(nteil);')==1
  s=s.replace('Zeitschleife.Calculate(index);','ProgressProbe.Visit(index);').replace('Zeitschleife.Calculate(nteil);','ProgressProbe.Visit(nteil);');p.write_text(s,encoding='utf-8');(dst/'ProgressProbe.cs').write_text(PROBE,encoding='utf-8')
  dll=build(dst,'probe_'+tag,True);code,log=run([DOTNET,dll,ROOT/'results'/f'probe_{tag}.json'],ROOT);assert code==0,log;records[tag]=json.loads((ROOT/'results'/f'probe_{tag}.json').read_text());print(log.strip(),tag,flush=True)
 assert all(r['exactly_once'] for r in records['candidate'])
 assert all(r['exactly_once'] for r in records['baseline'] if not r['fixed_seed'] or r['total']==0 or r['total']>=10)
 assert all(r['visited']==min(r['total'],r['workers']) and r['duplicates']==0 for r in records['baseline'] if r['fixed_seed'] and 0<r['total']<10)
 save(ROOT/'results/probe_summary.json',dict(status='pass',cases_per_variant=len(records['candidate']),candidate_exactly_once=sum(r['exactly_once'] for r in records['candidate']),baseline_defective_cases=sum(not r['exactly_once'] for r in records['baseline']),scope='The actual compiled driver is called through reflection. Only its particle-body call is replaced by an interlocked visit counter in separate diagnostic source copies.'))

TEMPLATE='''1\n30\n0\n4\n0\n0.1\n47\nY\nNOX\n2\n4\n1\n0\n0\ncompressed V03\nnokeystroke\nASCiiResults 0\n0\n0\n0\n0\n1\n'''
def inputs(folder,budget,workers,fixed):
 folder.mkdir(parents=True); a=TEMPLATE.splitlines();a[0]=str(budget/30);a[-1]=str(int(fixed));(folder/'in.dat').write_text('\n'.join(a)+'\n');(folder/'GRAL.geb').write_text('20\n20\n2,1.1\n10\n10\n1\n1\n0\n200\n0\n200\n');(folder/'Max_Proc.txt').write_text(str(workers)+'\n');(folder/'micro_vert_layers.txt').write_text('40\n');(folder/'meteopgt.all').write_text('10,1,10\nwind_dir,wind_speed,stability,frequency\n9,0.5,4,1\n');(folder/'mettimeseries.dat').write_text('01.01.2022 00 0.5 9 4\n');(folder/'cadastre.dat').write_text('header\n100,100,2,8,8,2,1,0,0,0,1\n');(folder/'GRAL_Trans_Conc_Threshold.txt').write_text('0.00001\n')
def outputs(folder):
 result={};total=0;maximum=0;nonzero=0
 for p in folder.glob('*.grz'):
  with zipfile.ZipFile(p) as z:
   for n in z.namelist():
    if not n.endswith('.con'):continue
    b=z.read(n);hdr=struct.unpack_from('<iiiffii',b);assert hdr==(-3,0,0,20.0,20.0,10,10),(hdr,n);v=struct.unpack_from('<100f',b,28);assert all(math.isfinite(x) and x>=0 for x in v);result[p.name+':'+n]=hashlib.sha256(b).hexdigest();total+=sum(v);maximum=max(maximum,max(v));nonzero+=sum(x>0 for x in v)
 assert len(result)==1
 return dict(payload_sha256=result,concentration_sum=total,maximum=maximum,nonzero_cells=nonzero)
def main_runs(dlls):
 records=[];pairs=[];start=time.monotonic()
 for budget in [6,9,10,100,3000]:
  for workers in [1,4,24]:
   case=f'p{budget}_w{workers}';template=ROOT/'inputs'/case;inputs(template,budget,workers,True)
   for repeat in range(3):
    pair={}
    for tag in ['baseline','candidate']:
     assert time.monotonic()-start<800
     folder=ROOT/'runs'/f'{case}_{tag}_{repeat}';shutil.copytree(template,folder);code,log=run([DOTNET,dlls[tag],folder],folder,60);(folder/'console.log').write_text(log,encoding='utf-8');assert code==0 and 'GRAL simulations finished at:' in (folder/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig'),log[-4000:]
     alloc=re.search(r'Using a total of (\d+) particles',log);assert alloc and int(alloc[1])==budget,(case,log)
     emission=re.search(r'Summarized emission rates per source group in kg\s*\n[^\n]+\n([^\n]+)',log);assert emission,log
     mass=float(emission[1].split()[0]);expected=30/3600
     if tag=='candidate' or budget>=10:assert abs(mass-expected)<=.00005,(tag,case,mass)
     else:assert abs(mass-expected*min(workers,budget)/budget)<=.00005,(tag,case,mass)
     r=dict(case=case,variant=tag,repeat=repeat,particles=budget,workers=workers,exit_code=code,emitted_mass_kg_logged=mass,expected_mass_kg=expected,**outputs(folder));records.append(r);pair[tag]=r
     print('[MAIN]',len(records),case,tag,repeat,flush=True)
    same=pair['baseline']['payload_sha256']==pair['candidate']['payload_sha256'];pairs.append(dict(case=case,repeat=repeat,payloads_equal=same))
    if workers==1 and budget>=10:assert same,(case,'unchanged driver mismatch')
 save(ROOT/'results/main.json',dict(status='pass',runs=len(records),records=records,comparisons=pairs,elapsed_seconds=time.monotonic()-start))
 with (ROOT/'results/main.csv').open('w',newline='',encoding='utf-8') as f:
  keys=[k for k in records[0] if k!='payload_sha256'];w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(records)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--resume',action='store_true');args=ap.parse_args()
 for name in ['results','logs','tmp','cache']:(ROOT/name).mkdir(exist_ok=True)
 ENV=os.environ.copy();ENV.update(DOTNET_CLI_HOME=str(ROOT/'cache'),TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'),DOTNET_CLI_UI_LANGUAGE='en',DOTNET_NOLOGO='1')
 if not args.resume:prepare()
 expected=json.loads((ROOT/'source_manifest_reference.json').read_text(encoding='utf-8'))['files']
 for tag in ['baseline','candidate']:
  source=ROOT/('baseline' if tag=='baseline' else 'repo')
  assert all(hashlib.sha256(norm(source/name)).hexdigest()==digest for name,digest in expected[tag].items()),tag+' source mismatch'
 dlls={tag:build(ROOT/('baseline/src' if tag=='baseline' else 'repo/src'),tag) for tag in ['baseline','candidate']}
 probes();main_runs(dlls)
 print('[PASS] full suite',flush=True)
