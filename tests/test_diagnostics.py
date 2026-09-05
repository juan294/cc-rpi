"""Read-only adopter diagnostics distinguish evidence from configuration."""
import hashlib
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'templates/scripts/rpi-diagnostics.py'


def digest(data):
    return hashlib.sha256(data).hexdigest()


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.project = self.workspace / 'project'
        self.project.mkdir()
        spec = importlib.util.spec_from_file_location('diagnostic_test', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.probe = patch.object(self.module, 'client_version', return_value=None)
        self.probe.start()
        self.addCleanup(self.probe.stop)

    def write(self, name, content):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def snapshot(self):
        return {str(p.relative_to(self.workspace)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.workspace.rglob('*') if p.is_file()}

    def report(self, **kwargs):
        kwargs.setdefault('globals_by_harness', {})
        return self.module.diagnose(self.project, **kwargs)

    def native(self, clients, **kwargs):
        return {'source': 'isolated native fixture', 'target': str(self.project),
                'cwd': str(self.project), 'session_id': 'fixture-session',
                'observed_at': '2026-09-05T12:00:00Z', 'clients': clients, **kwargs}

    def install_receipt(self, entries, installations=None):
        self.write('.rpi/manifest.json', json.dumps({'schema_version': 1, 'scope': 'project',
            'root_ids': ['project'], 'harnesses': ['claude', 'codex'],
            'installations': installations or {'claude': {'route': 'direct', 'domains': []},
                                              'codex': {'route': 'direct', 'domains': []}}, 'entries': entries}))

    def entry(self, destination, content, component='skill:rpi-plan', block=None):
        self.write(destination, content)
        self.write('.rpi/baselines/' + digest(content.encode()), content)
        value = {'destination': destination, 'root_id': 'project', 'component_id': component,
                 'ownership': 'cc-rpi', 'base_hash': digest(content.encode()),
                 'adapter': {'harness': 'codex'}, 'source': {'version': '2.0.0'}}
        if block:
            value['block'] = block
        return value

    def test_read_only_including_local_and_no_private_values(self):
        self.write('AGENTS.md', 'SYNTHETIC_PRIVATE_PROJECT_FACT\n')
        self.write('.claude/settings.json', json.dumps({'env': {'TOKEN': 'SYNTHETIC_PRIVATE_TOKEN'},
                     'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': [{'type': 'command',
                         'command': 'echo SYNTHETIC_PRIVATE_COMMAND'}]}]}}))
        self.write('.rpi/local/private.json', '{"credential":"SYNTHETIC_PRIVATE_LOCAL"}')
        before = self.snapshot()
        result = self.report()
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(result))
        self.assertEqual(result['telemetry']['status'], 'unobserved')
        self.assertNotIn('violations', result['telemetry'])

    def test_full_budget_fixture_preserved_and_markers_counted(self):
        fixture = json.loads((ROOT / 'tests/fixtures/instruction-budget-case.json').read_text())['project_instruction']
        text = fixture['prefix'] + fixture['repeat'] * fixture['repeat_count'] + fixture['suffix']
        self.assertEqual(len(text.encode()), fixture['expected_bytes'])
        block = '<!-- rpi:policy:start -->\nShared policy.\n<!-- rpi:policy:end -->\n'
        self.write('AGENTS.md', text + block)
        before = self.snapshot()
        report = self.report()['instructions']['codex']
        self.assertEqual(report['bytes'], 40026 + len(block.encode()))
        self.assertTrue(report['over_limit'])
        self.assertEqual(report['limit_source'], 'assumed native default; unverified')
        self.assertEqual(report['managed_root_bytes'], len(block.encode()))
        self.assertEqual(report['managed_root_limit'], 8192)
        self.assertEqual(self.snapshot(), before)

    def test_codex_global_override_project_fallback_and_nested_selection(self):
        global_dir = self.workspace / 'global'
        global_dir.mkdir()
        (global_dir / 'AGENTS.md').write_text('ignored global')
        (global_dir / 'AGENTS.override.md').write_text('global override\n')
        (global_dir / 'config.toml').write_text('project_doc_fallback_filenames = ["TEAM.md"]\nproject_doc_max_bytes = 100\nsecret = "SYNTHETIC_PRIVATE_CONFIG"\n')
        self.write('AGENTS.md', 'Root map: src/TEAM.md\n')
        self.write('src/AGENTS.md', '')
        self.write('src/TEAM.md', 'nested fallback\n')
        self.write('src/deep/AGENTS.override.md', 'deep override\n')
        self.write('src/deep/AGENTS.md', 'ignored deep')
        result = self.report(cwd=self.project / 'src/deep', globals_by_harness={'codex': [global_dir]})
        report = result['instructions']['codex']
        self.assertEqual([Path(e['path']).name for e in report['files']],
                         ['AGENTS.override.md', 'AGENTS.md', 'TEAM.md', 'AGENTS.override.md'])
        self.assertEqual(report['bytes'], sum(e['bytes'] for e in report['files']))
        self.assertEqual(report['limit_bytes'], 100)
        self.assertIn('config.toml', report['limit_source'])
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(result))
        root_report = self.report(globals_by_harness={'codex': [global_dir]})['instructions']['codex']
        self.assertEqual([Path(e['path']).name for e in root_report['files']], ['AGENTS.override.md', 'AGENTS.md'])
        self.assertEqual(root_report['root_instruction_present'], True)

    def test_explicit_limit_is_supplied_and_does_not_modify_configuration(self):
        self.write('AGENTS.md', 'x' * 80)
        result = self.report(max_instruction_bytes=40)['instructions']['codex']
        self.assertTrue(result['over_limit'])
        self.assertEqual(result['limit_source'], 'explicit supplied effective limit; native provenance not verified')
        with self.assertRaises(ValueError):
            self.report(max_instruction_bytes=0)

    def test_claude_import_graph_cycle_is_separate_from_codex_chain(self):
        self.write('CLAUDE.md', '@AGENTS.md\n')
        self.write('AGENTS.md', '@CLAUDE.md\n')
        result = self.report()['instructions']
        self.assertTrue(result['claude']['cycles'])
        self.assertEqual([Path(e['path']).name for e in result['codex']['files']], ['AGENTS.md'])
        self.assertEqual(len(result['claude']['files']), 2)

    def test_claude_inline_imports_ancestors_code_exclusions_and_four_hops(self):
        (self.workspace / 'CLAUDE.md').write_text('Ancestor rules.\n')
        self.write('CLAUDE.md', 'See @one.md for rules. `@ignored.md`\n```\n@also-ignored.md\n```\n')
        for number, name in enumerate(['one', 'two', 'three', 'four', 'five']):
            next_name = ['two', 'three', 'four', 'five', 'six'][number]
            self.write(name + '.md', '- Details @' + next_name + '.md\n')
        report = self.report()['instructions']['claude']
        names = [Path(e['path']).name for e in report['files']]
        self.assertIn(str((self.workspace / 'CLAUDE.md').resolve()), [e['path'] for e in report['files']])
        self.assertIn('four.md', names)
        self.assertNotIn('five.md', names)
        self.assertFalse(report['missing_imports'])
        self.assertIn(str((self.project / 'five.md').resolve()), report['depth_limited_imports'])

    def test_missing_instruction_import_and_outside_cwd_report_safely(self):
        self.write('CLAUDE.md', '@missing.md\n')
        self.assertEqual(len(self.report()['instructions']['claude']['missing_imports']), 1)
        with self.assertRaises(ValueError):
            self.report(cwd=self.workspace)

    def test_missing_resource_and_local_drift_from_recoverable_baseline(self):
        resource = '.agents/skills/rpi-plan/references/contract.md'
        a = self.entry('.agents/skills/rpi-plan/SKILL.md', '---\nname: rpi-plan\n---\nRead references/contract.md\n')
        b = self.entry(resource, 'Required original resource.\n')
        self.install_receipt([a, b])
        (self.project / resource).unlink()
        self.write(a['destination'], 'Locally changed skill.\n')
        result = self.report()['installation']
        self.assertIn(resource, [e['destination'] for e in result['missing_resources']])
        self.assertEqual({e['status'] for e in result['drift']}, {'local-modified', 'missing'})

    def test_symlink_ownership_and_damaged_baselines_are_observations_only(self):
        name = '.agents/skills/rpi-plan/SKILL.md'
        record = self.entry(name, 'Original skill.\n')
        self.install_receipt([record])
        self.write('.rpi/baselines/' + record['base_hash'], 'Corrupted baseline.')
        self.assertEqual(self.report()['installation']['drift'][0]['status'], 'missing or damaged baseline')
        path = self.project / name
        path.unlink()
        outside = self.workspace / 'outside.env'
        outside.write_text('SYNTHETIC_PRIVATE_EXTERNAL')
        path.symlink_to(outside)
        self.assertEqual(self.report()['installation']['drift'][0]['status'], 'unproven symlink')
        record['node_kind'] = 'symlink'
        record['base_hash'] = digest(str(outside).encode())
        self.write('.rpi/baselines/' + record['base_hash'], str(outside))
        self.install_receipt([record])
        before = self.snapshot()
        with patch.object(self.module, 'read', wraps=self.module.read) as reader:
            report = self.report()
        self.assertFalse(report['installation']['drift'])
        self.assertNotIn(outside, [call.args[0] for call in reader.call_args_list])
        self.assertEqual(self.snapshot(), before)

    def test_plugin_receipt_is_unverified_and_legacy_duplicates_visible(self):
        self.install_receipt([], {'codex': {'route': 'plugin', 'domains': [],
            'expected_package': {'name': 'cc-rpi', 'version': '2.0.0'}, 'native_discovery': 'verified'}})
        self.write('.agents/skills/rpi-plan/SKILL.md', '---\nname: rpi-plan\n---\n')
        self.write('.agents/skills/group/rpi-plan/SKILL.md', '---\nname: rpi-plan\n---\n')
        self.write('.claude/commands/plan.md', 'Unproven v1 command')
        report = self.report()
        self.assertEqual(report['installation']['native_discovery']['codex'], 'unverified')
        self.assertEqual(report['skills']['duplicates'][0]['name'], 'rpi-plan')
        self.assertIn('.claude/commands/plan.md', report['skills']['legacy_entries'])
        self.assertTrue(report['skills']['route_collisions'])

    def test_codex_skill_scan_prunes_hidden_and_beyond_native_depth(self):
        root = self.project / '.agents/skills'
        visible = self.write('.agents/skills/visible/SKILL.md', '---\nname: rpi-plan\n---\n')
        hidden = self.write('.agents/skills/.hidden/rpi-plan/SKILL.md', '---\nname: rpi-plan\n---\n')
        boundary = self.write('.agents/skills/a/b/c/d/e/f/SKILL.md', '---\nname: at-boundary\n---\n')
        deep = self.write('.agents/skills/a/b/c/d/e/f/g/SKILL.md', '---\nname: too-deep\n---\n')
        with patch.object(self.module.os, 'scandir', wraps=self.module.os.scandir) as scan:
            candidates, limited = self.module.skill_paths(root, True)
        self.assertIn(visible, candidates)
        self.assertIn(boundary, candidates)
        self.assertNotIn(hidden, candidates)
        self.assertNotIn(deep, candidates)
        scanned = [Path(call.args[0]) for call in scan.call_args_list]
        self.assertNotIn(hidden.parent.parent, scanned)
        self.assertNotIn(deep.parent, scanned)
        self.assertFalse(limited, 'native depth pruning is normal scope, not a traversal-budget failure')
        self.assertFalse(self.report()['skills']['duplicates'], 'hidden skills are not native direct candidates')

    def test_codex_skill_scan_caps_directory_work_and_reports_incomplete(self):
        root = self.project / '.agents/skills'
        root.mkdir(parents=True)
        for index in range(2001):
            directory = root / f'group-{index:04d}'
            directory.mkdir()
            (directory / 'SKILL.md').write_text('---\nname: wide-fixture\n---\n')
        candidates, limited = self.module.skill_paths(root, True)
        self.assertTrue(limited)
        self.assertEqual(len(candidates), 1999, 'native directory budget includes the root')
        self.assertTrue(self.report()['skills']['scan_issues'])

    def test_codex_skill_scan_caps_entries_before_materializing_wide_directory(self):
        root = self.project / '.agents/skills'
        root.mkdir(parents=True)
        for index in range(20001):
            (root / f'file-{index:05d}').touch()
        candidates, limited = self.module.skill_paths(root, True)
        self.assertEqual(candidates, [])
        self.assertTrue(limited, 'entry limits must apply even without child directories')

    def test_codex_skill_scan_follows_directory_links_but_skips_file_links(self):
        root = self.project / '.agents/skills'
        root.mkdir(parents=True)
        external = self.workspace / 'linked-skill'
        external.mkdir()
        (external / 'SKILL.md').write_text('---\nname: linked\n---\n')
        (root / 'linked').symlink_to(external, target_is_directory=True)
        (external / 'loop').symlink_to(root, target_is_directory=True)
        file_link = root / 'file-link'
        file_link.mkdir()
        (file_link / 'SKILL.md').symlink_to(external / 'SKILL.md')
        candidates, limited = self.module.skill_paths(root, True)
        self.assertEqual(candidates, [root / 'linked/SKILL.md'])
        self.assertFalse(limited)
        (root / 'dangling').symlink_to(self.workspace / 'missing-skill')
        self.assertTrue(self.module.skill_paths(root, True)[1])

    def test_hooks_registered_untrusted_and_hash_mismatch_never_enforced(self):
        path = self.write('.codex/hooks.json', '{"hooks": {}}')
        hook = {'sourcePath': str(path), 'currentHash': 'sha256:' + 'a' * 64, 'trustStatus': 'untrusted',
                'enabled': True, 'eventName': 'preToolUse', 'observed_hash': 'sha256:' + 'a' * 64,
                'source_sha256': digest(path.read_bytes())}
        report = self.report(native=self.native({'codex': {'version': '0.153.4', 'hooks': [hook]}}),
                             now='2026-09-05T12:01:00Z')['hooks']['codex'][0]
        self.assertEqual(report['trust'], 'untrusted')
        self.assertFalse(report['observed'])
        hook['trustStatus'] = 'trusted'
        hook['observed_hash'] = 'sha256:' + 'b' * 64
        report = self.report(native=self.native({'codex': {'hooks': [hook]}}), now='2026-09-05T12:01:00Z')['hooks']['codex'][0]
        self.assertFalse(report['observed'])
        self.write('.codex/hooks.json', '{"changed": true}')
        hook['observed_hash'] = 'sha256:' + 'a' * 64
        report = self.report(native=self.native({'codex': {'hooks': [hook]}}), now='2026-09-05T12:01:00Z')['hooks']['codex'][0]
        self.assertEqual(report['trust'], 'modified')
        self.assertFalse(report['observed'])

    def test_fresh_bound_native_evidence_is_labeled_provided_not_authorization(self):
        path = self.write('.codex/hooks.json', '{}')
        hook = {'sourcePath': str(path), 'currentHash': 'sha256:' + 'a' * 64, 'trustStatus': 'trusted',
                'enabled': True, 'observed_hash': 'sha256:' + 'a' * 64, 'source_sha256': digest(path.read_bytes())}
        result = self.report(native=self.native({'codex': {'hooks': [hook], 'version': '0.153.4'}}),
                             now='2026-09-05T12:01:00Z')
        self.assertTrue(result['hooks']['codex'][0]['observed'])
        self.assertEqual(result['native_evidence']['authority'], 'provided native evidence; not authorization')
        for change in [{'observed_at': '2025-01-01T00:00:00Z'}, {'target': str(self.workspace)}, {'session_id': ''}]:
            result = self.report(native=self.native({'codex': {'hooks': [hook]}}, **change), now='2026-09-05T12:01:00Z')
            self.assertEqual(result['native_evidence']['status'], 'unavailable')
            self.assertFalse(any(h['observed'] for h in result['hooks']['codex']))

    def test_missing_hook_hash_and_malformed_settings_are_visible_without_leaks(self):
        self.write('.claude/settings.json', '{"secret":"SYNTHETIC_PRIVATE_MALFORMED"')
        result = self.report(native=self.native({'codex': {'hooks': [{'enabled': True, 'trustStatus': 'trusted'}]}}),
                             now='2026-09-05T12:01:00Z')
        self.assertTrue(result['config_issues'])
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(result))
        self.assertFalse(result['hooks']['codex'][0]['observed'])

    def test_source_change_and_missing_declared_source_resource(self):
        from test_lifecycle_adopters import LifecycleAdopterTests
        fixture = LifecycleAdopterTests()
        fixture.source = self.workspace / 'source'
        fixture.make_source()
        plan = self.workspace / 'plan.json'
        engine = ROOT / 'templates/scripts/rpi-distribution.py'
        command = [sys.executable, str(engine)]
        result = subprocess.run(command + ['plan', '--source', str(fixture.source), '--target', str(self.project),
            '--output', str(plan), '--harness', 'codex', '--route', 'direct'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run(command + ['apply', '--plan', str(plan)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        target = fixture.source / 'templates/skills/rpi-plan/references/playbook.md'
        target.write_text('Updated upstream contract.\n')
        before = self.snapshot()
        result = self.report(source=fixture.source)['installation']
        self.assertIn('source-changed', [e['status'] for e in result['drift']])
        self.assertEqual(self.snapshot(), before)
        manifest_path = fixture.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        component = next(c for c in manifest['components'] if c.get('name') == 'rpi-plan')
        component['resources'].remove('scripts/validate.py')
        component['resources'].append('references/new.md')
        skill = fixture.source / 'templates/skills/rpi-plan'
        (skill / 'scripts/validate.py').unlink()
        (skill / 'references/new.md').write_text('New upstream requirement.\n')
        entry = skill / 'SKILL.md'
        entry.write_text(entry.read_text().replace('Read scripts/validate.py.', 'Read references/new.md.'))
        manifest_path.write_text(json.dumps(manifest))
        statuses = {e['status'] for e in self.report(source=fixture.source)['installation']['drift']}
        self.assertIn('source-added', statuses)
        self.assertIn('source-removed', statuses)
        target.unlink()
        self.assertIn('missing declared resources', self.report(source=fixture.source)['installation']['source']['status'])

    def test_owned_configuration_drift_is_reported_without_values(self):
        record = {'id': 'native-push-boundary', 'mode': 'entry', 'pointer': ['permissions', 'ask'],
                  'value': 'Bash(git push:*)'}
        baseline = (json.dumps(record, sort_keys=True, indent=2) + '\n').encode()
        self.write('.rpi/baselines/' + digest(baseline), baseline.decode())
        self.write('.claude/settings.json', '{"permissions":{"ask":[]},"env":{"TOKEN":"SYNTHETIC_PRIVATE"}}')
        self.install_receipt([{'root_id': 'project', 'destination': '.claude/settings.json',
            'component_id': 'config:claude-policy', 'ownership': 'cc-rpi', 'base_hash': digest(baseline),
            'adapter': {'harness': 'claude'}, 'config_record': record}])
        report = self.report()
        self.assertEqual(report['installation']['drift'][0]['status'], 'configuration-changed')
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(report))
        self.assertNotIn('Bash(git push:*)', json.dumps(report))

    def test_exact_v1_blanket_permissions_are_unverified_preserved_findings(self):
        settings = {'env': {'TOKEN': 'SYNTHETIC_PRIVATE'}, 'permissions': {'allow': [
            'Read', 'Bash(git *)', 'Bash(gh *)', 'Bash(git status *)', 'Bash(project-custom *)']}}
        self.write('.claude/settings.json', json.dumps(settings))
        before = self.snapshot()
        report = self.report()
        findings = report['config_issues']
        self.assertEqual({item.get('id') for item in findings},
                         {'legacy-broad-git-allow', 'legacy-broad-gh-allow'})
        for finding in findings:
            self.assertEqual(finding['ownership'], 'unverified')
            self.assertEqual(finding['status'], 'potential legacy broad allow')
            self.assertIn('preserve', finding['action'])
            self.assertIn('not authorization', finding['authority'])
        self.assertEqual(self.snapshot(), before)
        serialized = json.dumps(report)
        for value in ('SYNTHETIC_PRIVATE', 'project-custom', 'Bash(git *)', 'Bash(gh *)', 'Bash(git status *)'):
            self.assertNotIn(value, serialized)
        self.write('.claude/settings.json', '{"permissions":{"allow":"Bash(git *)"}}')
        self.assertFalse(self.report()['config_issues'], 'a malformed non-array is not an exact native allow entry')

    def test_upstream_native_configuration_records_report_change_add_remove_read_only(self):
        from test_lifecycle_adopters import LifecycleAdopterTests
        fixture = LifecycleAdopterTests()
        fixture.source = self.workspace / 'source'
        fixture.make_source()
        manifest_path = fixture.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['components'].append({'id': 'config:policy', 'kind': 'config', 'scope': 'project',
            'selection': 'default', 'harnesses': ['claude'], 'dependencies': [],
            'source': 'templates/adapters/policy.json', 'outputs': {'claude': 'configuration/policy.json'},
            'destinations': {'claude': '.claude/settings.json'},
            'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'}})
        manifest_path.write_text(json.dumps(manifest))
        declaration = fixture.source / 'templates/adapters/policy.json'
        changed = {'id': 'changed', 'pointer': ['permissions', 'ask'], 'mode': 'entry', 'value': 'Bash(git push:*)'}
        removed = {'id': 'removed', 'pointer': ['permissions', 'deny'], 'mode': 'entry', 'value': 'Read(.env)'}
        declaration.write_text(json.dumps({'schema_version': 1, 'entries': [changed, removed]}))
        self.write('.claude/settings.json', '{"env":{"TOKEN":"SYNTHETIC_PRIVATE"}}')
        plan = self.workspace / 'config-plan.json'
        command = [sys.executable, str(ROOT / 'templates/scripts/rpi-distribution.py')]
        for args in [['plan', '--source', str(fixture.source), '--target', str(self.project),
                      '--output', str(plan), '--harness', 'claude', '--allow-capabilities', 'config:policy'],
                     ['apply', '--plan', str(plan)]]:
            result = subprocess.run(command + args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.report(source=fixture.source)['installation']['drift'])
        declaration.write_text(json.dumps({'schema_version': 1, 'entries': [
            {**changed, 'value': 'Bash(git push origin develop)'},
            {'id': 'added', 'pointer': ['permissions', 'ask'], 'mode': 'entry', 'value': 'Bash(gh release:*)'}]}))
        before = self.snapshot()
        report = self.report(source=fixture.source)
        drift = {item.get('record_id'): item for item in report['installation']['drift']}
        self.assertEqual({key: drift.get(key, {}).get('status') for key in ('changed', 'removed', 'added')},
                         {'changed': 'source-changed', 'removed': 'source-removed', 'added': 'source-added'})
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(report))
        self.assertNotIn('Bash(git push', json.dumps(report))
        settings = json.loads((self.project / '.claude/settings.json').read_text())
        settings['permissions']['ask'] = ['Bash(project-custom-command)']
        self.write('.claude/settings.json', json.dumps(settings))
        report = self.report(source=fixture.source)
        item = next(item for item in report['installation']['drift'] if item.get('record_id') == 'changed')
        self.assertEqual(item['status'], 'configuration-changed')
        self.assertTrue(item['upstream_changed'])
        self.assertNotIn('project-custom-command', json.dumps(report))

    def test_documented_topology_and_telemetry_presence_are_not_authorization(self):
        self.write('.rpi/policy.json', '{"schema_version":1,"integration_branch":"develop","production_branches":["main"],"remote":"origin"}')
        self.write('.rpi/local/contract-events.jsonl', '')
        result = self.report()
        self.assertEqual(result['topology']['integration_branch'], 'develop')
        self.assertEqual(result['topology']['production_branches'], ['main'])
        self.assertEqual(result['telemetry']['status'], 'present; coverage unverified')
        self.assertNotIn('violations', result['telemetry'])

    def test_invalid_public_state_and_malformed_native_collection_do_not_crash(self):
        self.write('.rpi/manifest.json', '{"schema_version":1,"entries":[null]}')
        result = self.report(native=self.native({'codex': {'hooks': None, 'skills': None, 'skill_roots': None}}),
                             now='2026-09-05T12:01:00Z')
        self.assertTrue(result['config_issues'])
        self.assertEqual(result['installation']['status'], 'untracked')
        self.install_receipt([], {'codex': None})
        result = self.report()
        self.assertEqual(result['installation']['status'], 'untracked')
        self.assertTrue(result['config_issues'])

    def test_multiline_whitelisted_instruction_config_and_unknown_values_private(self):
        self.write('.codex/config.toml', 'project_doc_fallback_filenames = [\n "TEAM.md",\n]\nsecret = "SYNTHETIC_PRIVATE"\n')
        self.write('TEAM.md', 'Root instructions.\n')
        report = self.report()
        self.assertEqual([Path(e['path']).name for e in report['instructions']['codex']['files']], ['TEAM.md'])
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(report))

    def test_hook_fields_cannot_claim_observation_with_non_hash_data(self):
        path = self.write('.codex/hooks.json', '{}')
        private = {'SYNTHETIC_PRIVATE': 'not metadata'}
        native = self.native({'codex': {'hooks': [{'sourcePath': str(path), 'source_sha256': digest(path.read_bytes()),
            'currentHash': private, 'observed_hash': private, 'enabled': True, 'trustStatus': 'trusted',
            'eventName': private}]}})
        report = self.report(native=native, now='2026-09-05T12:01:00Z')
        self.assertFalse(report['hooks']['codex'][0]['observed'])
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(report))

    def test_process_claude_effort_is_observed_without_guessing_pane_model(self):
        with patch.dict('os.environ', {'CLAUDE_EFFORT': 'high'}):
            report = self.report()['model']['claude']
        self.assertEqual(report['resolved_model_effort']['effort'], 'high')
        self.assertIsNone(report['resolved_model_effort']['model'])
        self.assertIn('process', report['evidence_source_client_version']['source'])
        self.assertIn('unavailable', report['resolved_model_effort']['reason'])

    def test_safe_version_probe_filters_output_and_handles_native_failure(self):
        self.probe.stop()
        for response, expected in [(subprocess.CompletedProcess([], 0, 'Codex 0.153.4 SYNTHETIC_PRIVATE', ''), '0.153.4'),
                                   (subprocess.CompletedProcess([], 1, 'SYNTHETIC_PRIVATE', ''), None)]:
            with patch.object(self.module.shutil, 'which', return_value='/native/codex'), patch.object(self.module.subprocess, 'run', return_value=response):
                self.assertEqual(self.module.client_version('codex'), expected)
        with patch.object(self.module.shutil, 'which', return_value='/native/codex'), patch.object(self.module.subprocess, 'run', side_effect=subprocess.TimeoutExpired('codex', 5)):
            self.assertIsNone(self.module.client_version('codex'))
        self.probe.start()

    def test_main_valid_and_invalid_inputs_leave_all_files_unchanged(self):
        self.write('AGENTS.md', 'Root facts.\n')
        before = self.snapshot()
        for flags, code in [([], 0), (['--max-instruction-bytes', '0'], 1),
                            (['--global-instruction', 'bad=private'], 1),
                            (['--global-instruction', 'codex=' + str(self.workspace / 'global')], 0)]:
            output, errors = io.StringIO(), io.StringIO()
            with patch.object(sys, 'argv', [str(SCRIPT), '--target', str(self.project), *flags]), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                self.assertEqual(self.module.main(), code)
            self.assertEqual(self.snapshot(), before)
            if code:
                self.assertIn('BLOCKED / WHY', errors.getvalue())
                self.assertNotIn('bad=private', errors.getvalue())
            else:
                self.assertTrue(json.loads(output.getvalue())['read_only'])

    def test_source_hash_inspection_does_not_read_credential_paths(self):
        secret = self.write('.env', 'SYNTHETIC_PRIVATE_CREDENTIAL')
        native = self.native({'codex': {'hooks': [{'sourcePath': str(secret), 'source_sha256': digest(secret.read_bytes()),
            'currentHash': 'sha256:' + 'a' * 64, 'observed_hash': 'sha256:' + 'a' * 64,
            'enabled': True, 'trustStatus': 'trusted'}]}})
        with patch.object(self.module, 'read', wraps=self.module.read) as reader:
            report = self.report(native=native, now='2026-09-05T12:01:00Z')
        self.assertNotIn(secret, [call.args[0] for call in reader.call_args_list])
        self.assertFalse(report['hooks']['codex'][0]['observed'])

    def test_extracted_runtime_diagnose_does_not_create_source_caches(self):
        runtime = self.workspace / 'runtime'
        scripts = runtime / 'templates/scripts'
        scripts.mkdir(parents=True)
        for name in ['rpi-diagnostics.py', 'rpi-models.py', 'rpi-config.py', 'rpi-lifecycle.py', 'rpi-distribution.py']:
            shutil.copyfile(ROOT / 'templates/scripts' / name, scripts / name)
        adapters = runtime / 'templates/adapters'
        adapters.mkdir()
        shutil.copyfile(ROOT / 'templates/adapters/model-profiles.json', adapters / 'model-profiles.json')
        self.write('AGENTS.md', 'Project facts.\n')
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(scripts / 'rpi-distribution.py'), 'diagnose', '--target', str(self.project)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(list(runtime.rglob('__pycache__')))
        self.assertIn('invalid source', json.loads(result.stdout)['installation']['source']['status'])

    def test_cli_only_reports_and_does_not_create_local_state(self):
        self.write('AGENTS.md', 'Project facts')
        before = self.snapshot()
        result = subprocess.run([sys.executable, str(SCRIPT), '--target', str(self.project)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(json.loads(result.stdout)['read_only'], True)
        engine = ROOT / 'templates/scripts/rpi-distribution.py'
        result = subprocess.run([sys.executable, str(engine), 'diagnose', '--target', str(self.project)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['read_only'], True)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
