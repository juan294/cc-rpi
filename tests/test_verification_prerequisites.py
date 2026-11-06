"""The prerequisite failure tells the owner which interpreter to put first on PATH."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / 'scripts/verification-checks.py'
# Run the real script under an interpreter on which the named module cannot be imported.
WITHOUT = ('import os, runpy, sys; sys.modules[sys.argv[1]] = None; sys.argv = sys.argv[2:]; '
           'sys.path.insert(0, os.path.dirname(sys.argv[0])); runpy.run_path(sys.argv[0], run_name="__main__")')


class PrerequisiteMessageTests(unittest.TestCase):
    def run_without(self, module, root):
        return subprocess.run([sys.executable, '-c', WITHOUT, module, str(CHECKS), 'prerequisites', '--root', str(root)],
                              capture_output=True, text=True)

    def fix(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(result.stderr.startswith('BLOCKED / WHY: '), result.stderr)
        return result.stderr.strip().split(' / FIX: ', 1)

    def test_missing_module_says_a_complete_python_must_come_first_on_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            for module in ('coverage', 'yaml'):
                with self.subTest(module=module):
                    why, fix = self.fix(self.run_without(module, temporary))
                    self.assertIn(module, why)
                    self.assertIn('Python 3.11 or newer', fix)
                    for requirement in ('PyYAML', 'coverage', 'uv'):
                        self.assertIn(requirement, fix)
                    self.assertIn('first on PATH', fix)
                    self.assertIn(sys.executable, fix, 'the failing interpreter is named')
                    self.assertNotIn('local virtual environment', fix, 'no virtual environment exists here')

    def test_an_existing_local_venv_is_named(self):
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / '.rpi/local/venv/bin').mkdir(parents=True)
            _, fix = self.fix(self.run_without('coverage', temporary))
            self.assertIn('PATH="' + str(Path(temporary).resolve() / '.rpi/local/venv/bin') + ':$PATH"', fix)


if __name__ == '__main__':
    unittest.main()
