"""Exercise worktree cleanup against disposable git repositories."""
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/safe-worktree.py'

class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        (self.repo / 'file').write_text('base')
        self.git('add', 'file')
        self.git('commit', '-m', 'base')
        self.work = self.root / 'task'
        self.git('worktree', 'add', '-b', 'task', str(self.work))
    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)
    def cleanup(self, expected='task'):
        return subprocess.run(['python3', str(SCRIPT), '--repo', str(self.repo), '--worktree', str(self.work), '--branch', expected, '--integration', 'main'], capture_output=True)
    def test_clean_integrated_owned_removed(self):
        result = self.cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.work.exists())
    def test_dirty_and_untracked_preserved(self):
        for name in ['file', 'handoff.md']:
            with self.subTest(name=name):
                (self.work / name).write_text('sentinel')
                result = self.cleanup()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'dirty, untracked or ignored', result.stderr)
                self.assertEqual((self.work / name).read_text(), 'sentinel')
                (self.work / 'file').write_text('base')
    def test_ignored_handoff_preserved(self):
        (self.repo / ".git/info/exclude").write_text("handoff.md\n")
        (self.work / "handoff.md").write_text("durable evidence")
        self.assertNotEqual(self.cleanup().returncode, 0)
        self.assertEqual((self.work / "handoff.md").read_text(), "durable evidence")
    def test_unintegrated_commit_preserved(self):
        (self.work / 'file').write_text('new')
        self.git('-C', str(self.work), 'commit', '-am', 'unintegrated')
        self.assertNotEqual(self.cleanup().returncode, 0)
        self.assertTrue(self.work.exists())
    def test_foreign_branch_preserved(self):
        self.assertNotEqual(self.cleanup('someone-else').returncode, 0)
        self.assertTrue(self.work.exists())
    def test_main_worktree_preserved(self):
        self.work = self.repo
        self.assertNotEqual(self.cleanup('main').returncode, 0)
        self.assertTrue(self.repo.exists())

if __name__ == '__main__':
    unittest.main()
