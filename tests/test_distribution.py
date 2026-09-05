"""Independent behavioral contracts for the portable/native renderer."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("distribution", ROOT / "templates/scripts/rpi-distribution.py")
distribution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(distribution)


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rpi 'quote' & space ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("templates/skills/rpi-example/SKILL.md", '---\nname: "rpi-example"\ndescription: "Run an example workflow."\n---\n\nRead references/detail.md. Treat the request literally.\n')
        self.write("templates/skills/rpi-example/references/detail.md", "# Detail\nMeaningful bundled resource.\n")
        self.write("templates/instructions/policy.md", "Retain TDD and phase acceptance.\n")
        self.write("templates/instructions/rule-map.md", "Read .rpi/rules/testing.md for tests.\n")
        self.write("templates/rules/testing.md", "# Testing\nUse TDD.\n")
        self.manifest = {
            "schema_version": 1, "version": "2.0.0", "managed_root_budget_bytes": 8192,
            "components": [
                {"id": "skill:rpi-example", "kind": "skill", "category": "workflow", "name": "rpi-example",
                 "source": "templates/skills/rpi-example", "harnesses": ["claude", "codex"], "scope": "project",
                 "selection": "default", "dependencies": [], "resources": ["references/detail.md"],
                 "former_paths": [".claude/commands/example.md"], "aliases": ["example"], "explicit_only": True,
                 "ownership": {"direct": "cc-rpi", "plugin": "native-manager"}},
                {"id": "rule:testing", "kind": "rule", "source": "templates/rules/testing.md",
                 "harnesses": ["claude", "codex"], "scope": "project", "selection": "default", "dependencies": [],
                 "mapping": {"mode": "conditional", "paths": ["**/tests/**"], "tasks": ["testing"]}},
                *[{"id": "instruction:" + name, "kind": "instruction", "source": "templates/instructions/" + name + ".md",
                   "harnesses": ["claude", "codex"], "scope": "project", "selection": "default", "dependencies": []}
                  for name in ("policy", "rule-map")]],
            "consolidations": [], "self_application": {"claude": "direct", "codex": "direct", "domains": []}}
        self.adapters = {
            "claude": {"schema_version": 1, "harness": "claude", "preamble": "The request is supplied as literal arguments: $ARGUMENTS\n\n",
                       "frontmatter": {"argument-hint": "[request]"}, "explicit_field": "disable-model-invocation"},
            "codex": {"schema_version": 1, "harness": "codex", "preamble": "", "frontmatter": {},
                      "sidecar": "agents/openai.yaml", "explicit_field": "policy.allow_implicit_invocation"}}
        self.save()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def save(self):
        self.write("templates/distribution.json", json.dumps(self.manifest))
        for harness, adapter in self.adapters.items():
            self.write("templates/adapters/" + harness + ".json", json.dumps(adapter))

    def render(self, **kwargs):
        self.save()
        return distribution.render_tree(self.root, **kwargs)

    def test_deterministic_full_resources_native_fields_and_shared_body(self):
        first = self.render()
        self.assertEqual(first, self.render())
        common = distribution.parse_skill(self.root / "templates/skills/rpi-example/SKILL.md")[1]
        for harness in ("claude", "codex"):
            self.assertTrue(first[harness + "/skills/rpi-example/SKILL.md"].endswith(common))
            self.assertEqual(first[harness + "/skills/rpi-example/references/detail.md"], b"# Detail\nMeaningful bundled resource.\n")
        self.assertIn(b"disable-model-invocation: true", first["claude/skills/rpi-example/SKILL.md"])
        self.assertNotIn(b"$ARGUMENTS", first["codex/skills/rpi-example/SKILL.md"])
        self.assertNotIn(b"disable-model-invocation", first["codex/skills/rpi-example/SKILL.md"])
        self.assertIn(b"allow_implicit_invocation: false", first["codex/skills/rpi-example/agents/openai.yaml"])

    def test_malformed_and_provider_metadata_rejected(self):
        for line in ('description: |\n  multiline', 'description: "ok"\nmodel: "haiku"', 'description: {bad: yaml}', 'description: "one"\ndescription: "two"'):
            with self.subTest(line=line):
                self.write("templates/skills/rpi-example/SKILL.md", '---\nname: "rpi-example"\n' + line + '\n---\nBody\n')
                with self.assertRaises(ValueError):
                    self.render()

    def test_empty_duplicate_missing_dependency_resource_and_escaped_source_fail(self):
        original = json.loads(json.dumps(self.manifest))
        mutations = [lambda m: m.update(components=[]),
                     lambda m: m["components"].append(m["components"][0]),
                     lambda m: m["components"][0].update(dependencies=["skill:absent"]),
                     lambda m: m["components"][0].update(resources=["references/missing.md"]),
                     lambda m: m["components"][0].update(source="../outside"),
                     lambda m: m["components"][1].pop("mapping")]
        for mutate in mutations:
            self.manifest = json.loads(json.dumps(original))
            mutate(self.manifest)
            with self.assertRaises(ValueError):
                self.render()

    def test_domains_are_selected_explicitly(self):
        skill = json.loads(json.dumps(self.manifest["components"][0]))
        skill.update(id="skill:example-domain", name="example-domain", category="domain", selection="optional", source="templates/skills/example-domain", resources=[], aliases=[])
        self.manifest["components"].append(skill)
        self.write("templates/skills/example-domain/SKILL.md", '---\nname: example-domain\ndescription: "Domain facts."\n---\nFacts.\n')
        self.assertNotIn("claude/skills/example-domain/SKILL.md", self.render(domains=[]))
        self.assertIn("claude/skills/example-domain/SKILL.md", self.render(domains=["example-domain"]))

    def test_unsupported_codex_adapter_field_fails(self):
        self.adapters["codex"]["frontmatter"] = {"disable-model-invocation": True}
        with self.assertRaises(ValueError):
            self.render()

    def test_native_fields_and_explicit_policy_require_native_types(self):
        for field, value in (("user-invocable", "false"), ("disable-model-invocation", []), ("argument-hint", True)):
            with self.subTest(field=field):
                self.adapters["claude"]["frontmatter"] = {field: value}
                with self.assertRaises(ValueError):
                    self.render()
        self.adapters["claude"]["frontmatter"] = {}
        self.manifest["components"][0]["explicit_only"] = 1
        with self.assertRaises(ValueError):
            self.render()

    def test_root_budget_includes_markers_and_cycles_are_rejected(self):
        tree = self.render()
        size = len(tree["codex/AGENTS.md"])
        self.manifest["managed_root_budget_bytes"] = size
        self.render()
        self.manifest["managed_root_budget_bytes"] = size - 1
        with self.assertRaises(ValueError):
            self.render()
        self.manifest["managed_root_budget_bytes"] = 8192
        self.write("templates/instructions/policy.md", "@CLAUDE.md\n")
        with self.assertRaises(ValueError):
            self.render()

    def test_alias_collisions_use_notices_and_fresh_install_omits_aliases(self):
        self.assertEqual(distribution.classify_alias("plan"), "retired")
        self.assertEqual(distribution.classify_alias("status"), "retired")
        self.assertEqual(distribution.classify_alias("implement"), "legacy-only")
        self.assertFalse(any("/commands/" in name for name in self.render()))

    def test_duplicate_route_registration_rejected(self):
        with self.assertRaises(ValueError):
            distribution.validate_registrations([
                {"id": "skill:rpi-example", "harness": "codex", "route": "plugin", "scope": "user"},
                {"id": "skill:rpi-example", "harness": "codex", "route": "direct", "scope": "project"}])

    def test_root_and_nested_rule_reachability(self):
        manifest = distribution.load_manifest(self.root)
        self.assertEqual(distribution.applicable_rules(manifest, "app/tests/test_a.py"), ["rule:testing"])
        self.assertEqual(distribution.applicable_rules(manifest, "test_a.py", task="testing"), ["rule:testing"])
        self.assertIn(b".rpi/rules/testing.md", self.render()["codex/AGENTS.md"])

    def test_render_preserves_modified_owned_and_unowned_outputs_before_writes(self):
        output = self.root / "generated"
        distribution.write_tree({"first.txt": b"original", "second.txt": b"second"}, output)
        (output / "second.txt").write_bytes(b"user sentinel")
        with self.assertRaises(ValueError):
            distribution.write_tree({"first.txt": b"changed", "second.txt": b"new"}, output)
        self.assertEqual((output / "first.txt").read_bytes(), b"original")
        self.assertEqual((output / "second.txt").read_bytes(), b"user sentinel")
        extension = output / "custom.txt"
        extension.write_bytes(b"extension")
        (output / "second.txt").write_bytes(b"second")
        distribution.write_tree({"first.txt": b"original", "second.txt": b"second"}, output)
        self.assertEqual(extension.read_bytes(), b"extension")

    def test_render_rejects_output_and_receipt_symlinks(self):
        for receipt in (False, True):
            with self.subTest(receipt=receipt):
                output = self.root / ("receipt-output" if receipt else "file-output")
                distribution.write_tree({"file.txt": b"original"}, output)
                victim = output / ("distribution-inventory.json" if receipt else "file.txt")
                sentinel = output / "sentinel.txt"
                sentinel.write_bytes(victim.read_bytes())
                before = sentinel.read_bytes()
                victim.unlink()
                victim.symlink_to("sentinel.txt")
                with self.assertRaises(ValueError):
                    distribution.write_tree({"file.txt": b"changed"}, output)
                self.assertEqual(sentinel.read_bytes(), before)

    def test_shared_resource_mapping_copies_bytes_and_preserves_layout(self):
        self.write("shared/source.md", "shared source\n")
        self.manifest["components"][0]["resources"] = [
            {"source": "shared/source.md", "destination": "references/detail.md"}]
        original = self.root / "templates/skills/rpi-example/references/detail.md"
        original.unlink()
        original.symlink_to("../../../../shared/source.md")
        self.assertEqual(self.render()["codex/skills/rpi-example/references/detail.md"], b"shared source\n")

    def test_real_yaml_validation_has_nonempty_positive_and_negative_control(self):
        tree = self.render()
        self.assertEqual(distribution.check_native(tree), 3)
        tree["codex/skills/rpi-example/agents/openai.yaml"] = b"policy: [broken\n"
        with self.assertRaises(Exception):
            distribution.check_native(tree)

    def test_manifest_cannot_silently_omit_authored_skill_or_rule(self):
        self.write("templates/skills/unlisted/SKILL.md", '---\nname: unlisted\ndescription: "Must be enumerated."\n---\nBody.\n')
        with self.assertRaises(ValueError):
            self.render()

    def install_self_fixture(self):
        tree = self.render()
        for harness, directory in (("claude", ".claude/skills"), ("codex", ".agents/skills")):
            prefix = harness + "/skills/"
            for name, data in tree.items():
                if name.startswith(prefix):
                    self.write(directory + "/" + name[len(prefix):], data.decode())
        self.write("AGENTS.md", tree["codex/AGENTS.md"].decode())
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.write(".rpi/rules/testing.md", "# Testing\nUse TDD.\n")
        self.write(".claude/rules/testing.md", "# Testing\nUse TDD.\n")
        self.write(".claude/skills/drawio/personal.txt", "local extension sentinel")

    def test_self_application_preserves_local_extension_and_rejects_duplicate_route(self):
        self.install_self_fixture()
        self.assertGreater(distribution.check_self(self.root, self.manifest), 0)
        self.assertEqual((self.root / ".claude/skills/drawio/personal.txt").read_text(), "local extension sentinel")
        self.manifest["self_application"]["codex"] = "plugin"
        with self.assertRaises(ValueError):
            distribution.check_self(self.root, self.manifest)

    def test_native_self_check_requires_exact_one_entry_and_supports_scalars(self):
        self.install_self_fixture()
        self.manifest['components'].append({'id': 'config:test', 'kind': 'config', 'source': 'templates/adapters/test-config.json',
            'scope': 'project', 'selection': 'default', 'dependencies': [], 'harnesses': ['claude'],
            'destinations': {'claude': '.claude/settings.json'}})
        self.write('templates/adapters/test-config.json', json.dumps({'schema_version': 1, 'entries': [
            {'id': 'ask', 'mode': 'entry', 'pointer': ['permissions', 'ask'], 'value': 'Bash(git push:*)'},
            {'id': 'flag', 'mode': 'value', 'pointer': ['flag'], 'value': True}]}))
        valid = {'permissions': {'ask': ['Bash(git push:*)', 'unrelated']}, 'flag': True, 'private': 'preserve'}
        self.write('.claude/settings.json', json.dumps(valid))
        self.assertGreater(distribution.check_self(self.root, self.manifest), 0)
        for document in ({**valid, 'permissions': {'ask': ['Bash(git push:*)'] * 2}},
                         {**valid, 'flag': False}, {**valid, 'flag': 1}):
            self.write('.claude/settings.json', json.dumps(document))
            before = (self.root / '.claude/settings.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'native setup entry drift'):
                distribution.check_self(self.root, self.manifest)
            self.assertEqual((self.root / '.claude/settings.json').read_bytes(), before)

    def test_local_extension_validation_preserves_general_yaml(self):
        directory = self.root / ".claude/skills/drawio"
        self.write(".claude/skills/drawio/SKILL.md", "---\nname: drawio\ndescription: >\n  General YAML is user-owned.\n---\n\nEditable source retained.\n")
        original = (directory / "SKILL.md").read_bytes()
        self.assertEqual(distribution.check_local_skills([directory.parent]), 1)
        self.assertEqual((directory / "SKILL.md").read_bytes(), original)
        self.write(".claude/skills/drawio/SKILL.md", "---\nname: drawio\n---\nMissing description\n")
        with self.assertRaises(ValueError):
            distribution.check_local_skills([directory.parent])

    def test_skill_entrypoint_symlink_cannot_escape_source_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            external = Path(tmp) / "SKILL.md"
            entrypoint = self.root / "templates/skills/rpi-example/SKILL.md"
            external.write_bytes(entrypoint.read_bytes())
            entrypoint.unlink()
            entrypoint.symlink_to(external)
            with self.assertRaises(ValueError):
                self.render()

    def test_noncanonical_resource_paths_cannot_alias_reserved_entrypoint(self):
        entrypoint = self.root / "templates/skills/rpi-example/SKILL.md"
        entrypoint.write_text(entrypoint.read_text() + "\n./SKILL.md SKILL.md/ references/../SKILL.md\n")
        for destination in ("./SKILL.md", "SKILL.md/", "references/../SKILL.md"):
            with self.subTest(destination=destination):
                self.manifest["components"][0]["resources"] = [
                    {"source": "templates/skills/rpi-example/references/detail.md", "destination": destination}]
                with self.assertRaises(ValueError):
                    self.render()

    def test_nested_skill_entrypoint_is_not_silently_excluded_from_resources(self):
        self.write("templates/skills/rpi-example/references/SKILL.md", "Undeclared nested resource")
        with self.assertRaises(ValueError):
            self.render()


if __name__ == "__main__":
    unittest.main()
