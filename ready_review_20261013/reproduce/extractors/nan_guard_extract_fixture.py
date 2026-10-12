from pathlib import Path
import hashlib,json,re
j=Path(__file__).resolve().parent.parent
src=j/'source/nan_guard_state/src'
out=j/'tests/nan_guard'
blocks=[]
for name in ['Zeitschleife.cs','Zeitschleife_nonsteadystate.cs']:
 t=(src/name).read_text('utf-8-sig')
 for m in re.finditer(r'if \(!Program\.ParticleStateIsFinite',t):
  start=m.start();b=t.index('{',start);depth=1;end=b+1
  while depth:
   depth+=(t[end]=='{')-(t[end]=='}');end+=1
  blocks.append({'file':name,'line':t[:start].count('\n')+1,'code':t[start:end]})
t=(src/'Zeitschleife_nonsteadystate.cs').read_text('utf-8-sig')
start=t.index('            // Add local receptor concentrations to receptor array',t.index('        REMOVE_PARTICLE:'))
end=t.index('            return;',start)
cleanup=t[start:end]
source='''using System;
using System.Collections.Generic;
using System.Threading;
using Program = ExitProbeProgram;
static class ExtractedParticleExit
{
'''
for i,block in enumerate(blocks):
 source+=f'''    public static bool Guard_{i}(double xcoord_nteil, double ycoord_nteil, float zcoord_nteil, double masse, float idt, double mass_real)
    {{
        bool continued = false;
        int SG_nteil = 0;
        double[] ReceptorConcentration = {{ 0, .25, 1.5 }};
        double epsilonW_Masse = masse;
        {block['code']}
        continued = true;
    REMOVE_PARTICLE:
{cleanup}
        return continued;
    }}
'''
source+='    public static bool HasTimeStepGuard(int i) => new bool[]{' + ','.join('true' if ', idt)' in b['code'] else 'false' for b in blocks) + '}[i];\n}\n'
(out/'ExtractedParticleExit.cs').write_text(source,encoding='utf-8')
for b in blocks:b['sha256']=hashlib.sha256(b['code'].encode()).hexdigest()
(j/'qa/nan_guard_extracted_blocks.json').write_text(json.dumps({'guard_block_count':len(blocks),'source_blocks':blocks,'receptor_cleanup_sha256':hashlib.sha256(cleanup.encode()).hexdigest(),'scope':'Actual production branch and receptor exit blocks compiled with a fixture facade bound to the candidate DLL helper. This is component control-flow validation, not a full tracking run.'},indent=2),encoding='utf-8')
(out/'NaNGuardFixture.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><Optimize>true</Optimize><Nullable>disable</Nullable><TreatWarningsAsErrors>true</TreatWarningsAsErrors></PropertyGroup></Project>',encoding='utf-8')
print('guard_blocks',len(blocks))
