"""Write a single-precision variant of gpu/runtime/generated.cu for an A/B experiment.

Usage: make_variant.py <D|M|F>[2] <out folder>
  D  double: the trajectory code is unchanged.
  M  mixed: absolute particle and tunnel positions stay double; every other trajectory scalar, cast and literal is float.
  F  float: positions are float as well.
  X  diagnostic: as M, and the cell-relative coordinates (xsi, eta, xsi1, eta1) stay double too.
  2  suffix: add a float overload of cs_cast<int> (the .NET saturating conversion), so float arguments are compared
     and converted in fp32. For float inputs this gives the same int as the double version.
The State struct, the output buffers (double accumulators) and the step-limit line (ops_*) are left unchanged, so
fields_manifest.json and the host code work as they are. The out folder gets generated.cu, fields_manifest.json
and variant.json (counts of each kind of edit).
"""
import json
import re
import shutil
import sys
from pathlib import Path

JOB = Path(__file__).resolve().parents[1]
RUNTIME = JOB / 'wt' / 'gpu' / 'runtime'

# Absolute coordinates (metres in the project CRS). Kept double in the mixed variant.
POSITIONS = {'xcoord_nteil', 'ycoord_nteil', 'xcoord_nteil_Prev', 'ycoord_nteil_Prev', 'xtun', 'ytun', 'yneu', 'xneuy',
             'yneuy', 'yold', 'xoldy', 'yoldy', 'depoX', 'depoY', 'xcoord', 'ycoord'}
FUNCTIONS = ('TransientConcentration_Conz5dZeitschleife(', 'TransientConcentration_Conz5dZeitschleifeTransient(',
             'Zeitschleife_Calculate(int nteil)', 'ZeitschleifeNonSteadyState_ParticleDriver(',
             'Zeitschleife_IntWindCalculate(')
LITERAL = re.compile(r'(?<![\w.])((?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)(?![\w.])')


def base(name):
    return re.sub(r'_\d+$', '', name)


# Cell-relative coordinates (x - grid origin). Also kept double in the diagnostic variant X.
RELATIVE = {'xsi', 'eta', 'xsi1', 'eta1'}


def keep_double(name, mode):
    return (mode in ('M', 'X') and base(name) in POSITIONS) or (mode == 'X' and base(name) in RELATIVE)


def body_ranges(lines):
    """(start, end) line indices of the definitions of FUNCTIONS (definition = line ending with '{')."""
    out = []
    for i, line in enumerate(lines):
        if line.startswith('__device__') and line.rstrip().endswith('{') and any(f in line for f in FUNCTIONS):
            depth, j = 0, i
            while True:
                depth += lines[j].count('{') - lines[j].count('}')
                if depth == 0:
                    break
                j += 1
            out.append((i, j))
    return out


def params(line, mode, counts):
    def repl(m):
        if keep_double(m.group(1), mode):
            return m.group(0)
        counts['parameters'] += 1
        return 'float ' + m.group(1)
    head, sep, rest = line.partition('(')
    args, sep2, tail = rest.partition(')')
    return head + sep + re.sub(r'\bdouble ([A-Za-z_]\w*)', repl, args) + sep2 + tail


def main():
    variant, out = sys.argv[1], Path(sys.argv[2])
    mode, overload = variant[0], variant[1:] == '2'
    if mode not in ('D', 'M', 'F', 'X') or variant[1:] not in ('', '2'):
        raise SystemExit('variant must be D, M, F or X, optionally followed by 2')
    lines = (RUNTIME / 'generated.cu').read_text(encoding='utf8').splitlines()
    counts = {'declarations': 0, 'parameters': 0, 'casts': 0, 'literals': 0, 'skipped_ops_lines': 0, 'cs_cast_float': 0}
    if overload:
        anchor = next(i for i, l in enumerate(lines) if l.startswith('template<>__device__ unsigned long long cs_cast<'))
        lines[anchor + 1:anchor + 1] = [
            'template<class T>__device__ T cs_cast(float x);',
            'template<>__device__ int cs_cast<int>(float x){if(isnan(x))return 0;if(x>=2147483648.0f)return 2147483647;'
            'if(x<=-2147483648.0f)return (-2147483647-1);return (int)x;}']
        counts['cs_cast_float'] = 1
    if mode == 'D':
        return write(out, lines, variant, counts)
    # Prototypes of the changed functions.
    for i, line in enumerate(lines):
        if line.startswith('__device__') and line.rstrip().endswith(';') and any(f in line for f in FUNCTIONS):
            lines[i] = params(line, mode, counts)
    for start, end in body_ranges(lines):
        lines[start] = params(lines[start], mode, counts)
        for i in range(start + 1, end + 1):
            line = lines[i]
            m = re.fullmatch(r'double ([A-Za-z_]\w*)\{\};', line.strip())
            if m:
                if not keep_double(m.group(1), mode):
                    lines[i] = line.replace('double ', 'float ', 1)
                    counts['declarations'] += 1
                continue
            if 'ops_' in line:
                counts['skipped_ops_lines'] += 1
                continue
            if re.search(r'\d[eE]-10\b', line):
                # Uniform random numbers (u * 2^-32 or 2^-33): keep them as they are, so every variant draws the
                # same random numbers and only the trajectory arithmetic differs.
                counts['skipped_rng_lines'] = counts.get('skipped_rng_lines', 0) + 1
                continue
            n = line.count('(double)(')
            line = line.replace('(double)(', '(float)(')
            counts['casts'] += n
            line, k = LITERAL.subn(lambda x: x.group(1) + 'f', line)
            counts['literals'] += k
            lines[i] = line
    write(out, lines, variant, counts)


def write(out, lines, variant, counts):
    out.mkdir(parents=True, exist_ok=False)
    (out / 'generated.cu').write_text('\n'.join(lines) + '\n', encoding='utf8')
    shutil.copyfile(RUNTIME / 'fields_manifest.json', out / 'fields_manifest.json')
    (out / 'variant.json').write_text(json.dumps({'variant': variant, 'counts': counts}, indent=1), encoding='utf8')
    print(json.dumps({'variant': variant, 'counts': counts}))


if __name__ == '__main__':
    main()
