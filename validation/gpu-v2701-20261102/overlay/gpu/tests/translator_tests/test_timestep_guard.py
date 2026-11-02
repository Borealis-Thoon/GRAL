"""Exercise the original time-step calculation and limiter through the translator."""
import argparse
import ctypes as c
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

from test_generated_nonfinite import ROOT, fixture
sys.path.insert(0,str(ROOT/'gpu/runtime'))
from cuda_common import Cuda,I,P


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--translator',default=str(ROOT/'gpu/translator/Transpile.csproj'))
    parser.add_argument('--report',required=True)
    parser.add_argument('--check-anchors',action='store_true')
    args=parser.parse_args()
    report={'status':'running','tests':[],'full_model_run':False,'anchor_rejections':[]}
    with tempfile.TemporaryDirectory(prefix='timestep_') as scratch:
        work=Path(scratch);source=work/'source';source.mkdir();output=work/'output'
        (source/'Program.cs').write_text('''namespace GRAL_2001 { partial class Program {
        public static int Case,Stored; public static double Value;
        public static float GralDx,Variance,Epsilon,Wind,FinalIdt;
        static void Main(){} } class Consts { public const int SourceTypePoint=0; } }''',encoding='utf-8')
        (source/'ProgramFunctions.cs').write_text('namespace GRAL_2001 { partial class Program { public static float Pow2(float v) { return v*v; } } }',encoding='utf-8')
        for name,method,signature in [('Zeitschleife.cs','Zeitschleife','Calculate(int nteil)'),
                ('Zeitschleife_nonsteadystate.cs','ZeitschleifeNonSteadyState','ParticleDriver(int i,int j,int k,int SG,float TransConcentration,int splitIndex)')]:
            text=fixture(method,signature).replace('float varw=1, eps=1, FFGridX=1;',
                'float varw=Program.Variance, eps=Program.Epsilon, FFGridX=1;')
            text=text.replace('roughZ0=1, windge=1;','roughZ0=1, windge=Program.Wind;')
            text=text.replace('Program.Stored++;','Program.FinalIdt=idt; Program.Stored++;')
            (source/name).write_text(text,encoding='utf-8')
        command=['dotnet','run','--project',args.translator,'-c','Release','--',str(source),str(output)]
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        generated=(output/'generated.cu').read_text(encoding='utf-8')
        kernel='''
extern "C" __global__ void timestep_test(int phase,float variance,float epsilon,float wind,int* output){
 P.DeviceError=0;P.DeviceErrorPhase=0;P.DeviceErrorParticle=0;P.TraceEnabled=false;
 P.Case=-1;P.Stored=0;P.Value=0;P.GralDx=1;P.Variance=variance;P.Epsilon=epsilon;P.Wind=wind;P.FinalIdt=-999;
 if(phase==1)Zeitschleife_Calculate(7);
 else ZeitschleifeNonSteadyState_ParticleDriver(1,1,1,0,1.0f,0,7);
 output[0]=P.DeviceError;output[1]=P.DeviceErrorPhase;output[2]=P.DeviceErrorParticle;
 output[3]=P.Stored;output[4]=__float_as_int(P.FinalIdt);
}
'''
        cases=[('positive_inf_recovers',1,0,1,0.5),('zero_div_zero_rejected',0,0,1,None),
               ('persistent_inf_rejected',1,0,0,None),('finite_raw_inf_limit',1,1,0,0.1),
               ('finite_raw_finite_limit',1,1,1,0.1),('nan_limit_leaves_inf',1,0,math.nan,None),
               ('nan_raw_rejected',1,math.nan,1,None),('ignored_clamp_preserved',1000,1,0,100.0)]
        cuda=Cuda()
        try:
            function,log=cuda.compile(generated+kernel,'timestep_test');out=cuda.buffer(20)
            for phase in (1,2):
                for label,varw,eps,wind,expected in cases:
                    values=[I(phase),c.c_float(varw),c.c_float(eps),c.c_float(wind),out]
                    pointers=(P*len(values))(*(c.cast(c.byref(v),P) for v in values))
                    cuda.check(cuda.launch(function,1,1,1,1,1,1,0,None,pointers,None),'timestep fixture')
                    cuda.check(cuda.sync(),'timestep fixture synchronize')
                    actual=(I*5)();cuda.check(cuda.d2h(c.cast(actual,P),out,20),'timestep fixture result')
                    expected_prefix=[1,phase,7,0] if expected is None else [0,0,0,1]
                    passed=list(actual)[:4]==expected_prefix
                    if expected is not None:passed &= actual[4]==struct.unpack('<i',struct.pack('<f',expected))[0]
                    report['tests'].append({'phase':phase,'case':label,'actual':list(actual),'pass':passed})
        finally:
            cuda.close()
        if args.check_anchors:
            path=source/'Zeitschleife.cs';original=path.read_text(encoding='utf-8')
            for label,old,new in [('missing_clamp','Math.Clamp(idt, 0.1F, 4F);',''),
                ('changed_clamp','Math.Clamp(idt, 0.1F, 4F);','Math.Clamp(idt, 0.1F, 5F);'),
                ('reversed_limiter','if (idtt < idt)','if (idtt > idt)'),
                ('extra_write','Math.Clamp(idt, 0.1F, 4F);','idt=1; Math.Clamp(idt, 0.1F, 4F);')]:
                assert old in original
                path.write_text(original.replace(old,new),encoding='utf-8')
                rejected=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
                report['anchor_rejections'].append({'mutation':label,'pass':rejected.returncode!=0 and 'time-step' in rejected.stderr})
            path.write_text(original,encoding='utf-8')
        report['status']='pass' if all(t['pass'] for t in report['tests']+report['anchor_rejections']) else 'fail'
    Path(args.report).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'tests':len(report['tests']),
        'failed':[t['case'] for t in report['tests'] if not t['pass']], 'anchor_rejections':report['anchor_rejections']}))
    return 0 if report['status']=='pass' else 1


if __name__=='__main__':raise SystemExit(main())
