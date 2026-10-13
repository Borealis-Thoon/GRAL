from pathlib import Path
import argparse, difflib, hashlib, json, os, shutil, subprocess, sys, time

ROOT=Path(__file__).resolve().parent
JOB=ROOT.parents[1]
QA=JOB/'qa'/'probe'
VARIANTS=['float','double','dictionary_fixed']
DOTNET=Path(r'C:\Program Files\dotnet\dotnet.exe')

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def sha(raw):return hashlib.sha256(raw).hexdigest()

def files(root):
    return {p.relative_to(root).as_posix():p for p in sorted((root/'src').glob('*')) if p.is_file() and p.suffix in ('.cs','.csproj')}

def lock(root):return {name:sha(p.read_bytes()) for name,p in files(root).items()}

def replace_once(text,old,new):
    assert text.count(old)==1,('replacement marker count',old[:100],text.count(old))
    return text.replace(old,new)

def helper(variant):
    is_dictionary=variant=='dictionary_fixed'
    counts='''r["dictionary_central_count"] = Program.Concentration2D.Count;
            r["dictionary_plus_count"] = Program.Concentration2D_P.Count;
            r["dictionary_minus_count"] = Program.Concentration2D_M.Count;''' if is_dictionary else '''r["dictionary_central_count"] = null;
            r["dictionary_plus_count"] = null;
            r["dictionary_minus_count"] = null;'''
    return '''// Diagnostic-only instrumentation; not a proposed engine patch.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Threading;
namespace GRAL_2001
{
    internal static class ConcentrationProbe
    {
        private static long conversionTicks;
        private static long conversionCalls;
        private static long[] conversionTicksByKind = new long[3];
        private static long[] conversionCallsByKind = new long[3];
        private static readonly object LogLock = new object();
        internal static long BeginWriter(int weather)
        {
            conversionTicks = 0;
            conversionCalls = 0;
            Array.Clear(conversionTicksByKind);
            Array.Clear(conversionCallsByKind);
            Snapshot("before_writer", weather, null);
            return Stopwatch.GetTimestamp();
        }
        internal static void EndWriter(int weather, long start)
        {
            long elapsed = Stopwatch.GetTimestamp() - start;
            var extra = new Dictionary<string, object>();
            extra["writer_seconds"] = elapsed / (double)Stopwatch.Frequency;
            extra["conversion_seconds"] = conversionTicks / (double)Stopwatch.Frequency;
            extra["conversion_calls"] = conversionCalls;
            extra["conversion_seconds_by_kind"] = new double[] {conversionTicksByKind[0] / (double)Stopwatch.Frequency, conversionTicksByKind[1] / (double)Stopwatch.Frequency, conversionTicksByKind[2] / (double)Stopwatch.Frequency};
            extra["conversion_calls_by_kind"] = conversionCallsByKind;
            Snapshot("after_writer", weather, extra);
        }
        internal static void EndConversion(long start, int kind)
        {
            long elapsed = Stopwatch.GetTimestamp() - start;
            Interlocked.Add(ref conversionTicks, elapsed);
            Interlocked.Increment(ref conversionCalls);
            Interlocked.Add(ref conversionTicksByKind[kind], elapsed);
            Interlocked.Increment(ref conversionCallsByKind[kind]);
        }
        internal static void Snapshot(string stage, int weather, Dictionary<string, object> extra)
        {
            var r = new Dictionary<string, object>();
            r["variant"] = "''' + variant + '''";
            r["stage"] = stage;
            r["weather"] = weather;
            r["groups"] = Program.SourceGroups.Count;
            r["slices"] = Program.NS;
            r["nx"] = Program.NXL;
            r["ny"] = Program.NYL;
            r["logical_output_slots"] = (long)Program.SourceGroups.Count * Program.NS * Program.NXL * Program.NYL;
            r["group_slice_files"] = (long)Program.SourceGroups.Count * Program.NS;
            r["odour"] = Program.Odour;
            r["managed_bytes_no_collection"] = GC.GetTotalMemory(false);
            r["allocated_bytes_approx_cumulative"] = GC.GetTotalAllocatedBytes(false);
            r["gc_collections"] = new int[] { GC.CollectionCount(0), GC.CollectionCount(1), GC.CollectionCount(2) };
            using (var process = Process.GetCurrentProcess())
            {
                process.Refresh();
                r["working_set_bytes"] = process.WorkingSet64;
                r["private_bytes"] = process.PrivateMemorySize64;
            }
            ''' + counts + '''
            if (extra != null) foreach (var pair in extra) r[pair.Key] = pair.Value;
            lock (LogLock) File.AppendAllText("concentration_probe.jsonl", JsonSerializer.Serialize(r) + Environment.NewLine);
        }
    }
}
'''

def prepare():
    QA.mkdir(parents=True,exist_ok=True)
    authoritative=json.loads((JOB/'qa/source_lock.json').read_text())['variants']
    records={}
    for variant in VARIANTS:
        source=JOB/'work'/variant
        if not source.exists():source=JOB/'work'/'restored'/variant
        target=ROOT/'source'/variant
        assert not target.exists(),target
        originals={name:p.read_bytes() for name,p in files(source).items()}
        if variant in authoritative:
            expected=authoritative[variant]['sources']
            normalized={name:sha(raw) for name,raw in originals.items() if name in expected}
            assert normalized==expected,('source lock mismatch',variant)
        target.mkdir(parents=True)
        for name,raw in originals.items():
            p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        p=target/'src/Program.cs';s=p.read_text(encoding='utf-8-sig')
        marker='                    RnGSeed = new DeterministicRandomGenerator(IWET, WindVelGral, WindDirGral);'
        s=replace_once(s,marker,'                    ConcentrationProbe.Snapshot("before_dispersion", IWET, null);\n'+marker)
        old='ThreadWrite2DConcentrationFiles = new Thread(() => WriteClass.Write2DConcentrations(recentWeatherSituation, ZippedFile));'
        new='''ThreadWrite2DConcentrationFiles = new Thread(() =>
                    {
                        long probeWriterStart = ConcentrationProbe.BeginWriter(recentWeatherSituation);
                        try { WriteClass.Write2DConcentrations(recentWeatherSituation, ZippedFile); }
                        finally { ConcentrationProbe.EndWriter(recentWeatherSituation, probeWriterStart); }
                    });'''
        s=replace_once(s,old,new);p.write_text(s,encoding='utf-8-sig',newline='\n')
        if variant=='dictionary_fixed':
            p=target/'src/Write2DConcentrations.cs';s=p.read_text(encoding='utf-8-sig')
            marker='        private static void ConvertFromDictionaryToArray('
            start=s.index(marker);left=s.index('{',start);depth=1;right=left+1
            while depth:
                if s[right]=='{':depth+=1
                elif s[right]=='}':depth-=1
                right+=1
            old=s[left+1:right-1]
            lead='''
            int probeKind = object.ReferenceEquals(Concentration, Program.Concentration2D) ? 0 : object.ReferenceEquals(Concentration, Program.Concentration2D_P) ? 1 : 2;
            long probeConversionStart = System.Diagnostics.Stopwatch.GetTimestamp();
            try
            {'''
            end='''
            }
            finally { ConcentrationProbe.EndConversion(probeConversionStart, probeKind); }
        '''
            s=s[:left+1]+lead+old+end+s[right-1:];p.write_text(s,encoding='utf-8-sig',newline='\n')
        (target/'src/ConcentrationProbe.cs').write_text(helper(variant),encoding='utf-8',newline='\n')
        patches=[]
        for name,p in files(target).items():
            before=originals.get(name,b'').decode('utf-8-sig').replace('\r\n','\n')
            after=p.read_text(encoding='utf-8-sig')
            if before!=after:patches.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
        patch=''.join(patches);(QA/(variant+'.instrumentation.patch')).write_text(patch,encoding='utf-8',newline='\n')
        records[variant]=dict(source_original_bytes={name:sha(raw) for name,raw in originals.items()},instrumented_bytes=lock(target),instrumentation_patch_sha256=sha(patch.encode()),diagnostic_only=True)
    save(QA/'source_lock.json',records)
    save(QA/'plan.json',dict(stage='prepared_not_built',variants=VARIANTS,diagnostic_only=True,writer_timing='Whole Write2DConcentrations call including output, array clear and dictionary reset; excludes snapshot collection and JSON log.',conversion_timing='Clear of temporary float[][] plus full dictionary enumeration and matching-key transfer, accumulated over calls; timer overhead is present.',counts='ConcurrentDictionary.Count before dispersion and before writer; counts reflect stored keys including any zero-valued entry, not count of nonzero output cells.',occupancy_denominator='SourceGroups.Count * NS * NXL * NYL, separately for central/plus/minus dictionaries.',memory='Snapshots of GC.GetTotalMemory(false), GC.GetTotalAllocatedBytes(false), GC.CollectionCount(0/1/2), working set and private bytes without forced GC. Allocation and collection deltas are reported for before_dispersion-to-before_writer and before_writer-to-after_writer; allocation estimates include the diagnostic snapshots/logging. Uninstrumented native benchmark is performance authority.',before_dispersion='After flow-field work and prior particle transport for that weather situation.'))
    print('[PREPARED]',len(records),'variants; no build or model run')

def environment():
    env=os.environ.copy();(ROOT/'tmp').mkdir(exist_ok=True)
    env.update(DOTNET_CLI_HOME=str(ROOT/'cache'),TEMP=str(ROOT/'tmp'),TMP=str(ROOT/'tmp'),DOTNET_CLI_UI_LANGUAGE='en')
    return env

def verify_source(variant):
    expected=json.loads((QA/'source_lock.json').read_text())[variant]['instrumented_bytes']
    assert lock(ROOT/'source'/variant)==expected,('instrumented source changed',variant)

def build(variants):
    records=[]
    for variant in variants:
        verify_source(variant)
        target=ROOT/'source'/variant
        r=subprocess.run([str(DOTNET),'build',str(target/'src/GRAL.csproj'),'-c','Release','--nologo','-v:minimal','/p:TreatWarningsAsErrors=true'],capture_output=True,env=environment(),timeout=120)
        text=(r.stdout+r.stderr).decode('utf-8',errors='replace');(QA/('build_'+variant+'.log')).write_text(text,encoding='utf-8')
        assert r.returncode==0 and '0 Warning(s)' in text and '0 Error(s)' in text,text[-5000:]
        dll=target/'src/bin/Release/net10.0/GRAL.dll';records.append(dict(variant=variant,exit_code=r.returncode,dll_sha256=sha(dll.read_bytes())))
        print('[BUILD]',variant,flush=True)
    save(QA/'builds.json',records)

def run(variants,input_dir,tag,timeout):
    sys.path.insert(0,str(JOB/'work'/'benchmark'))
    import field_support as f
    f.DOTNET=DOTNET
    assert input_dir.is_dir(),input_dir
    case=json.loads((input_dir/'case.json').read_text())
    out=ROOT/'results'/tag;out.mkdir(parents=True,exist_ok=False)
    all_records=[];start=time.perf_counter()
    for variant in variants:
        verify_source(variant)
        dll=ROOT/'source'/variant/'src/bin/Release/net10.0/GRAL.dll';assert dll.is_file(),dll
        d=out/variant;shutil.copytree(input_dir,d)
        assert not (d/'concentration_probe.jsonl').exists()
        rec=f.process(dll,d,environment(),min(timeout,max(1,840-(time.perf_counter()-start))))
        core=(d/'Logfile_GRALCore.txt').read_text(encoding='utf-8-sig',errors='replace');problem=d/'Problemreport_GRAL.txt'
        assert rec['exit_code']==0 and 'GRAL simulations finished at:' in core and not(problem.exists() and problem.read_text().strip()),(variant,rec)
        snapshots=[json.loads(s) for s in (d/'concentration_probe.jsonl').read_text().splitlines()]
        expected=3*case.get('situations',1);assert len(snapshots)==expected,(variant,len(snapshots),expected)
        for r in snapshots:
            assert r['logical_output_slots']==case['sg']*case['slices']*case['nx']*case['ny']
        before={r['weather']:r for r in snapshots if r['stage']=='before_writer'}
        dispersion={r['weather']:r for r in snapshots if r['stage']=='before_dispersion'}
        for r in snapshots:
            if r['stage'] in ('before_writer','after_writer'):
                first=dispersion[r['weather']] if r['stage']=='before_writer' else before[r['weather']]
                r['interval_from_stage']=first['stage']
                r['interval_allocated_bytes_approx']=r['allocated_bytes_approx_cumulative']-first['allocated_bytes_approx_cumulative']
                r['interval_gc_collections']=[a-b for a,b in zip(r['gc_collections'],first['gc_collections'])]
            if r['stage']=='before_writer' and r['dictionary_central_count'] is not None:
                r['central_stored_key_fraction']=r['dictionary_central_count']/r['logical_output_slots']
            if r['stage']=='after_writer' and variant=='dictionary_fixed':
                b=before[r['weather']]
                counts=[b['dictionary_central_count'],b['dictionary_plus_count'],b['dictionary_minus_count']]
                r['estimated_entries_visited']=sum(c*k for c,k in zip(counts,r['conversion_calls_by_kind']))
                r['conversion_fraction_of_writer']=r['conversion_seconds']/r['writer_seconds']
        record=dict(variant=variant,case=case['id'],whole_process_diagnostic=rec,snapshots=snapshots,input_sha256={p.name:sha(p.read_bytes()) for p in sorted(input_dir.iterdir()) if p.is_file()},dll_sha256=sha(dll.read_bytes()))
        all_records.append(record);save(QA/(tag+'.progress.json'),dict(records=all_records));print('[PROBE]',variant,case['id'],round(rec['wall_s'],3),flush=True)
    save(QA/(tag+'.json'),dict(status='pass',purpose='diagnostic attribution only; not native benchmark timing',case=case,records=all_records))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','build','run']);p.add_argument('--variants',nargs='+',choices=VARIANTS,default=VARIANTS);p.add_argument('--input-dir',type=Path);p.add_argument('--tag',default='diagnostic');p.add_argument('--timeout',type=float,default=120);a=p.parse_args()
    if a.mode=='prepare':prepare()
    elif a.mode=='build':build(a.variants)
    else:run(a.variants,a.input_dir.resolve(),a.tag,a.timeout)
