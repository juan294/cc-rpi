"""Real process-death recovery and lock ownership, without remote/native work."""
import importlib.util
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import unittest
from unittest import mock

import test_lifecycle_adopters as adopters


# Only the synchronization seam is substituted. Actual apply, durable journals,
# filesystem writes, kernel process death and public recovery remain exercised.
CHILD = r'''
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('crash_distribution', sys.argv[1])
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
lifecycle = engine.load_sibling('rpi-lifecycle')
if sys.argv[2] == 'hold':
    lock = lifecycle.acquire_lock(sys.argv[3])
    print('READY', flush=True)
    sys.stdin.buffer.read(1)
else:
    plan = json.loads(Path(sys.argv[3]).read_text())
    original = lifecycle.atomic_node
    def checkpoint(path, node):
        original(path, node)
        if path.name == 'journal.json':
            journal = json.loads(path.read_text())
            if journal['status'] == 'applying' and journal['completed'] >= 1:
                print('READY', flush=True)
                sys.stdin.buffer.read(1)
    lifecycle.atomic_node = checkpoint
    lifecycle.apply_plan(engine, plan)
'''


@unittest.skipUnless(os.name == 'posix', 'Process-death contract targets macOS/Linux')
class LifecycleCrashTests(unittest.TestCase):
    setUp = adopters.LifecycleAdopterTests.setUp
    write = adopters.LifecycleAdopterTests.write
    make_source = adopters.LifecycleAdopterTests.make_source
    git = adopters.LifecycleAdopterTests.git
    commit_source = adopters.LifecycleAdopterTests.commit_source
    plan = adopters.LifecycleAdopterTests.plan
    apply_ready = adopters.LifecycleAdopterTests.apply_ready
    snapshot = adopters.LifecycleAdopterTests.snapshot

    def invoke(self, *arguments):
        return subprocess.run([sys.executable, str(adopters.ENGINE), *map(str, arguments)],
                              capture_output=True, text=True, timeout=20,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def child(self, mode, argument):
        process = subprocess.Popen([sys.executable, '-B', '-c', CHILD,
                                    str(adopters.ENGINE), mode, str(argument)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
        self.addCleanup(cleanup)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=20), 'child never reached the durable handshake')
        self.assertEqual(process.stdout.readline().strip(), 'READY', 'child exited before checkpoint')
        self.assertIsNone(process.poll())
        return process

    def kill(self, process):
        process.send_signal(signal.SIGKILL)
        process.communicate(timeout=10)
        self.assertEqual(process.returncode, -signal.SIGKILL)

    def runtime(self):
        spec = importlib.util.spec_from_file_location('crash_review_engine', adopters.ENGINE)
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        return engine, engine.load_sibling('rpi-lifecycle')

    def test_missing_mutation_prerequisites_leave_state_uncreated(self):
        engine, lifecycle = self.runtime()
        for missing in ('fcntl', 'O_NOFOLLOW'):
            with self.subTest(missing=missing):
                state = (self.workspace / ('unsupported-' + missing)).resolve()
                patch = (mock.patch.dict(sys.modules, {'fcntl': None}) if missing == 'fcntl'
                         else mock.patch.object(lifecycle.os, 'O_NOFOLLOW'))
                before = self.snapshot(include_local=True)
                with patch:
                    if missing == 'O_NOFOLLOW':
                        del lifecycle.os.O_NOFOLLOW
                    # Read-only source validation does not require mutation locks.
                    self.assertEqual(engine.load_manifest(self.source)['schema_version'], 1)
                    with self.assertRaisesRegex(ValueError, 'tested macOS or Linux runtime'):
                        lifecycle.acquire_lock(state)
                self.assertFalse(state.exists())
                self.assertEqual(self.snapshot(include_local=True), before)

    def test_sigkill_partial_apply_recovers_without_removing_lock_or_owner_work(self):
        self.write(self.project, 'AGENTS.md', '# Original owner knowledge\n')
        original = self.snapshot()
        plan, artifact = self.plan()
        self.assertEqual(plan['status'], 'ready')
        process = self.child('apply', artifact)
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        progress = json.loads(journal.read_text())
        self.assertEqual(progress['status'], 'applying')
        self.assertGreaterEqual(progress['completed'], 1)
        self.assertLess(progress['completed'], len(progress['operations']))
        self.assertNotEqual(self.snapshot(), original, 'kill must follow an actual owned write')
        lock = self.project / '.rpi/local/lock'
        inode = lock.stat().st_ino
        self.kill(process)
        owner = self.write(self.project, 'recovery-owner-note.txt', 'Concurrent owner knowledge.\n')
        result = self.invoke('rollback', '--journal', journal)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), {**original, owner.name: owner.read_bytes()})
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')
        self.assertEqual(lock.read_bytes(), b'')
        self.assertEqual(lock.stat().st_ino, inode)
        before = self.snapshot(include_local=True)
        self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.assertEqual(self.snapshot(include_local=True), before)
        self.apply_ready()
        self.assertTrue((self.project / '.agents/skills/rpi-plan/SKILL.md').is_file())
        self.assertEqual(owner.read_text(), 'Concurrent owner knowledge.\n')
        self.assertEqual(lock.stat().st_ino, inode)

    def test_live_holder_blocks_second_apply_and_dead_holder_releases_same_inode(self):
        plan, artifact = self.plan()
        state = Path(plan['state_root'])
        holder = self.child('hold', state)
        lock = state / 'local/lock'
        inode = lock.stat().st_ino
        before = self.snapshot(include_local=True)
        blocked = self.invoke('apply', '--plan', artifact)
        self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
        self.assertIn('lock', blocked.stdout + blocked.stderr)
        self.assertEqual(self.snapshot(include_local=True), before)
        self.kill(holder)
        result = self.invoke('apply', '--plan', artifact)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(lock.read_bytes(), b'')
        self.assertEqual(lock.stat().st_ino, inode)
        # A subsequent process must contend on the original inode, too.
        second = self.child('hold', state)
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Updated resource.\n')
        _, update = self.plan('update')
        before = self.snapshot(include_local=True)
        self.assertEqual(self.invoke('apply', '--plan', update).returncode, 2)
        self.assertEqual(self.snapshot(include_local=True), before)
        self.kill(second)
        self.assertEqual(self.invoke('apply', '--plan', update).returncode, 0)
        self.assertEqual(lock.stat().st_ino, inode)

    def test_unknown_and_nonregular_lock_nodes_are_preserved(self):
        _, artifact = self.plan()
        lock = self.project / '.rpi/local/lock'
        lock.parent.mkdir(parents=True)
        external = self.workspace / 'unowned-empty-file'
        external.write_bytes(b'')
        for kind in ('legacy-pid', 'unknown-text', 'symlink', 'dangling', 'directory', 'fifo', 'hardlink'):
            with self.subTest(kind=kind):
                if kind == 'legacy-pid':
                    lock.write_text('99999999\n')
                elif kind == 'unknown-text':
                    lock.write_text('Preserve this owner-managed lock content.\n')
                elif kind == 'symlink':
                    lock.symlink_to(external)
                elif kind == 'dangling':
                    lock.symlink_to(self.workspace / 'missing-owner-target')
                elif kind == 'directory':
                    lock.mkdir()
                    (lock / 'owner-note').write_text('Keep this directory.\n')
                elif kind == 'fifo':
                    os.mkfifo(lock)
                else:
                    os.link(external, lock)
                before = self.snapshot(include_local=True)
                identity = lock.lstat()
                link = os.readlink(lock) if lock.is_symlink() else None
                try:
                    result = self.invoke('apply', '--plan', artifact)
                    self.assertNotEqual(result.returncode, 0, kind)
                    self.assertEqual(self.snapshot(include_local=True), before)
                    self.assertEqual(lock.lstat().st_ino, identity.st_ino)
                    self.assertEqual(lock.lstat().st_mode, identity.st_mode)
                    self.assertEqual(external.read_bytes(), b'')
                    if link is not None:
                        self.assertEqual(os.readlink(lock), link)
                finally:
                    if kind == 'directory':
                        (lock / 'owner-note').unlink()
                        lock.rmdir()
                    else:
                        lock.unlink()

    def test_rollback_revalidates_journal_after_acquiring_lock(self):
        _, artifact = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', artifact, '--fail-after', '1').returncode, 2)
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        _, lifecycle = self.runtime()
        acquire = lifecycle.acquire_lock
        changed = None
        latest = None
        def concurrent_checkpoint(state):
            nonlocal changed, latest
            # The active apply advances one real operation between rollback's
            # preliminary read and exclusive ownership. Preserve that checkpoint.
            value = json.loads(journal.read_text())
            operation = value['operations'][value['completed']]
            lifecycle.atomic_node(lifecycle.operation_path(value, operation), operation['after'])
            value['completed'] += 1
            value['pending'] = None
            changed = lifecycle.serialized(value)
            journal.write_bytes(changed)
            latest = self.snapshot()
            return acquire(state)
        with mock.patch.object(lifecycle, 'acquire_lock', side_effect=concurrent_checkpoint):
            with self.assertRaises(lifecycle.Conflict):
                lifecycle.rollback(journal)
        self.assertIsNotNone(changed)
        self.assertEqual(journal.read_bytes(), changed)
        self.assertEqual(self.snapshot(), latest)


if __name__ == '__main__':
    unittest.main()
