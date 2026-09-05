"""Real subprocess branches must be measured, and stale results cannot be reused."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MEASURE = ROOT / 'scripts/measure-tests.py'
CHECKS = ROOT / 'scripts/verification-checks.py'


class MeasuredCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rpi measured coverage ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'templates/scripts').mkdir(parents=True)
        (self.root / 'scripts').mkdir()
        (self.root / 'tests').mkdir()
        self.module = self.root / 'templates/scripts/rpi-fixture.py'
        self.module.write_text('import sys\nif sys.argv[1] == "yes":\n    print("covered branch")\nelse:\n    print("missing branch")\n')
        (self.root / 'tests/test_fixture.py').write_text(
            'import subprocess, sys, unittest\nclass ChildTest(unittest.TestCase):\n'
            '    def test_child(self):\n        subprocess.run([sys.executable, ' + repr(str(self.module)) + ', "yes"], check=True)\n')
        for script in ('validate-findings.py', 'contract-metrics.py'):
            (self.root / 'templates/scripts' / script).write_text('print("SELF-TEST PASS: fixture contract")\n')

    def invoke(self, script, *arguments, environment=None):
        return subprocess.run([sys.executable, str(script), *map(str, arguments)], cwd=self.root,
                              capture_output=True, text=True, env=environment or dict(os.environ))

    def runtime_fixture(self):
        binaries = self.root / '.rpi/local/bin'
        binaries.mkdir(parents=True)
        tool = binaries / 'gh'
        tool.write_text('#!/bin/sh\nexit 0\n')
        tool.chmod(0o755)
        return tool, {**os.environ, 'PATH': str(binaries) + os.pathsep + os.environ.get('PATH', '')}

    def test_changed_tool_runtime_rejects_previous_report(self):
        tool, environment = self.runtime_fixture()
        result = self.invoke(MEASURE, '--root', self.root, environment=environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        tool.write_text('#!/bin/sh\nexit 7\n# replaced\n')
        reused = self.invoke(CHECKS, 'coverage', '--root', self.root, environment=environment)
        self.assertNotEqual(reused.returncode, 0)
        self.assertIn('stale', reused.stderr.lower())

    def test_runtime_change_during_suite_invalidates_measurement(self):
        tool, environment = self.runtime_fixture()
        (self.root / 'tests/test_mutation.py').write_text(
            'from pathlib import Path\nimport unittest\nclass Mutation(unittest.TestCase):\n'
            '    def test_runtime_change(self):\n        Path(' + repr(str(tool)) + ').write_text("changed runtime")\n')
        result = self.invoke(MEASURE, '--root', self.root, environment=environment)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads((self.root / '.rpi/local/test-results.json').read_text())
        self.assertFalse(report['passed'])
        self.assertFalse(report['environment_unchanged'])
        self.assertEqual(report['identity'], report['identity_after'])

    def test_branch_measurement_and_reuse_do_not_rerun_tests(self):
        result = self.invoke(MEASURE, '--root', self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads((self.root / '.rpi/local/test-results.json').read_text())
        self.assertEqual(report['producer'], 'coverage.py')
        self.assertEqual(report['test_count'], 1)
        self.assertGreater(report['coverage_percent'], 0)
        self.assertLess(report['coverage_percent'], 100)
        measured = report['files']['templates/scripts/rpi-fixture.py']
        self.assertIn(3, measured['executed_lines'])
        self.assertIn(5, measured['missing_lines'])
        self.assertGreater(measured['summary']['num_branches'], 0)
        before = (self.root / '.rpi/local/test-results.json').read_bytes()
        reused = self.invoke(CHECKS, 'coverage', '--root', self.root)
        self.assertEqual(reused.returncode, 0, reused.stdout + reused.stderr)
        self.assertEqual((self.root / '.rpi/local/test-results.json').read_bytes(), before)
        self.assertNotIn('covered branch', reused.stdout)

    def test_changed_inputs_reject_previous_report(self):
        result = self.invoke(MEASURE, '--root', self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.module.write_text(self.module.read_text() + '# changed candidate\n')
        output = self.root / '.rpi/local/github-output'
        reused = self.invoke(CHECKS, 'coverage', '--root', self.root, '--github-output', output)
        self.assertNotEqual(reused.returncode, 0)
        self.assertFalse(output.exists())
        self.assertIn('stale', reused.stderr.lower())

    def test_failed_new_attempt_cannot_reuse_previous_success(self):
        result = self.invoke(MEASURE, '--root', self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.root / 'tests/test_fixture.py').unlink()
        failed = self.invoke(MEASURE, '--root', self.root)
        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse((self.root / '.rpi/local/test-results.json').exists())

    def test_symlink_receipt_is_rejected_without_touching_target(self):
        local = self.root / '.rpi/local'
        local.mkdir(parents=True)
        target = self.root / 'sentinel.json'
        target.write_text('private sentinel')
        (local / 'test-results.json').symlink_to(target)
        for script, arguments in ((MEASURE, ('--root', self.root)),
                                  (CHECKS, ('coverage', '--root', self.root))):
            with self.subTest(script=script):
                result = self.invoke(script, *arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(target.read_text(), 'private sentinel')

    def test_failed_contract_is_not_reported_as_measured_success(self):
        (self.root / 'templates/scripts/validate-findings.py').write_text('raise SystemExit(7)\n')
        result = self.invoke(MEASURE, '--root', self.root)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads((self.root / '.rpi/local/test-results.json').read_text())
        self.assertFalse(report['passed'])
        self.assertIn('SELF-TEST PASS: fixture contract', result.stdout)

    def test_multiple_failed_subtests_count_one_failed_method(self):
        (self.root / 'tests/test_outcomes.py').write_text(
            'import unittest\nclass Outcomes(unittest.TestCase):\n'
            '    def test_subtests(self):\n        for item in range(2):\n'
            '            with self.subTest(item=item):\n                self.fail("fixture")\n'
            '    def test_skipped(self):\n        for item in range(2):\n'
            '            with self.subTest(item=item):\n                self.skipTest("fixture")\n'
            '    @unittest.expectedFailure\n    def test_expected(self): self.fail("fixture")\n')
        result = self.invoke(MEASURE, '--root', self.root)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads((self.root / '.rpi/local/test-results.json').read_text())
        self.assertEqual(report['test_count'], 4)
        self.assertEqual(report['tests_failed'], 1)
        self.assertEqual(report['tests_passed'], 1)
        self.assertEqual(report['tests_skipped'], 1)
        self.assertEqual(report['tests_expected_failures'], 1)


if __name__ == '__main__':
    unittest.main()
