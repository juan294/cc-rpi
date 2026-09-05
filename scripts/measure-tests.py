#!/usr/bin/env python3
"""Run the authoritative suite once with measured line and branch coverage."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

from candidate import environment, identity, inventory


def load_checks():
    path = Path(__file__).with_name('verification-checks.py')
    spec = importlib.util.spec_from_file_location('rpi_verification_checks', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(root):
    import coverage
    root = root.resolve()
    before = identity(root)
    runtime_before = environment()
    candidates = inventory(root)
    measured = [p for p in candidates if p.suffix == '.py' and
                p.parent in (Path('scripts'), Path('templates/scripts'))]
    if not measured:
        raise ValueError('no implementation modules selected for measured coverage')
    local = root / '.rpi/local'
    if local.resolve() != local:
        raise ValueError('coverage evidence cannot traverse a symlink')
    destination = local / 'test-results.json'
    if destination.is_symlink():
        raise ValueError('coverage receipt must be a regular owned file')
    # A failed new attempt must not leave a previous success as the latest run.
    destination.unlink(missing_ok=True)
    run_root = local / ('coverage-' + uuid.uuid4().hex)
    run_root.mkdir(parents=True)
    config = run_root / 'coverage.ini'
    sources = [root / directory for directory in ('scripts', 'templates/scripts') if (root / directory).is_dir()]
    selected = {str((root / path).resolve()) for path in measured}
    omitted = sorted(str(path.resolve()) for directory in sources for path in directory.glob('*.py')
                     if str(path.resolve()) not in selected)
    config.write_text('[run]\nbranch = True\nparallel = True\npatch = subprocess\n'
                      'disable_warnings = no-data-collected\n'
                      'data_file = ' + str(run_root / '.coverage') + '\nsource =\n    ' +
                      '\n    '.join(map(str, sources)) + '\nomit =\n    ' + '\n    '.join(omitted) + '\n')
    cov = coverage.Coverage(config_file=str(config))
    cov.start()
    result = None
    contract_code = 1
    previous_cwd = Path.cwd()
    try:
        os.chdir(root)
        suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern='test_*.py')
        count = suite.countTestCases()
        if not count:
            raise ValueError('no unit tests discovered')
        print(f'Running {count} tests with coverage.py {coverage.__version__}', flush=True)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        contract_code = load_checks().contract_tests(root, None)
    finally:
        cov.stop()
        cov.save()
        os.chdir(previous_cwd)
    cov.combine(data_paths=[str(run_root)])
    cov.save()
    coverage_json = run_root / 'coverage.json'
    cov.json_report(outfile=str(coverage_json))
    raw = json.loads(coverage_json.read_text())
    files = {}
    for name, data in raw['files'].items():
        path = Path(name)
        if not path.is_absolute():
            path = previous_cwd / path
        path = path.resolve()
        if str(path) in selected:
            files[str(path.relative_to(root))] = data
    missing = selected - {str(root / name) for name in files}
    if missing:
        raise ValueError('coverage omitted selected implementation modules: ' + ', '.join(sorted(missing)))
    totals = {key: sum(data['summary'][key] for data in files.values())
              for key in ('covered_lines', 'num_statements', 'missing_lines', 'num_branches', 'covered_branches', 'missing_branches')}
    if not totals['num_statements']:
        raise ValueError('coverage measured zero executable statements')
    after = identity(root)
    runtime_after = environment()
    def case_ids(cases):
        return {getattr(case, 'test_case', case).id() for case in cases}

    failed_cases = [case for case, _ in result.failures + result.errors] + result.unexpectedSuccesses
    # unittest counts methods in testsRun, but each failed subTest separately.
    failed_ids = case_ids(failed_cases)
    skipped_ids = case_ids(case for case, _ in result.skipped) - failed_ids
    expected_ids = case_ids(case for case, _ in result.expectedFailures) - failed_ids - skipped_ids
    failures = len(failed_ids)
    payload = {'schema_version': 1, 'producer': 'coverage.py', 'producer_version': coverage.__version__,
               'identity': before, 'identity_after': after, 'environment': runtime_before,
               'environment_after': runtime_after, 'environment_unchanged': runtime_before == runtime_after,
               'passed': result.wasSuccessful() and contract_code == 0 and before == after and runtime_before == runtime_after,
               'test_count': result.testsRun,
               'test_files': len([p for p in candidates if p.parent == Path('tests') and p.name.startswith('test_') and p.suffix == '.py']),
               'tests_passed': result.testsRun - failures - len(skipped_ids) - len(expected_ids), 'tests_failed': failures,
               'tests_skipped': len(skipped_ids), 'tests_expected_failures': len(expected_ids), 'contract_exit_code': contract_code,
               'coverage_percent': round(100 * totals['covered_lines'] / totals['num_statements'], 2),
               'branch_coverage_percent': round(100 * totals['covered_branches'] / totals['num_branches'], 2) if totals['num_branches'] else None,
               'totals': totals, 'files': files}
    temporary = run_root / 'test-results.json'
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    os.replace(temporary, destination)
    print(json.dumps({key: value for key, value in payload.items() if key not in ('files', 'identity', 'identity_after')}, sort_keys=True))
    return 0 if payload['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        return run(args.root)
    except (OSError, ValueError, ImportError, subprocess.CalledProcessError) as error:
        print(f'BLOCKED / WHY: {error} / FIX: python3 -m pip install coverage==7.16.0 PyYAML==6.0.3; '
              'then run python3 scripts/measure-tests.py', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
