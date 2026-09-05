"""The compatibility entry point must not overwrite unknown user commands."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

INSTALLER = Path(__file__).resolve().parents[1] / 'scripts/install.sh'


class InstallationEntryTests(unittest.TestCase):
    def invoke(self, *args):
        with tempfile.TemporaryDirectory(prefix='rpi entry & quote ') as temporary:
            root = Path(temporary)
            checkout = root / 'source with spaces'
            (checkout / 'scripts').mkdir(parents=True)
            shutil.copy2(INSTALLER, checkout / 'scripts/install.sh')
            engine = checkout / 'templates/scripts/rpi-distribution.py'
            engine.parent.mkdir(parents=True)
            engine.write_text('import sys\nprint("ENGINE", repr(sys.argv[1:]))\n')
            commands = checkout / 'templates/commands'
            commands.mkdir()
            for name in ('bootstrap', 'adopt', 'update', 'detach'):
                (commands / (name + '.md')).write_text('upstream command\n')
            user_commands = root / 'user-commands'
            user_commands.mkdir()
            sentinel = user_commands / 'update.md'
            sentinel.write_text('custom command sentinel\n')
            result = subprocess.run(['bash', str(checkout / 'scripts/install.sh'), *args],
                                    env={**os.environ, 'CLAUDE_COMMANDS_DIR': str(user_commands)},
                                    capture_output=True, text=True)
            return result, sentinel.read_text(), sorted(p.name for p in user_commands.iterdir())

    def test_default_requires_explicit_destination_and_preserves_unknown_commands(self):
        result, sentinel, files = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BLOCKED', result.stdout + result.stderr)
        self.assertEqual(sentinel, 'custom command sentinel\n')
        self.assertEqual(files, ['update.md'])

    def test_project_plan_preserves_literal_destination_and_route(self):
        result, sentinel, files = self.invoke('--target', "/tmp/π & 'quoted'", '--harness', 'codex', '--route', 'direct', '--output', '/tmp/plan.json', '--allow-capabilities', 'config:claude-policy')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('config:claude-policy', result.stdout)
        self.assertIn("'plan'", result.stdout)
        self.assertIn("π &", result.stdout)
        self.assertIn("'codex'", result.stdout)
        self.assertIn("'direct'", result.stdout)
        self.assertEqual(sentinel, 'custom command sentinel\n')
        self.assertEqual(files, ['update.md'])

    def test_apply_delegates_exact_plan_without_inventing_selection(self):
        result, _, _ = self.invoke('--apply', "/tmp/plan with '&.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("'apply', '--plan'", result.stdout)
        self.assertNotIn("'--target'", result.stdout)

    def test_fake_user_roots_are_explicitly_bound(self):
        result, _, _ = self.invoke('--scope', 'user', '--state-root', '/tmp/state',
                                   '--claude-skill-root', '/tmp/claude', '--codex-skill-root', '/tmp/codex',
                                   '--output', '/tmp/plan.json')
        self.assertEqual(result.returncode, 0, result.stderr)
        for expected in ('--state-root', '/tmp/state', '--claude-skill-root', '/tmp/claude', '--codex-skill-root', '/tmp/codex'):
            self.assertIn(expected, result.stdout)

    def test_missing_option_value_is_actionable(self):
        result, _, _ = self.invoke('--target')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BLOCKED', result.stderr)

    def test_check_delegates_read_only_source_and_generated_validation(self):
        result, sentinel, files = self.invoke('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("'validate'", result.stdout)
        self.assertIn("'check-generated'", result.stdout)
        self.assertIn('source with spaces', result.stdout)
        self.assertEqual(sentinel, 'custom command sentinel\n')
        self.assertEqual(files, ['update.md'])


if __name__ == '__main__':
    unittest.main()
