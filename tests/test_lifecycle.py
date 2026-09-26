"""Transaction failure and containment oracles against explicit temporary roots."""
import json
import shlex
import importlib.util
from unittest import mock
from pathlib import Path
import unittest
import test_lifecycle_adopters as adopters


def lifecycle():
    spec = importlib.util.spec_from_file_location('fixture_lifecycle', adopters.ROOT / 'templates/scripts/rpi-lifecycle.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def add_policy_component(self, entries):
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        self.write(self.source, 'templates/adapters/policy.json', json.dumps({'schema_version': 1, 'entries': entries}))
        if not any(component['id'] == 'config:policy' for component in manifest['components']):
            manifest['components'].append({'id': 'config:policy', 'kind': 'config', 'scope': 'project',
                'selection': 'default', 'harnesses': ['claude'], 'dependencies': [],
                'source': 'templates/adapters/policy.json', 'outputs': {'claude': 'configuration/policy.json'},
                'destinations': {'claude': '.claude/settings.json'},
                'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'}})
            manifest_path.write_text(json.dumps(manifest))

    def test_retired_entry_conflict_names_the_entry_and_capability_flag(self):
        ask = {'id': 'ask-push', 'pointer': ['permissions', 'ask'], 'mode': 'entry', 'value': 'Bash(git push:*)'}
        self.add_policy_component([ask])
        self.apply_ready('install', '--allow-capabilities', 'config:policy')
        self.add_policy_component([])
        plan, _ = self.plan('update')
        self.assertEqual(plan['status'], 'conflict')
        reasons = [item['reason'] for item in plan['conflicts'] if item.get('record_id') == 'ask-push']
        self.assertEqual(len(reasons), 1, plan['conflicts'])
        self.assertIn('entry ask-push: "Bash(git push:*)"', reasons[0])
        self.assertIn('--allow-capabilities config:policy', reasons[0])
        self.assertNotIn('native diff', reasons[0])
        self.apply_ready('update', '--allow-capabilities', 'config:policy')
        settings = json.loads((self.project / '.claude/settings.json').read_text())
        self.assertNotIn('Bash(git push:*)', settings['permissions']['ask'])

    def test_locally_edited_owned_entry_conflict_names_its_repair(self):
        ask = {'id': 'ask-push', 'pointer': ['permissions', 'ask'], 'mode': 'entry', 'value': 'Bash(git push:*)'}
        self.add_policy_component([ask])
        self.apply_ready('install', '--allow-capabilities', 'config:policy')
        settings_path = self.project / '.claude/settings.json'
        settings_path.write_text(settings_path.read_text().replace('Bash(git push:*)', 'Bash(git push origin:*)'))
        self.add_policy_component([dict(ask, value='Bash(git push --dry-run:*)')])
        plan, _ = self.plan('update', '--allow-capabilities', 'config:policy')
        reason = next(item['reason'] for item in plan['conflicts'] if item.get('record_id') == 'ask-push')
        self.assertIn('replace your edited entry with the new value "Bash(git push --dry-run:*)"', reason)
        self.assertIn('restore the previous value "Bash(git push:*)"', reason)
        self.assertNotIn('delete the local entry', reason)

    def edited_hook_update(self):
        """Owner adds a timeout to the owned hook entry while the template value changes."""
        previous = {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'guard old'}]}
        desired = {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'guard new'}]}
        hook = {'id': 'hook-guard', 'pointer': ['hooks', 'PreToolUse'], 'mode': 'entry', 'value': previous}
        self.add_policy_component([hook])
        self.apply_ready('install', '--allow-capabilities', 'config:policy')
        settings_path = self.project / '.claude/settings.json'
        settings = json.loads(settings_path.read_text())
        settings['hooks']['PreToolUse'][0]['hooks'][0]['timeout'] = 20
        settings_path.write_text(json.dumps(settings, indent=2))
        self.add_policy_component([dict(hook, value=desired)])
        plan, _ = self.plan('update', '--allow-capabilities', 'config:policy')
        conflict = next(item for item in plan['conflicts'] if item.get('record_id') == 'hook-guard')
        self.assertEqual((conflict['previous'], conflict['desired']), (previous, desired))
        compact = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'))
        self.assertIn('replace your edited entry with the new value ' + compact(desired), conflict['reason'])
        self.assertIn('restore the previous value ' + compact(previous), conflict['reason'])
        self.assertIn('--allow-capabilities config:policy', conflict['reason'])
        return settings_path, settings, previous, desired

    def assert_healthy_after(self, settings_path, settings, value):
        settings['hooks']['PreToolUse'][0] = value
        settings_path.write_text(json.dumps(settings, indent=2))
        self.apply_ready('update', '--allow-capabilities', 'config:policy')
        result = self.invoke('check', '--source', self.source, '--target', self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'healthy')
        entries = json.loads(settings_path.read_text())['hooks']['PreToolUse']
        return entries

    def test_replacing_edited_entry_with_new_value_reaches_healthy_update(self):
        settings_path, settings, _, desired = self.edited_hook_update()
        self.assertEqual(self.assert_healthy_after(settings_path, settings, desired), [desired])
        self.apply_ready('detach')
        self.assertEqual(json.loads(settings_path.read_text())['hooks']['PreToolUse'], [])

    def test_restoring_previous_value_reaches_healthy_update(self):
        settings_path, settings, previous, desired = self.edited_hook_update()
        self.assertEqual(self.assert_healthy_after(settings_path, settings, previous), [desired])

    def test_edited_owned_deny_is_reported_by_record_and_value(self):
        self.add_policy_component([{'id': 'deny-env', 'pointer': ['permissions', 'deny'], 'mode': 'entry', 'value': 'Read(.env)'}])
        self.apply_ready('install', '--allow-capabilities', 'config:policy')
        settings_path = self.project / '.claude/settings.json'
        settings_path.write_text(settings_path.read_text().replace('Read(.env)', 'Read(.env.local)'))
        result = self.invoke('check', '--source', self.source, '--target', self.project)
        retained = [item for item in json.loads(result.stdout)['retained'] if item.get('record_id') == 'deny-env']
        self.assertEqual(len(retained), 1, result.stdout)
        self.assertEqual(retained[0]['value'], 'Read(.env)')
        self.assertIn('deny-env', retained[0]['reason'])
        self.assertIn('not in effect', retained[0]['reason'])

    def test_existing_plan_output_hint_names_a_new_output(self):
        _, path = self.plan()
        result = self.invoke('plan', '--source', self.source, '--target', self.project, '--output', path)
        self.assertEqual(result.returncode, 1)
        self.assertIn('choose a new --output path', result.stderr)
        self.assertNotIn('distribution.json', result.stderr)

    def test_interrupted_apply_hint_names_exact_rollback_and_check_reports_journal(self):
        _, path = self.plan()
        result = self.invoke('apply', '--plan', path, '--fail-after', '2')
        self.assertEqual(result.returncode, 2)
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json')).resolve()
        rollback = 'rollback --journal ' + shlex.quote(str(journal))
        self.assertIn(rollback, json.loads(result.stdout)['fix'])
        self.assertNotIn('--help', result.stdout + result.stderr)
        check = self.invoke('check', '--source', self.source, '--target', self.project, '--harness', 'both')
        summary = json.loads(check.stdout)
        self.assertEqual(summary['status'], 'action-needed')
        self.assertEqual(summary['interrupted_transactions'], [str(journal)])
        self.assertIn(rollback, summary['fix'])
        for arguments in ((), ('--journal', self.workspace / 'missing-journal.json')):
            with self.subTest(arguments=arguments):
                result = self.invoke('rollback', '--target', self.project, *arguments)
                self.assertEqual(result.returncode, 1)
                self.assertIn(rollback, result.stderr)
                self.assertNotIn('distribution.json', result.stderr)
        self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)

    def test_rollback_refuses_an_older_journal_than_the_latest_transaction(self):
        before = self.snapshot()
        self.apply_ready()
        first = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        self.apply_ready('detach')
        self.apply_ready()
        journals = set((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        installed = self.snapshot()
        result = self.invoke('rollback', '--journal', first)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), installed)
        self.assertIn('not the most recent', result.stdout)
        latest = [path for path in journals if path != first and json.loads(path.read_text())['sequence'] == 3]
        self.assertEqual(len(latest), 1)
        self.assertIn('rollback --journal ' + shlex.quote(str(latest[0].resolve())), json.loads(result.stdout)['fix'])
        for journal in sorted(journals, key=lambda path: -json.loads(path.read_text())['sequence']):
            self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_owner_json_indentation_is_preserved(self):
        self.add_policy_component([{'id': 'deny-env', 'pointer': ['permissions', 'deny'], 'mode': 'entry', 'value': 'Read(.env)'}])
        self.write(self.project, '.claude/settings.json', '{\n    "model": "owner-choice"\n}\n')
        self.apply_ready('install', '--allow-capabilities', 'config:policy')
        text = (self.project / '.claude/settings.json').read_text()
        self.assertIn('\n    "model": "owner-choice"', text)
        self.assertIn('Read(.env)', text)

    def interrupted_update(self):
        self.apply_ready()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        _, stale = self.plan('update')
        _, path = self.plan('update')
        self.assertEqual(self.invoke('apply', '--plan', path, '--fail-after', '1').returncode, 2)
        journal = next(p for p in (self.project / '.rpi/local/transactions').glob('*/journal.json')
                       if json.loads(p.read_text())['status'] == 'applying').resolve()
        return stale, journal

    def test_interrupted_transaction_blocks_plan_apply_and_check_names_a_working_rollback(self):
        stale, journal = self.interrupted_update()
        rollback = 'rollback --journal ' + shlex.quote(str(journal))
        before = self.snapshot(include_local=True)
        applied = self.invoke('apply', '--plan', stale)
        self.assertEqual(applied.returncode, 2, applied.stdout + applied.stderr)
        self.assertIn(rollback, json.loads(applied.stdout)['fix'])
        plan, path = self.plan('update')
        self.assertEqual(plan['status'], 'conflict')
        self.assertTrue(any(rollback in item.get('fix', '') for item in plan['conflicts']), plan['conflicts'])
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 2)
        self.assertEqual(self.snapshot(include_local=True), before)
        check = json.loads(self.invoke('check', '--source', self.source, '--target', self.project).stdout)
        self.assertEqual(check['status'], 'action-needed')
        self.assertIn(rollback, check['fix'])
        self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.apply_ready('update')
        check = self.invoke('check', '--source', self.source, '--target', self.project)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_check_names_newest_first_rollbacks_when_work_followed_an_interruption(self):
        _, journal = self.interrupted_update()
        self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.apply_ready('update')
        newer = next(p for p in (self.project / '.rpi/local/transactions').glob('*/journal.json')
                     if json.loads(p.read_text())['status'] == 'complete' and json.loads(p.read_text())['sequence'] == 3).resolve()
        value = json.loads(journal.read_text())
        value['status'] = 'applying'  # State left by older releases that allowed apply over an interruption.
        journal.write_text(json.dumps(value))
        fix = json.loads(self.invoke('check', '--source', self.source, '--target', self.project).stdout)['fix']
        chain = fix.split(' with ', 1)[1].split(', then create a new plan', 1)[0]
        commands = [shlex.split(part) for part in chain.split(' && ')]
        self.assertEqual([command[-1] for command in commands], [str(newer), str(journal)])
        for command in commands:
            result = adopters.subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('interrupted_transactions', json.loads(self.invoke('check', '--source', self.source, '--target', self.project).stdout))

    def test_moved_project_names_a_runnable_rebind(self):
        self.apply_ready()
        moved = self.workspace / 'renamed project'
        self.project.rename(moved)
        self.project = moved
        result = self.invoke('check', '--source', self.source, '--target', self.project)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        fix = json.loads(result.stdout)['fix']
        binding = (self.project / '.rpi/local/root-binding.json').resolve()
        rebind = shlex.join(['rm', str(binding)])
        self.assertIn(rebind, fix)
        self.assertNotIn(' check --source', fix)
        self.assertEqual(adopters.subprocess.run(shlex.split(rebind)).returncode, 0)
        check = self.invoke('check', '--source', self.source, '--target', self.project)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        self.apply_ready('update')
        self.assertEqual(json.loads(binding.read_text()), {'project': str(self.project.resolve())})

    def test_unsequenced_older_journal_cannot_undo_newer_install(self):
        before = self.snapshot()
        self.apply_ready()
        self.apply_ready('detach')
        self.apply_ready()
        journals = sorted((p.resolve() for p in (self.project / '.rpi/local/transactions').glob('*/journal.json')),
                          key=lambda path: json.loads(path.read_text())['sequence'])
        for order, journal in enumerate(journals):  # Rewrite as pre-2.1 journals: no sequence, mtime order only.
            for path in (journal, journal.with_name('receipt.json')):
                value = json.loads(path.read_text())
                value.pop('sequence')
                path.write_text(json.dumps(value))
            adopters.os.utime(journal, ns=(10 ** 18 + order * 10 ** 9,) * 2)
        installed = self.snapshot()
        result = self.invoke('rollback', '--journal', journals[0])
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), installed)
        self.assertIn('rollback --journal ' + shlex.quote(str(journals[-1])), json.loads(result.stdout)['fix'])
        for journal in reversed(journals):
            self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_edited_entry_conflict_shows_the_owner_current_value(self):
        settings_path, settings, previous, desired = self.edited_hook_update()
        plan, _ = self.plan('update', '--allow-capabilities', 'config:policy')
        conflict = next(item for item in plan['conflicts'] if item.get('record_id') == 'hook-guard')
        current = json.loads(settings_path.read_text())['hooks']['PreToolUse'][0]
        self.assertEqual(conflict['current'], current)
        self.assertIn('your current value ' + json.dumps(current, sort_keys=True, separators=(',', ':')), conflict['reason'])

    def test_removed_owned_deny_is_listed_by_value_in_healthy_check(self):
        self.add_policy_component([{'id': 'deny-mirror', 'pointer': ['permissions', 'deny'], 'mode': 'entry',
                                    'value': 'Bash(git push --mirror:*)'}])
        self.apply_ready('install', '--allow-capabilities', 'config:policy')
        settings_path = self.project / '.claude/settings.json'
        settings = json.loads(settings_path.read_text())
        settings['permissions']['deny'].remove('Bash(git push --mirror:*)')
        settings_path.write_text(json.dumps(settings))
        result = self.invoke('check', '--source', self.source, '--target', self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary['status'], 'healthy')
        self.assertEqual(summary['owned_entries_not_in_effect'], [
            {'component_id': 'config:policy', 'destination': '.claude/settings.json',
             'record_id': 'deny-mirror', 'value': 'Bash(git push --mirror:*)'}])

    def test_flag_only_conflicts_name_an_exact_replan_command(self):
        ask = {'id': 'ask-push', 'pointer': ['permissions', 'ask'], 'mode': 'entry', 'value': 'Bash(git push:*)'}
        self.add_policy_component([ask])
        for command in ('plan', 'check'):
            with self.subTest(command=command):
                output = ('--output', self.plans / (command + '-flags.json')) if command == 'plan' else ()
                result = self.invoke(command, '--source', self.source, '--target', self.project, *output)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                fix = json.loads(result.stdout)['fix']
                replan = shlex.split(fix.split(' then create a new plan with ', 1)[1])
                self.assertEqual(replan[replan.index('--allow-capabilities') + 1], 'config:policy')
                self.assertIn('--output', replan)
        replanned = adopters.subprocess.run(replan, capture_output=True, text=True)
        self.assertEqual(replanned.returncode, 0, replanned.stdout + replanned.stderr)
        self.assertEqual(json.loads(Path(replan[replan.index('--output') + 1]).read_text())['status'], 'ready')

    def test_update_without_harness_keeps_recorded_harnesses(self):
        output = self.plans / 'claude-install.json'
        result = self.invoke('plan', '--source', self.source, '--target', self.project, '--harness', 'claude',
                             '--route', 'direct', '--action', 'install', '--output', output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.invoke('apply', '--plan', output).returncode, 0)
        update = self.plans / 'default-update.json'
        result = self.invoke('plan', '--source', self.source, '--target', self.project,
                             '--route', 'direct', '--action', 'update', '--output', update)
        self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
        self.assertEqual(json.loads(update.read_text())['request']['harnesses'], ['claude'])
        self.assertFalse((self.project / '.codex').exists())
        install = self.plans / 'default-install.json'
        fresh = self.workspace / 'fresh-project'
        fresh.mkdir()
        self.invoke('plan', '--source', self.source, '--target', fresh, '--route', 'direct',
                    '--action', 'install', '--output', install)
        self.assertEqual(json.loads(install.read_text())['request']['harnesses'], ['claude', 'codex'])

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

    def check(self):
        result = self.invoke('check', '--source', self.source, '--target', self.project)
        return result, json.loads(result.stdout)

    def test_retained_owner_customization_is_healthy_without_a_looping_fix(self):
        self.apply_ready()
        destination = '.agents/skills/rpi-plan/references/playbook.md'
        self.write(self.project, destination, 'Owner planning customization.\n')
        before = self.snapshot(include_local=True)
        result, summary = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(summary['status'], 'healthy')
        self.assertIn({'destination': destination, 'reason': 'local-only customization retained'}, summary['retained'])
        self.assertEqual(self.snapshot(include_local=True), before)

    def test_check_fix_is_a_runnable_update_plan_then_apply(self):
        self.apply_ready()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'New upstream planning resource.\n')
        result, summary = self.check()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(summary['status'], 'action-needed')
        plan_part, apply_part = summary['fix'].split(' create the update plan with ', 1)[1].split(', review it, then apply it with ', 1)
        replan, apply = shlex.split(plan_part), shlex.split(apply_part)
        self.assertEqual(replan[replan.index('--action') + 1], 'update')
        self.assertEqual(replan[replan.index('--output') + 1], apply[apply.index('--plan') + 1])
        self.assertEqual(adopters.subprocess.run(replan, capture_output=True, text=True).returncode, 0)
        applied = adopters.subprocess.run(apply, capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        result, summary = self.check()
        self.assertEqual((result.returncode, summary['status']), (0, 'healthy'), result.stdout)

    def receipt_gate(self, summary):
        return next((item for item in summary.get('notices', []) if 'receipt_gate' in item), None)

    def test_update_and_check_name_the_opt_in_receipt_gate(self):
        self.apply_ready()
        policy = {'schema_version': 1, 'integration_branch': 'main', 'verification_checks': ['unit']}
        self.write(self.project, '.rpi/policy.json', json.dumps(policy))
        result, summary = self.check()
        self.assertEqual((result.returncode, summary['status']), (0, 'healthy'), result.stdout)
        notice = self.receipt_gate(summary)
        self.assertEqual(notice['receipt_gate'], 'off')
        for fragment in ('"require_verification_receipt": true', 'pre-push', lifecycle().GATE_DOC):
            self.assertIn(fragment, notice['fix'])
        self.assertEqual(notice['enable_command'], lifecycle().PRE_PUSH_ENABLE)
        plan, _ = self.plan('update')
        self.assertEqual(plan['status'], 'noop')
        self.assertEqual(self.receipt_gate(plan)['receipt_gate'], 'off')
        self.assertIsNone(self.receipt_gate(self.plan('install')[0]))
        adopters.subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        self.write(self.project, '.rpi/policy.json', json.dumps({**policy, 'require_verification_receipt': True}))
        hooks = self.project / '.git/hooks'
        before = sorted(p.name for p in hooks.iterdir())
        notice = self.receipt_gate(self.check()[1])
        self.assertEqual((notice['receipt_gate'], notice['pre_push_hook']), ('on', 'missing'))
        self.assertEqual(notice['hook_path'], str((hooks / 'pre-push').resolve()))
        self.assertIn(lifecycle().GATE_DOC, notice['fix'])
        self.assertEqual(notice['enable_command'], lifecycle().PRE_PUSH_ENABLE)
        self.assertEqual(sorted(p.name for p in hooks.iterdir()), before)
        hook = self.write(hooks, 'pre-push', '#!/bin/sh\nexec python3 "$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py" "$@"\n')
        hook.chmod(0o644)  # Git silently skips a hook without the execute bit.
        notice = self.receipt_gate(self.check()[1])
        self.assertEqual((notice['receipt_gate'], notice['pre_push_hook']), ('on', 'not executable'))
        chmod = shlex.split(notice['fix'].split(' run ', 1)[1])
        self.assertEqual(chmod, ['chmod', '+x', str(hook.resolve())])
        self.assertEqual(adopters.subprocess.run(chmod).returncode, 0)
        notice = self.receipt_gate(self.check()[1])
        self.assertEqual((notice['receipt_gate'], notice['pre_push_hook']), ('on', 'present'))
        self.assertNotIn('fix', notice)
        self.write(hooks, 'pre-push', '#!/bin/sh\nexec other-hook "$@"\n')
        self.assertEqual(self.receipt_gate(self.check()[1])['pre_push_hook'], 'does not invoke rpi-prepush.py')
        (self.project / '.rpi/policy.json').unlink()
        self.assertIsNone(self.receipt_gate(self.check()[1]))

    def test_notice_enable_command_matches_the_documented_command(self):
        text = (adopters.ROOT / 'docs/native-policy.md').read_text()
        block = text.split('Enable it once per clone', 1)[1].split('```bash\n', 1)[1].split('```', 1)[0]
        self.assertEqual(lifecycle().PRE_PUSH_ENABLE, block.rstrip('\n'))
        self.assertTrue(lifecycle().GATE_DOC.startswith('https://github.com/juan294/cc-rpi/blob/main/docs/native-policy.md'))

    def test_update_from_an_older_release_names_the_removed_push_block_without_a_policy(self):
        self.apply_ready()
        self.assertIsNone(self.receipt_gate(self.check()[1]))  # Same release: nothing changed.
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        recorded, manifest['version'] = manifest['version'], '2.1.0'
        manifest_path.write_text(json.dumps(manifest))
        self.assertFalse((self.project / '.rpi/policy.json').exists())
        result, summary = self.check()
        notice = self.receipt_gate(summary)
        self.assertEqual((notice['receipt_gate'], notice['recorded_version']), ('off', recorded), summary)
        for fragment in ('git push', 'gh pr', 'gh workflow run', 'no longer'):
            self.assertIn(fragment, notice['reason'])
        for fragment in ('"require_verification_receipt": true', 'enable_command', lifecycle().GATE_DOC):
            self.assertIn(fragment, notice['fix'])
        self.assertEqual(notice['enable_command'], lifecycle().PRE_PUSH_ENABLE)
        plan, _ = self.plan('update')
        self.assertEqual(self.receipt_gate(plan)['recorded_version'], recorded)
        self.apply_ready('update')
        self.assertIsNone(self.receipt_gate(self.check()[1]))  # Recorded once the update applies.

    def blocked(self, result):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        why, fix = result.stderr.strip().split(' / FIX: ', 1)
        self.assertNotIn('distribution.json', fix)
        return why, fix

    def test_unselected_capability_flag_names_the_value_and_prints_the_corrected_command(self):
        self.apply_ready()
        path = self.plans / 'unselected.json'
        why, fix = self.blocked(self.invoke('plan', '--source', self.source, '--target', self.project,
                                            '--action', 'update', '--allow-capabilities', 'config:codex-hooks',
                                            '--output', path))
        self.assertIn('config:codex-hooks', why)
        self.assertIn('--allow-capabilities config:codex-hooks', fix)
        rerun = shlex.split(fix.split('rerun ', 1)[1])
        self.assertNotIn('--allow-capabilities', rerun)
        self.assertEqual(rerun[rerun.index('--output') + 1], str(path))
        self.assertFalse(path.exists())
        self.assertEqual(adopters.subprocess.run(rerun, capture_output=True).returncode, 0)
        self.assertEqual(json.loads(path.read_text())['status'], 'noop')

    def test_unknown_domain_names_the_value_and_prints_the_corrected_command(self):
        path = self.plans / 'domain.json'
        why, fix = self.blocked(self.invoke('plan', '--source', self.source, '--target', self.project,
                                            '--domain', 'no-such-domain', '--output', path))
        self.assertIn('no-such-domain', why)
        rerun = shlex.split(fix.split('rerun ', 1)[1])
        self.assertNotIn('--domain', rerun)
        self.assertEqual(adopters.subprocess.run(rerun, capture_output=True).returncode, 0)
        self.assertTrue(path.is_file())

    def test_missing_plan_output_and_target_print_runnable_commands(self):
        why, fix = self.blocked(self.invoke('plan', '--source', self.source, '--target', self.project))
        self.assertIn('--output', why)
        rerun = shlex.split(fix.split('rerun ', 1)[1])
        output = Path(rerun[rerun.index('--output') + 1])
        self.assertTrue(output.is_relative_to(self.project.resolve() / '.rpi/local/plans'), output)
        self.assertEqual(adopters.subprocess.run(rerun, capture_output=True).returncode, 0)
        self.assertTrue(output.is_file())
        why, fix = self.blocked(adopters.subprocess.run(
            [adopters.sys.executable, str(adopters.ENGINE), 'check', '--source', str(self.source)],
            capture_output=True, text=True, cwd=self.project))
        self.assertIn('--target', why)
        rerun = shlex.split(fix.split('rerun ', 1)[1])
        self.assertEqual(Path(rerun[rerun.index('--target') + 1]).resolve(), self.project.resolve())

    def test_abbreviated_legacy_base_prints_the_command_that_resolves_it(self):
        short = self.base_revision[:8]
        why, fix = self.blocked(self.invoke('plan', '--source', self.source, '--target', self.project,
                                            '--legacy-base', short, '--output', self.plans / 'legacy.json'))
        self.assertIn(short, why)
        resolve = shlex.split(fix.split('pass the full ID that ', 1)[1].rsplit(' prints', 1)[0])
        resolved = adopters.subprocess.run(resolve, capture_output=True, text=True)
        self.assertEqual(resolved.stdout.strip(), self.base_revision)

    def test_apply_without_a_usable_plan_names_the_path_and_a_runnable_repair(self):
        why, fix = self.blocked(self.invoke('apply'))
        self.assertIn('--plan', why)
        self.assertIn('--output', fix)
        missing = self.plans / 'never-created.json'
        why, fix = self.blocked(self.invoke('apply', '--plan', missing))
        self.assertIn(str(missing), why)
        self.assertIn('--output', fix)
        self.apply_ready()
        saved = self.write(self.project, '.rpi/local/plans/update-saved.json', '{}')
        why, fix = self.blocked(self.invoke('apply', '--plan', missing, '--target', self.project))
        self.assertIn(shlex.join(['--plan', str(saved.resolve())]), fix)  # The newest saved plan nearby.
        self.assertIn('--action update', fix)  # An existing installation is updated, never re-installed or widened.
        broken = self.write(self.plans, 'broken.json', '{"not": "a plan"')
        why, fix = self.blocked(self.invoke('apply', '--plan', broken))
        self.assertIn(str(broken), why)
        self.assertIn('create a new plan', fix)

    def test_detach_names_a_pre_push_hook_that_invokes_the_removed_gate(self):
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        self.write(self.source, 'templates/scripts/rpi-prepush.py', 'print("gate")\n')
        manifest['components'].append({'id': 'resource:prepush-gate', 'kind': 'resource', 'scope': 'project',
            'selection': 'default', 'harnesses': ['claude', 'codex'], 'dependencies': [],
            'source': 'templates/scripts/rpi-prepush.py',
            'outputs': {'claude': '.rpi/scripts/rpi-prepush.py', 'codex': '.rpi/scripts/rpi-prepush.py'},
            'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'}})
        manifest_path.write_text(json.dumps(manifest))
        self.apply_ready()
        self.assertTrue((self.project / '.rpi/scripts/rpi-prepush.py').is_file())
        plan, _ = self.plan('detach')
        self.assertFalse(any('pre_push_hook' in item for item in plan.get('notices', [])))
        adopters.subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        hook = self.write(self.project / '.git/hooks', 'pre-push', '#!/bin/sh\nexec python3 .rpi/scripts/rpi-prepush.py "$@"\n')
        plan, path = self.plan('detach')
        notice = next(item for item in plan['notices'] if 'pre_push_hook' in item)
        self.assertEqual(notice['hook_path'], str(hook.resolve()))
        self.assertIn(str(hook.resolve()), notice['fix'])
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        self.assertTrue(hook.is_file())
        self.assertFalse((self.project / '.rpi/scripts/rpi-prepush.py').exists())


if __name__ == '__main__':
    unittest.main()
