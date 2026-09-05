"""Transaction failure and containment oracles against explicit temporary roots."""
import json
import importlib.util
from unittest import mock
from pathlib import Path
import unittest
import test_lifecycle_adopters as adopters


class TransactionTests(unittest.TestCase):
    setUp = adopters.LifecycleAdopterTests.setUp
    write = adopters.LifecycleAdopterTests.write
    make_source = adopters.LifecycleAdopterTests.make_source
    git = adopters.LifecycleAdopterTests.git
    commit_source = adopters.LifecycleAdopterTests.commit_source
    invoke = adopters.LifecycleAdopterTests.invoke
    plan = adopters.LifecycleAdopterTests.plan
    apply_ready = adopters.LifecycleAdopterTests.apply_ready
    snapshot = adopters.LifecycleAdopterTests.snapshot

    def test_packaged_source_never_claims_ancestor_adopter_revision(self):
        adopters.shutil.rmtree(self.source / '.git')
        for command in (
                ['init', '-q'], ['add', 'source'],
                ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Unrelated adopter']):
            result = adopters.subprocess.run(['git', '-C', str(self.workspace), *command], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        plan, _ = self.plan()
        self.assertEqual(plan['source']['revision'], 'packaged')
        self.assertEqual(len(plan['source']['rendered_sha256']), 64)

    def test_conflict_plan_contains_three_way_diff_without_printing_private_bytes(self):
        self.apply_ready()
        destination = '.agents/skills/rpi-plan/references/playbook.md'
        self.write(self.project, destination, 'Private local planning requirement.\n')
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Different upstream planning requirement.\n')
        before = self.snapshot()
        plan, path = self.plan('update')
        conflict = next(item for item in plan['conflicts'] if item['destination'] == destination)
        self.assertIn('Private local planning requirement.', conflict['diffs']['base_to_local'])
        self.assertIn('Required independent fixture resource', conflict['diffs']['base_to_local'])
        self.assertIn('Different upstream planning requirement.', conflict['diffs']['base_to_upstream'])
        result = self.invoke('apply', '--plan', path)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Private local planning requirement.', result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_detach_command_is_a_read_only_plan_alias(self):
        self.apply_ready()
        before = self.snapshot(include_local=True)
        path = self.plans / 'detach-alias.json'
        result = self.invoke('detach', '--source', self.source, '--target', self.project, '--output', path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.read_text())['request']['action'], 'detach')
        self.assertEqual(self.snapshot(include_local=True), before)
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        self.assertFalse((self.project / '.agents/skills/rpi-plan/SKILL.md').exists())

    def test_malformed_manifest_cannot_claim_internal_state_root(self):
        self.apply_ready()
        path = self.project / '.rpi/manifest.json'
        original = json.loads(path.read_text())
        for declare_state in (False, True, "project-alias"):
            changed = json.loads(json.dumps(original))
            changed['entries'][0]['root_id'] = 'state'
            changed['entries'][0]['destination'] = 'baselines/' + changed['entries'][0]['base_hash']
            if declare_state is True:
                changed['root_ids'].append('state')
            elif declare_state == 'project-alias':
                changed['entries'][0]['root_id'] = 'project'
                changed['entries'][0]['destination'] = '.rpi/manifest.json'
            path.write_text(json.dumps(changed))
            before = self.snapshot(include_local=True)
            result = self.invoke('plan', '--source', self.source, '--target', self.project,
                                 '--action', 'detach', '--output', self.plans / 'invalid-state.json')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(self.snapshot(include_local=True), before)

    def test_component_output_cannot_alias_reserved_manifest_state(self):
        source_manifest = self.source / 'templates/distribution.json'
        manifest = json.loads(source_manifest.read_text())
        self.write(self.source, 'templates/unsafe.txt', 'Unrelated resource bytes.\n')
        manifest['components'].append({'id': 'resource:unsafe', 'kind': 'resource', 'scope': 'project',
            'selection': 'default', 'harnesses': ['codex'], 'dependencies': [], 'source': 'templates/unsafe.txt',
            'outputs': {'codex': '.rpi/manifest.json'}, 'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'}})
        source_manifest.write_text(json.dumps(manifest))
        before = self.snapshot(include_local=True)
        result = self.invoke('plan', '--source', self.source, '--target', self.project,
                             '--output', self.plans / 'reserved.json')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(include_local=True), before)

    def test_concurrent_preimage_edit_prevents_every_write(self):
        plan, path = self.plan()
        self.write(self.project, 'AGENTS.md', 'Concurrent user knowledge.\n')
        before = self.snapshot()
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 2)
        self.assertEqual(self.snapshot(), before)

    def test_tampered_operation_path_is_rejected(self):
        plan, path = self.plan()
        plan['operations'][0]['destination'] = '../outside-sentinel.txt'
        path.write_text(json.dumps(plan))
        before = self.snapshot()
        self.assertNotEqual(self.invoke('apply', '--plan', path).returncode, 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.outside.read_text(), 'Outside every bound installation root.\n')

    def test_symlink_parent_never_traversed(self):
        external = self.workspace / 'external-skills'
        external.mkdir()
        (self.project / '.agents').mkdir()
        (self.project / '.agents/skills').symlink_to(external, target_is_directory=True)
        plan, path = self.plan()
        self.assertEqual(plan['status'], 'conflict')
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 2)
        self.assertEqual(list(external.iterdir()), [])

    def test_missing_baseline_fails_closed(self):
        self.apply_ready()
        baseline = next((self.project / '.rpi/baselines').iterdir())
        baseline.unlink()
        before = self.snapshot()
        plan, _ = self.plan('update')
        self.assertEqual(plan['status'], 'conflict')
        self.assertEqual(self.snapshot(), before)

    def test_interruption_journal_rolls_back_exact_preimages(self):
        self.write(self.project, 'AGENTS.md', '# User facts\n')
        before = self.snapshot()
        _, path = self.plan()
        result = self.invoke('apply', '--plan', path, '--fail-after', '3')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        journals = list((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        self.assertEqual(len(journals), 1)
        self.assertEqual(self.invoke('rollback', '--journal', journals[0]).returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_rollback_retains_post_transaction_user_edit(self):
        _, path = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        journals = list((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        managed = self.project / '.agents/skills/rpi-plan/SKILL.md'
        managed.write_text('Edited after installation.\n')
        before = self.snapshot()
        self.assertEqual(self.invoke('rollback', '--journal', journals[0]).returncode, 2)
        self.assertEqual(self.snapshot(), before)

    def test_write_ahead_recovers_rename_before_completion_checkpoint(self):
        before = self.snapshot()
        _, path = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', path, '--fail-after-rename', '1').returncode, 2)
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_tampered_journal_root_cannot_restore_external_file(self):
        self.apply_ready()
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        value = json.loads(journal.read_text())
        value['roots']['project'] = str(self.workspace)
        journal.write_text(json.dumps(value))
        before = self.snapshot()
        self.assertNotEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.outside.read_text(), 'Outside every bound installation root.\n')

    def test_lock_prevents_apply_without_removing_lock(self):
        _, path = self.plan()
        self.write(self.project, '.rpi/local/lock', 'Another transaction.\n')
        before = self.snapshot(include_local=True)
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 2)
        self.assertEqual(self.snapshot(include_local=True), before)

    def test_commit_rechecks_untouched_instruction_preimage(self):
        self.apply_ready()
        manifest_before = (self.project / '.rpi/manifest.json').read_bytes()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Changed upstream resource.\n')
        plan, _ = self.plan('update')
        spec = importlib.util.spec_from_file_location('fixture_distribution', adopters.ENGINE)
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        lifecycle = engine.load_sibling('rpi-lifecycle')
        original_atomic = lifecycle.atomic_node
        injected = False
        def concurrent_edit(path, node):
            nonlocal injected
            original_atomic(path, node)
            if path.name == 'playbook.md' and not injected:
                injected = True
                agents = self.project / 'AGENTS.md'
                agents.write_bytes(agents.read_bytes() + b'Concurrent project knowledge.\n')
        with mock.patch.object(lifecycle, 'atomic_node', side_effect=concurrent_edit):
            with self.assertRaises(lifecycle.Conflict):
                lifecycle.apply_plan(engine, plan)
        self.assertTrue(injected)
        self.assertEqual((self.project / '.rpi/manifest.json').read_bytes(), manifest_before)
        self.assertIn(b'Concurrent project knowledge.', (self.project / 'AGENTS.md').read_bytes())

    def test_duplicate_or_nonfinite_unmanaged_settings_are_invalid(self):
        for payload in ('{"env":{},"env":{}}', '{"value":NaN}'):
            self.write(self.project, '.claude/settings.json', payload)
            before = self.snapshot(include_local=True)
            result = self.invoke('plan', '--source', self.source, '--target', self.project,
                                 '--output', self.plans / 'invalid-config.json')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(self.snapshot(include_local=True), before)

    def test_rollback_resumes_after_restore_before_checkpoint(self):
        self.write(self.project, 'AGENTS.md', '# Existing facts\n')
        before = self.snapshot()
        self.apply_ready()
        journal_path = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        journal = json.loads(journal_path.read_text())
        last = journal['operations'][-1]
        self.assertEqual(last['destination'], 'manifest.json')
        self.assertEqual(last['before']['kind'], 'missing')
        (self.project / '.rpi/manifest.json').unlink()  # Crash after the first reverse rename.
        self.assertEqual(self.invoke('rollback', '--journal', journal_path).returncode, 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.invoke('rollback', '--journal', journal_path).returncode, 0)

    def test_one_harness_update_and_detach_preserve_other_installation(self):
        self.apply_ready()
        claude = self.project / '.claude/skills/rpi-plan/references/playbook.md'
        original = claude.read_bytes()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'New source resource.\n')
        self.commit_source('New resource')
        self.apply_ready('update', '--harness', 'codex')
        self.assertEqual(claude.read_bytes(), original)
        self.assertEqual((self.project / '.agents/skills/rpi-plan/references/playbook.md').read_text(), 'New source resource.\n')
        self.apply_ready('detach', '--harness', 'codex')
        self.assertTrue(claude.is_file())
        self.assertFalse((self.project / '.agents/skills/rpi-plan/SKILL.md').exists())
        self.assertIn('Keep local verification', (self.project / 'AGENTS.md').read_text())

    def test_configuration_requires_scoped_authorization_and_never_baselines_secrets(self):
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        declaration = {'schema_version': 1, 'entries': [
            {'id': 'deny-secrets', 'pointer': ['permissions', 'deny'], 'mode': 'entry', 'value': 'Read(.env)'}]}
        self.write(self.source, 'templates/adapters/policy.json', json.dumps(declaration))
        manifest['components'].append({'id': 'config:policy', 'kind': 'config', 'scope': 'project',
            'selection': 'default', 'harnesses': ['claude'], 'dependencies': [],
            'source': 'templates/adapters/policy.json', 'outputs': {'claude': 'configuration/policy.json'},
            'destinations': {'claude': '.claude/settings.json'},
            'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'}})
        manifest_path.write_text(json.dumps(manifest))
        self.write(self.project, '.claude/settings.json', '{"env":{"KEY":"SYNTHETIC_PRIVATE"},"permissions":{"deny":["Read(private/**)"]}}')
        before = self.snapshot()
        plan, path = self.plan()
        self.assertEqual(plan['status'], 'conflict')
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 2)
        self.assertEqual(self.snapshot(), before)
        self.apply_ready('install', '--allow-capabilities', 'config:policy')
        settings = json.loads((self.project / '.claude/settings.json').read_text())
        self.assertEqual(settings['permissions']['deny'], ['Read(private/**)', 'Read(.env)'])
        for baseline in (self.project / '.rpi/baselines').iterdir():
            self.assertNotIn(b'SYNTHETIC_PRIVATE', baseline.read_bytes())
        self.apply_ready('detach')
        settings = json.loads((self.project / '.claude/settings.json').read_text())
        self.assertEqual(settings['env']['KEY'], 'SYNTHETIC_PRIVATE')
        self.assertEqual(settings['permissions']['deny'], ['Read(private/**)'])

    def test_explicit_user_roots_do_not_install_project_workflows(self):
        user_source = self.source / 'templates/distribution.json'
        manifest = json.loads(user_source.read_text())
        manifest['components'][0]['scope'] = 'user'
        user_source.write_text(json.dumps(manifest))
        state, claude, codex = [self.workspace / name for name in ('user-state', 'user-claude', 'user-codex')]
        plan, path = self.plan('install', '--scope', 'user', '--state-root', state,
                               '--claude-skill-root', claude, '--codex-skill-root', codex)
        self.assertEqual(plan['status'], 'ready', plan)
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        self.assertTrue((claude / 'rpi-plan/SKILL.md').is_file())
        self.assertTrue((codex / 'rpi-plan/SKILL.md').is_file())
        self.assertFalse((claude / 'rpi-release').exists())
        self.assertFalse((self.project / '.rpi').exists())
        self.assertTrue((state / 'manifest.json').is_file())


if __name__ == '__main__':
    unittest.main()
