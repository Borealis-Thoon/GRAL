"""Serial isolated GRAL runs with explicit launch, containment and paired inputs."""
from __future__ import annotations

import argparse
import csv
import ctypes
import datetime
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import compare
import fixtures
from support import runtime_controls, runtime_helpers

JOB = Path(__file__).resolve().parents[1]
EXPECTED_AFFINITY = sum(1 << i for i in range(16, 32))
RUNTIME_FILES = ('server.py', 'cuda_common.py', 'fields_manifest.json', 'generated.cu', 'ptx_cache.py')


def write_new(path: Path, value) -> None:
    with path.open('x', encoding='utf-8') as out:
        json.dump(value, out, indent=2, allow_nan=False)


def clean_environment(environment) -> dict:
    return {k: v for k, v in environment.items() if not k.upper().startswith(('INU_', 'GRAL_BENCH_'))}


def check_dispatch(logs: Path, text: str, expected: str, hours: int | None = None) -> dict:
    metric_path = logs / 'gpu_metrics.jsonl'
    markers = [line.strip() for line in text.splitlines() if 'GPU' in line]
    fallback = [line for line in markers if re.search(r'(?:CPU fallback|GPU fallback to CPU)\s*:', line, re.I)]
    if expected == 'fallback':
        if not fallback or metric_path.exists() or (logs / 'gpu_server.stderr').exists():
            raise ValueError('fallback lacks explicit reason or started GPU side effects')
        return dict(path='cpu_fallback', reasons=fallback)
    if expected == 'cpu':
        if metric_path.exists() or (logs / 'gpu_server.stderr').exists():
            raise ValueError('explicit CPU run has GPU side effects')
        return dict(path='cpu_requested', markers=markers)
    if expected != 'gpu' or fallback or not metric_path.exists():
        raise ValueError('GPU dispatch missing or unexpected fallback')
    rows = [json.loads(line) for line in metric_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if hours is not None and [r.get('situation') for r in rows] != list(range(1, hours+1)):
        raise ValueError('GPU metrics missing/duplicate situation')
    return dict(path='gpu', metrics=rows, markers=markers)


def summarize_situations(samples: list[dict], boundaries: list[dict]) -> list[dict]:
    results = []
    for row in boundaries:
        selected = [s for s in samples if row['start_s'] <= float(s['elapsed_s']) <= row['end_s']]
        result = dict(row, telemetry_samples=len(selected))
        for key in ('tree_rss_bytes', 'tree_private_bytes', 'dotnet_rss_bytes', 'python_rss_bytes'):
            values = [float(s[key]) for s in selected if s.get(key) not in ('', None)]
            result['peak_' + key] = max(values) if values else None
        results.append(result)
    return results


class Telemetry:
    def __init__(self, logs: Path, roots: list, dependencies: Path | None):
        if dependencies is not None:
            sys.path.insert(0, str(dependencies.resolve()))
        import psutil
        self.psutil, self.logs, self.roots = psutil, logs, roots
        self.stop = threading.Event()
        self.errors, self.samples, self.affinity = [], [], []
        self.origin = time.perf_counter()
        self.process_ready, self.gpu_ready = threading.Event(), threading.Event()
        self.model_finished=threading.Event()
        self.skipped_exiting=[]
        self.threads = [threading.Thread(target=self.processes, daemon=True), threading.Thread(target=self.gpu, daemon=True)]

    def start(self):
        for thread in self.threads: thread.start()
        if not self.process_ready.wait(5) or not self.gpu_ready.wait(5) or self.errors:
            self.finish()
            raise RuntimeError('telemetry baseline could not start')
        # Baseline is collected before the contained model process is created.
        if self.stop.wait(.4):
            self.finish()
            raise RuntimeError('telemetry baseline interrupted')

    def finish(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(timeout=5)
        if any(t.is_alive() for t in self.threads):
            self.errors.append('telemetry thread did not stop')
        if self.errors:
            raise RuntimeError('; '.join(self.errors))

    def now(self):
        return dict(timestamp=datetime.datetime.now().astimezone().isoformat(timespec='milliseconds'),
                    elapsed_s=time.perf_counter()-self.origin)

    def exited_process(self, proc):
        if self.model_finished.wait(.1):
            return True
        if not self.psutil.pid_exists(proc.pid):
            return True
        try:
            return not proc.is_running()
        except (self.psutil.NoSuchProcess,self.psutil.ZombieProcess):
            return True
        except self.psutil.AccessDenied:
            return False

    def processes(self):
        fields = ['timestamp', 'elapsed_s', 'tree_rss_bytes', 'tree_private_bytes', 'dotnet_rss_bytes',
                  'python_rss_bytes', 'available_ram_bytes', 'process_count', 'os_peak_working_set_bytes']
        try:
            known_masks = {}
            with (self.logs / 'process_telemetry.csv').open('x', encoding='utf-8', newline='') as stream, (self.logs / 'affinity_children.jsonl').open('x', encoding='utf-8') as masks, (self.logs / 'process_memory.jsonl').open('x', encoding='utf-8') as detail:
                writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
                while not self.stop.is_set():
                    started = time.monotonic()
                    row = dict(self.now(), tree_rss_bytes=0, tree_private_bytes=0, dotnet_rss_bytes=0,
                               python_rss_bytes=0, available_ram_bytes=self.psutil.virtual_memory().available,
                               process_count=0, os_peak_working_set_bytes=0)
                    processes = []
                    if self.roots:
                        try:
                            root = self.psutil.Process(self.roots[0]['pid'])
                            processes = [root] + root.children(recursive=True)
                        except self.psutil.NoSuchProcess:
                            pass
                    for proc in processes:
                        try:
                            # Cache creation identity before a process can disappear.
                            proc.create_time()
                            with proc.oneshot():
                                mem = proc.memory_full_info(); name = proc.name(); ppid = proc.ppid()
                                key = (proc.pid, proc.create_time()); affinity = sum(1 << c for c in proc.cpu_affinity())
                                private = getattr(mem, 'private', getattr(mem, 'uss', None))
                                row['tree_rss_bytes'] += mem.rss
                                if private is not None: row['tree_private_bytes'] += private
                                row['process_count'] += 1
                                row['os_peak_working_set_bytes'] += getattr(mem, 'peak_wset', 0)
                                if name.lower().startswith('dotnet'): row['dotnet_rss_bytes'] += mem.rss
                                if name.lower().startswith('python'): row['python_rss_bytes'] += mem.rss
                                record = dict(self.now(), pid=proc.pid, ppid=ppid, name=name,
                                              rss_bytes=mem.rss, private_bytes=private,
                                              os_peak_working_set_bytes=getattr(mem, 'peak_wset', None))
                                detail.write(json.dumps(record)+'\n')
                                if known_masks.get(key) != affinity:
                                    entry = dict(record, mask=affinity, create_time=key[1])
                                    masks.write(json.dumps(entry)+'\n'); self.affinity.append(entry); known_masks[key]=affinity
                                if affinity != EXPECTED_AFFINITY:
                                    raise RuntimeError('owned model process affinity differs from CPU16..31')
                        except (self.psutil.NoSuchProcess, self.psutil.ZombieProcess):
                            continue
                        except self.psutil.AccessDenied:
                            if not self.exited_process(proc):
                                raise
                            self.skipped_exiting.append(dict(self.now(),pid=proc.pid,reason='AccessDenied after verified process exit or contained job completion'))
                            continue
                    writer.writerow(row); stream.flush(); masks.flush(); detail.flush(); self.samples.append(row)
                    self.process_ready.set()
                    self.stop.wait(max(0, .1-(time.monotonic()-started)))
        except BaseException as exc:
            self.errors.append(f'process telemetry: {exc!r}'); self.stop.set(); self.process_ready.set()

    def gpu(self):
        fields = ['timestamp', 'elapsed_s', 'device_gpu_util_pct', 'device_memory_used_mib',
                  'device_temperature_c', 'device_power_w', 'query_error']
        proc = None
        try:
            proc = subprocess.Popen(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw', '--format=csv,noheader,nounits', '--loop-ms=200'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            terminator = threading.Thread(target=lambda: (self.stop.wait(), proc.terminate() if proc.poll() is None else None), daemon=True)
            terminator.start()
            with (self.logs / 'gpu_telemetry.csv').open('x', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
                while not self.stop.is_set():
                    row = self.now()
                    try:
                        line = proc.stdout.readline()
                        if not line:
                            if self.stop.is_set(): break
                            raise ValueError('persistent NVIDIA query exited')
                        row = self.now()
                        values = [v.strip() for v in line.split(',')]
                        if len(values) != 4: raise ValueError('expected one GPU')
                        numeric = [float(v) for v in values]
                        if not all(math.isfinite(v) and v >= 0 for v in numeric):
                            raise ValueError('NVIDIA query nonfinite/negative value')
                        row.update(zip(fields[2:6], numeric)); row['query_error']=''
                    except (OSError, subprocess.SubprocessError, ValueError) as exc:
                        row['query_error']=type(exc).__name__
                        writer.writerow(row); stream.flush(); self.gpu_ready.set()
                        self.errors.append(f'persistent GPU telemetry: {exc!r}'); self.stop.set()
                        return
                    writer.writerow(row); stream.flush(); self.gpu_ready.set()
        except BaseException as exc:
            self.errors.append(f'GPU telemetry: {exc!r}'); self.stop.set(); self.gpu_ready.set()
        finally:
            if proc is not None:
                if proc.poll() is None: proc.terminate()
                try: proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait(timeout=3)


def verify_input_hashes(root: Path, manifest: dict):
    for name, expected in manifest['input_sha256'].items():
        if fixtures.sha(root / name) != expected:
            raise ValueError('input changed: ' + name)


def validate_seed_rows(rows: list[dict], offset: int, fixed_mode: bool) -> dict:
    states=[]
    f32=lambda value: struct.unpack('<f',struct.pack('<f',value))[0]
    for row in rows:
        situation=row['IWET']+offset
        speed,direction=f32(row['WindVelGral']),f32(row['WindDirGral'])
        first=round(f32(abs(direction)+f32(speed*100)))
        second=round(f32(abs(direction)*2))
        expected1=(521288629+first+(situation<<2))&0xffffffff
        expected2=(2232121+second+(situation<<1))&0xffffffff
        expected=(expected1 or 521288629,expected2 or 2232121)
        if (row['Seed1'],row['Seed2'])!=expected or row['fixed_mode'] is not fixed_mode:
            raise ValueError('observer seed differs from designated constructor contract')
        states.append(expected)
    if not rows or len(set(states))!=len(states):
        raise ValueError('missing or duplicate situation seed states')
    return dict(status='pass',offset=offset,situations=len(rows),states=states)


def validate_completion(comp: Path, stdout: str, manifest: dict) -> dict:
    hours = manifest['hours']
    logfiles = list(comp.glob('Logfile_GRALCore*.txt'))
    if not logfiles or sum(p.read_text(errors='replace').count('GRAL simulations finished at:') for p in logfiles) != 1:
        raise ValueError('missing or duplicate completion marker')
    for problem in comp.glob('Problemreport_GRAL*'):
        if problem.read_text(errors='replace').strip(): raise ValueError('model problem report')
    banners = list(re.finditer(r'Weather number:\s*(\d+)', stdout))
    sequence = [int(match[1]) for match in banners]
    expected = list(range(1, hours+1))
    terminal_banner = sequence == expected + [hours+1]
    if terminal_banner:
        tail = stdout[banners[-1].end():]
        if re.search(r'Using a total of|Dispersion computation|FLOW FIELD COMPUTATION|Reading GRAMM|Total simulation time',tail):
            raise ValueError('terminal situation banner has unexpected integration work')
    if sequence != expected and not terminal_banner:
        raise ValueError('unexpected situation sequence: ' + repr(sequence))
    rows = re.findall(r'Summarized emission rates per source group in kg\s*\n[^\n]*\n([^\n]+)', stdout)
    if not manifest['config'].get('steady') and len(rows) != 1: raise ValueError('missing final emitted mass ledger')
    if manifest['config'].get('steady') and rows: raise ValueError('unexpected transient mass ledger in steady case')
    emitted = [float(value.replace(',', '.')) for value in rows[0].split()] if rows else []
    if any(not math.isfinite(value) or value < 0 for value in emitted):
        raise ValueError('nonfinite or negative emitted mass')
    mass = dict(actual_kg=emitted, expected_kg=manifest['expected_emitted_mass_kg'], checked=False)
    groups = tuple(manifest.get('source_groups', (1,2,3)))
    if not manifest['config'].get('steady'):
        if len(emitted) != len(groups) or any(abs(a-b) > .02 for a,b in zip(emitted, manifest['expected_emitted_mass_kg'])):
            raise ValueError('emitted mass differs from synthetic source/time contract')
        mass['checked']=True
    required = ('Receptor_Timeseries_Transient.txt',) if manifest['config'].get('receptors') else ()
    own = compare.compare_outputs(comp, comp, hours=hours, expected_groups=groups,
                                  deposition=manifest['config'].get('deposition',False), required_receptors=required,
                                  expected_receptor_columns=manifest['config']['receptors']*len(groups) if manifest['config'].get('receptors') else None)
    if not own['positive_concentration']: raise ValueError('all concentration outputs are zero')
    expected_members = hours * len(groups) * (2 if manifest['config'].get('deposition') else 1)
    if len(own['members']) != expected_members: raise ValueError('source group/slice/member count mismatch')
    if manifest['config'].get('receptors') and not own['receptors']:
        raise ValueError('requested receptors missing')
    residual = re.findall(r'INU residual: situation (\d+): planned (\d+) released (\d+)', stdout)
    if any(a != b for _, a, b in residual): raise ValueError('residual planned/released mismatch')
    return dict(mass_ledger=mass, output_members=len(own['members']), residual_ledger=residual,
                completed_situations=expected, terminal_banner_only=hours+1 if terminal_banner else None,
                positive_concentration=True, finite_nonnegative=True)


def load_observer(logs: Path, telemetry: Telemetry, model_start: float, hours: int) -> dict:
    path = logs / 'timing.jsonl'
    if not path.exists(): return dict(status='unavailable', reason='unmodified production build lacks observer')
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    seeds = [r for r in rows if r.get('event_type') == 'seed']
    starts = [r for r in rows if r.get('event_type') == 'situation_start']
    ends = [r for r in rows if r.get('event_type') == 'situation_end']
    if [r.get('IWET') for r in seeds] != list(range(1, hours+1)) or [r.get('IWET') for r in ends] != list(range(1,hours+1)):
        raise ValueError('observer per-situation coverage mismatch')
    if starts and [r.get('IWET') for r in starts] != list(range(1,hours+1)):
        raise ValueError('observer full situation start coverage mismatch')
    frequency = rows[0]['stopwatch_frequency']
    first_clock = rows[0]['stopwatch_timestamp']
    # Observer config logs a wall-clock UTC anchor to join independent telemetry.
    origin = datetime.datetime.fromisoformat(rows[0]['utc_timestamp']).timestamp()
    telemetry_origin = datetime.datetime.fromisoformat(telemetry.samples[0]['timestamp']).timestamp()-telemetry.samples[0]['elapsed_s'] if telemetry.samples else None
    boundaries = []
    if telemetry_origin is not None:
        for index,(seed, end) in enumerate(zip(seeds, ends)):
            start = starts[index] if starts else seed
            start_s = origin-telemetry_origin+(start['stopwatch_timestamp']-first_clock)/frequency
            end_s = origin-telemetry_origin+(end['stopwatch_timestamp']-first_clock)/frequency
            boundaries.append(dict(situation=seed['IWET'], start_s=start_s, end_s=end_s, wall_s=end_s-start_s,
                                   seed_to_end_s=(end['stopwatch_timestamp']-seed['stopwatch_timestamp'])/frequency,
                                   time_scope='full_situation_after_stop_check' if starts else 'seed_to_end_legacy'))
    summaries = summarize_situations(telemetry.samples, boundaries)
    write_new(logs / 'situation_series.json', summaries)
    return dict(status='pass', seed_rows=seeds, situation_series=summaries, raw_events=rows)


def run_one(args) -> dict:
    target = args.target.resolve()
    manifest = json.loads((target / 'input_manifest.json').read_text(encoding='utf-8'))
    verify_input_hashes(target, manifest)
    kernel = ctypes.WinDLL('kernel32'); kernel.GetCurrentProcess.restype=ctypes.c_void_p
    allowed, system = runtime_helpers.process_affinity_masks(kernel.GetCurrentProcess())
    if allowed != EXPECTED_AFFINITY:
        raise ValueError(f'runner must inherit CPU16..31 from existing policy; got {allowed:#x}')
    if args.seed_offset < 0 or args.seed_offset > 500000:
        raise ValueError('seed offset outside approved cohort')
    with runtime_helpers.reservation(JOB / 'JOBS.lock'):
        logs = target / 'logs'; logs.mkdir(exist_ok=False)
        result = dict(status='fail', case=manifest['case'], requested_mode=args.mode, seed_offset=args.seed_offset,
                      model_hours=manifest['hours'], timing_eligible=not args.no_quiet and manifest['hours'] in (24,48),
                      quiet_gate_enabled=not args.no_quiet, errors=[], allowed_affinity_mask=allowed, system_affinity_mask=system)
        try:
            build_hashes = runtime_helpers.stage_build(args.dll.resolve(), logs / 'build')
            result['build_hashes']=build_hashes
            env, controls = runtime_controls.configure_tiering(clean_environment(os.environ), 'default')
            result['runtime_controls']=controls
            temp = target / 'temp'; temp.mkdir()
            env.update(TEMP=str(temp), TMP=str(temp), INU_GPU_EXPERIMENTAL='1' if args.mode == 'gpu' else '0')
            env['GRAL_BENCH_SEED_OFFSET']=str(args.seed_offset)
            env.update(INU_BENCH_TIMING=str(logs / 'timing.jsonl'), INU_BENCH_WARMUP='3', INU_BENCH_END=str(manifest['hours']))
            if args.mode == 'gpu':
                env.update(INU_GPU_METRICS=str(logs / 'gpu_metrics.jsonl'), INU_GPU_STDERR=str(logs / 'gpu_server.stderr'),
                           INU_GPU_PYTHON=str(args.gpu_python.resolve()), INU_GRAL_GPU_CHUNK='65536', INU_GRAL_GPU_BLOCK='128')
                if manifest['config']['dispatch'] == 'fallback':
                    # These paths must remain absent; valid fallback must be decided before GPU construction.
                    invalid = logs / 'must_not_exist'
                    env.update(INU_GPU_SERVER=str(invalid/'server.py'), INU_GPU_MANIFEST=str(invalid/'fields_manifest.json'), INU_GPU_NVRTC_DIR=str(invalid))
                else:
                    if args.runtime is None or args.nvrtc_dir is None: raise ValueError('GPU runtime and NVRTC are required')
                    staged = logs / 'gpu_runtime'; staged.mkdir()
                    runtime_hashes = {}
                    for name in RUNTIME_FILES:
                        runtime_hashes[name]=fixtures.sha(args.runtime/name)
                        shutil.copyfile(args.runtime/name, staged/name)
                        if fixtures.sha(staged/name) != runtime_hashes[name]: raise ValueError('GPU runtime stage mismatch')
                    result['runtime_hashes']=runtime_hashes
                    env.update(INU_GPU_SERVER=str(staged/'server.py'), INU_GPU_MANIFEST=str(staged/'fields_manifest.json'), INU_GPU_NVRTC_DIR=str(args.nvrtc_dir.resolve()))
                    if args.cache is not None:
                        args.cache.mkdir(parents=True, exist_ok=True); env['INU_GPU_CACHE_DIR']=str(args.cache.resolve())
            gate = runtime_helpers.quiet_gate(required_seconds=getattr(args, 'quiet_required_s', 45)) if not args.no_quiet else dict(status='skipped_functional_smoke')
            result['quiet_gate']=gate
            roots=[]; telemetry=Telemetry(logs, roots, args.dependencies); telemetry.start()
            try:
                with (logs/'stdout.log').open('xb') as stdout, (logs/'stderr.log').open('xb') as stderr:
                    started=time.perf_counter()
                    pid, rc, timed_out=runtime_helpers.run_contained(
                        ['dotnet', str(logs/'build'/args.dll.name), str(target/'Computation'), f'SITUATIONS:1:{manifest["hours"]}'],
                        target/'Computation', env, stdout, stderr, args.timeout,
                        expected_affinity_mask=EXPECTED_AFFINITY, affinity_record=roots)
                    # run_contained returns only after its Job Object is verified empty.
                    telemetry.model_finished.set()
                    result.update(pid=pid, exit_code=rc, timed_out=timed_out, process_start_to_exit_s=time.perf_counter()-started)
            finally:
                telemetry.finish()
            if rc or timed_out: raise ValueError('model exit or timeout failure')
            stdout=(logs/'stdout.log').read_text(encoding='utf-8', errors='replace')
            expected = 'cpu' if args.mode == 'cpu' else manifest['config']['dispatch']
            result['dispatch']=check_dispatch(logs, stdout, expected, manifest['hours'])
            result['functional']=validate_completion(target/'Computation', stdout, manifest)
            result['affinity']=runtime_controls.validate_affinity_records(telemetry.affinity, pid, EXPECTED_AFFINITY, 'gpu' if expected=='gpu' else 'cpu')
            result['skipped_exiting_process_samples']=telemetry.skipped_exiting
            if expected == 'fallback' and result['affinity']['gpu_python_observed']:
                raise ValueError('fallback launched GPU Python process')
            result['observer']=load_observer(logs, telemetry, started, manifest['hours'])
            if result['observer']['status']=='pass':
                seeds=result['observer']['seed_rows']
                result['seed_validation']=validate_seed_rows(seeds,args.seed_offset,not manifest['config'].get('nonfixed_seed',False))
                if expected=='gpu':
                    for seed,metric in zip(seeds,result['dispatch']['metrics']):
                        if (seed['Seed1'],seed['Seed2'])!=(metric['rng_seed1'],metric['rng_seed2']):
                            raise ValueError('GPU metric RNG state differs from observer state')
            result['memory_scope']=dict(process_gpu_memory_mib=None,
                process_gpu_memory_availability='unavailable in current WDDM query; device total must not be attributed to process',
                process_sample_target_s=.1,gpu_device_sample_target_s=.2,
                process_actual_sample_intervals_s=[b['elapsed_s']-a['elapsed_s'] for a,b in zip(telemetry.samples,telemetry.samples[1:])],
                process_rows=len(telemetry.samples),idle_baseline='samples before contained model PID creation')
            verify_input_hashes(target, manifest)
            runtime_helpers.verify_build(logs/'build', build_hashes)
            runtime_helpers.verify_build(args.dll.parent, build_hashes)
            result['status']='pass'
        except BaseException as exc:
            result['errors'].append(type(exc).__name__+': '+str(exc)); result['timing_eligible']=False
            write_new(logs/'result.json', result)
            if isinstance(exc, runtime_helpers.CleanupFailure): raise
            return result
        write_new(logs/'result.json', result)
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', type=Path, required=True)
    p.add_argument('--dll', type=Path, required=True)
    p.add_argument('--mode', choices=('cpu','gpu'), required=True)
    p.add_argument('--gpu-python', type=Path, default=Path(sys.executable))
    p.add_argument('--runtime', type=Path)
    p.add_argument('--nvrtc-dir', type=Path)
    p.add_argument('--dependencies', type=Path)
    p.add_argument('--cache', type=Path)
    p.add_argument('--seed-offset', type=int, default=0)
    p.add_argument('--timeout', type=int, default=7200)
    p.add_argument('--no-quiet', action='store_true')
    p.add_argument('--quiet-required-s', type=int, choices=(10,45), default=45)
    args=p.parse_args()
    result=run_one(args)
    print('[RESULT]', result['case'], args.mode, result['status'])
    return 0 if result['status']=='pass' else 1


if __name__=='__main__':
    raise SystemExit(main())
