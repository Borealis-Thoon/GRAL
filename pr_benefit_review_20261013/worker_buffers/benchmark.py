from pathlib import Path
import argparse, hashlib, json, os, re, shutil, statistics, subprocess, time
import numpy as np
import field_support as f

ROOT=Path(__file__).resolve().parent
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def cases():
    common=dict(kind='point',sources=2,sg=2,length=800,flow=40,conc=40,slices=1,speed=.25,sc=6,hot=False,workers=24)
    specs=[
      dict(id='tutorial_100',pps=100,tau=60,workers=4),
      dict(id='typical_1000',pps=1000,tau=120,sources=8,sg=8,speed=.5,sc=4),
      dict(id='concentrated_8000',pps=8000,tau=120,sc=2),
      dict(id='longer_32_sources',pps=1000,tau=300,sources=32,sg=8,length=1200,speed=1,sc=6,distributed=True),
      dict(id='fine_9_heights',pps=1000,tau=120,kind='area',sources=8,sg=8,length=1200,conc=10,slices=9,speed=1,sc=4),
    ]
    return [dict(common,**s,particles=s['pps']*s['tau']) for s in specs]
def prepare(c,d):
    # Keep source rates equal, alter locations only to vary contention independently of particle rate.
    cc=f.configure(c,d)
    if c.get('distributed'):
        p=d/'point.dat';lines=p.read_text().splitlines()
        for i in range(c['sources']):
            row=lines[2+i].split(',');row[0]=str(160+120*(i%8));row[1]=str(200+200*(i//8));lines[2+i]=','.join(row)
        p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert float((d/'in.dat').read_text().splitlines()[0])==c['pps']
    save(d/'case.json',cc)
    return cc
def build():
    manifest=json.loads((ROOT/'source_manifest.json').read_text())
    reports=[]
    for variant in ['before','after']:
        source=ROOT/'sources'/variant
        for p,h in manifest['hashes'][variant].items():assert hashlib.sha256((source/p).read_bytes()).hexdigest()==h
        cmd=[str(f.DOTNET),'build',str(source/'src/GRAL.csproj'),'-c','Release','-p:TreatWarningsAsErrors=true','--nologo']
        buildenv=os.environ.copy();buildenv['DOTNET_CLI_UI_LANGUAGE']='en'
        p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90,env=buildenv)
        (ROOT/f'build_{variant}.log').write_text(p.stdout+p.stderr,encoding='utf-8')
        assert p.returncode==0,p.stdout+p.stderr
        assert re.search(r'0 Warning\(s\)',p.stdout) and re.search(r'0 Error\(s\)',p.stdout),p.stdout
        reports.append(dict(variant=variant,exit_code=p.returncode,warnings=0,errors=0))
    save(ROOT/'builds.json',reports)
def main():
    a=argparse.ArgumentParser();a.add_argument('--build-only',action='store_true');a.add_argument('--run-name',default='main');a.add_argument('--max-seconds',type=int,default=720);a.add_argument('--cases',nargs='+');args=a.parse_args()
    if args.build_only:build();return
    run=ROOT/args.run_name;run.mkdir();(run/'tmp').mkdir();env=os.environ.copy();env.update(TEMP=str(run/'tmp'),TMP=str(run/'tmp'));env.pop('GRAL_WORKER_CONCENTRATION_MB',None)
    dlls={v:ROOT/'sources'/('before' if v=='before' else 'after')/'src/bin/Release/net10.0/GRAL.dll' for v in ['before','off','on']}
    records=[];pairs=[];repeats=[];summary=[];conditions=[];start=time.perf_counter()
    for ix,c in enumerate(cases()):
        if args.cases and c['id'] not in args.cases:continue
        d=run/'inputs'/c['id'];d.parent.mkdir(exist_ok=True);c=prepare(c,d);conditions.append(c);first={};vv={v:[] for v in dlls}
        for rep in range(-1,5):
            rotation=(rep+1+ix)%3;variants=['before','off','on'];variants=variants[rotation:]+variants[:rotation];current={}
            for v in variants:
                if v=='before' and rep>=3:continue
                assert time.perf_counter()-start<args.max_seconds,'suite watchdog'
                folder=run/'runs'/f'{c["id"]}_{v}_{rep}';folder.parent.mkdir(exist_ok=True);shutil.copytree(d,folder)
                e=env.copy()
                if v=='on':e['GRAL_WORKER_CONCENTRATION_MB']='256'
                result=f.process(dlls[v],folder,e,timeout=90)
                text=(folder/'console.log').read_text(encoding='utf-8',errors='replace');core=folder/'Logfile_GRALCore.txt';problem=folder/'Problemreport_GRAL.txt'
                assert result['exit_code']==0 and core.exists() and 'GRAL simulations finished at:' in core.read_text(encoding='utf-8-sig') and not(problem.exists() and problem.read_text().strip()),text[-3000:]
                allocated=[int(n) for n in re.findall(r'Using a total of (\d+) particles',text)];assert allocated and all(n==c['particles'] for n in allocated),(c['id'],allocated,c['particles'])
                actual_sources={}
                for kind,label in {'point':'point sources','area':'area source partitions','line':'line source segments','portal':'tunnel portals'}.items():
                    matches=re.findall(r'Total number of '+label+r': (\d+)',text)
                    actual_sources[kind]=int(matches[0]) if matches else 0
                    assert actual_sources[kind]==c['source_counts'].get(kind,0),(c['id'],actual_sources,c['source_counts'])
                logs=re.findall(r'Worker concentration buffers: ([^\r\n]+)',text)
                if v=='on':assert len(logs)==1 and logs[0].startswith('enabled'),logs
                else:assert not logs,(v,logs)
                arrays,hashes=f.payloads(folder,c);current[v]=(arrays,hashes)
                if rep>=0:
                    if v in first:repeats.append(dict(case=c['id'],variant=v,repeat=rep,all_payload_equal=first[v][1]==hashes,**f.diff(first[v][0],arrays)))
                    else:first[v]=(arrays,hashes)
                buffer_bytes=int(re.search(r'reserved=(\d+)',logs[0]).group(1)) if logs else 0
                result.update(case=c['id'],variant=v,repeat=rep,warmup=rep<0,particles_per_second=c['pps'],duration_s=c['tau'],allocated_particles=allocated,source_counts=actual_sources,buffer_bytes=buffer_bytes,payload_hashes=hashes)
                records.append(result)
                if rep>=0:vv[v].append(result)
                save(run/'progress.json',dict(completed=len(records),case=c['id'],variant=v,repeat=rep))
                print('[MAIN]',len(records),c['id'],v,rep,round(result['wall_s'],3),flush=True)
            for ref,v in [('off','on'),('before','off'),('before','on')]:
                if ref in current and v in current:pairs.append(dict(case=c['id'],reference=ref,variant=v,repeat=rep,warmup=rep<0,all_payload_equal=current[ref][1]==current[v][1],**f.diff(current[ref][0],current[v][0])))
        med={v:statistics.median(r['wall_s'] for r in rr) for v,rr in vv.items()}
        paired=[100*(1-n['wall_s']/o['wall_s']) for o,n in zip(vv['off'],vv['on'])]
        for v,rr in vv.items():
            times=[r['wall_s'] for r in rr]
            summary.append(dict(case=c['id'],variant=v,repetitions=len(rr),median_s=med[v],min_s=min(times),max_s=max(times),median_peak_working_set=statistics.median(r['memory']['PeakWorkingSetSize'] for r in rr),max_peak_working_set=max(r['memory']['PeakWorkingSetSize'] for r in rr),buffer_bytes=max(r['buffer_bytes'] for r in rr)))
        summary[-1]['paired_savings_percent']=paired;summary[-1]['ratio_of_medians_savings_percent']=100*(1-med['on']/med['off'])
    out=dict(status='pass',base=json.loads((ROOT/'source_manifest.json').read_text())['base'],conditions=conditions,main_runs=len(records),timed_runs=sum(not r['warmup'] for r in records),records=records,paired_comparisons=pairs,repeat_differences=repeats,summaries=summary,elapsed_s=time.perf_counter()-start)
    save(run/'summary.json',out)
    print('[PASS]',len(records),'Main runs',flush=True)
if __name__=='__main__':main()
