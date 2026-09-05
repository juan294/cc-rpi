"""Behavioral regressions for the sequential, fail-closed local gate."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify-local.py"
CHECKS = SCRIPT.with_name("verification-checks.py")


class LocalVerificationTests(unittest.TestCase):
    def run_checks(self, checks):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "input.txt").write_text("candidate\n")
            config = root / "checks.json"
            config.write_text(json.dumps(checks))
            evidence = root / ".rpi/local/result.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root),
                 "--checks", str(config), "--evidence", str(evidence)],
                capture_output=True, text=True)
            return result, json.loads(evidence.read_text()) if evidence.exists() else None

    def test_earlier_exit_seven_is_not_hidden_by_later_success(self):
        result, evidence = self.run_checks([
            {"name": "first", "argv": [sys.executable, "-c", "raise SystemExit(7)"]},
            {"name": "second", "argv": [sys.executable, "-c", "print('ran second')"]},
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([c["exit_code"] for c in evidence["checks"]], [7, 0])
        self.assertFalse(evidence["passed"])
        self.assertIn("ran second", result.stdout)
        self.assertEqual(len(evidence["identity"]["sha256"]), 64)
        self.assertGreater(evidence["identity"]["file_count"], 0)

    def test_empty_inventory_and_missing_executable_fail(self):
        result, _ = self.run_checks([])
        self.assertNotEqual(result.returncode, 0)
        result, evidence = self.run_checks([
            {"name": "missing", "argv": ["cc-rpi-nonexistent-executable"]}])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(evidence["checks"][0]["exit_code"], 127)

    def test_success_produces_custom_not_full_gate_evidence(self):
        result, evidence = self.run_checks([
            {"name": "ok", "argv": [sys.executable, "-c", "pass"]}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(evidence["passed"])
        self.assertEqual(evidence["suite"], "custom")

    def test_changed_tested_inputs_invalidate_evidence(self):
        result, evidence = self.run_checks([
            {"name": "mutate", "argv": [sys.executable, "-c",
             "from pathlib import Path; Path('input.txt').write_text('changed')"]}])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(evidence["identity_unchanged"])

    def test_evidence_cannot_overwrite_candidate_or_escape_through_symlink(self):
        for escaped in (False, True):
            with self.subTest(escaped=escaped), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                subprocess.run(["git", "init", "-q", str(root)], check=True)
                sentinel = root / "README.md"
                sentinel.write_text("user sentinel\n")
                config = root / "checks.json"
                config.write_text(json.dumps([{"name": "ok", "argv": [sys.executable, "-c", "pass"]}]))
                evidence = sentinel
                if escaped:
                    (root / ".rpi").mkdir()
                    (root / ".rpi/local").symlink_to(root, target_is_directory=True)
                    evidence = root / ".rpi/local/README.md"
                result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root),
                                         "--checks", str(config), "--evidence", str(evidence)],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(sentinel.read_text(), "user sentinel\n")


class CoverageProducerTests(unittest.TestCase):
    def producer(self, first, second):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "templates/scripts"
            scripts.mkdir(parents=True)
            (scripts / "validate-findings.py").write_text(first)
            (scripts / "contract-metrics.py").write_text(second)
            output = root / "output.txt"
            result = subprocess.run([sys.executable, str(CHECKS), "coverage",
                                     "--root", str(root), "--github-output", str(output)],
                                    capture_output=True, text=True)
            return result, output.read_text() if output.exists() else ""

    def test_preserves_count_only_semantics(self):
        result, output = self.producer("print('SELF-TEST PASS: one')",
                                       "print('SELF-TEST PASS: two')")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("test_count=2\n", output)
        self.assertIn("coverage_percent=null\n", output)
        self.assertIn("producer=count_only\n", output)

    def test_each_suite_must_succeed_and_emit_nonzero_results(self):
        for source in ("pass", "print('SELF-TEST PASS'); raise SystemExit(7)"):
            with self.subTest(source=source):
                result, output = self.producer(source, "print('SELF-TEST PASS: later')")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output, "")
                self.assertIn("later", result.stdout)


class RequiredInputTests(unittest.TestCase):
    def test_staged_deletion_cannot_remove_required_syntax_input(self):
        for required in ("templates/settings.json.template", ".github/ISSUE_TEMPLATE/config.yml"):
            with self.subTest(required=required), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                subprocess.run(["git", "init", "-q", str(root)], check=True)
                files = {"templates/settings.json.template": "{}", ".github/ISSUE_TEMPLATE/config.yml": "{}",
                         "other.json": "{}", "other.yml": "{}", "other.py": "pass"}
                for name, source in files.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(source)
                subprocess.run(["git", "-C", str(root), "add", "."], check=True)
                subprocess.run(["git", "-C", str(root), "rm", "--cached", required], check=True,
                               capture_output=True)
                (root / required).unlink()
                result = subprocess.run([sys.executable, str(CHECKS), "syntax", "--root", str(root)],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(required, result.stderr)

    def test_nonempty_shell_inventory_cannot_hide_missing_required_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "other.sh").write_text("#!/bin/bash\ntrue\n")
            result = subprocess.run([sys.executable, str(CHECKS), "shellcheck", "--root", str(root)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("scripts/install.sh", result.stderr)


if __name__ == "__main__":
    unittest.main()
