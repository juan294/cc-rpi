"""Latest verification attempts supersede old success, including process death."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import unittest

import test_policy


VERIFY = test_policy.ROOT / 'templates/scripts/rpi-verify.py'
PAUSED = r'''
import importlib.util, sys
spec = importlib.util.spec_from_file_location('paused_verifier', sys.argv[1])
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
original = verifier.subprocess.run
def pause_check(argv, *args, **kwargs):
    if len(argv) > 1 and argv[1] == 'check.py':
        print('WAIT_READY', flush=True)
        sys.stdin.buffer.read(1)
    return original(argv, *args, **kwargs)
verifier.subprocess.run = pause_check
sys.argv = sys.argv[1:]
raise SystemExit(verifier.main())
'''


@unittest.skipUnless(os.name == 'posix', 'Process-death acceptance targets macOS/Linux')
class VerificationAttemptTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_policy.PolicyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.project = self.fixture.project
        self.environment = {**self.fixture.environment, 'PYTHONDONTWRITEBYTECODE': '1'}
        self.local = self.project / '.rpi/local'
        self.local.mkdir()
        self.receipt = self.local / 'verification.json'
        self.checks = [{'name': 'behavior', 'argv': [sys.executable, 'check.py']}]
        (self.project / 'check.py').write_text(
            'from pathlib import Path\n'
            'p=Path(".rpi/local/check-exit")\n'
            'raise SystemExit(int(p.read_text()) if p.exists() else 0)\n')
        declaration = self.project / '.rpi/policy.json'
        value = json.loads(declaration.read_text())
        value['verification_checks'] = self.checks
        declaration.write_text(json.dumps(value))
        self.fixture.git('add', '.')
        self.fixture.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                         'commit', '-qm', 'Declare actual fixture check')

    def run_verifier(self, *args):
        return subprocess.run([sys.executable, str(VERIFY), '--root', str(self.project), *map(str, args)],
                              cwd=self.project, env=self.environment, capture_output=True,
                              text=True, timeout=20)

    def seed_success(self):
        result = self.run_verifier()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(self.receipt.read_text())['passed'])
        self.assertEqual(self.fixture.invoke('git push origin develop', environment=self.environment).returncode, 0)

    def assert_unpublishable(self):
        report = json.loads(self.receipt.read_text())
        self.assertFalse(report['passed'])
        self.assertIn(report['status'], ('running', 'failed'))
        outcome = self.fixture.invoke('git push origin develop', environment=self.environment)
        self.assertEqual(outcome.returncode, 2, outcome.stdout + outcome.stderr)
        self.assertFalse(self.fixture.sentinel.exists())

    def paused(self, *args):
        process = subprocess.Popen([sys.executable, '-B', '-c', PAUSED, str(VERIFY),
                                    '--root', str(self.project), *map(str, args)],
                                   cwd=self.project, env=self.environment,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
        self.addCleanup(cleanup)
        output = b''
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while b'WAIT_READY\n' not in output:
                self.assertTrue(selector.select(timeout=20), 'verifier never reached check boundary')
                chunk = os.read(process.stdout.fileno(), 8192)
                self.assertTrue(chunk, 'verifier exited before handshake: ' + output.decode())
                output += chunk
        return process

    def test_running_and_sigkilled_attempt_supersede_old_success(self):
        self.seed_success()
        process = self.paused()
        self.assert_unpublishable()
        process.send_signal(signal.SIGKILL)
        process.communicate(timeout=10)
        self.assertEqual(process.returncode, -signal.SIGKILL)
        self.assert_unpublishable()
        (self.local / 'check-exit').write_text('7')
        self.assertEqual(self.run_verifier().returncode, 1)
        self.assert_unpublishable()
        (self.local / 'check-exit').write_text('0')
        self.seed_success()

    def test_competing_run_cannot_execute_or_overwrite_active_attempt(self):
        self.seed_success()
        first = self.paused()
        active = self.receipt.read_bytes()
        second = self.run_verifier()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn('lock', second.stderr.lower())
        self.assertEqual(self.receipt.read_bytes(), active)
        self.assert_unpublishable()
        first.communicate(b'x', timeout=10)
        self.assertEqual(first.returncode, 0)
        self.assertTrue(json.loads(self.receipt.read_text())['passed'])
        (self.local / 'check-exit').write_text('7')
        self.assertEqual(self.run_verifier().returncode, 1)
        self.assert_unpublishable()

    def test_custom_output_and_custom_suite_invalidate_authoritative_receipt(self):
        self.seed_success()
        checks = self.local / 'checks.json'
        checks.write_text(json.dumps(self.checks))
        output = self.local / 'custom-result.json'
        process = self.paused('--checks', checks, '--evidence', output)
        self.assert_unpublishable()
        process.communicate(b'x', timeout=10)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(output.read_text())['suite'], 'custom')
        self.assertEqual(json.loads(self.receipt.read_text())['suite'], 'custom')
        self.assertEqual(self.fixture.invoke('git push origin develop', environment=self.environment).returncode, 2)

    def test_in_root_redirect_cannot_hide_an_output_symlink(self):
        self.seed_success()
        alias = self.local / 'alias'
        alias.symlink_to(self.project, target_is_directory=True)
        before = self.receipt.read_bytes()
        result = self.run_verifier('--evidence', alias / '.rpi/local/redirected.json')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.receipt.read_bytes(), before)
        self.assertFalse((self.local / 'redirected.json').exists())
        self.assertTrue(alias.is_symlink())
        alias.unlink()
        self.seed_success()  # Rejection did not strand an acquired lock.

    def test_unsafe_authoritative_receipt_preserves_owner_and_allows_recovery(self):
        self.seed_success()
        saved = self.receipt.read_bytes()
        owner = self.fixture.workspace / 'owner-receipt.json'
        owner.write_bytes(saved)
        for kind in ('symlink', 'hardlink'):
            with self.subTest(kind=kind):
                self.receipt.unlink()
                if kind == 'symlink':
                    self.receipt.symlink_to(owner)
                else:
                    os.link(owner, self.receipt)
                node = self.receipt.lstat()
                result = self.run_verifier()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(owner.read_bytes(), saved)
                self.assertEqual(self.receipt.read_bytes(), saved)
                self.assertEqual((self.receipt.lstat().st_ino, self.receipt.lstat().st_mode,
                                  self.receipt.lstat().st_size, self.receipt.lstat().st_mtime_ns),
                                 (node.st_ino, node.st_mode, node.st_size, node.st_mtime_ns))
                self.receipt.unlink()
                self.seed_success()  # Only the fixture removes its alias.

    def test_unsafe_output_and_lock_aliases_leave_owner_bytes_untouched(self):
        self.seed_success()
        sentinel = self.fixture.workspace / 'owner.txt'
        sentinel.write_text('Preserve owner bytes.\n')
        for relative in ('result.json', 'verification.lock'):
            with self.subTest(relative=relative):
                path = self.local / relative
                if path.exists():
                    path.unlink()  # Only this fixture's inactive engine-owned lock.
                path.symlink_to(sentinel)
                before = self.receipt.read_bytes()
                try:
                    result = self.run_verifier('--evidence', path) if relative == 'result.json' else self.run_verifier()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(sentinel.read_text(), 'Preserve owner bytes.\n')
                    self.assertEqual(self.receipt.read_bytes(), before)
                    self.assertTrue(path.is_symlink())
                finally:
                    path.unlink()


if __name__ == '__main__':
    unittest.main()
