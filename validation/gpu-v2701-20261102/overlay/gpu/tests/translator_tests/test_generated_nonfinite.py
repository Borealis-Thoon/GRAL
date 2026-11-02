"""Inject nonfinite updates through the real translator, then execute tiny kernels."""
import argparse
import ctypes as c
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "gpu/runtime"))
from cuda_common import Cuda, I, P


def fixture(method, signature):
    helper = "public static void Corrupt(ref float value) { value=(float)Program.Value; }" if method=="Zeitschleife" else ""
    point_limit = '''if (SourceType == Consts.SourceTypePoint && auszeit < 20) {
            idt = MathF.Min(0.2F, idt);
            if (horPSExitDistance > 0 && auszeit < 3) {
                idt = MathF.Round(MathF.Max(0.01F, MathF.Min(0.2F, 0.5F / (5 + horPSPlumeVelocity))), 3);
            }
        }''' if method=='Zeitschleife' else ''
    return f'''using System;
namespace GRAL_2001 {{ partial class {method} {{
    static void {signature} {{
        double xcoord_nteil=1, ycoord_nteil=1, masse=1;
        float zcoord_nteil=1, auszeit=0, idt=0.1F;
        int timestep_number=0, FFCellX=1, FFCellY=1, IndexK=1;
        float velxold=0, velyold=0, velzold=0, ObLength=1, roughZ0=1, windge=1;
        uint m_w=1, m_z=2;
        float varw=1, eps=1, FFGridX=1;
        int SourceType=2; float horPSExitDistance=0,horPSPlumeVelocity=0;
        idt = 0.1F * varw / eps;
        {point_limit}
        float idtt = 0.5F * Math.Min(Program.GralDx, FFGridX) / (windge + MathF.Sqrt(Program.Pow2(velxold) + Program.Pow2(velyold)));
        if (idtt < idt) {{ idt = idtt; }}
        Math.Clamp(idt, 0.1F, 4F);
        ++timestep_number;
        if (Program.Case==0) xcoord_nteil += Program.Value;
        if (Program.Case==1) ycoord_nteil += Program.Value;
        if (Program.Case==2) zcoord_nteil += (float)Program.Value;
        if (Program.Case==3) auszeit += (float)Program.Value;
        if (Program.Case==4) idt = (float)Program.Value;
        // Early-return path must also fail before publishing a completed trace.
        if (Program.Case==5) {{ float unused=0; zcoord_nteil=(float)Program.Value; return; }}
        if (Program.Case==6) {{ Zeitschleife.Corrupt(ref zcoord_nteil); return; }}
        // A mutation inside a condition exercises the return guard independently.
        if (Program.Case==7) {{ if ((zcoord_nteil=(float)Program.Value)>100) return; return; }}
        if (zcoord_nteil >= 100 || xcoord_nteil >= 100 || ycoord_nteil >= 100)
            goto REMOVE_PARTICLE;
        // Records whether a storage call was reached after an invalid update.
        Program.Stored++;
        REMOVE_PARTICLE:
        return;
    }}
    {helper}
}} }}'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--translator", default=str(ROOT / "gpu/translator/Transpile.csproj"))
    args=parser.parse_args()
    report={"status":"running", "tests":[], "full_model_run":False}
    with tempfile.TemporaryDirectory(prefix="nonfinite_") as scratch:
        path=Path(scratch)
        source=path/"source"; source.mkdir()
        output=path/"generated"
        (source/"Program.cs").write_text('''namespace GRAL_2001 {
        partial class Program { public static int Case,Stored; public static double Value; public static float GralDx=1; static void Main(){} }
        class Consts { public const int SourceTypePoint=0; }
        }''', encoding="utf-8")
        (source/"ProgramFunctions.cs").write_text('namespace GRAL_2001 { partial class Program { public static float Pow2(float value) { return value*value; } } }',encoding='utf-8')
        (source/"Zeitschleife.cs").write_text(fixture("Zeitschleife","Calculate(int nteil)"),encoding="utf-8")
        (source/"Zeitschleife_nonsteadystate.cs").write_text(fixture("ZeitschleifeNonSteadyState",
            "ParticleDriver(int i,int j,int k,int SG,float TransConcentration,int splitIndex)"),encoding="utf-8")
        generated=subprocess.run(["dotnet","run","--project",args.translator,
                                  "-c","Release","--",str(source),str(output)],capture_output=True,text=True,
                                 encoding="utf-8",check=True)
        code=(output/"generated.cu").read_text(encoding="utf-8")
        code+='''
extern "C" __global__ void injection_test(int phase,int test_case,double value,int* output){
 P.DeviceError=0;P.DeviceErrorPhase=0;P.DeviceErrorParticle=0;
 P.TraceEnabled=false;P.Case=test_case;P.Value=value;P.Stored=0;P.GralDx=1;
 if(phase==1)Zeitschleife_Calculate(7);
 else ZeitschleifeNonSteadyState_ParticleDriver(1,1,1,0,1.0f,0,7);
 output[0]=P.DeviceError;output[1]=P.DeviceErrorPhase;
 output[2]=P.DeviceErrorParticle;output[3]=P.Stored;
}
'''
        cuda=Cuda()
        try:
            function,log=cuda.compile(code,"injection_test")
            report["fixture_generated_sha256"]=hashlib.sha256(code.encode()).hexdigest()
            output_ptr=cuda.buffer(16)
            for phase in (1,2):
                for case in range(8):
                    for label,value in (("finite",0.5),("nan",math.nan),("positive_infinity",math.inf),("negative_infinity",-math.inf)):
                        values=[I(phase),I(case),c.c_double(value),output_ptr]
                        pointers=(P*len(values))(*(c.cast(c.byref(v),P) for v in values))
                        cuda.check(cuda.launch(function,1,1,1,1,1,1,0,None,pointers,None),"injection kernel")
                        cuda.check(cuda.sync(),"injection synchronize")
                        result=(I*4)()
                        cuda.check(cuda.d2h(c.cast(result,P),output_ptr,16),"injection result")
                        actual=list(result)
                        want=[0,0,0,0 if case in (5,6,7) else 1] if label=="finite" else [1,phase,7,0]
                        report["tests"].append({"phase":phase,"case":case,"value":label,"actual":actual,
                                                "expected":want,"pass":actual==want})
            report["status"]="pass" if all(t["pass"] for t in report["tests"]) else "fail"
        finally:
            cuda.close()
    Path(args.report).write_text(json.dumps(report,indent=2),encoding="utf-8")
    failed=[x for x in report["tests"] if not x["pass"]]
    print(json.dumps({"status":report["status"],"tests":len(report["tests"]),"failed":len(failed),
                      "first_failure":failed[:1]}))
    return 0 if report["status"]=="pass" else 1


if __name__=="__main__":
    raise SystemExit(main())
