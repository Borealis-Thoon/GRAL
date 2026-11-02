"""Compile actual source expressions, compare binary32 bits, optionally test CUDA expressions."""
import argparse
import ctypes as c
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
ANALYSIS=json.loads(Path(__file__).with_name('rng_sites.json').read_text(encoding='utf-8'))
RUNTIME=ROOT/'gpu/runtime'
BOUNDARIES=[0,1,16777215,16777216,16777217,16777218,33554433,4294967167,4294967168,4294967294,4294967295]


def statements():
    cases=[]
    unchanged={}
    for relative,lines in ANALYSIS['gaussian_log_assignment_lines'].items():
        path=ROOT/relative
        current_bytes=path.read_bytes()
        baseline_bytes=current_bytes.replace(b'u1_rg = u_rg == uint.MaxValue ? 1.0F : ',b'u1_rg = ')
        normalized=baseline_bytes.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode('utf-8')
        assert hashlib.sha256(normalized).hexdigest()==ANALYSIS['baseline_normalized_sha256'][relative], 'Unexpected source changes: '+relative
        current=current_bytes.decode('utf-8-sig').splitlines()
        baseline=baseline_bytes.decode('utf-8-sig').splitlines()
        restored=current_bytes
        for line in lines:
            statement=current[line-1].strip()
            old=baseline[line-1].strip()
            assert statement.startswith('u1_rg = ') and old.startswith('u1_rg = ')
            cases.append({'file':path.name,'line':line,'current':statement,'baseline':old})
        # Only this exact conditional prefix may differ anywhere in the files.
        restored=restored.replace(b'u1_rg = u_rg == uint.MaxValue ? 1.0F : ',b'u1_rg = ')
        assert restored==baseline_bytes, 'Unexpected source changes: '+relative
        for line in ANALYSIS['exclude_non_log_uniform_lines'][relative]:
            assert current[line-1]==baseline[line-1], 'Non-log uniform changed'
        unchanged[relative]={'baseline_normalized_sha256':hashlib.sha256(normalized).hexdigest(),
                             'current_sha256':hashlib.sha256(current_bytes).hexdigest(),
                             'other_bytes_unchanged':True}
    assert len(cases)==31
    return cases,unchanged


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',required=True)
    parser.add_argument('--cuda',action='store_true')
    args=parser.parse_args()
    cases,unchanged=statements()
    inputs=BOUNDARIES[:]
    sample=0xA341316C
    for _ in range(4096):
        sample=(1664525*sample+1013904223)&0xffffffff
        inputs.append(sample)
    report={'status':'running','sites':len(cases),'inputs':len(inputs),'source_checks':unchanged,
            'excluded_non_log_uniform_sites':4,'full_model_run':False,'cuda_executed':False}
    with tempfile.TemporaryDirectory(prefix='expression_') as scratch:
        work=Path(scratch)
        (work/'Inputs.json').write_text(json.dumps(inputs),encoding='utf-8')
        (work/'Check.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup></Project>',encoding='utf-8')
        methods='\n'.join(f'static float Current{i}(uint u_rg){{float u1_rg;{entry["current"]}return u1_rg;}}\n'
                          f'static float Baseline{i}(uint u_rg){{float u1_rg;{entry["baseline"]}return u1_rg;}}'
                          for i,entry in enumerate(cases))
        source='''using System.Text.Json;
class Check {
const float RNG_Const=2.328306435454494e-10F;
METHODS
static int Main(string[] args){
 uint[] inputs=JsonSerializer.Deserialize<uint[]>(File.ReadAllText(args[0]))!;
 Func<uint,float>[] current={CURRENT};Func<uint,float>[] baseline={BASELINE};
 var bad=new List<object>();var bits=new int[inputs.Length*current.Length];int changed=0;
 for(int site=0;site<current.Length;site++)for(int row=0;row<inputs.Length;row++){
  uint u=inputs[row];float value=current[site](u),old=baseline[site](u);
  int actual=BitConverter.SingleToInt32Bits(value),previous=BitConverter.SingleToInt32Bits(old);
  bits[site*inputs.Length+row]=actual;
  int expected=u==uint.MaxValue?0x3f800000:previous;
  bool radiusFinite=float.IsFinite(MathF.Sqrt(-2F*MathF.Log(value)));
  if(actual!=previous)changed++;
  if((actual!=expected || !radiusFinite) && bad.Count<64)bad.Add(new{site,u,actual,expected,radiusFinite});
 }
 uint counterexample=16777217;float premature=(counterexample+1F)*RNG_Const;
 bool sensitive=BitConverter.SingleToInt32Bits(premature)!=BitConverter.SingleToInt32Bits(baseline[0](counterexample));
 byte[] bytes=new byte[bits.Length*4];Buffer.BlockCopy(bits,0,bytes,0,bytes.Length);File.WriteAllBytes(args[1],bytes);
 Console.WriteLine(JsonSerializer.Serialize(new{status=bad.Count==0 && sensitive?"pass":"fail",checked_values=bits.Length,
 changed_values=changed,premature_rounding_counterexample_detected=sensitive,failures=bad}));
 return bad.Count==0 && sensitive?0:1;
}}
'''.replace('METHODS',methods).replace('CURRENT',','.join(f'Current{i}' for i in range(31))).replace('BASELINE',','.join(f'Baseline{i}' for i in range(31)))
        (work/'Program.cs').write_text(source,encoding='utf-8')
        result=subprocess.run(['dotnet','run','--project',str(work/'Check.csproj'),'-c','Release','--',str(work/'Inputs.json'),str(work/'bits.bin')],capture_output=True,text=True,encoding='utf-8')
        if result.returncode not in (0,1) or not result.stdout.strip().startswith('{'):
            raise RuntimeError(result.stdout+result.stderr)
        report['csharp']=json.loads(result.stdout)
        report['status']=report['csharp']['status']
        if args.cuda:
            sys.path.insert(0,str(RUNTIME))
            from cuda_common import Cuda,D,I,P
            generated=(RUNTIME/'generated.cu').read_text(encoding='utf-8')
            expressions=re.findall(r'u1_rg_\d+ = (u_rg_\d+ == \(4294967295u\) \? 1\.0F : [^;]+);',generated)
            assert len(expressions)==31, ('Generated guarded sites',len(expressions))
            expressions=[re.sub(r'\bu_rg_\d+\b','u_rg',expr) for expr in expressions]
            switch=''.join(f'case {site}:value={expression};break;' for site,expression in enumerate(expressions))
            kernel='''
extern "C" __global__ void rng_expression_test(const unsigned int* inputs,int count,int* output){
 int q=blockIdx.x*blockDim.x+threadIdx.x;if(q>=31*count)return;
 int site=q/count;unsigned int u_rg=inputs[q%count];float value=0;
 switch(site){SWITCH}output[q]=__float_as_int(value);
}
'''.replace('SWITCH',switch)
            cuda=Cuda()
            try:
                function,log=cuda.compile(generated+kernel,'rng_expression_test')
                cpu_bits=(work/'bits.bin').read_bytes()
                array=(c.c_uint*len(inputs))(*inputs)
                in_ptr=cuda.buffer(c.sizeof(array));out_ptr=cuda.buffer(len(cpu_bits))
                cuda.check(cuda.h2d(in_ptr,c.cast(array,P),c.sizeof(array)),'RNG inputs')
                arguments=[in_ptr,I(len(inputs)),out_ptr]
                pointers=(P*len(arguments))(*(c.cast(c.byref(v),P) for v in arguments))
                cuda.check(cuda.launch(function,(len(cpu_bits)//4+127)//128,1,1,128,1,1,0,None,pointers,None),'RNG expression kernel')
                cuda.check(cuda.sync(),'RNG expression synchronize')
                output=(c.c_byte*len(cpu_bits))()
                cuda.check(cuda.d2h(c.cast(output,P),out_ptr,len(cpu_bits)),'RNG outputs')
                report['cuda_executed']=True
                report['cuda_bits_match_csharp']=bytes(output)==cpu_bits
                report['generated_guarded_sites']=len(expressions)
                report['generated_sha256']=hashlib.sha256((RUNTIME/'generated.cu').read_bytes()).hexdigest()
                if bytes(output)!=cpu_bits:report['status']='fail'
            finally:
                cuda.close()
    Path(args.report).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'sites':31,'inputs':len(inputs),
                      'csharp_values':report['csharp']['checked_values'],'csharp_failures':len(report['csharp']['failures']),
                      'cuda_executed':report['cuda_executed'],'cuda_bits_match_csharp':report.get('cuda_bits_match_csharp')}))
    return 0 if report['status']=='pass' else 1


if __name__=='__main__':
    raise SystemExit(main())
