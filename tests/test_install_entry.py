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

    def test_default_preserves_unknown_commands_and_reports_pending_engine(self):
        result, sentinel, files = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('BLOCKED', result.stdout + result.stderr)
        self.assertEqual(sentinel, 'custom command sentinel\n')
        self.assertEqual(files, ['update.md'])

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
