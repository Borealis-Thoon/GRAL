from pathlib import Path
import hashlib,json
j=Path(__file__).resolve().parent.parent
code='''using System;
using System.Collections.Generic;
using System.Threading;
using ProgramWriters = ReportFixtureLog;
using TransientConcentration = ReportFixtureStorageCounter;
static class ReportFixtureLog { public static List<string> Lines=new(); public static void LogfileGralCoreWrite(string s) => Lines.Add(s); }
static class ReportFixtureStorageCounter { public static long NonFiniteResidualWriteCount; }
'''
records=[]
for v,field,start_token in [('nan_guard_state','NonFiniteParticleCount','long nonFiniteParticles ='),('nan_guard_storage','NonFiniteResidualWriteCount','long nonFiniteResidualWrites =')]:
 t=(j/'source'/v/'src/Program.cs').read_text('utf-8-sig')
 start=t.index('                    '+start_token)
 end=t.index('                    // Wait until conz4d file is written',start)
 block=t[start:end]
 name='StateReportProbe' if v.endswith('state') else 'StorageReportProbe'
 code+=f'''static class {name}
{{
    public static long NonFiniteParticleCount;
    public static int IWET = 17;
    public static void Run()
    {{
        string Info;
{block}
    }}
}}
'''
 records.append({'variant':v,'file':'Program.cs','line':t[:start].count('\n')+1,'sha256':hashlib.sha256(block.encode()).hexdigest(),'production_block':block})
# The storage report class has no bare state-counter reference; remove its fixture-only unused field.
code=code.replace('static class StorageReportProbe\n{\n    public static long NonFiniteParticleCount;','static class StorageReportProbe\n{')
(j/'tests/nan_guard/ExtractedReports.cs').write_text(code,encoding='utf-8')
(j/'qa/nan_guard_report_blocks.json').write_text(json.dumps({'blocks':records,'scope':'Production Program.cs Exchange/report blocks compiled in test-only storage facades; the DLL counter increment is separately exercised.'},indent=2),encoding='utf-8')
print('report_blocks_written')
