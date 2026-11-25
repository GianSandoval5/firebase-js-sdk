#!/usr/bin/env python3
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0; see LICENSE.
"""Run actual Firestore browser specs against the base and patch."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'verification-results'
BASE = '6e8b0eb9e64365fb7c4b44359949a83f865c41c4'
SOURCE = ROOT / 'packages/firestore/src/remote/remote_store.ts'
RESULTS = {'base': BASE, 'commands': []}
OUT.mkdir(exist_ok=True)

def run(name, args, env=None):
    print(f'::group::{name}', flush=True)
    print(subprocess.list2cmdline(args), flush=True)
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=env)
    (OUT / f'{name}.log').write_text(result.stdout)
    print(result.stdout, flush=True)
    print('::endgroup::', flush=True)
    RESULTS['commands'].append({'name': name, 'args': args, 'exit': result.returncode})
    (OUT / 'results.json').write_text(json.dumps(RESULTS, indent=2))
    return result

def require(name, args):
    r = run(name, args)
    if r.returncode:
        raise RuntimeError(f'{name} failed with exit {r.returncode}')
    return r

def main():
    patched = SOURCE.read_bytes()
    cmd = ['yarn', '--cwd', 'packages/firestore', 'vitest', 'run', '--project=browser', 'test/unit/specs/write_spec.test.ts', '-t', 'An idle write stream closed with permission-denied allows later writes', '--retry=0', '--reporter=json', '--outputFile=' + str(OUT / 'baseline.json')]
    try:
        SOURCE.write_bytes(subprocess.check_output(['git', 'show', f'{BASE}:packages/firestore/src/remote/remote_store.ts'], cwd=ROOT))
        baseline = run('baseline-browser', cmd)
        data = json.loads((OUT / 'baseline.json').read_text())
        failed = [a for f in data['testResults'] for a in f['assertionResults'] if a['status'] == 'failed']
        if baseline.returncode == 0 or len(failed) != 4:
            raise RuntimeError('Expected exactly four failed regression variants; infrastructure errors do not count')
        if not all('An idle write stream closed with permission-denied allows later writes' in a['fullName'] for a in failed):
            raise RuntimeError('Unexpected failing test')
        if not any('batchId' in str(a.get('failureMessages', [])) for a in failed):
            raise RuntimeError('Expected baseline batchId failure not observed')
        RESULTS['baseline_expected_regression'] = True
    finally:
        SOURCE.write_bytes(patched)
        (OUT / 'results.json').write_text(json.dumps(RESULTS, indent=2))
    require('patched-browser', ['yarn', '--cwd', 'packages/firestore', 'vitest', 'run', '--project=browser', 'test/unit/specs/write_spec.test.ts', 'test/unit/specs/remote_store_spec.test.ts', 'test/unit/specs/recovery_spec.test.ts', '--reporter=json', '--outputFile=' + str(OUT / 'patched.json')])
    require('source-restored', ['git', 'diff', '--exit-code', '--', 'packages/firestore'])
    RESULTS['complete'] = True
    (OUT / 'results.json').write_text(json.dumps(RESULTS, indent=2))

if __name__ == '__main__':
    main()
