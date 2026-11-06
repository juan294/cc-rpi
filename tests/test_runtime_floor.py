"""The engine refuses an unsupported Python before it plans, renders or writes."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "templates/scripts/rpi-distribution.py"
# Run the real script as __main__ under an interpreter that reports an old version.
OLD_RUNTIME = ('import runpy, sys; sys.version_info = (3, 9, 6, "final", 0); '
               'sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name="__main__")')


class EngineRuntimeFloorTests(unittest.TestCase):
    def run_old(self, *arguments, cwd=None):
        return subprocess.run([sys.executable, "-c", OLD_RUNTIME, str(ENGINE), *map(str, arguments)],
                              capture_output=True, text=True, cwd=cwd)

    def test_old_interpreter_is_refused_before_any_plan_or_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            project = workspace / "project"
            project.mkdir()
            plan = workspace / "plan.json"
            result = self.run_old("plan", "--source", ROOT, "--target", project, "--output", plan)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertFalse(plan.exists())
            self.assertEqual(list(project.iterdir()), [])
            message = result.stderr
            self.assertTrue(message.startswith("BLOCKED / WHY: "), message)
            self.assertIn("Python 3.11 or newer", message)
            self.assertIn("3.9.6", message)
            self.assertIn(sys.executable, message)
            fix = message.split(" / FIX: ", 1)[1]
            self.assertTrue("python3.1" in fix or "uv run" in fix, fix)
            self.assertIn("rpi-distribution.py plan", fix)
            self.assertIn(str(plan), fix, "the fix reruns the same request on a supported interpreter")

    def test_every_command_is_refused_not_only_lifecycle_ones(self):
        for command in ("validate", "counts", "check", "diagnose"):
            with self.subTest(command=command):
                result = self.run_old(command, "--source", ROOT)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("Python 3.11 or newer", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_supported_interpreter_is_unaffected(self):
        result = subprocess.run([sys.executable, str(ENGINE), "counts", "--source", str(ROOT)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("workflow", json.loads(result.stdout))

    def test_guard_precedes_syntax_and_imports_newer_than_python_38(self):
        # The guard must run on an interpreter that cannot import newer modules;
        # compile the file for the oldest syntax this repository still parses.
        import ast
        source = ENGINE.read_text()
        ast.parse(source, feature_version=(3, 9))
        guard = source.index("sys.version_info < (3, 11)")
        for marker in ("import argparse", "import importlib.util", "from pathlib import Path"):
            self.assertLess(guard, source.index(marker), marker)


if __name__ == "__main__":
    unittest.main()
