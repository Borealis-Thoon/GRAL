"""Add isolated test-only seed and timing hooks to a reviewed source snapshot."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import fixtures


def replace_once(text: str, original: str, updated: str) -> str:
    if text.count(original) != 1:
        raise ValueError('source hook must occur exactly once: ' + original[:80])
    return text.replace(original, updated, 1)


def patch_program(text: str) -> str:
    text = replace_once(text, 'LogLevel = CheckCommandLineArguments(args);',
        'LogLevel = CheckCommandLineArguments(args);\n'
        '            BenchmarkTelemetry benchmarkTelemetry = BenchmarkTelemetry.FromEnvironment(IWETstartstop.Start, IWETstartstop.End);\n'
        '            string benchmarkSeedText = Environment.GetEnvironmentVariable("GRAL_BENCH_SEED_OFFSET");\n'
        '            int benchmarkSeedOffset = 0;\n'
        '            if (benchmarkSeedText != null && (!int.TryParse(benchmarkSeedText, System.Globalization.NumberStyles.None, System.Globalization.CultureInfo.InvariantCulture, out benchmarkSeedOffset) || benchmarkSeedOffset < 0 || benchmarkSeedOffset > 500000))\n'
        '                throw new ArgumentException("Test seed offset must be an integer from 0 through 500000.");')
    text = replace_once(text, 'RnGSeed = new DeterministicRandomGenerator(IWET, WindVelGral, WindDirGral);',
        'RnGSeed = new DeterministicRandomGenerator(checked(IWET + benchmarkSeedOffset), WindVelGral, WindDirGral);\n'
        '                    benchmarkTelemetry?.RecordSeed(IWET, TAUS, WindVelGral, WindDirGral, RnGSeed.Seed1, RnGSeed.Seed2, UseFixedRndSeedVal);')
    text = replace_once(text, '                String WindfieldPath = ReadWindfeldTXT();',
        '                benchmarkTelemetry?.SituationStarted(IWET);\n'
        '                String WindfieldPath = ReadWindfeldTXT();')
    text = replace_once(text, '                } //skipped situation if no entry in meteopgt.all could be found in transient GRAL mode',
        '                    benchmarkTelemetry?.CompleteSituation(IWET, () =>\n'
        '                    {\n'
        '                        ThreadWriteGffFiles?.Join();\n'
        '                        ThreadWrite2DConcentrationFiles?.Join();\n'
        '                        ThreadWriteConz4dFile?.Join();\n'
        '                    });\n'
        '                } //skipped situation if no entry in meteopgt.all could be found in transient GRAL mode')
    return replace_once(text, 'FinishGral:', 'FinishGral:\n            benchmarkTelemetry?.Finish();')


def patch_observer(text: str) -> str:
    text = replace_once(text, '(end != 24 && end != 48)', '(end != 4 && end != 24 && end != 48)')
    text = replace_once(text, '(endText != "24" && endText != "48")', '(endText != "4" && endText != "24" && endText != "48")')
    text = text.replace('end=24 or 48', 'end=4, 24 or 48').replace('INU_BENCH_END=24 or 48', 'INU_BENCH_END=4, 24 or 48')
    text = replace_once(text, 'Write(new { event_type = "config", warmup, end, stopwatch_frequency = frequency });',
        'Write(new { event_type = "config", warmup, end, stopwatch_frequency = frequency, stopwatch_timestamp = timestamp(), utc_timestamp = DateTimeOffset.UtcNow.ToString("O") });')
    text = replace_once(text, '        internal void RecordSeed(',
        '        internal void SituationStarted(int situation)\n'
        '        {\n'
        '            Write(new { event_type = "situation_start", IWET = situation, stopwatch_timestamp = timestamp() });\n'
        '        }\n\n'
        '        internal void RecordSeed(')
    return replace_once(text, '            if (situation != warmup && situation != end) return;',
        '            Write(new { event_type = "situation_end", IWET = situation, stopwatch_timestamp = timestamp() });\n'
        '            if (situation != warmup && situation != end) return;')


def prepare(source: Path, observer: Path, destination: Path) -> dict:
    if destination.exists(): raise FileExistsError(destination)
    before = {str(p.relative_to(source)).replace('\\','/'): fixtures.sha(p) for p in source.rglob('*')
              if p.is_file() and not set(p.relative_to(source).parts).intersection({'.git','bin','obj','__pycache__'})}
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('.git','bin','obj','__pycache__'))
    program = destination/'src'/'Program.cs'
    program.write_text(patch_program(program.read_text(encoding='utf-8-sig')), encoding='utf-8', newline='\n')
    observer_text = patch_observer(observer.read_text(encoding='utf-8-sig'))
    (destination/'src'/'BenchmarkTelemetry.cs').write_text(observer_text, encoding='utf-8', newline='\n')
    actual = {str(p.relative_to(destination)).replace('\\','/'): fixtures.sha(p) for p in destination.rglob('*') if p.is_file()}
    changed = [name for name in before if actual.get(name) != before[name]]
    added = sorted(actual.keys()-before.keys())
    if changed != ['src/Program.cs'] or added != ['src/BenchmarkTelemetry.cs']:
        raise ValueError('overlay changed unexpected files')
    if any(fixtures.sha(source/name) != value for name,value in before.items()):
        raise ValueError('reviewed source changed during snapshot')
    return dict(schema=1, source_sha256=before, overlay_sha256=actual, changed=changed, added=added,
                original_observer_sha256=fixtures.sha(observer), seed_parameter='GRAL_BENCH_SEED_OFFSET',
                seed_offsets=[0,100000,200000,300000,400000,500000],
                seed_scope='designated RNG constructor first argument only; model IWET/weather unchanged',
                observer_scope='original boundary drains retained; per-situation timestamps added; smoke end4 allowed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--observer',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--qa',type=Path,required=True)
    a=p.parse_args()
    report=prepare(a.source,a.observer,a.out)
    with a.qa.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2)
    print('[PREPARED] benchmark overlay')
