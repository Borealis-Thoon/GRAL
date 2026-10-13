from pathlib import Path
import subprocess, shutil, json, os, hashlib, importlib.util, time, re
import argparse
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--run-dir',type=Path,required=True);ap.add_argument('--dotnet',default='dotnet');args=ap.parse_args()
W=args.run_dir.resolve();Q=W/'qa';W.mkdir(parents=True,exist_ok=False);Q.mkdir();DOTNET=args.dotnet
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
def command(args,cwd,timeout=180):
 p=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout);assert p.returncode==0,p.stdout+p.stderr;return p.stdout+p.stderr
env=os.environ.copy(); env.update(DOTNET_CLI_HOME=str(W/'dotnet'),TMP=str(W/'tmp'),TEMP=str(W/'tmp'),DOTNET_CLI_UI_LANGUAGE='en');(W/'tmp').mkdir(exist_ok=True)
repo=W/'repo';command(['git','clone','--no-hardlinks',str(args.repo.resolve()),str(repo)],W)
command(['git','checkout','-b','codex/review-residual-floor-20261013','370084ba3d933e8cf444b33af93a34db41ba91fe'],repo)
p=repo/'src/Zeitschleife_nonsteadystate.cs';before=p.read_text(encoding='utf-8-sig');after=before.replace('long total = 0;','long total = 0, entries = 0;').replace('long local = 0;','long local = 0, localEntries = 0;').replace('local += ResidualSplitCount(concentrations[group] * volume / Program.TAUS);','local += ResidualSplitCount(concentrations[group] * volume / Program.TAUS);\n                                    localEntries++;').replace('Interlocked.Add(ref total, local);','Interlocked.Add(ref total, local);\n                    Interlocked.Add(ref entries, localEntries);').replace('if (total <= budget) break;','if (total <= budget || total == entries) break;')
assert before!=after and after.count('localEntries++')==1;p.write_text(after,encoding='utf-8',newline='')
(Q/'pr63_floor.patch').write_bytes(subprocess.run(['git','diff','--','src/Zeitschleife_nonsteadystate.cs'],cwd=repo,capture_output=True,check=True).stdout)
for variant,source in [('before',before),('after',after)]:
 target=W/variant;shutil.copytree(repo/'src',target/'src',ignore=shutil.ignore_patterns('obj','bin'));(target/'src/Zeitschleife_nonsteadystate.cs').write_text(source,encoding='utf-8')
 log=command([DOTNET,'build',str(target/'src/GRAL.csproj'),'-c','Release','-t:Rebuild','--nologo','/p:TreatWarningsAsErrors=true'],target)
 (Q/f'build_{variant}.log').write_text(log,encoding='utf-8');assert '0 Warning(s)' in log and '0 Error(s)' in log
 print('[BUILD] '+variant,flush=True)
# The fixture compiles the exact reviewed split-count and planner methods, with only a scan counter added.
start=before.index('        private static double residualSplitK');end=before.index('        /// <summary>',start)
prelude=r'''using System; using System.Collections.Generic; using System.Threading; using System.Threading.Tasks; using System.Text.Json;
class Program { public static CancellationToken CancelToken; public static float TAUS=1,TPS=200,DXK=1,DYK=1,GridVolume=1,TransConcThreshold=1; public static float[] DZK_Trans=new float[]{0,1}; public static int NII,NJJ=1,NKK_Transient=1;public static List<int> SourceGroups=new List<int>{1}; public static ParallelOptions pOptions=new ParallelOptions(); public static float[][][][] Conz4d; }
class ParticleManagement {public static double ParticleMassActive=1;}
class Planner { public static int Scans;
'''
post=r'''
public static int Split(double m)=>ResidualSplitCount(m); public static double K=>residualSplitK; }
class Entry {
 static void Main(string[] args) {var rows=new List<object>();int checks=0;
 foreach(int workers in new[]{1,4,24}) foreach(int n in new[]{0,1,100,300,1000}) foreach(int pattern in new[]{0,1,2,3,4}) foreach(float budget in new[]{20f,200f,3000f}) {
 Program.NII=Math.Max(1,(n+6)/7);Program.NJJ=7;Program.TPS=budget;Program.pOptions.MaxDegreeOfParallelism=workers; Program.Conz4d=new float[Program.NII+1][][][]; int idx=0;
 for(int i=0;i<=Program.NII;i++){Program.Conz4d[i]=new float[8][][];for(int j=0;j<8;j++){Program.Conz4d[i][j]=new float[2][];for(int k=0;k<2;k++)Program.Conz4d[i][j][k]=new float[1];}}
 for(int i=1;i<=Program.NII;i++)for(int j=1;j<=7;j++){if(idx<n)Program.Conz4d[i][j][1][0]=pattern==0?1:pattern==1?9:pattern==2?10:pattern==3?(idx%2==0?1:10000):10000000;idx++;}
 Planner.Scans=0;Planner.PlanResidual();var splits=new List<int>();for(int i=1;i<=Program.NII;i++)for(int j=1;j<=7;j++){float v=Program.Conz4d[i][j][1][0];if(v>=1)splits.Add(Planner.Split(v));}
 rows.Add(new{workers,n,pattern,budget,scans=Planner.Scans,k=Planner.K,splits});checks++;
 }
 var cancel=new CancellationTokenSource();cancel.Cancel();Program.CancelToken=cancel.Token;Planner.Scans=0;Planner.PlanResidual();if(Planner.Scans!=0)throw new Exception("cancel scan");checks++;
 Program.CancelToken=CancellationToken.None; foreach(float budget in new[]{0f,-1f}){Program.TPS=budget;Planner.Scans=0;Planner.PlanResidual();if(Planner.Scans!=0)throw new Exception("budget");checks++;}
 Program.TPS=100;ParticleManagement.ParticleMassActive=0;Planner.Scans=0;Planner.PlanResidual();if(Planner.Scans!=0)throw new Exception("reference");checks++;
 System.IO.File.WriteAllText(args[0],JsonSerializer.Serialize(new{checks,rows})); }
}
'''
for variant,source in [('before',before),('after',after)]:
 d=W/f'component_{variant}';d.mkdir();s=source.index('        private static double residualSplitK');e=source.index('        /// <summary>',s)
 fragment=source[s:e].replace('long total = 0','Scans++;\n                long total = 0')
 (d/'Program.cs').write_text(prelude+fragment+post,encoding='utf-8');(d/'Component.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><Nullable>disable</Nullable></PropertyGroup></Project>')
 log=command([DOTNET,'build','Component.csproj','-c','Release','--nologo','/p:TreatWarningsAsErrors=true'],d);(Q/f'build_component_{variant}.log').write_text(log);assert '0 Warning(s)' in log and '0 Error(s)' in log
 command([DOTNET,str(d/'bin/Release/net10.0/Component.dll'),str(Q/f'component_{variant}.json')],d);print('[COMPONENT] '+variant,flush=True)
a=json.loads((Q/'component_before.json').read_text());b=json.loads((Q/'component_after.json').read_text());assert a['checks']==b['checks']; reductions=[]
for x,y in zip(a['rows'],b['rows']):
 assert x['splits']==y['splits'],(x,y)
 assert y['scans']<=x['scans']
 if y['scans']<x['scans']:reductions.append({k:x[k] for k in ['workers','n','pattern','budget']}|dict(before=x['scans'],after=y['scans'],before_k=x['k'],after_k=y['k']))
save(Q/'component_comparison.json',dict(status='pass',checks_per_variant=a['checks'],exact_split_count_cases=len(a['rows']),reduced_scan_cases=len(reductions),scan_reductions=reductions))
# Reuse only the previous public input generator and output decoder; both engine builds are fresh.
spec=importlib.util.spec_from_file_location('existing',ROOT/'prior_fixture/residual_benchmark.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=ROOT/'prior_fixture'
cs=[dict(next(c for c in m.cases() if c['id']==id)) for id in ['steady_20m_n1000','largeoff_20m_n1000','alloff_20m_n1000']]
c=dict(next(c for c in m.cases() if c['id']=='many_sources_20m_n3000'));c.update(id='many_sources_10m_requested100',dx=10,budget=100);cs.append(c)
records=[]
for c in cs:
 for rep in range(2):
  for variant in (['before','after'] if rep==0 else ['after','before']):
   d=W/'main'/f'{c["id"]}_{variant}_{rep}';m.input_case(c,d);t=time.perf_counter();out=command([DOTNET,str(W/variant/'src/bin/Release/net10.0/GRAL.dll'),str(d)],d,60);elapsed=time.perf_counter()-t
   (d/'console.log').write_text(out,encoding='utf-8');assert 'GRAL simulations finished at:' in (d/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig');problem=d/'Problemreport_GRAL.txt';assert not problem.exists() or not problem.read_text().strip()
   digests,values=m.outputs(d,c);records.append(dict(case=c['id'],variant=variant,repeat=rep,wall_s=elapsed,payload=digests));print('[RUN] '+d.name,flush=True)
for c in cs:
 subset=[r for r in records if r['case']==c['id']];assert all(r['payload']==subset[0]['payload'] for r in subset)
save(Q/'main_comparison.json',dict(status='pass',runs=len(records),cases=cs,payload_pairs=sum(len(r['payload']) for r in records if r['variant']=='after'),all_equal=True,records=records))
save(Q/'validation.json',dict(status='pass',strict_builds=4,warnings=0,errors=0,component_checks_per_variant=a['checks'],main_runs=len(records),exact_split_count_cases=len(a['rows']),reduced_scan_cases=len(reductions),main_payload_pairs=sum(len(r['payload']) for r in records if r['variant']=='after')))
print('[PASS] #63 floor early exit',flush=True)
