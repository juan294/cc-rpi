"""Independent filesystem oracles for migration of synthetic adopter knowledge.

Every source, project, user location and recovery path is temporary. These tests
exercise the public CLI; no adopter checkout or native user profile is a target.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "templates/scripts/rpi-distribution.py"
FIXTURES = json.loads((ROOT / "tests/fixtures/lifecycle-adopters.json").read_text())


class LifecycleAdopterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rpi adopter é 'quote' & ")
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.source = self.workspace / "source"
        self.project = self.workspace / "project"
        self.project.mkdir()
        self.plans = self.workspace / "plans"
        self.plans.mkdir()
        self.plan_number = 0
        self.outside = self.workspace / "outside-sentinel.txt"
        self.outside.write_bytes(b"Outside every bound installation root.\n")
        self.make_source()

    def write(self, root, relative, content):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def make_source(self):
        components = []
        for name in ("rpi-plan", "rpi-release"):
            resources = (["references/playbook.md", "references/nested/detail.md", "scripts/validate.py"]
                         if name == "rpi-plan" else [])
            body = "Preserve project release requirements.\n" + "\n".join("Read " + p + "." for p in resources) + "\n"
            self.write(self.source, "templates/skills/" + name + "/SKILL.md",
                       '---\nname: ' + name + '\ndescription: "Synthetic workflow contract."\n---\n\n' + body)
            for resource in resources:
                self.write(self.source, "templates/skills/" + name + "/" + resource,
                           "# Required independent fixture resource: " + resource + "\n")
            components.append({
                "id": "skill:" + name, "kind": "skill", "category": "workflow", "name": name,
                "source": "templates/skills/" + name, "harnesses": ["claude", "codex"],
                "scope": "project", "selection": "default", "dependencies": [],
                "resources": resources, "former_paths": [".claude/commands/" + name[4:] + ".md"],
                "aliases": [name[4:]], "explicit_only": name == "rpi-release",
                "ownership": {"direct": "cc-rpi", "plugin": "native-manager"}})
        self.write(self.source, "templates/instructions/policy.md", "Keep local verification and bounded work.\n")
        components.append({"id": "instruction:policy", "kind": "instruction",
                           "source": "templates/instructions/policy.md", "harnesses": ["claude", "codex"],
                           "scope": "project", "selection": "default", "dependencies": [],
                           "ownership": {"direct": "cc-rpi", "plugin": "cc-rpi"}})
        self.write(self.source, "templates/distribution.json", json.dumps({
            "schema_version": 1, "version": "2.0.0", "managed_root_budget_bytes": 8192,
            "components": components, "consolidations": [],
            "self_application": {"claude": "direct", "codex": "direct", "domains": []}}))
        self.write(self.source, "templates/adapters/claude.json", json.dumps({
            "schema_version": 1, "harness": "claude", "preamble": "Literal request: $ARGUMENTS\n\n",
            "frontmatter": {"argument-hint": "[request]"}, "explicit_field": "disable-model-invocation"}))
        self.write(self.source, "templates/adapters/codex.json", json.dumps({
            "schema_version": 1, "harness": "codex", "preamble": "", "frontmatter": {},
            "sidecar": "agents/openai.yaml", "explicit_field": "policy.allow_implicit_invocation"}))
        self.write(self.source, "templates/commands/plan.md", "# Proven v1 plan\n\nRead the old project plan.\n")
        self.git("init", "-q")
        self.base_revision = self.commit_source("Synthetic immutable baseline")

    def git(self, *arguments):
        result = subprocess.run(["git", "-C", str(self.source), *arguments], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit_source(self, message):
        self.git("add", ".")
        self.git("-c", "user.name=RPI Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def invoke(self, *arguments):
        return subprocess.run([sys.executable, str(ENGINE), *map(str, arguments)],
                              capture_output=True, text=True)

    def plan(self, action="install", *extra):
        self.plan_number += 1
        path = self.plans / (str(self.plan_number) + ".json")
        result = self.invoke("plan", "--source", self.source, "--target", self.project,
                             "--harness", "both", "--route", "direct", "--action", action,
                             "--output", path, *extra)
        self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
        self.assertTrue(path.is_file(), result.stdout + result.stderr)
        return json.loads(path.read_text()), path

    def apply_ready(self, action="install", *extra):
        plan, path = self.plan(action, *extra)
        diagnostic = {key: plan.get(key) for key in ("status", "conflicts", "retained")}
        self.assertIn(plan["status"], ("ready", "noop"), json.dumps(diagnostic, indent=2))
        result = self.invoke("apply", "--plan", path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return plan

    def snapshot(self, root=None, include_local=False):
        root = root or self.project
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*")
                if p.is_file() and (include_local or ".rpi/local/" not in str(p.relative_to(root)))}

    def assert_preserved(self, fixture):
        for name in fixture["preserve"]:
            self.assertEqual((self.project / name).read_text(), fixture["files"][name], name)
        instructions = "\n".join((self.project / name).read_text() for name in ("AGENTS.md", "CLAUDE.md"))
        for fragment in fixture["instruction_fragments"]:
            self.assertIn(fragment, instructions)
        self.assertEqual(self.outside.read_bytes(), b"Outside every bound installation root.\n")

    def test_synthetic_adopter_knowledge_survives_adoption_and_detach(self):
        for fixture in FIXTURES:
            with self.subTest(adopter=fixture["name"]):
                shutil.rmtree(self.project)
                self.project.mkdir()
                for name, content in fixture["files"].items():
                    self.write(self.project, name, content)
                before = self.snapshot()
                plan, path = self.plan()
                if plan["status"] == "conflict":
                    result = self.invoke("apply", "--plan", path)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertEqual(self.snapshot(), before)
                    self.assertTrue(plan["conflicts"])
                else:
                    self.assertEqual(self.invoke("apply", "--plan", path).returncode, 0)
                    self.assert_preserved(fixture)
                    self.apply_ready("detach")
                    detached = self.snapshot()
                    self.apply_ready("detach")
                    self.assertEqual(self.snapshot(), detached, "second detach must have no timestamp-only changes")
                self.assert_preserved(fixture)

    def test_generated_vendor_blocks_allow_real_adoption(self):
        fixture = next(f for f in FIXTURES if f["name"] == "generated-Next")
        for name, content in fixture["files"].items():
            self.write(self.project, name, content)
        self.apply_ready()
        self.assert_preserved(fixture)
        for harness in (".claude", ".agents"):
            self.assertTrue((self.project / harness / "skills/rpi-plan/SKILL.md").is_file())

    def test_clean_v1_alias_migrates_only_with_immutable_baseline(self):
        old = (self.source / "templates/commands/plan.md").read_bytes()
        self.write(self.project, ".claude/commands/plan.md", old.decode())
        self.apply_ready("install", "--legacy-base", self.base_revision)
        self.assertFalse((self.project / ".claude/commands/plan.md").exists())
        self.assertTrue((self.project / ".agents/skills/rpi-plan/SKILL.md").is_file())
        self.assertTrue(any(p.is_file() and p.read_bytes() == old
                            for p in (self.project / ".rpi").rglob("*")), "retired alias recovery bytes must survive")

    def prepare_v1_domain_and_rule(self):
        manifest_path = self.source / "templates/distribution.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["components"].extend([
            {"id": "skill:git-workflow", "kind": "skill", "category": "domain", "name": "git-workflow",
             "source": "templates/skills/git-workflow", "harnesses": ["claude", "codex"], "scope": "project",
             "selection": "default", "dependencies": [], "resources": ["references/advice.md"],
             "former_paths": [".claude/skills/git-workflow"], "aliases": [], "explicit_only": False,
             "ownership": {"direct": "cc-rpi", "plugin": "native-manager"}},
            {"id": "rule:testing", "kind": "rule", "source": "templates/rules/testing.md",
             "harnesses": ["claude", "codex"], "scope": "project", "selection": "default", "dependencies": [],
             "mapping": {"mode": "conditional", "paths": ["**/tests/**"], "tasks": ["testing"]},
             "ownership": {"direct": "cc-rpi", "plugin": "cc-rpi"}}])
        manifest_path.write_text(json.dumps(manifest))
        self.write(self.source, "templates/instructions/policy.md", "Read .rpi/rules/testing.md for testing.\n")
        originals = {
            "skills/git-workflow/SKILL.md": '---\nname: git-workflow\ndescription: "Git workflow fixture."\n---\n\nRead references/advice.md.\nVersion one workflow behavior.\n',
            "skills/git-workflow/references/advice.md": "Version one bundled advice.\n",
            "rules/testing.md": '---\npaths:\n  - "**/tests/**"\n---\n\nVersion one conditional testing rule.\n'}
        for relative, content in originals.items():
            self.write(self.source, "templates/" + relative, content)
            self.write(self.project, ".claude/" + relative, content)
        revision = self.commit_source("Proven v1 domain, resource and conditional rule")
        for relative, content in originals.items():
            self.write(self.source, "templates/" + relative, content.replace("Version one", "Version two"))
        self.commit_source("V2 domain and conditional rule behavior")
        return revision, originals

    def test_clean_v1_domain_resources_and_rules_migrate_from_immutable_base(self):
        revision, originals = self.prepare_v1_domain_and_rule()
        self.apply_ready("install", "--legacy-base", revision)
        for relative, old in originals.items():
            installed = (self.project / ".claude" / relative).read_text()
            self.assertIn("Version two", installed, relative)
            self.assertNotIn("Version one", installed, relative)
            self.assertTrue(any(p.is_file() and p.read_bytes() == old.encode()
                                for p in (self.project / ".rpi").rglob("*")), relative + " needs recovery bytes")
        self.assertTrue((self.project / ".agents/skills/git-workflow/references/advice.md").is_file())
        self.assertEqual((self.project / ".rpi/rules/testing.md").read_bytes(),
                         (self.source / "templates/rules/testing.md").read_bytes())

    def test_modified_v1_domain_resource_is_not_claimed_by_immutable_source_alone(self):
        revision, _ = self.prepare_v1_domain_and_rule()
        self.write(self.project, ".claude/skills/git-workflow/references/advice.md", "Unproven project-specific release requirement.\n")
        before = self.snapshot()
        plan, path = self.plan("install", "--legacy-base", revision)
        self.assertEqual(plan["status"], "conflict")
        self.assertEqual(self.invoke("apply", "--plan", path).returncode, 2)
        self.assertEqual(self.snapshot(), before)

    def test_legacy_source_does_not_claim_matching_bytes_at_a_non_v1_path(self):
        revision, originals = self.prepare_v1_domain_and_rule()
        # v1's known destination was .claude/skills. A user's same-byte copy at
        # the new native Codex destination does not prove a v1 installation.
        self.write(self.project, ".agents/skills/git-workflow/SKILL.md", originals["skills/git-workflow/SKILL.md"])
        before = self.snapshot()
        plan, path = self.plan("install", "--legacy-base", revision)
        self.assertEqual(plan["status"], "conflict")
        self.assertEqual(self.invoke("apply", "--plan", path).returncode, 2)
        self.assertEqual(self.snapshot(), before)

    def test_selected_harness_preserves_other_route_and_domain_selection(self):
        self.prepare_v1_domain_and_rule()
        shutil.rmtree(self.project)
        self.project.mkdir()
        manifest_path = self.source / "templates/distribution.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["components"].append({
            "id": "skill:python-rules", "kind": "skill", "category": "domain", "name": "python-rules",
            "source": "templates/skills/python-rules", "harnesses": ["claude", "codex"], "scope": "project",
            "selection": "optional", "dependencies": [], "resources": [], "former_paths": [],
            "aliases": [], "explicit_only": False,
            "ownership": {"direct": "cc-rpi", "plugin": "native-manager"}})
        manifest_path.write_text(json.dumps(manifest))
        self.write(self.source, "templates/skills/python-rules/SKILL.md",
                   '---\nname: python-rules\ndescription: "Optional Python knowledge."\n---\n\nUse the configured Python environment.\n')
        self.commit_source("Add a separately selectable optional domain")
        self.apply_ready("install", "--harness", "claude", "--domain", "git-workflow")
        claude_before = self.snapshot(self.project / ".claude")
        state_path = self.project / ".rpi/manifest.json"
        claude_selection = json.loads(state_path.read_text())["installations"]["claude"]
        self.apply_ready("install", "--harness", "codex", "--route", "plugin", "--domain", "python-rules")
        state = json.loads(state_path.read_text())
        selections = {harness: {key: selection[key] for key in ("route", "domains")}
                      for harness, selection in state["installations"].items()}
        self.assertEqual(selections, {
            "claude": {"route": "direct", "domains": ["git-workflow"]},
            "codex": {"route": "plugin", "domains": ["python-rules"]}})
        self.assertEqual(state["installations"]["claude"], claude_selection)
        self.assertEqual(self.snapshot(self.project / ".claude"), claude_before)
        self.assertFalse((self.project / ".agents/skills/rpi-plan/SKILL.md").exists())

        # Omitting --route inherits Codex's own prior route, never a global
        # last-used route or the other harness's direct installation.
        artifact = self.plans / "codex-domain-update.json"
        result = self.invoke("plan", "--source", self.source, "--target", self.project,
                             "--harness", "codex", "--action", "update", "--domain", "git-workflow",
                             "--output", artifact)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.invoke("apply", "--plan", artifact).returncode, 0)
        state = json.loads(state_path.read_text())
        self.assertEqual(state["installations"]["claude"], claude_selection)
        self.assertEqual(state["installations"]["codex"]["route"], "plugin")
        self.assertEqual(state["installations"]["codex"]["domains"], ["git-workflow"])
        self.assertEqual(self.snapshot(self.project / ".claude"), claude_before)
        self.assertFalse((self.project / ".agents/skills/rpi-plan/SKILL.md").exists())

    def test_missing_provenance_never_claims_custom_alias(self):
        content = "# Custom plan\n\nThis legacy filename does not establish ownership.\n"
        self.write(self.project, ".claude/commands/plan.md", content)
        self.write(self.project, ".claude/cc-rpi-sync.json", '{"version":"1.29.0"}\n')
        plan, path = self.plan()
        if plan["status"] != "conflict":
            self.assertEqual(self.invoke("apply", "--plan", path).returncode, 0)
        self.assertEqual((self.project / ".claude/commands/plan.md").read_text(), content)
        self.assertTrue(plan.get("retained") or plan.get("conflicts"), "unproven legacy ownership must be diagnosed")

    def test_full_directories_and_read_only_check(self):
        self.apply_ready()
        for harness in (".claude", ".agents"):
            for resource in ("references/playbook.md", "references/nested/detail.md", "scripts/validate.py"):
                self.assertEqual((self.project / harness / "skills/rpi-plan" / resource).read_bytes(),
                                 (self.source / "templates/skills/rpi-plan" / resource).read_bytes())
        before = self.snapshot(include_local=True)
        result = self.invoke("check", "--source", self.source, "--target", self.project,
                             "--harness", "both", "--route", "direct")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(include_local=True), before)
        before = self.snapshot()
        self.apply_ready("update")
        self.assertEqual(self.snapshot(), before, "repeat updates must not create timestamp-only diffs")

    def test_local_only_change_survives_update_and_repeated_detach(self):
        self.apply_ready()
        local = self.project / ".agents/skills/rpi-plan/references/playbook.md"
        local.write_text("Project release override: all eight maneuvers must PASS.\n")
        self.apply_ready("update")
        self.assertEqual(local.read_text(), "Project release override: all eight maneuvers must PASS.\n")
        self.apply_ready("detach")
        detached = self.snapshot()
        self.assertEqual(local.read_text(), "Project release override: all eight maneuvers must PASS.\n")
        self.apply_ready("detach")
        self.assertEqual(self.snapshot(), detached)

    def test_source_only_change_updates_complete_resource(self):
        self.apply_ready()
        self.write(self.source, "templates/skills/rpi-plan/references/playbook.md", "New upstream playbook contract.\n")
        self.commit_source("Update upstream playbook")
        self.apply_ready("update")
        for harness in (".claude", ".agents"):
            self.assertEqual((self.project / harness / "skills/rpi-plan/references/playbook.md").read_text(),
                             "New upstream playbook contract.\n")

    def test_both_changed_conflict_is_all_or_nothing(self):
        self.apply_ready()
        self.write(self.project, ".agents/skills/rpi-plan/references/playbook.md", "Local release strictness.\n")
        self.write(self.source, "templates/skills/rpi-plan/references/playbook.md", "Different upstream release contract.\n")
        self.write(self.source, "templates/skills/rpi-plan/references/nested/detail.md", "Independent upstream change.\n")
        self.commit_source("Conflicting upstream change")
        before = self.snapshot()
        plan, path = self.plan("update")
        self.assertEqual(plan["status"], "conflict")
        self.assertTrue(plan["conflicts"])
        result = self.invoke("apply", "--plan", path)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_same_source_detects_missing_owned_resource(self):
        self.apply_ready()
        (self.project / ".agents/skills/rpi-plan/scripts/validate.py").unlink()
        before = self.snapshot(include_local=True)
        result = self.invoke("check", "--source", self.source, "--target", self.project,
                             "--harness", "both", "--route", "direct")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(include_local=True), before)

    def test_mixed_settings_are_never_committed_as_baseline(self):
        fixture = next(f for f in FIXTURES if f["name"] == "Coach-partial-policy")
        for name, content in fixture["files"].items():
            self.write(self.project, name, content)
        plan, path = self.plan()
        if plan["status"] != "conflict":
            self.assertEqual(self.invoke("apply", "--plan", path).returncode, 0)
        self.assert_preserved(fixture)
        settings = fixture["files"][".claude/settings.json"].encode()
        for path in (self.project / ".rpi/baselines").rglob("*"):
            if path.is_file():
                self.assertNotIn(b"SYNTHETIC_PRIVATE_VALUE", path.read_bytes())
                self.assertNotEqual(path.name, hashlib.sha256(settings).hexdigest())

    def test_malformed_settings_block_before_any_project_mutation(self):
        self.write(self.project, ".claude/settings.json", '{"permissions": {"deny": ["Read(private/**)"]}, BROKEN\n')
        self.write(self.project, "AGENTS.md", "Keep project knowledge intact.\n")
        before = self.snapshot(include_local=True)
        result = self.invoke("plan", "--source", self.source, "--target", self.project,
                             "--harness", "both", "--route", "direct", "--action", "install",
                             "--output", self.plans / "malformed.json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("settings", result.stdout + result.stderr)
        self.assertEqual(self.snapshot(include_local=True), before)

    def test_upstream_rename_and_delete_preserve_local_modified_old_resource(self):
        self.apply_ready()
        preserved = "Project-only release requirement: all eight maneuvers must pass.\n"
        self.write(self.project, ".agents/skills/rpi-plan/references/playbook.md", preserved)
        skill = self.source / "templates/skills/rpi-plan"
        (skill / "references/playbook.md").unlink()
        (skill / "references/nested/detail.md").rename(skill / "references/nested/renamed.md")
        entry = skill / "SKILL.md"
        entry.write_text(entry.read_text().replace("Read references/playbook.md.\n", "")
                         .replace("references/nested/detail.md", "references/nested/renamed.md"))
        manifest_path = self.source / "templates/distribution.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["components"][0]["resources"] = ["references/nested/renamed.md", "scripts/validate.py"]
        manifest_path.write_text(json.dumps(manifest))
        self.commit_source("Rename one resource and retire another")
        self.apply_ready("update")
        self.assertEqual((self.project / ".agents/skills/rpi-plan/references/playbook.md").read_text(), preserved)
        self.assertFalse((self.project / ".claude/skills/rpi-plan/references/playbook.md").exists())
        for harness in (".claude", ".agents"):
            installed = self.project / harness / "skills/rpi-plan/references/nested"
            self.assertFalse((installed / "detail.md").exists())
            self.assertEqual((installed / "renamed.md").read_bytes(), (skill / "references/nested/renamed.md").read_bytes())

    def test_unknown_same_name_direct_skill_blocks_without_overwrite(self):
        original = '---\nname: rpi-plan\ndescription: "Private team planner."\n---\n\nKeep our custom planning contract.\n'
        self.write(self.project, ".agents/skills/rpi-plan/SKILL.md", original)
        self.write(self.project, ".agents/skills/rpi-plan/references/team.md", "User-owned reference.\n")
        before = self.snapshot()
        plan, path = self.plan()
        self.assertEqual(plan["status"], "conflict")
        self.assertTrue(plan["conflicts"])
        result = self.invoke("apply", "--plan", path)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_reverse_instruction_import_migrates_without_losing_facts(self):
        agent_fact = "Keep the project's tenant identifiers stable."
        claude_fact = "Use the existing integration branch for completed work."
        self.write(self.project, "AGENTS.md", "# Existing project\n\n@CLAUDE.md\n\n" + agent_fact + "\n")
        self.write(self.project, "CLAUDE.md", "# Existing assistant\n\n" + claude_fact + "\n")
        self.apply_ready()
        agents = (self.project / "AGENTS.md").read_text()
        claude = (self.project / "CLAUDE.md").read_text()
        self.assertNotRegex(agents, r"(?m)^@(?:\./)?CLAUDE\.md\s*$")
        self.assertRegex(claude, r"(?m)^@AGENTS\.md\s*$")
        self.assertIn(agent_fact, agents + claude)
        self.assertIn(claude_fact, agents + claude)
        self.apply_ready("detach")
        agents = (self.project / "AGENTS.md").read_text()
        claude = (self.project / "CLAUDE.md").read_text()
        self.assertIn(agent_fact, agents + claude)
        self.assertIn(claude_fact, agents + claude)
        self.assertRegex(claude, r"(?m)^@AGENTS\.md\s*$", "the surviving project knowledge still needs its import")

    def test_owned_symlink_detach_removes_entries_without_following_targets(self):
        self.apply_ready()
        manifest_path = self.project / ".rpi/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        missing_target = self.workspace / "must-remain-missing.txt"
        links = [
            (".agents/skills/rpi-plan/references/playbook.md", self.outside),
            (".agents/skills/rpi-plan/references/nested/detail.md", missing_target)]
        for destination, target in links:
            path = self.project / destination
            path.unlink()
            link_text = os.path.relpath(target, path.parent)
            path.symlink_to(link_text)
            # This explicit fixture represents a prior installer that owned
            # the link itself. Replacing a file with an unknown user link does
            # not establish this provenance (covered separately below).
            baseline = link_text.encode()
            baseline_hash = hashlib.sha256(baseline).hexdigest()
            (self.project / ".rpi/baselines" / baseline_hash).write_bytes(baseline)
            entry = next(e for e in manifest["entries"] if e["destination"] == destination)
            entry.update(node_kind="symlink", base_hash=baseline_hash)
        manifest_path.write_text(json.dumps(manifest))
        self.apply_ready("detach")
        for destination, _ in links:
            self.assertFalse((self.project / destination).is_symlink())
            self.assertFalse((self.project / destination).exists())
        self.assertEqual(self.outside.read_bytes(), b"Outside every bound installation root.\n")
        self.assertFalse(missing_target.exists(), "detaching a dangling link must not create its target")

    def test_unknown_replacement_symlink_never_becomes_owned_by_filename(self):
        self.apply_ready()
        path = self.project / ".agents/skills/rpi-plan/references/playbook.md"
        path.unlink()
        path.symlink_to(os.path.relpath(self.outside, path.parent))
        plan, artifact = self.plan("detach")
        if plan["status"] != "conflict":
            self.assertEqual(self.invoke("apply", "--plan", artifact).returncode, 0)
        self.assertTrue(path.is_symlink())
        self.assertEqual(self.outside.read_bytes(), b"Outside every bound installation root.\n")

    def test_changed_rollback_journal_cannot_rebind_an_outside_root(self):
        self.apply_ready()
        journal_path = next((self.project / ".rpi/local/transactions").glob("*/journal.json"))
        journal = json.loads(journal_path.read_text())
        original = self.outside.read_bytes()
        def file_node(content):
            return {"kind": "file", "data": base64.b64encode(content).decode(),
                    "sha256": hashlib.sha256(content).hexdigest(), "mode": 0o644}
        journal["roots"] = {"project": str(self.workspace)}
        journal["operations"] = [{"root_id": "project", "destination": self.outside.name,
                                  "before": file_node(b"Corrupted outside the installation root.\n"),
                                  "after": file_node(original)}]
        journal["completed"] = 1
        journal_path.write_text(json.dumps(journal))
        result = self.invoke("rollback", "--journal", journal_path)
        self.assertIn(result.returncode, (1, 2), result.stdout + result.stderr)
        self.assertEqual(self.outside.read_bytes(), original)

    def test_project_plan_with_private_preimages_is_ignored_before_apply(self):
        result = subprocess.run(["git", "-C", str(self.project), "init", "-q"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write(self.project, "AGENTS.md", "Private synthetic project context belongs in local recovery only.\n")
        artifact = self.project / ".rpi/local/plans/adoption.json"
        result = self.invoke("plan", "--source", self.source, "--target", self.project,
                             "--harness", "both", "--route", "direct", "--action", "install",
                             "--output", artifact)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(artifact.is_file())
        ignored = subprocess.run(["git", "-C", str(self.project), "check-ignore", "--quiet",
                                  ".rpi/local/plans/adoption.json"], capture_output=True, text=True)
        self.assertEqual(ignored.returncode, 0, "private plan is stageable before apply: " + ignored.stderr)
        self.assertFalse((self.project / ".rpi/manifest.json").exists(), "planning must not mark the project installed")


if __name__ == "__main__":
    unittest.main()
