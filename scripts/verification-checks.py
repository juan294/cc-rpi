#!/usr/bin/env python3
"""Shared CI/local checks with explicit nonempty inventories."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from candidate import inventory


def prerequisites(_root):
    required = ("git", "bash", "shellcheck", "node", "gh", "uv")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise ValueError("missing executables: " + ", ".join(missing))
    for name in ("node", "gh", "uv"):
        subprocess.run([name, "--version"], check=True)


def require_inputs(root, files, required):
    available = {str(path) for path in files}
    missing = [name for name in required if name not in available or not (root / name).is_file()]
    if missing:
        raise ValueError("missing required candidate inputs: " + ", ".join(missing))


def syntax(root):
    import yaml
    files = inventory(root)
    require_inputs(root, files, ("templates/settings.json.template", ".github/ISSUE_TEMPLATE/config.yml"))
    groups = {
        "JSON": [p for p in files if p.suffix == ".json" or str(p) == "templates/settings.json.template"],
        "YAML": [p for p in files if p.suffix in (".yml", ".yaml")],
        "Python": [p for p in files if p.suffix == ".py"],
    }
    failures = []
    for kind, paths in groups.items():
        if not paths:
            failures.append(f"empty {kind} inventory")
        for path in paths:
            try:
                source = (root / path).read_text(encoding="utf-8")
                if kind == "JSON":
                    json.loads(source)
                elif kind == "YAML":
                    yaml.safe_load(source)
                else:
                    compile(source, str(path), "exec")
            except (OSError, ValueError, SyntaxError, yaml.YAMLError) as error:
                failures.append(f"{path}: {error}")
        print(f"Validated {len(paths)} {kind} files")
    if failures:
        raise ValueError("; ".join(failures))


def shellcheck(root):
    files = inventory(root)
    require_inputs(root, files, (
        "scripts/install.sh", "scripts/verify-local.sh",
        "templates/scripts/cc-rpi-update-agent.sh",
        "templates/scripts/agents/contract-metrics-agent.sh",
        "templates/scripts/verify-counts.sh", "templates/scripts/verify-skills.sh",
        "templates/scripts/verify-version.sh", "templates/scripts/check-tree-drift.sh",
        "templates/hooks/guard-bash.sh", "templates/hooks/verify-edit.sh",
    ))
    paths = [str(p) for p in files if p.suffix == ".sh"]
    if not paths:
        raise ValueError("empty shell inventory")
    print(f"Checking {len(paths)} shell files", flush=True)
    return subprocess.run(["shellcheck", "--severity=warning", *paths], cwd=root).returncode


def unit_tests(root):
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    count = suite.countTestCases()
    if not count:
        raise ValueError("no unit tests discovered")
    print(f"Running {count} unit tests", flush=True)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


def coverage(root, github_output):
    # This producer counts existing authoritative self-tests. It does not
    # measure source coverage or fabricate a percentage for documentation.
    suites = ["templates/scripts/validate-findings.py", "templates/scripts/contract-metrics.py"]
    total = 0
    failed = False
    for script in suites:
        result = subprocess.run([sys.executable, script, "--self-test"], cwd=root,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(result.stdout, end="", flush=True)
        count = sum("SELF-TEST PASS" in line for line in result.stdout.splitlines())
        if result.returncode or count == 0:
            print(f"BLOCKED / WHY: {script}: exit={result.returncode}, pass_lines={count} "
                  "/ FIX: repair the self-test producer", file=sys.stderr)
            failed = True
        total += count
    if failed:
        return 1
    payload = {"producer": "count_only", "test_count": total, "test_files": len(suites),
               "tests_passed": total, "tests_failed": 0, "coverage_percent": None}
    print(json.dumps(payload, sort_keys=True))
    if github_output:
        with github_output.open("a", encoding="utf-8") as handle:
            for key, value in payload.items():
                handle.write(f"{key}={'null' if value is None else value}\n")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("prerequisites", "syntax", "shellcheck", "unit-tests", "coverage"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.check == "coverage":
            return coverage(root, args.github_output)
        return {"prerequisites": prerequisites, "syntax": syntax, "shellcheck": shellcheck,
                "unit-tests": unit_tests}[args.check](root) or 0
    except (OSError, ValueError, ImportError, subprocess.CalledProcessError) as error:
        print(f"BLOCKED / WHY: {error} / FIX: install Git, Bash, ShellCheck, Node, gh; "
              "python3 -m pip install PyYAML==6.0.3 uv==0.12.10; then repair missing or invalid inputs", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
