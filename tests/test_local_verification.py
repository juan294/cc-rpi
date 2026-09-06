"""Behavioral regressions for the sequential, fail-closed local gate."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify-local.py"
CHECKS = SCRIPT.with_name("verification-checks.py")


class EnvironmentTests(unittest.TestCase):
    def test_locale_timezone_and_python_settings_bind_receipts_without_recording_values(self):
        spec = importlib.util.spec_from_file_location("candidate_settings_test", SCRIPT.with_name("candidate.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        baseline = module.environment({"PATH": os.defpath})
        for name in ("LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "LC_COLLATE", "LC_MESSAGES",
                     "LC_MONETARY", "LC_NUMERIC", "LC_TIME", "TZ", "PYTHONUTF8",
                     "PYTHONIOENCODING", "PYTHONCOERCECLOCALE", "PYTHONHASHSEED"):
            with self.subTest(name=name):
                changed = module.environment({"PATH": os.defpath, name: "private-setting-value"})
                self.assertNotEqual(baseline, changed)
                self.assertNotIn("private-setting-value", json.dumps(changed))
                self.assertNotEqual(baseline, module.environment({"PATH": os.defpath, name: ""}))
        self.assertEqual(baseline, module.environment({"PATH": os.defpath, "UNRELATED_SECRET": "private"}))

    def test_tool_replacement_changes_fingerprint_without_executing_it(self):
        spec = importlib.util.spec_from_file_location("candidate_test", SCRIPT.with_name("candidate.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool = root / "gh"
            sentinel = root / "executed"
            tool.write_text("#!/bin/sh\ntouch '" + str(sentinel) + "'\n")
            tool.chmod(0o755)
            fake_uname = root / 'uname'
            fake_uname.write_text(tool.read_text())
            fake_uname.chmod(0o755)
            before = module.environment({"PATH": str(root), "SECRET": "never-record-this"})
            self.assertFalse(sentinel.exists())
            self.assertNotIn("never-record-this", json.dumps(before))
            self.assertIsNone(before["executables"]["git"])
            tool.write_text(tool.read_text() + "# replacement\n")
            self.assertNotEqual(before, module.environment({"PATH": str(root)}))



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

    def test_declared_adopter_ci_selection_is_complete_and_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            local = root / ".rpi"
            local.mkdir()
            checks = [{"name": name, "argv": [sys.executable, "-c", "print(" + repr(name) + ")"]}
                      for name in ("test", "lint", "build")]
            (local / "policy.json").write_text(json.dumps({"schema_version": 1, "verification_checks": checks}))
            runtime = local / "scripts"
            runtime.mkdir()
            portable = runtime / "rpi-verify.py"
            portable.write_bytes(SCRIPT.read_bytes())
            (runtime / "rpi-candidate.py").write_bytes(SCRIPT.with_name("candidate.py").read_bytes())
            result = subprocess.run([sys.executable, str(portable)], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((local / "local/verification.json").read_text())
            self.assertEqual(report["suite"], "ci-equivalent")
            self.assertEqual([{"name": item["name"], "argv": item["argv"]} for item in report["checks"]], checks)
            self.assertFalse((runtime / "__pycache__").exists())

    def test_missing_or_ambiguous_project_selection_never_attests_complete_ci(self):
        for declaration in (None, '{"schema_version":1}', '{"schema_version":1,"verification_checks":[],"verification_checks":[]}'):
            with self.subTest(declaration=declaration), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                subprocess.run(["git", "init", "-q", str(root)], check=True)
                (root / ".rpi").mkdir()
                if declaration is not None:
                    (root / ".rpi/policy.json").write_text(declaration)
                result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("BLOCKED", result.stderr)
                self.assertFalse((root / ".rpi/local/verification.json").exists())

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
        self.assertTrue(evidence["environment_unchanged"])
        self.assertEqual(evidence["environment"], evidence["environment_after"])

    def test_changed_tested_inputs_invalidate_evidence(self):
        result, evidence = self.run_checks([
            {"name": "mutate", "argv": [sys.executable, "-c",
             "from pathlib import Path; Path('input.txt').write_text('changed')"]}])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(evidence["identity_unchanged"])

    def test_runtime_change_invalidates_otherwise_unchanged_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "input.txt").write_text("candidate\n")
            binaries = root / ".rpi/local/bin"
            binaries.mkdir(parents=True)
            tool = binaries / "gh"
            tool.write_text("#!/bin/sh\nexit 0\n")
            tool.chmod(0o755)
            config = root / ".rpi/local/checks.json"
            config.write_text(json.dumps([{"name": "mutate-runtime", "argv": [sys.executable, "-c",
                "from pathlib import Path; Path(" + repr(str(tool)) + ").write_text('changed runtime')"]}]))
            result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--checks", str(config)],
                env={**os.environ, "PATH": str(binaries) + os.pathsep + os.environ.get("PATH", "")},
                capture_output=True, text=True)
            report = json.loads((root / ".rpi/local/verification.json").read_text())
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(report["identity_unchanged"])
            self.assertFalse(report["environment_unchanged"])

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

    def test_predictable_temporary_symlink_cannot_overwrite_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            sentinel = root / "input.txt"
            sentinel.write_text("user sentinel\n")
            local = root / ".rpi/local"
            local.mkdir(parents=True)
            evidence = local / "result.json"
            evidence.with_suffix(".json.tmp").symlink_to(sentinel)
            config = local / "checks.json"
            config.write_text(json.dumps([{"name": "ok", "argv": [sys.executable, "-c", "pass"]}]))
            result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root),
                                     "--checks", str(config), "--evidence", str(evidence)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sentinel.read_text(), "user sentinel\n")
            self.assertFalse(evidence.is_symlink())
            self.assertTrue(json.loads(evidence.read_text())["passed"])


class CoverageProducerTests(unittest.TestCase):
    def producer(self, first, second):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "templates/scripts"
            scripts.mkdir(parents=True)
            (scripts / "validate-findings.py").write_text(first)
            (scripts / "contract-metrics.py").write_text(second)
            output = root / "output.txt"
            result = subprocess.run([sys.executable, str(CHECKS), "contract-tests",
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
