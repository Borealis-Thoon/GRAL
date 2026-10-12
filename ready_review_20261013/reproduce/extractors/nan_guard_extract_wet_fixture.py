from pathlib import Path
import json,hashlib
j=Path(__file__).resolve().parent.parent
out='''using System;
using Program = WetProbeProgram;
static class ExtractedWetStep
{
'''
manifest=[]
for v in ['warning_free_baseline','nan_guard_state']:
 for name in ['Zeitschleife.cs','Zeitschleife_nonsteadystate.cs']:
  t=(j/'source'/v/'src'/name).read_text('utf-8-sig')
  wet=t.index('                // compute Wet deposition')
  start=t.rfind('                //decay rate',0,wet)
  end=t.index('                    masse -= epsilonW_Masse;',wet)+len('                    masse -= epsilonW_Masse;')
  block=t[start:end]
  key=v+'_'+('new' if name=='Zeitschleife.cs' else 'residual')
  out+=f'''    public static bool {key}(double masse, float idt, double decay_rate, out double remainingMass)
    {{
        double xcoord_nteil = 1, ycoord_nteil = 1;
        float zcoord_nteil = 1;
        _ = (xcoord_nteil, ycoord_nteil, zcoord_nteil);
        bool reachedWrite = false;
        if (WetProbeProgram.ForceExit) goto REMOVE_PARTICLE;
{block}
                    _ = ex;
                    reachedWrite = true;
                }}
        remainingMass = masse;
        return reachedWrite;
    REMOVE_PARTICLE:
        remainingMass = masse;
        return false;
    }}
'''
  manifest.append({'variant':v,'file':name,'start_line':t[:start].count('\n')+1,'sha256':hashlib.sha256(block.encode()).hexdigest(),'extracted_code':block})
out+='}\n'
(j/'tests/nan_guard/ExtractedWetStep.cs').write_text(out,encoding='utf-8')
(j/'qa/nan_guard_wet_blocks.json').write_text(json.dumps({'blocks':manifest,'scope':'Actual production decay and wet-loss arithmetic through the last statement preceding deposition writes, compiled with a fixture facade. No full Main deposition fault injection.'},indent=2),encoding='utf-8')
print('wet_arithmetic_prewrite_blocks_written')
