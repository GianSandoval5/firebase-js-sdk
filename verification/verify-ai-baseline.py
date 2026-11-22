"""Verify the mapper regression with the repository's browser configuration.

This verifier is fork-only test infrastructure; it is not part of the SDK patch.
It restores the patched source even when browser startup or a test fails.
"""
import json
from pathlib import Path
import subprocess

BASE = "dd0bfd995cc13f1fd16bc928fcab05fb8ceed1ca"
SOURCE = Path("packages/ai/src/googleai-mappers.ts")
LOGS = Path("verification-logs")
LOGS.mkdir(exist_ok=True)
original = SOURCE.read_bytes()
base = subprocess.check_output(["git", "show", f"{BASE}:{SOURCE.as_posix()}"])
report = LOGS.resolve() / "baseline-browser.json"
expected_failures = {
    "should preserve omitted ratings after a rated candidate",
    "should keep safety ratings independent across multiple candidates",
}
try:
    SOURCE.write_bytes(base)
    with (LOGS / "baseline-browser.log").open("w") as output:
        result = subprocess.run(
            ["yarn", "--cwd", "packages/ai", "test:browser",
             "src/googleai-mappers.test.ts", "--reporter=json",
             f"--outputFile={report}"],
            stdout=output, stderr=subprocess.STDOUT, check=False,
        )
    if not report.exists():
        raise RuntimeError("No browser test report was produced; baseline is not reproduced.")
    data = json.loads(report.read_text())
    failed = {
        assertion["title"]
        for suite in data.get("testResults", [])
        for assertion in suite.get("assertionResults", [])
        if assertion.get("status") == "failed"
    }
    summary = {
        "base": BASE,
        "exit_code": result.returncode,
        "passed": data.get("numPassedTests"),
        "failed": data.get("numFailedTests"),
        "failed_titles": sorted(failed),
    }
    (LOGS / "baseline-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    if (result.returncode != 1 or data.get("numFailedTests") != 2
            or data.get("numPassedTests") != 19 or failed != expected_failures):
        raise RuntimeError("Baseline did not fail in exactly the two expected regression cases.")
finally:
    SOURCE.write_bytes(original)
