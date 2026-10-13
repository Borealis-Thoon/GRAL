"""Confirm that a 16 MiB budget avoids the dense-grid allocation."""
from pathlib import Path
import json, os, re, shutil, statistics
import field_support as f

ROOT=Path(__file__).resolve().parent
def main():
    main=json.loads((ROOT/'main/summary.json').read_text());c=next(c for c in main['conditions'] if c['id']=='fine_9_heights')
    source=ROOT/'main/inputs'/c['id'];run=ROOT/'budget16';run.mkdir();(run/'tmp').mkdir()
    env=os.environ.copy();env.update(TEMP=str(run/'tmp'),TMP=str(run/'tmp'),GRAL_WORKER_CONCENTRATION_MB='16')
    reference,_=f.payloads(ROOT/'main/runs'/(c['id']+'_off_0'),c)
    records=[]
    for rep in range(-1,5):
        folder=run/f'run_{rep}';shutil.copytree(source,folder)
        result=f.process(ROOT/'sources/after/src/bin/Release/net10.0/GRAL.dll',folder,env,timeout=60)
        text=(folder/'console.log').read_text(encoding='utf-8',errors='replace');core=folder/'Logfile_GRALCore.txt';problem=folder/'Problemreport_GRAL.txt'
        assert result['exit_code']==0 and core.exists() and 'GRAL simulations finished at:' in core.read_text(encoding='utf-8-sig') and not(problem.exists() and problem.read_text().strip())
        allocation=[int(x) for x in re.findall(r'Using a total of (\d+) particles',text)];assert allocation==[c['particles']]
        log=re.findall(r'Worker concentration buffers: ([^\r\n]+)',text);assert len(log)==1 and log[0].startswith('shared (budget or no groups)'),log
        assert 'required=205756416; reserved=0; limit=16777216 bytes' in log[0],log
        arrays,hashes=f.payloads(folder,c);delta=f.diff(reference,arrays);assert delta['changed_cells']==0,delta
        result.update(repeat=rep,warmup=rep<0,buffer_log=log[0],payload_hashes=hashes,comparison_to_off=delta);records.append(result)
        print('[BUDGET]',rep,round(result['wall_s'],3),flush=True)
    out=dict(status='pass',runs=len(records),condition=c,budget_MiB=16,required_MiB=205756416/2**20,reserved_bytes=0,all_payload_equal=True,records=records,median_s=statistics.median(r['wall_s'] for r in records if not r['warmup']),median_peak_working_set_MiB=statistics.median(r['memory']['PeakWorkingSetSize']/2**20 for r in records if not r['warmup']))
    (run/'summary.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print('[PASS]',len(records),'budget fallback runs')
if __name__=='__main__':main()
