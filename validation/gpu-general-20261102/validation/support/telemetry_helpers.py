"""Verbatim helper definitions from the prior reviewed synthetic harness."""
from pathlib import Path
DEPS = Path(__file__).parent
import argparse, contextlib, csv, datetime, hashlib, json, os, random, re, subprocess, sys, threading, time


from pathlib import Path


def telemetry(path,stop,ready,errors,affinity_path=None,affinity_root=None):
    try:
        if str(DEPS) not in sys.path:sys.path.insert(0,str(DEPS))
        import psutil
        me=psutil.Process(); cores=psutil.cpu_count();last={};last_t=time.monotonic();psutil.cpu_percent(None)
        fields=['timestamp','elapsed_s','system_cpu_pct','tree_cpu_pct_total_machine','tree_rss_bytes','tree_private_bytes','available_ram_bytes','gpu_util_pct','gpu_memory_used_mib','gpu_temperature_c','gpu_power_w','gpu_query_error','processes_inaccessible']
        t0=time.perf_counter();last_masks={};owned_pids=set()
        with contextlib.ExitStack() as stack:
            f=stack.enter_context(path.open('x',encoding='utf-8',newline=''))
            affinity=stack.enter_context(affinity_path.open('x',encoding='utf-8')) if affinity_path else None
            out=csv.DictWriter(f,fieldnames=fields);out.writeheader();f.flush();ready.set()
            while not stop.is_set():
                now=time.monotonic();dt=max(now-last_t,1e-9);last_t=now;current={};cpu=rss=private=0;inaccessible=0
                for proc in me.children(recursive=True):
                    try:
                        with proc.oneshot():
                            key=(proc.pid,proc.create_time());ct=proc.cpu_times();total=ct.user+ct.system;mem=proc.memory_full_info()
                            rss+=mem.rss;private+=getattr(mem,'private',getattr(mem,'uss',0));current[key]=total
                            if key in last:cpu+=max(0,total-last[key])
                            if affinity is not None:
                                mask=sum(1<<core for core in proc.cpu_affinity())
                                parent_pid=proc.ppid()
                                root_pid=affinity_root[0]['pid'] if affinity_root else None
                                if proc.pid==root_pid or parent_pid==root_pid or parent_pid in owned_pids:
                                    owned_pids.add(proc.pid)
                                if last_masks.get(key)!=mask:
                                    affinity.write(json.dumps({'pid':proc.pid,'ppid':parent_pid,
                                        'name':proc.name(),'mask':mask,'create_time':key[1],
                                        'timestamp':datetime.datetime.now().astimezone().isoformat()})+'\n')
                                    affinity.flush();last_masks[key]=mask
                    except psutil.AccessDenied as exc:
                        inaccessible+=1
                        root_pid=affinity_root[0]['pid'] if affinity_root else None
                        if affinity is not None and (proc.pid==root_pid or proc.pid in owned_pids):
                            raise RuntimeError(f'affinity telemetry access denied for owned PID {proc.pid}') from exc
                    except (psutil.NoSuchProcess,psutil.ZombieProcess):inaccessible+=1
                last=current
                try:
                    query=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=0.8,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    lines=query.stdout.strip().splitlines()
                    vals=[v.strip() for v in lines[0].split(',')] if len(lines)==1 else []
                    if len(vals)!=4:raise ValueError('unexpected GPU count or output')
                    gpu_error=''
                except (OSError,subprocess.SubprocessError,ValueError) as e:vals=['','','',''];gpu_error=type(e).__name__
                out.writerow({'timestamp':datetime.datetime.now().astimezone().isoformat(timespec='milliseconds'),'elapsed_s':round(time.perf_counter()-t0,3),'system_cpu_pct':psutil.cpu_percent(None),
                              'tree_cpu_pct_total_machine':round(cpu/dt/cores*100,3),'tree_rss_bytes':rss,'tree_private_bytes':private,'available_ram_bytes':psutil.virtual_memory().available,
                              'gpu_util_pct':vals[0],'gpu_memory_used_mib':vals[1],'gpu_temperature_c':vals[2],'gpu_power_w':vals[3],'gpu_query_error':gpu_error,'processes_inaccessible':inaccessible})
                f.flush();stop.wait(max(0,1-(time.monotonic()-now)))
    except BaseException as e:errors.append(repr(e));stop.set();ready.set()

