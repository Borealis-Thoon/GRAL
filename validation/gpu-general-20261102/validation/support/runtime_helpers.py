"""Verbatim helper definitions from the prior reviewed synthetic harness."""
QUIET_RULE={'window_seconds':45,'sample_interval_seconds':5,'window_samples':9,
            'mean_cpu_pct_lt':12.0,'max_cpu_pct_lt':20.0,'max_wait_seconds':600}

import argparse, contextlib, ctypes, datetime, hashlib, json, math, os, re, shutil, struct, subprocess, sys, time, zipfile


from pathlib import Path


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def save(path, data):
    with path.open('x', encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)


def build_hashes(folder):
    return {str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def verify_build(folder, expected):
    if build_hashes(folder)!=expected: raise ValueError('build files changed: '+str(folder))


def stage_build(dll, dest):
    source=dll.parent
    if not dll.is_file(): raise ValueError('build DLL missing')
    if any(p.is_symlink() for p in source.rglob('*')): raise ValueError('symlink in build')
    before=build_hashes(source)
    shutil.copytree(source,dest)
    verify_build(dest,before);verify_build(source,before)
    return before


class CleanupFailure(RuntimeError):
    pass


def wait_for_process(proc, job, timeout):
    try:
        rc=proc.wait(timeout=timeout)
    except BaseException:
        try: job.terminate_and_wait()
        except BaseException as e: raise CleanupFailure('job cleanup could not be verified') from e
        raise
    try: job.wait_empty()
    except BaseException:
        try: job.terminate_and_wait()
        except BaseException as e: raise CleanupFailure('job cleanup could not be verified') from e
        raise
    return rc


class JobAccounting(ctypes.Structure):
    _fields_=[('total_user',ctypes.c_longlong),('total_kernel',ctypes.c_longlong),
              ('period_user',ctypes.c_longlong),('period_kernel',ctypes.c_longlong),
              ('page_faults',ctypes.c_uint32),('total',ctypes.c_uint32),
              ('active',ctypes.c_uint32),('terminated',ctypes.c_uint32)]


class WindowsJob:
    def __init__(self):
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.k.CreateJobObjectW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p];self.k.CreateJobObjectW.restype=ctypes.c_void_p
        self.k.AssignProcessToJobObject.argtypes=[ctypes.c_void_p,ctypes.c_void_p];self.k.AssignProcessToJobObject.restype=ctypes.c_int
        self.k.TerminateJobObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32];self.k.TerminateJobObject.restype=ctypes.c_int
        self.k.QueryInformationJobObject.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p];self.k.QueryInformationJobObject.restype=ctypes.c_int
        self.k.CloseHandle.argtypes=[ctypes.c_void_p];self.k.CloseHandle.restype=ctypes.c_int
        self.handle=self.k.CreateJobObjectW(None,None)
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
    def assign(self,process_handle):
        if not self.k.AssignProcessToJobObject(self.handle,int(process_handle)): raise ctypes.WinError(ctypes.get_last_error())
    def active(self):
        info=JobAccounting()
        if not self.k.QueryInformationJobObject(self.handle,1,ctypes.byref(info),ctypes.sizeof(info),None): raise ctypes.WinError(ctypes.get_last_error())
        return info.active
    def wait_empty(self):
        deadline=time.monotonic()+10
        while self.active():
            if time.monotonic()>=deadline: raise TimeoutError('model job still has active processes')
            time.sleep(0.1)
    def terminate_and_wait(self):
        if self.active() and not self.k.TerminateJobObject(self.handle,1): raise ctypes.WinError(ctypes.get_last_error())
        self.wait_empty()
    def close(self):
        if not self.k.CloseHandle(self.handle): raise ctypes.WinError(ctypes.get_last_error())


def resume_process(handle):
    nt=ctypes.WinDLL('ntdll');nt.NtResumeProcess.argtypes=[ctypes.c_void_p];nt.NtResumeProcess.restype=ctypes.c_long
    status=nt.NtResumeProcess(int(handle))
    if status!=0: raise OSError(f'NtResumeProcess failed: {status:#x}')


def process_affinity_masks(handle):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
    kernel.GetProcessAffinityMask.restype=ctypes.c_int
    process,system=ctypes.c_size_t(),ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(handle,ctypes.byref(process),ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    return process.value,system.value


def run_contained(command,cwd,env,stdout,stderr,timeout,*,expected_affinity_mask=None,affinity_record=None):
    job=WindowsJob();proc=None;assigned=False
    try:
        proc=subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|0x4)
        job.assign(proc._handle);assigned=True
        if expected_affinity_mask is not None:
            process_mask,system_mask=process_affinity_masks(proc._handle)
            if affinity_record is not None:
                affinity_record.append({'pid':proc.pid,'process_mask':process_mask,'system_mask':system_mask})
            if process_mask!=expected_affinity_mask:
                raise ValueError('contained child affinity mask mismatch')
        resume_process(proc._handle)
        try:
            rc=wait_for_process(proc,job,timeout);timed_out=False
        except subprocess.TimeoutExpired:
            rc=proc.wait(timeout=10);timed_out=True
        return proc.pid,rc,timed_out
    except BaseException as original:
        if isinstance(original,CleanupFailure): raise
        try:
            if assigned: job.terminate_and_wait()
            elif proc is not None:
                proc.kill();proc.wait(timeout=10)
                if proc.poll() is None: raise TimeoutError('suspended model still active')
        except BaseException as e: raise CleanupFailure('model tree cleanup could not be verified') from e
        raise
    finally:
        try: job.close()
        except BaseException as e: raise CleanupFailure('job handle close failed') from e


@contextlib.contextmanager
def reservation(path):
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,json.dumps({'pid':os.getpid(),'started':datetime.datetime.now().astimezone().isoformat()}).encode());os.close(fd)
        try: yield
        except CleanupFailure: raise
        else: path.unlink()
    except CleanupFailure: raise
    except BaseException:
        path.unlink()
        raise


def cpu_total():
    idle=ctypes.c_ulonglong();kernel=ctypes.c_ulonglong();user=ctypes.c_ulonglong()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle),ctypes.byref(kernel),ctypes.byref(user)): raise OSError('GetSystemTimes failed')
    return idle.value,kernel.value+user.value


class QuietGateTimeout(TimeoutError):
    def __init__(self,report):
        super().__init__('CPU quiet gate timed out')
        self.report=report


def quiet_gate(*,now=time.monotonic,sleep=time.sleep,read=cpu_total):
    rule=dict(QUIET_RULE);start=now();previous_time=start;previous=read();samples=[]
    while True:
        remaining=rule['max_wait_seconds']-(now()-start)
        if remaining<rule['sample_interval_seconds']:
            raise QuietGateTimeout({'status':'timeout','rule':rule,'samples':samples})
        sleep(rule['sample_interval_seconds']);end=now();current=read()
        total=current[1]-previous[1];idle=current[0]-previous[0]
        if total<=0 or idle<0 or idle>total:raise ValueError('invalid CPU usage counters')
        samples.append({'offset_s':end-start,'duration_s':end-previous_time,'cpu_pct':100*(total-idle)/total})
        previous=current;previous_time=end
        recent=samples[-rule['window_samples']:]
        if len(recent)==rule['window_samples'] and sum(x['duration_s'] for x in recent)>=rule['window_seconds']:
            values=[x['cpu_pct'] for x in recent];mean=sum(values)/len(values);maximum=max(values)
            if end-start<=rule['max_wait_seconds'] and mean<rule['mean_cpu_pct_lt'] and maximum<rule['max_cpu_pct_lt']:
                return {'status':'pass','rule':rule,'samples':samples,'selected_mean_pct':mean,'selected_max_pct':maximum}
        if end-start>=rule['max_wait_seconds']:
            raise QuietGateTimeout({'status':'timeout','rule':rule,'samples':samples})

