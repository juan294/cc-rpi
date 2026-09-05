#!/usr/bin/env python3
"""Run the CI-equivalent selection sequentially and bind results to candidate bytes.

Prerequisites: Git, Bash, Python 3, PyYAML, ShellCheck, Node, gh and uv.
Disposable database recipe acceptance is a separate required phase check.
The custom --checks
option supports fixture/regression execution and emits a clearly distinct suite
identity; it can never attest that the full default suite ran.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from candidate import identity


def required_checks():
    checks = [{"name": "prerequisites", "argv": [sys.executable, "scripts/verification-checks.py", "prerequisites"]},
              {"name": "internal-links", "argv": [sys.executable, "scripts/check-links.py"]}]
    checks.extend({"name": name, "argv": ["bash", f"templates/scripts/{name}.sh"]}
                  for name in ("verify-counts", "verify-version", "verify-skills", "check-tree-drift"))
    checks.extend({"name": name, "argv": [sys.executable, "scripts/verification-checks.py", name]}
                  for name in ("shellcheck", "syntax", "unit-tests", "coverage"))
    return checks


def run(root, checks, evidence, suite):
    local = root / ".rpi/local"
    try:
        relative = evidence.resolve().relative_to(local)
    except ValueError as error:
        raise ValueError("evidence must stay inside .rpi/local without escaping symlinks") from error
    if relative == Path("."):
        raise ValueError("evidence must name a file inside .rpi/local")
    if not isinstance(checks, list) or not checks:
        raise ValueError("required check inventory is empty or invalid")
    names = set()
    for check in checks:
        if (not isinstance(check, dict) or not isinstance(check.get("name"), str)
                or not check["name"] or check["name"] in names
                or not isinstance(check.get("argv"), list) or not check["argv"]
                or any(not isinstance(arg, str) or not arg for arg in check["argv"])):
            raise ValueError("checks require unique names and nonempty argv arrays")
        names.add(check["name"])
    before = identity(root)
    results = []
    for check in checks:
        print(f"\nCHECK {check['name']}", flush=True)
        started = time.monotonic()
        try:
            completed = subprocess.run(check["argv"], cwd=root, check=False)
            code = completed.returncode
        except OSError as error:
            print(f"BLOCKED / WHY: {error} / FIX: install the prerequisite or correct argv", file=sys.stderr)
            code = 127
        results.append({**check, "exit_code": code,
                        "duration_seconds": round(time.monotonic() - started, 3)})
    after = identity(root)
    unchanged = before == after
    passed = unchanged and len(results) == len(checks) and all(c["exit_code"] == 0 for c in results)
    report = {"schema_version": 1, "suite": suite, "identity": before,
              "identity_after": after, "identity_unchanged": unchanged,
              "recorded_at": datetime.now(timezone.utc).isoformat(),
              "checks": results, "passed": passed,
              "scope": "Portable CI selection; excludes separately required live-harness and disposable database acceptance"}
    evidence.parent.mkdir(parents=True, exist_ok=True)
    temporary = evidence.with_suffix(evidence.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, evidence)
    if not unchanged:
        print("BLOCKED / WHY: candidate inputs changed during verification / FIX: rerun bash scripts/verify-local.sh", file=sys.stderr)
    print(f"{'PASS' if passed else 'FAIL'}: {len(results)} checks; evidence: {evidence}")
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--checks", type=Path, help="custom JSON check array (not a full-gate attestation)")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    evidence = args.evidence or root / ".rpi/local/verification.json"
    try:
        checks = json.loads(args.checks.read_text()) if args.checks else required_checks()
        return run(root, checks, evidence, "custom" if args.checks else "ci-equivalent")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"BLOCKED / WHY: {error} / FIX: provide a nonempty Git candidate and required checks", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
