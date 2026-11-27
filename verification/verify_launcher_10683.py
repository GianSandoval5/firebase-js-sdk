#!/usr/bin/env python3
"""Verify the real launcher command contract and launch actual Vitest projects."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/firestore'
OUT = ROOT / 'verification-results'
BASE = '6e8b0eb9e64365fb7c4b44359949a83f865c41c4'
JS = PACKAGE / 'scripts/run-tests.js'
OUT.mkdir(exist_ok=True)
RESULTS = {'base': BASE, 'commands': []}

def run(name, args, cwd=PACKAGE):
    print(f'::group::{name}', flush=True)
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', timeout=240)
    (OUT / f'{name}.log').write_text(result.stdout)
    print(result.stdout, flush=True)
    print('::endgroup::', flush=True)
    RESULTS['commands'].append({'name': name, 'args': args, 'exit': result.returncode})
    (OUT / 'results.json').write_text(json.dumps(RESULTS, indent=2))
    return result

patched = JS.read_bytes()
try:
    JS.write_bytes(subprocess.check_output(['git', 'show', f'{BASE}:packages/firestore/scripts/run-tests.js'], cwd=ROOT))
    baseline = run('baseline-launcher', ['node', '--test', '--test-reporter=tap', 'scripts/run-tests.test.cjs'])
    assert baseline.returncode == 1
    assert '# pass 5' in baseline.stdout and '# fail 5' in baseline.stdout
    RESULTS['baseline_expected_regression'] = True
finally:
    JS.write_bytes(patched)

result = run('patched-launcher', ['node', '--test', '--test-reporter=tap', 'scripts/run-tests.test.cjs'])
assert result.returncode == 0 and '# pass 10' in result.stdout and '# fail 0' in result.stdout
result = run('tooling-script-build-and-tests', ['yarn', 'test:tooling'])
assert result.returncode == 0
for platform, suite, marker in [
    ('node', 'test/unit/util/sorted_set.test.ts', 'node'),
    ('browser', 'test/unit/util/sorted_set.test.ts', 'chromium'),
]:
    result = run(f'actual-{platform}-launcher', ['node', 'scripts/run-tests.js', '--main', 'test', '--platform', platform, suite])
    assert result.returncode == 0, f'{platform} suite failed'
    assert marker in result.stdout and 'passed' in result.stdout
result = run('source-restored', ['git', 'diff', '--exit-code', '--', 'packages/firestore'], ROOT)
assert result.returncode == 0
RESULTS['complete'] = True
(OUT / 'results.json').write_text(json.dumps(RESULTS, indent=2))
