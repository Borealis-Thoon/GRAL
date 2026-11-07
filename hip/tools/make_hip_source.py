"""Write the HIP source exactly as GpuCuda.HipSource of the current pr77_hip tree builds it (for offline compiles).

Usage: make_hip_source.py <generated.cu> <out.cu>
Reads the HipAtomicAddDouble constant and the transform rules from src/GpuCuda.cs by mirroring them here; keep in sync.
"""
import re
import sys
from pathlib import Path

JOB = Path(__file__).resolve().parents[1]
cs = (JOB / 'pr77_hip' / 'src' / 'GpuCuda.cs').read_text(encoding='utf8')
m = re.search(r'private const string HipAtomicAddDouble =\s*(.*?);\s*\n', cs, re.S)
parts = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
agg = ''.join(p.encode('utf8').decode('unicode_escape') for p in parts)
src = Path(sys.argv[1]).read_text(encoding='utf8')
decl = 'extern "C" {__device__ State P;}'
assert src.count(decl) == 1
hip = (src.replace('asm("trap;")', '{atomicExch(&gral_hip_trap,1);__threadfence();__builtin_trap();}')
       .replace(decl, 'extern "C" {__constant__ State P;}')
       .replace('&P.DeviceError,', '&gral_hip_status[0],')
       .replace('P.DeviceErrorPhase=', 'gral_hip_status[1]=')
       .replace('P.DeviceErrorParticle=', 'gral_hip_status[2]=').replace('\r\n', '\n'))
assert 'P.DeviceError' not in hip
out = 'extern "C" {__device__ int gral_hip_trap=0;__device__ int gral_hip_status[3];}\n' + agg + hip
Path(sys.argv[2]).write_text(out, encoding='utf8', newline='\n')
print('written', sys.argv[2], len(out))
