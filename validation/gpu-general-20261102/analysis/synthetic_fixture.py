"""Create synthetic analysis fixtures only; never invoke GRAL or GPU code."""
from pathlib import Path
import csv
import json
import struct
import zipfile
from analyze_study import SEED_OFFSETS,sha256


def write_json(path,value):
    path.write_text(json.dumps(value),encoding='utf-8')


def make_study(root:Path):
    root.mkdir(exist_ok=False)
    records=[]
    definitions=[(24,s,'science',0,f'science_{s}') for s in SEED_OFFSETS]
    definitions += [(24,0,'timing',i,f'timing24_{i}') for i in (1,2)]
    definitions += [(48,0,'timing',i,f'timing48_{i}') for i in (0,1,2)]
    for hours,offset,role,repeat,pair in definitions:
        for backend in ('cpu','gpu'):
            name=f'{pair}_{backend}';run=root/name;comp=run/'Computation';logs=run/'logs'
            logs.mkdir(parents=True);comp.mkdir()
            (run/'fixed.txt').write_text('synthetic immutable inputs',encoding='utf-8')
            (comp/'emissions_timeseries.txt').write_text('Date;Hour;1;2;3\n'+''.join(f'{1+h//24:02d}.01;{1+h%24};1;1;1\n' for h in range(hours+1)),encoding='ascii')
            (comp/'mettimeseries.dat').write_text(''.join(f'{1+h//24:02d}.01 {1+h%24} 2 27 4\n' for h in range(hours+1)),encoding='ascii')
            inputs={'hours':hours,'grid_cells':[50,50],'workers':16,'particles_per_hour':360000,
                    'factors':[[1,1,1]]*hours,'input_sha256':{'fixed.txt':sha256(run/'fixed.txt')}}
            write_json(run/'input_manifest.json',inputs)
            series=[{'situation':h,'start_s':float(h),'end_s':float(h)+.5,'wall_s':.5,'seed_to_end_s':.4,'time_scope':'full_situation_after_stop_check','telemetry_samples':2,
                     'peak_tree_rss_bytes':2048,'peak_tree_private_bytes':1024,
                     'peak_dotnet_rss_bytes':1024,'peak_python_rss_bytes':1024} for h in range(1,hours+1)]
            seeds=[{'IWET':h,'Seed1':521288829+((h+offset)<<2),'Seed2':2232121+((h+offset)<<1),'fixed_mode':True} for h in range(1,hours+1)]
            raw=[{'event_type':'boundary','boundary':'start','IWET':3,'stopwatch_timestamp':3000000,'stopwatch_frequency':1000000,'elapsed_s':0},
                 {'event_type':'boundary','boundary':'stop','IWET':hours,'stopwatch_timestamp':hours*1000000,'stopwatch_frequency':1000000,'elapsed_s':hours-3,'measured_situations':hours-3},
                 {'event_type':'finished','complete':True,'completed_situations':hours,'seeded_situations':hours}]
            result={'status':'pass','timing_eligible':True,'model_hours':hours,'seed_offset':offset,'requested_mode':backend,
                    'process_start_to_exit_s':float(hours+2+repeat),'dispatch':{'path':'gpu' if backend=='gpu' else 'cpu_requested'},
                    'build_hashes':{'synthetic':'fake-test-only'},'observer':{'status':'pass','seed_rows':seeds,'situation_series':series,'raw_events':raw}}
            write_json(logs/'result.json',result)
            rows=[{'elapsed_s':float(h),'tree_rss_bytes':2048,'tree_private_bytes':1024,'dotnet_rss_bytes':1024,'python_rss_bytes':1024,'os_peak_working_set_bytes':2048} for h in range(hours+1)]
            for filename,data in [('process_telemetry.csv',rows),('gpu_telemetry.csv',[{'elapsed_s':float(h),'device_memory_used_mib':1000.,'query_error':''} for h in range(hours+1)])]:
                with (logs/filename).open('w',newline='') as stream:
                    w=csv.DictWriter(stream,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
            (logs/'process_memory.jsonl').write_text('\n'.join(json.dumps({'pid':pid,'name':pname,'elapsed_s':float(h),'rss_bytes':1024,'private_bytes':512}) for h in range(hours+1) for pid,pname in [(1,'dotnet.exe'),(2,'python.exe')]),encoding='utf-8')
            if backend=='gpu':
                from plot_study import PHASES
                gpu=[{'situation':h,**{phase:.01 for phase in PHASES},'fresh_kernel_ms':5.,'residual_kernel_ms':1.,'saved_payload_bytes':1000,'bytes_sent':2000,'bytes_received':1000,
                      'result_server_metrics':{'kernel_device_ms':h*4.,'buffer_allocation_count':10,'buffer_reuse_count':h,'buffer_free_count':0,'device_buffer_bytes':100000,'peak_device_buffer_bytes':100000}} for h in range(1,hours+1)]
                (logs/'gpu_metrics.jsonl').write_text('\n'.join(map(json.dumps,gpu)),encoding='utf-8')
            if role=='science' or offset==0:
                for h in range(1,hours+1):
                    with zipfile.ZipFile(comp/f'{h:05d}.grz','w',compression=zipfile.ZIP_DEFLATED) as archive:
                        for group in (1,2,3):
                            value=group*(1+offset/1000000)+(.001 if backend=='gpu' else 0)
                            raw=struct.pack('<i',-1)+struct.pack('<iif',2010,2010,value)+struct.pack('<iif',2490,2490,value/2)
                            archive.writestr(f'{h:05d}-1{group:02d}.con',raw)
            records.append({'run_id':name,'fixture_case':'supported_primary','hours':hours,'seed_offset':offset,'backend':backend,'pair_id':pair,'role':role,'repeat':repeat,'path':str(run)})
    manifest=root/'study_manifest.json';write_json(manifest,{'synthetic_test_only':True,'runs':records})
    return manifest
