"""Copy reviewed helper definitions verbatim, excluding historical local paths."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

SELECT = {
    'bench_tool.py': ('runtime_helpers.py', {
        'sha', 'save', 'build_hashes', 'verify_build', 'stage_build', 'CleanupFailure',
        'wait_for_process', 'JobAccounting', 'WindowsJob', 'resume_process',
        'process_affinity_masks', 'run_contained', 'reservation', 'quiet_gate',
        'cpu_total', 'QuietGateTimeout'}),
    'bench_suite.py': ('telemetry_helpers.py', {'telemetry'}),
    'run_synthetic_bench.py': ('runtime_controls.py', {'runtime_setting', 'compilation_setting',
        'runtime_tuning_setting', 'configure_tiering', 'validate_affinity_records'}),
}


def snapshot(source: Path, destination: Path) -> dict:
    destination.mkdir(exist_ok=False)
    evidence = {}
    for original, (output, names) in SELECT.items():
        data = (source / original).read_bytes()
        code = data.decode('utf-8-sig')
        lines = code.splitlines(keepends=True)
        blocks, found = [], set()
        for node in ast.parse(code).body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # These extracted definitions have no sibling imports.
                if ((isinstance(node, ast.ImportFrom) and node.module in ('pathlib', 'typing')) or
                    (isinstance(node, ast.Import) and all(alias.name not in ('bench_tool', 'bench_suite') for alias in node.names))):
                    blocks.append(''.join(lines[node.lineno-1:node.end_lineno]))
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
                start = min([node.lineno] + [deco.lineno for deco in node.decorator_list])
                blocks.append(''.join(lines[start-1:node.end_lineno])); found.add(node.name)
        if found != names:
            raise ValueError(f'helper definition mismatch: {original}: {names-found}')
        header = '"""Verbatim helper definitions from the prior reviewed synthetic harness."""\n'
        if original == 'bench_suite.py':
            header += 'from pathlib import Path\nDEPS = Path(__file__).parent\n'
        if original == 'bench_tool.py':
            # Exact quiet-gate constants are part of the historical contract.
            for node in ast.parse(code).body:
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'QUIET_RULE' for t in node.targets):
                    header += ''.join(lines[node.lineno-1:node.end_lineno]) + '\n'
        target = destination / output
        target.write_text(header + '\n\n'.join(blocks) + '\n', encoding='utf-8', newline='\n')
        evidence[output] = {'source_basename': original, 'source_sha256': hashlib.sha256(data).hexdigest(),
                            'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'definitions': sorted(names)}
    return evidence


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--destination', required=True, type=Path)
    p.add_argument('--qa', required=True, type=Path)
    a = p.parse_args()
    report = snapshot(a.source, a.destination)
    with a.qa.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
