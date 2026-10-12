from pathlib import Path
import json,hashlib
j=Path(__file__).resolve().parent.parent
code='''using System;
using Program = ExpiryProbeProgram;
using Consts = ExpiryFixtureConstants;
using TransientConcentration = ExpiryStorageFixture;
static class ExpiryProbeProgram { public static bool ParticleStateIsFinite(double x,double y,float z,double mass,float dt) => ExitProbeProgram.Check(x,y,z,mass,dt); }
static class ExpiryFixtureConstants { public const int DepoOff=0, TransientMode=0, SourceTypePoint=0, SourceTypePortal=1, ParticleIsNotAPortal=1; }
static class ExpiryStorageFixture { public static int Calls; public static Action<int,float,float,double,double,float,double,double,int> Save; public static void Conz5dZeitschleife(int r,float z,float h,double m,double a,float dt,double x,double y,int sg) { Calls++;Save(r,z,h,m,a,dt,x,y,sg); } }
static class ExtractedTransientExpiry
{
'''
meta=[]
for v in ['warning_free_baseline','nan_guard_state']:
 t=(j/'source'/v/'src/Zeitschleife.cs').read_text('utf-8-sig')
 first=t.index('                //control dispersion time of particles')
 start=t.rfind('                if (Deposition_type > Consts.DepoOff && vsed > 0)',0,first)
 end=t.index('                //remove particles above maximum orography',first)
 block=t[start:end]
 code+=f'''    public static bool {v}(int SourceType,float zcoord_nteil,float vsed,float idt,bool expired,double masse=1)
    {{
        double xcoord_nteil=25,ycoord_nteil=25,xsi=25,eta=25,Area_cart=400;
        _ = (xcoord_nteil, ycoord_nteil);
        float auszeit=0,tgesamt=expired?.05f:100,wpHurley=0,AHint=0;
        int Deposition_type=1,ISTATIONAER=0,tunfak=1,reflexion_flag=0,SG_nteil=0;
{block}
        return true;
    REMOVE_PARTICLE:
        return false;
    }}
'''
 meta.append({'variant':v,'file':'Zeitschleife.cs','line':t[:start].count('\n')+1,'sha256':hashlib.sha256(block.encode()).hexdigest(),'production_block':block})
code+='}\n'
(j/'tests/nan_guard/ExtractedTransientExpiry.cs').write_text(code,encoding='utf-8')
(j/'qa/nan_guard_expiry_blocks.json').write_text(json.dumps({'blocks':meta,'scope':'Actual production sedimentation and transient expiry branches; selected z values represent the immediately preceding vertical update. The storage facade calls the unpatched baseline DLL store so the state patch is tested independently.'},indent=2),encoding='utf-8')
# Preserve original RNG expression for endpoint arithmetic only; this does not change the generator or prove endpoint frequency in a full run.
t=(j/'source/warning_free_baseline/src/Zeitschleife.cs').read_text('utf-8-sig')
c1='u1_rg = (u_rg + 1) * RNG_Const;'
c2='zahl1 = MathF.Sqrt(-2F * MathF.Log(u1_rg)) * MathF.Sin(Pi2F * (u_rg + 1) * RNG_Const);'
assert c1 in t and c2 in t
rng='''using System;
static class ExtractedRngEndpoint
{
    private const float Pi2F = 2F * MathF.PI;
    private const float RNG_Const = 2.328306435454494e-10F;
    public static float Normal(uint first,uint second,out float uniform)
    {
        uint u_rg=first;
        float u1_rg;
        '''+c1+'''
        uniform=u1_rg;
        u_rg=second;
        float zahl1;
        '''+c2+'''
        return zahl1;
    }
}
'''
(j/'tests/nan_guard/ExtractedRngEndpoint.cs').write_text(rng,encoding='utf-8')
(j/'qa/nan_guard_rng_expression.json').write_text(json.dumps({'source':'src/Zeitschleife.cs','expressions':[c1,c2],'scope':'Unsigned maximum endpoint arithmetic of unchanged production expressions. No claim of natural occurrence rate or changed RNG.'},indent=2),encoding='utf-8')
print('expiry_and_endpoint_blocks_written')
