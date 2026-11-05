"""Compile a generated.cu with the runtime's NVRTC settings and report kernel resources and f64 instruction counts.

Usage: compile_check.py <folder with generated.cu> [<folder> ...]
"""
import collections
import json
import os
import re
import sys
from pathlib import Path

JOB = Path(__file__).resolve().parents[1]
os.environ.setdefault('INU_GPU_NVRTC_DIR', r'<jobs>\20261031_132339_gral_gramm_gpu_resident\work\gral_host\candidate_gpu\support\nvrtc\nvidia\cuda_nvrtc\bin')
# cuda_common.py of the former Python host (06eb66b): same NVRTC options as GpuCuda.cs; used here only to compile and load.
sys.path.insert(0, r'<jobs>\20261104_gral_gpu_pr_integration\wt_final\gpu\runtime')
import cuda_common  # noqa: E402


def ptx_counts(ptx):
    out = {}
    for chunk in re.split(r'\n(?=\.visible \.entry|\.func|\.weak \.func)', ptx):
        m = re.match(r'(?:\.visible \.entry|\.func|\.weak \.func)\s+(?:\([^)]*\)\s*)?([A-Za-z0-9_$]+)', chunk)
        if not m:
            continue
        ins = re.findall(r'^\s+([a-z][a-z0-9_.]*)\s', chunk, re.M)
        c = collections.Counter('f64' if '.f64' in i else 'f32' if '.f32' in i else 'other' for i in ins)
        out[m.group(1)] = dict(c, total=len(ins))
    return out


def main():
    cuda = cuda_common.Cuda()
    for folder in sys.argv[1:]:
        source = (Path(folder) / 'generated.cu').read_text(encoding='utf8')
        ptx, _log = cuda.compile_ptx(source)
        text = ptx.decode('utf8', 'replace')
        module = cuda.load_image(ptx)
        res = {}
        for name in ('gral_fresh', 'gral_residual'):
            fn = cuda_common.c.c_void_p()
            cuda.check(cuda.get_fn(cuda_common.c.byref(fn), module, name.encode()), 'cuModuleGetFunction')
            res[name] = cuda.function_attributes(fn)
            regs = cuda_common.c.c_int()
            cuda.check(cuda.func_attribute(cuda_common.c.byref(regs), 4, fn), 'cuFuncGetAttribute registers')
            res[name]['registers'] = regs.value
        counts = ptx_counts(text)
        print(json.dumps({'folder': folder, 'resources': res,
                          'f64': {k: v.get('f64', 0) for k, v in counts.items() if v['total'] > 1000},
                          'total': {k: v['total'] for k, v in counts.items() if v['total'] > 1000}}))
    cuda.close()


if __name__ == '__main__':
    main()
