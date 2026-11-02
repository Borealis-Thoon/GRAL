"""Compile the actual V2701 output and run only small ABI/seed/CSR kernels."""
import argparse
import ctypes as c
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "gpu/runtime"
sys.path.insert(0, str(RUNTIME))
import server
from cuda_common import Cuda, D, I, P, Z


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--nvrtc-log")
    args = parser.parse_args()
    reference = subprocess.run([
        "dotnet", "run", "--project", str(Path(__file__).with_name("SeedReference.csproj")),
        "-c", "Release", "--", str(ROOT / "src/bin/Release/net10.0/GRAL.dll")
    ], capture_output=True, text=True, encoding="utf-8", check=True)
    fixtures = json.loads(reference.stdout.strip())
    fields = server.State._fields_
    abi = "out[0]=sizeof(State);" + "".join(
        f"out[{q+1}]=(unsigned long long)((char*)&P.{name}-(char*)&P);"
        for q, (name, _) in enumerate(fields))
    tests = '''
extern "C" __global__ void test_abi(unsigned long long* out){ABI}
extern "C" __global__ void test_seed(int i,int j,int k,int sg,int split,unsigned int* out){
 unsigned int w=P.RnGSeed1+(unsigned int)(i+j),z=P.RnGSeed2+(unsigned int)(2*i);
 ZeitschleifeNonSteadyState_ResidualSeeds(i,j,k,sg,split,w,z);out[0]=w;out[1]=z;
}
extern "C" __global__ void test_csr(int* out){
 Arr<int,1> r{};
 out[0]=GridCellLookup(0,0,r);out[1]=GridCellLookup(0,1,r);
 out[2]=r.d[0];out[3]=r[0];out[4]=r[1];
 out[5]=GridCellLookup(1,0,r);out[6]=r[0];
 out[7]=GridCellLookup(1,1,r);out[8]=GridCellLookup(-1,0,r);
 out[9]=GridCellLookup(0,2,r);out[10]=GridCellLookup(2,0,r);
}
extern "C" __global__ void test_abort(int* out){
 out[0]=CheckParticleFinite(1,2,3,4,0.1f,1,5);
 out[1]=CheckParticleFinite(1,2,3,4,__int_as_float(0x7fc00000),2,17);
 out[2]=CheckParticleFinite(1,2,3,4,__int_as_float(0x7f800000),1,99);
 out[3]=P.DeviceError;out[4]=P.DeviceErrorPhase;out[5]=P.DeviceErrorParticle;
}
'''.replace("ABI", abi)
    source = (RUNTIME / "generated.cu").read_text(encoding="utf-8") + tests
    cuda = Cuda()
    report = {"status": "running", "particle_kernels_launched": False}
    try:
        fn, log = cuda.compile(source, "test_abi")
        if args.nvrtc_log: Path(args.nvrtc_log).write_text(log, encoding="utf-8")
        module = cuda.modules[-1]
        address, size = D(), Z()
        get_global = cuda.cuda.cuModuleGetGlobal_v2
        get_global.argtypes = [c.POINTER(D), c.POINTER(Z), P, c.c_char_p]
        get_global.restype = I
        cuda.check(get_global(c.byref(address), c.byref(size), module, b"P"), "State address")
        assert size.value == c.sizeof(server.State), (size.value, c.sizeof(server.State))
        output = cuda.buffer(max((len(fields)+1)*8, 64))

        def launch(function, arguments, array_type):
            values = (P * len(arguments))(*(c.cast(c.byref(x), P) for x in arguments))
            cuda.check(cuda.launch(function,1,1,1,1,1,1,0,None,values,None), "test kernel")
            cuda.check(cuda.sync(), "test synchronize")
            values = array_type()
            cuda.check(cuda.d2h(c.cast(values,P),output,c.sizeof(values)), "test output")
            return list(values)

        actual = launch(fn,[output],c.c_uint64*(len(fields)+1))
        expected = [c.sizeof(server.State)] + [getattr(server.State,n).offset for n,_ in fields]
        assert actual == expected, [(q,a,b) for q,(a,b) in enumerate(zip(actual,expected)) if a!=b]
        report["state_bytes"] = actual[0]
        report["field_offsets_checked"] = len(fields)
        state = server.State()
        seed_fn, csr_fn = P(), P()
        cuda.check(cuda.get_fn(c.byref(seed_fn),module,b"test_seed"), "seed kernel")
        cuda.check(cuda.get_fn(c.byref(csr_fn),module,b"test_csr"), "CSR kernel")
        for entry in fixtures:
            hour,i,j,k,sg,split,w,z = entry["fixture"]
            state.IWET, state.RnGSeed1, state.RnGSeed2 = hour,w,z
            cuda.check(cuda.h2d(address,c.cast(c.byref(state),P),c.sizeof(state)), "seed state")
            actual = launch(seed_fn,[I(i),I(j),I(k),I(sg),I(split),output],c.c_uint*2)
            assert actual == entry["seeds"], (entry,actual)
        report["seed_fixtures"] = fixtures
        start, values = (I*5)(0,0,2,3,3), (I*3)(7,3,2)
        start_ptr, list_ptr = cuda.buffer(c.sizeof(start)),cuda.buffer(c.sizeof(values))
        cuda.check(cuda.h2d(start_ptr,c.cast(start,P),c.sizeof(start)), "CSR starts")
        cuda.check(cuda.h2d(list_ptr,c.cast(values,P),c.sizeof(values)), "CSR list")
        state.GridRecRow=2
        state.GridRecStart.p=start_ptr.value; state.GridRecStart.d[0]=5
        state.GridRecList.p=list_ptr.value; state.GridRecList.d[0]=3
        cuda.check(cuda.h2d(address,c.cast(c.byref(state),P),c.sizeof(state)), "CSR state")
        actual = launch(csr_fn,[output],I*11)
        assert actual == [0,1,2,7,3,1,2,0,0,0,0], actual
        report["csr_empty_order_bounds"] = actual
        abort_fn = P()
        cuda.check(cuda.get_fn(c.byref(abort_fn),module,b"test_abort"), "abort kernel")
        actual = launch(abort_fn,[output],I*6)
        assert actual == [1,0,0,1,2,17], actual
        report["nonfinite_abort_first_error_retained"] = actual
        report["status"] = "pass"
        report["generated_sha256"] = hashlib.sha256((RUNTIME/"generated.cu").read_bytes()).hexdigest()
    finally:
        cuda.close()
        Path(args.report).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "seed_fixtures"}))


if __name__ == "__main__":
    main()
