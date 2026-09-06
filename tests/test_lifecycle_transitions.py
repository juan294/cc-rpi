"""Public CLI transitions preserve owner directories and target repair guidance."""
import json
import shlex
import subprocess
import sys
import unittest

import test_lifecycle_adopters


class LifecycleTransitionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_lifecycle_adopters.LifecycleAdopterTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_direct_detach_then_plugin_preserves_empty_directory_trees(self):
        f = self.fixture
        f.apply_ready()
        for harness, native in (('claude', '.claude'), ('codex', '.agents')):
            with self.subTest(harness=harness):
                f.apply_ready('detach', '--harness', harness)
                directory = f.project / native / 'skills/rpi-plan'
                owner_empty = directory / 'owner-empty/nested'
                owner_empty.mkdir(parents=True)
                directories = {p: p.stat().st_ino for p in [directory, *directory.rglob('*')] if p.is_dir()}
                self.assertFalse(any(p.is_file() or p.is_symlink() for p in directory.rglob('*')))
                f.apply_ready('install', '--harness', harness, '--route', 'plugin')
                self.assertEqual({p: p.stat().st_ino for p in directories}, directories)
                self.assertFalse((directory / 'SKILL.md').exists())
                result = f.invoke('check', '--source', f.source, '--target', f.project,
                                  '--harness', harness, '--route', 'plugin')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_nonempty_or_aliased_unknown_direct_roots_still_block_plugin(self):
        f = self.fixture
        for harness, native in (('claude', '.claude'), ('codex', '.agents')):
            directory = f.project / native / 'skills/rpi-plan'
            directory.mkdir(parents=True)
            for kind in ('skill', 'owner-file', 'dangling-symlink', 'directory-symlink'):
                with self.subTest(harness=harness, kind=kind):
                    path = directory / ('SKILL.md' if kind == 'skill' else 'owner')
                    if kind == 'dangling-symlink':
                        path.symlink_to(f.workspace / 'absent')
                    elif kind == 'directory-symlink':
                        path.symlink_to(f.plans, target_is_directory=True)
                    else:
                        path.write_text('Owner content remains unchanged.\n')
                    node = path.lstat()
                    before = f.snapshot(include_local=True)
                    plan, artifact = f.plan('install', '--harness', harness, '--route', 'plugin')
                    self.assertEqual(plan['status'], 'conflict')
                    self.assertTrue(any(c['destination'].endswith('skills/rpi-plan') for c in plan['conflicts']))
                    self.assertEqual(f.invoke('apply', '--plan', artifact).returncode, 2)
                    self.assertEqual(f.snapshot(include_local=True), before)
                    self.assertEqual((path.lstat().st_ino, path.lstat().st_mode, path.lstat().st_size, path.lstat().st_mtime_ns),
                                     (node.st_ino, node.st_mode, node.st_size, node.st_mtime_ns))
                    path.unlink()

    def test_malformed_target_settings_identifies_repair_and_exact_rerun(self):
        f = self.fixture
        path = f.write(f.project, '.claude/settings.json', '{"private": "owner", BROKEN\n')
        before = f.snapshot(include_local=True)
        source_before = f.snapshot(f.source, include_local=True)
        artifact = f.plans / 'target-error.json'
        arguments = ['plan', '--source', str(f.source), '--target', str(f.project),
                     '--harness', 'both', '--route', 'direct', '--output', str(artifact)]
        result = f.invoke(*arguments)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(f.snapshot(include_local=True), before)
        self.assertEqual(f.snapshot(f.source, include_local=True), source_before)
        self.assertFalse(artifact.exists())
        fix = result.stderr.split(' / FIX: ', 1)[1]
        self.assertIn(str(path.resolve()), fix)
        self.assertNotIn('correct templates/distribution.json', fix)
        rerun = shlex.split(fix.split('; rerun ', 1)[1])
        self.assertEqual(rerun, [sys.executable, str(test_lifecycle_adopters.ENGINE), *arguments])
        path.write_text('{"private": "owner"}\n')
        recovered = subprocess.run(rerun, capture_output=True, text=True)
        self.assertEqual(recovered.returncode, 0, recovered.stdout + recovered.stderr)
        self.assertEqual(json.loads(artifact.read_text())['status'], 'ready')
        self.assertEqual(path.read_text(), '{"private": "owner"}\n')


if __name__ == '__main__':
    unittest.main()
