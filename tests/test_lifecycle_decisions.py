"""Ownership rejection and recovery decisions preserve independent user sentinels."""
import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_lifecycle_adopters as adopters


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'templates/scripts' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def record(**changes):
    return {'id': 'permission:publish', 'pointer': ['permissions', 'ask'],
            'mode': 'entry', 'value': 'old', **changes}


class ConfigurationDecisionTests(unittest.TestCase):
    def setUp(self):
        self.config = module('rpi-config')

    def test_invalid_ownership_shapes_cannot_modify_input_records(self):
        invalid = [None, [None], [record(extra='unowned')], [record(pointer=[''])],
                   [record(mode='object')], [record(retain_on_remove='true')],
                   [record(), record(id='second')]]
        for records in invalid:
            with self.subTest(records=records):
                before = copy.deepcopy(records)
                with self.assertRaises(ValueError):
                    self.config.reconcile(b'{"private":"preserve"}', [], records, True)
                self.assertEqual(records, before)

    def test_non_boolean_setup_scope_and_wrong_native_leaf_types_are_rejected(self):
        for scope in ('yes', 1, None):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.config.reconcile(b'{}', [], [record()], allow_capabilities=scope)
        for local, desired in [(b'{"permissions":false}', record()),
                               (b'{"flag":{}}', record(pointer=['flag'], mode='value', value=True))]:
            with self.subTest(local=local), self.assertRaises(ValueError):
                self.config.reconcile(local, [], [desired], True)

    def test_pointer_or_mode_migration_retains_exact_old_ownership_and_bytes(self):
        local = b'{ "permissions": {"ask": ["old"]}, "private":"preserve" }\n'
        for new in [record(pointer=['permissions', 'deny']), record(mode='value')]:
            with self.subTest(new=new):
                result = self.config.reconcile(local, [record()], [new], True)
                self.assertTrue(result['conflicts'])
                self.assertEqual(result['content'], local)
                self.assertEqual(result['entries'], [record()])

    def test_modified_or_missing_owned_entry_remains_project_customization(self):
        for local in [b'{"permissions":{"ask":["custom"]}}', b'{}']:
            with self.subTest(local=local):
                result = self.config.reconcile(local, [record()], [record()])
                self.assertEqual(result['content'], local)
                self.assertFalse(result['conflicts'])
                self.assertEqual(result['entries'], [record()])
                self.assertTrue(result['retained'])

    def test_unowned_scalar_is_preserved_even_with_capability_setup(self):
        local = b'{"flag":"owner selected","private":"preserve"}'
        result = self.config.reconcile(local, [], [record(pointer=['flag'], mode='value', value=True)], True)
        self.assertTrue(result['conflicts'])
        self.assertEqual(result['content'], local)
        self.assertEqual(result['entries'], [])

    def test_exact_scalar_removal_requires_scope_and_preserves_other_values(self):
        old = record(pointer=['flag'], mode='value', value=True)
        local = b'{"flag":true,"private":"preserve"}'
        self.assertEqual(self.config.reconcile(local, [old], [])['content'], local)
        result = self.config.reconcile(local, [old], [], allow_removal=True)
        self.assertEqual(json.loads(result['content']), {'private': 'preserve'})
        self.assertEqual(result['entries'], [])

    def test_unchanged_owned_capability_needs_no_new_setup_authorization(self):
        local = b'{ "permissions": {"ask": ["old"]}, "private":"preserve" }\n'
        result = self.config.reconcile(local, [record()], [record()])
        self.assertEqual(result['content'], local)
        self.assertEqual(result['entries'], [record()])
        self.assertFalse(result['conflicts'])


class SourceAndRootDecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rpi decision roots ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.lifecycle = module('rpi-lifecycle')
        self.package = module('rpi-package')

    def test_user_roots_must_be_explicit_disjoint_and_not_symlinks(self):
        base = {'scope': 'user', 'target': str(self.root / 'target'), 'harnesses': ['claude'],
                'state_root': str(self.root / 'state'), 'claude_skill_root': str(self.root / 'skills')}
        link = self.root / 'link'
        link.symlink_to(self.root / 'skills', target_is_directory=True)
        changes = [{'state_root': None}, {'claude_skill_root': None}, {'scope': 'unknown'},
                   {'state_root': str(link)}, {'claude_skill_root': str(link)},
                   {'claude_skill_root': str(self.root / 'state/skills')},
                   {'claude_skill_root': '/'}, {'target': str(link)}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.lifecycle.request_roots({**base, **change})
        self.assertEqual(list(self.root.iterdir()), [link])
        roots, state = self.lifecycle.request_roots(base)
        self.assertEqual(set(roots), {'claude-user-skills'})
        self.assertEqual(state, base['state_root'])
        self.assertFalse(Path(state).exists())

    def test_noncanonical_or_file_parent_destination_does_not_touch_sentinel(self):
        sentinel = self.root / 'sentinel'
        sentinel.write_bytes(b'preserve')
        for destination in ('../outside', '/tmp/outside', 'a//b', 'sentinel/child'):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                self.lifecycle.bound_path(self.root, destination)
        with self.assertRaises(ValueError):
            self.lifecycle.snapshot(self.root)
        self.assertEqual(sentinel.read_bytes(), b'preserve')

    def test_package_rejects_empty_sources_and_conflicting_resource_aliases(self):
        with self.assertRaises(ValueError):
            self.package.bundle_sources(self.root, {'runtime_sources': [''], 'components': []})
        skill = self.root / 'skill'
        skill.mkdir()
        (skill / 'SKILL.md').write_text('skill')
        (skill / 'reference.md').write_text('local source')
        (self.root / 'canonical.md').write_text('different canonical source')
        manifest = {'runtime_sources': ['skill/reference.md'], 'components': [{
            'kind': 'skill', 'source': 'skill', 'resources': ['reference.md',
                {'source': 'canonical.md', 'destination': 'reference.md'}]}]}
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'alias collision'):
            self.package.bundle_sources(self.root, manifest)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        (self.root / 'canonical.md').write_text('local source')
        tree = self.package.bundle_sources(self.root, manifest)
        self.assertEqual(tree['skill/reference.md'], tree['canonical.md'])

    def test_changed_source_between_duplicate_reads_never_emits_a_mixed_package(self):
        source = self.root / 'shared.md'
        source.write_bytes(b'Original source.\n')
        original_read = Path.read_bytes
        reads = 0

        def concurrent_read(path):
            nonlocal reads
            data = original_read(path)
            if path == source:
                reads += 1
                if reads == 1:
                    path.write_bytes(b'Newer source edit.\n')
            return data

        with patch.object(Path, 'read_bytes', concurrent_read):
            with self.assertRaisesRegex(ValueError, 'runtime source collision'):
                self.package.bundle_sources(self.root, {'runtime_sources': ['shared.md', 'shared.md'], 'components': []})
        self.assertEqual(source.read_bytes(), b'Newer source edit.\n')

    def test_invalid_atomic_node_preserves_file_and_removes_staging(self):
        target = self.root / 'sentinel'
        target.write_bytes(b'preserve')
        for node in [{'kind': 'directory'}, {**self.lifecycle.file_node(b'replacement'), 'sha256': '0' * 64}]:
            with self.subTest(node=node), self.assertRaises(ValueError):
                self.lifecycle.atomic_node(target, node)
            self.assertEqual(target.read_bytes(), b'preserve')
            self.assertEqual(list(self.root.iterdir()), [target])
        self.lifecycle.atomic_node(self.root / 'absent', {'kind': 'missing'})
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_ambiguous_instruction_markers_cannot_claim_an_owner_block(self):
        for data in (b'<!-- rpi:policy:start -->\nmissing end',
                     b'<!-- rpi:policy:end -->\n<!-- rpi:policy:start -->',
                     b'<!-- rpi:policy:start --><!-- rpi:policy:start --><!-- rpi:policy:end -->'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.lifecycle.extract_block(data, 'policy')
        complete = b'<!-- rpi:policy:start -->\nowned\n<!-- rpi:policy:end -->'
        self.assertEqual(self.lifecycle.extract_block(complete, 'policy'), complete)

    def test_legacy_resource_alias_claims_only_its_declared_historical_source(self):
        manifest = {'components': [{'id': 'skill:domain', 'kind': 'skill', 'category': 'domain',
            'name': 'domain', 'source': 'templates/skills/domain', 'resources': ['local.md',
                {'source': 'templates/shared.md', 'destination': 'references/shared.md'}]}]}
        proposed = {'component_id': 'skill:domain', 'destination': '.claude/skills/domain/references/shared.md'}
        self.assertEqual(self.lifecycle.legacy_source_path(manifest, proposed), 'templates/shared.md')
        for changed in ({'destination': '.claude/skills/domain/unknown.md'}, {'component_id': 'absent'},
                        {'block': 'owner'}, {'destination': '.agents/skills/domain/references/shared.md'}):
            with self.subTest(changed=changed):
                self.assertIsNone(self.lifecycle.legacy_source_path(manifest, {**proposed, **changed}))


class LifecycleDecisionTests(unittest.TestCase):
    setUp = adopters.LifecycleAdopterTests.setUp
    write = adopters.LifecycleAdopterTests.write
    make_source = adopters.LifecycleAdopterTests.make_source
    git = adopters.LifecycleAdopterTests.git
    commit_source = adopters.LifecycleAdopterTests.commit_source
    invoke = adopters.LifecycleAdopterTests.invoke
    plan = adopters.LifecycleAdopterTests.plan
    apply_ready = adopters.LifecycleAdopterTests.apply_ready
    snapshot = adopters.LifecycleAdopterTests.snapshot

    def assert_rejected_preserving_project(self, *args):
        before = self.snapshot(include_local=True)
        result = self.invoke(*args)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(include_local=True), before)
        self.assertEqual(self.outside.read_bytes(), b'Outside every bound installation root.\n')
        return result

    def test_uninstalled_detach_is_noop_and_never_creates_installation_state(self):
        self.write(self.project, 'AGENTS.md', 'Unowned project knowledge.\n')
        plan, path = self.plan('detach')
        self.assertEqual(plan['status'], 'noop')
        before = self.snapshot(include_local=True)
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        self.assertEqual(self.snapshot(include_local=True), before)
        self.assertFalse((self.project / '.rpi').exists())

    def test_legacy_revision_requires_full_locally_bound_commit(self):
        for revision in ('main', '0' * 40, self.git('rev-parse', 'HEAD:templates/commands/plan.md')):
            with self.subTest(revision=revision):
                self.assert_rejected_preserving_project('plan', '--source', self.source, '--target', self.project,
                    '--legacy-base', revision, '--output', self.plans / (revision + '.json'))

    def test_source_absent_from_immutable_revision_cannot_prove_legacy_ownership(self):
        lifecycle = module('rpi-lifecycle')
        self.write(self.source, 'templates/not-in-baseline.md', 'New content with no historic authority.\n')
        before = self.snapshot(include_local=True)
        self.assertIsNone(lifecycle.historical_blob(self.source, self.base_revision, 'templates/not-in-baseline.md'))
        self.assertEqual(self.snapshot(include_local=True), before)

    def test_native_settings_symlink_and_non_object_are_never_replaced(self):
        path = self.project / '.claude/settings.json'
        path.parent.mkdir()
        path.symlink_to(self.outside)
        self.assert_rejected_preserving_project('plan', '--source', self.source, '--target', self.project,
                                               '--output', self.plans / 'symlink.json')
        self.assertTrue(path.is_symlink())
        path.unlink()
        path.write_text('[]')
        self.assert_rejected_preserving_project('plan', '--source', self.source, '--target', self.project,
                                               '--output', self.plans / 'array.json')

    def test_binary_simultaneous_edits_conflict_without_logging_private_bytes(self):
        self.apply_ready()
        destination = '.agents/skills/rpi-plan/references/playbook.md'
        (self.project / destination).write_bytes(b'PRIVATE_BINARY\0local')
        (self.source / 'templates/skills/rpi-plan/references/playbook.md').write_bytes(b'UPSTREAM_BINARY\0remote')
        plan, path = self.plan('update')
        self.assertEqual(plan['status'], 'conflict')
        self.assertIn('binary', next(c for c in plan['conflicts'] if c['destination'] == destination)['diffs'])
        result = self.assert_rejected_preserving_project('apply', '--plan', path)
        self.assertNotIn('PRIVATE_BINARY', result.stdout + result.stderr)

    def test_nonoverlapping_three_way_edits_preserve_both_customizations(self):
        relative = 'templates/skills/rpi-plan/references/playbook.md'
        original = 'first\n' + 'middle\n' * 12 + 'last\n'
        (self.source / relative).write_text(original)
        self.apply_ready()
        target = self.project / '.agents/skills/rpi-plan/references/playbook.md'
        target.write_text(original.replace('first', 'owner first'))
        (self.source / relative).write_text(original.replace('last', 'upstream last'))
        self.apply_ready('update')
        self.assertEqual(target.read_text(), original.replace('first', 'owner first').replace('last', 'upstream last'))

    def test_modified_direct_registration_blocks_plugin_switch(self):
        self.apply_ready()
        self.write(self.project, '.agents/skills/rpi-plan/SKILL.md', 'Owner modified workflow.\n')
        plan, path = self.plan('update', '--route', 'plugin')
        self.assertEqual(plan['status'], 'conflict')
        self.assertTrue(any('modified direct registration' in c['reason'] for c in plan['conflicts']))
        self.assert_rejected_preserving_project('apply', '--plan', path)

    def test_unknown_direct_registration_blocks_plugin_install(self):
        self.write(self.project, '.agents/skills/rpi-plan/SKILL.md', 'Unowned workflow.\n')
        plan, path = self.plan('install', '--route', 'plugin')
        self.assertEqual(plan['status'], 'conflict')
        self.assertTrue(any('unknown direct registration' in c['reason'] for c in plan['conflicts']))
        self.assert_rejected_preserving_project('apply', '--plan', path)

    def test_altered_binding_and_duplicate_manifest_entries_block_detach(self):
        self.apply_ready()
        binding = self.project / '.rpi/local/root-binding.json'
        original = binding.read_bytes()
        binding.write_text('{}')
        self.assert_rejected_preserving_project('check', '--source', self.source, '--target', self.project)
        binding.write_bytes(original)
        manifest = self.project / '.rpi/manifest.json'
        value = json.loads(manifest.read_text())
        value['entries'].append(value['entries'][0])
        manifest.write_text(json.dumps(value))
        self.assert_rejected_preserving_project('detach', '--source', self.source, '--target', self.project,
                                               '--output', self.plans / 'duplicate.json')

    def test_journal_symlink_and_pending_tampering_cannot_overwrite_newer_work(self):
        _, path = self.plan()
        result = self.invoke('apply', '--plan', path, '--fail-after-rename', '1')
        self.assertEqual(result.returncode, 2)
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        alias = self.plans / 'journal-link.json'
        alias.symlink_to(journal)
        self.assert_rejected_preserving_project('rollback', '--journal', alias)
        value = json.loads(journal.read_text())
        value['pending'] = len(value['operations']) + 1
        journal.write_text(json.dumps(value))
        self.assert_rejected_preserving_project('rollback', '--journal', journal)

    def test_invalid_recovery_progress_is_rejected_before_any_restoration(self):
        self.apply_ready()
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        original = json.loads(journal.read_text())
        changes = [{'completed': value} for value in (-1, len(original['operations']) + 1, True)]
        changes += [{'pending': value, 'status': 'applying'} for value in (True, -1)]
        changes += [{'status': 'unknown'}, {'status': 'complete', 'completed': 1}]
        changes += [{'schema_version': 2}, {'transaction': True}, {'transaction': '0' * 32}]
        for change in changes:
            with self.subTest(change=change):
                value = copy.deepcopy(original)
                value.update(change)
                journal.write_text(json.dumps(value))
                self.assert_rejected_preserving_project('rollback', '--journal', journal)

    def test_interrupted_operation_with_newer_bytes_is_never_rolled_back(self):
        plan, path = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', path, '--fail-after-rename', '1').returncode, 2)
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        operation = plan['operations'][0]
        root = Path(plan['state_root'] if operation['root_id'] == 'state' else plan['roots'][operation['root_id']])
        target = root / operation['destination']
        target.write_bytes(b'Newer user work after interrupted installation.\n')
        self.assert_rejected_preserving_project('rollback', '--journal', journal)

    def owned_link(self):
        self.apply_ready()
        lifecycle = module('rpi-lifecycle')
        destination = '.agents/skills/rpi-plan/SKILL.md'
        path = self.project / destination
        path.unlink()
        path.symlink_to(self.outside)
        target = str(self.outside).encode()
        baseline = self.project / '.rpi/baselines' / lifecycle.digest(target)
        baseline.write_bytes(target)
        manifest = self.project / '.rpi/manifest.json'
        value = json.loads(manifest.read_text())
        entry = next(e for e in value['entries'] if e['destination'] == destination)
        entry.update(node_kind='symlink', base_hash=lifecycle.digest(target))
        manifest.write_text(json.dumps(value))
        return path, baseline

    def test_exact_owned_symlink_detaches_without_traversing_target(self):
        path, _ = self.owned_link()
        existing = set((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        self.apply_ready('detach')
        self.assertFalse(path.is_symlink())
        self.assertEqual(self.outside.read_bytes(), b'Outside every bound installation root.\n')
        journal = next(iter(set((self.project / '.rpi/local/transactions').glob('*/journal.json')) - existing))
        self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.assertTrue(path.is_symlink())
        self.assertEqual(self.outside.read_bytes(), b'Outside every bound installation root.\n')

    def test_missing_symlink_baseline_blocks_detach_without_traversal(self):
        path, baseline = self.owned_link()
        baseline.unlink()
        plan, artifact = self.plan('detach')
        self.assertEqual(plan['status'], 'conflict')
        self.assertTrue(any('symlink ownership baseline' in c['reason'] for c in plan['conflicts']))
        self.assert_rejected_preserving_project('apply', '--plan', artifact)
        self.assertTrue(path.is_symlink())

    def test_modified_owned_symlink_is_retained_on_detach(self):
        path, _ = self.owned_link()
        replacement = self.workspace / 'new-owner-target'
        replacement.write_bytes(b'New owner target.\n')
        path.unlink()
        path.symlink_to(replacement)
        self.apply_ready('detach')
        self.assertTrue(path.is_symlink())
        self.assertEqual(path.resolve(), replacement.resolve())
        self.assertEqual(replacement.read_bytes(), b'New owner target.\n')

    def test_corrupt_recovery_payload_or_state_destination_never_mutates_project(self):
        self.apply_ready()
        lifecycle = module('rpi-lifecycle')
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        receipt = journal.with_name('receipt.json')
        original = json.loads(journal.read_text())
        original_receipt = json.loads(receipt.read_text())
        for change in ('hash', 'mode', 'kind', 'state-path'):
            with self.subTest(change=change):
                value = copy.deepcopy(original)
                operation = value['operations'][0]
                if change == 'hash':
                    operation['after']['sha256'] = '0' * 64
                elif change == 'mode':
                    operation['after']['mode'] = 0o4777
                elif change == 'kind':
                    operation['after'] = {'kind': 'directory'}
                else:
                    operation.update(root_id='state', destination='local/private.json')
                # Even mutually consistent recovery metadata cannot authorize an
                # unsupported node or widen the portable state destination set.
                changed_receipt = {**original_receipt, 'operations_sha256': lifecycle.digest(lifecycle.serialized(value['operations']))}
                journal.write_text(json.dumps(value))
                receipt.write_text(json.dumps(changed_receipt))
                self.assert_rejected_preserving_project('rollback', '--journal', journal)

    def test_recovery_receipt_mismatch_blocks_without_lock_or_restoration(self):
        self.apply_ready()
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        receipt = journal.with_name('receipt.json')
        receipt.write_text('{}')
        self.assert_rejected_preserving_project('rollback', '--journal', journal)

    def test_matching_local_binding_cannot_redirect_project_recovery_root(self):
        self.apply_ready()
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        value = json.loads(journal.read_text())
        value['roots'] = {'project': str(self.workspace.resolve())}
        journal.write_text(json.dumps(value))
        lifecycle = module('rpi-lifecycle')
        (self.project / '.rpi/local/root-binding.json').write_bytes(lifecycle.serialized(value['roots']))
        self.assert_rejected_preserving_project('rollback', '--journal', journal)

    def test_project_recovery_state_cannot_be_renamed_to_an_unowned_directory(self):
        self.apply_ready()
        state = self.project / '.rpi'
        renamed = self.project / '.unowned-state'
        state.rename(renamed)
        journal = next((renamed / 'local/transactions').glob('*/journal.json'))
        value = json.loads(journal.read_text())
        value['state_root'] = str(renamed.resolve())
        journal.write_text(json.dumps(value))
        self.assert_rejected_preserving_project('rollback', '--journal', journal)

    def test_pending_operation_not_yet_renamed_does_not_restore_unwritten_data(self):
        before = self.snapshot()
        plan, path = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', path, '--fail-after-rename', '1').returncode, 2)
        lifecycle = module('rpi-lifecycle')
        operation = plan['operations'][0]
        lifecycle.atomic_node(lifecycle.operation_path(plan, operation), operation['before'])
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.assertEqual(self.snapshot(), before)

    def test_user_edit_between_rollback_checks_survives(self):
        self.apply_ready()
        lifecycle = module('rpi-lifecycle')
        journal = next((self.project / '.rpi/local/transactions').glob('*/journal.json'))
        target = self.project / '.rpi/manifest.json'
        original_snapshot = lifecycle.snapshot
        reads = 0

        def concurrent_snapshot(path):
            nonlocal reads
            if path == target.resolve():
                reads += 1
                if reads == 3:
                    path.write_bytes(b'Concurrent user repair.\n')
            return original_snapshot(path)

        before = self.snapshot()
        with patch.object(lifecycle, 'snapshot', side_effect=concurrent_snapshot):
            with self.assertRaisesRegex(ValueError, 'postimage changed during rollback'):
                lifecycle.rollback(journal)
        expected = {**before, '.rpi/manifest.json': b'Concurrent user repair.\n'}
        self.assertEqual(self.snapshot(), expected)

    def test_user_edit_after_transaction_start_blocks_the_first_write(self):
        plan, _ = self.plan()
        lifecycle = module('rpi-lifecycle')
        engine = module('rpi-distribution')
        operation = plan['operations'][0]
        self.assertEqual(operation['root_id'], 'project')
        target = Path(plan['roots']['project']) / operation['destination']
        original_atomic = lifecycle.atomic_node

        def concurrent_atomic(path, node):
            original_atomic(path, node)
            if path.name == 'receipt.json':
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'Concurrent user document.\n')

        before = self.snapshot()
        with patch.object(lifecycle, 'atomic_node', side_effect=concurrent_atomic):
            with self.assertRaisesRegex(ValueError, 'preimage changed during transaction'):
                lifecycle.apply_plan(engine, plan)
        self.assertEqual(self.snapshot(), {**before, operation['destination']: b'Concurrent user document.\n'})

    def config_source(self, harness='claude', scope='project'):
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        declaration = {'schema_version': 1, 'entries': [record()]}
        self.write(self.source, 'templates/adapters/test-policy.json', json.dumps(declaration))
        manifest['components'].append({'id': 'config:decision', 'kind': 'config', 'scope': scope,
            'selection': 'default', 'harnesses': [harness], 'dependencies': [],
            'source': 'templates/adapters/test-policy.json', 'outputs': {harness: 'configuration/test-policy.json'},
            'destinations': {harness: '.claude/settings.json' if harness == 'claude' else '.codex/hooks.json'},
            'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'}})
        manifest_path.write_text(json.dumps(manifest))

    def test_unselected_capability_authorization_cannot_widen_setup_scope(self):
        self.assert_rejected_preserving_project('plan', '--source', self.source, '--target', self.project,
            '--allow-capabilities', 'config:not-selected', '--output', self.plans / 'unknown-capability.json')

    def test_damaged_exact_configuration_baseline_blocks_detach(self):
        self.config_source()
        self.apply_ready('install', '--allow-capabilities', 'config:decision')
        value = json.loads((self.project / '.rpi/manifest.json').read_text())
        entry = next(e for e in value['entries'] if 'config_record' in e)
        (self.project / '.rpi/baselines' / entry['base_hash']).write_bytes(b'Changed exact entry baseline.\n')
        plan, path = self.plan('detach')
        self.assertEqual(plan['status'], 'conflict')
        self.assertTrue(any('configuration baseline' in c['reason'] for c in plan['conflicts']))
        self.assert_rejected_preserving_project('apply', '--plan', path)

    def test_other_harness_configuration_survives_selected_harness_detach(self):
        self.config_source()
        self.apply_ready('install', '--allow-capabilities', 'config:decision')
        path = self.project / '.claude/settings.json'
        before = path.read_bytes()
        self.apply_ready('detach', '--harness', 'codex')
        self.assertEqual(path.read_bytes(), before)
        value = json.loads((self.project / '.rpi/manifest.json').read_text())
        self.assertTrue(any(e.get('config_record') for e in value['entries']))

    def test_codex_configuration_symlink_never_writes_external_target(self):
        self.config_source(harness='codex')
        path = self.project / '.codex/hooks.json'
        path.parent.mkdir()
        path.symlink_to(self.outside)
        plan, artifact = self.plan('install', '--allow-capabilities', 'config:decision')
        self.assertEqual(plan['status'], 'conflict')
        self.assertTrue(any('native configuration must be a regular file' in c['reason'] for c in plan['conflicts']))
        self.assert_rejected_preserving_project('apply', '--plan', artifact)

    def test_existing_damaged_future_baseline_is_not_overwritten(self):
        lifecycle = module('rpi-lifecycle')
        data = (self.source / 'templates/skills/rpi-plan/references/playbook.md').read_bytes()
        path = self.project / '.rpi/baselines' / lifecycle.digest(data)
        path.parent.mkdir(parents=True)
        path.write_bytes(b'Preserve damaged baseline for diagnosis.\n')
        plan, artifact = self.plan()
        self.assertEqual(plan['status'], 'conflict')
        self.assertTrue(any('baseline hash collision or damaged baseline' in c['reason'] for c in plan['conflicts']))
        self.assert_rejected_preserving_project('apply', '--plan', artifact)

    def test_user_configuration_cannot_reuse_project_bound_destination(self):
        self.config_source(scope='user')
        state, claude, codex = [self.workspace / name for name in ('state-only', 'claude-only', 'codex-only')]
        self.assert_rejected_preserving_project('plan', '--source', self.source, '--target', self.project,
            '--scope', 'user', '--state-root', state, '--claude-skill-root', claude,
            '--codex-skill-root', codex, '--allow-capabilities', 'config:decision',
            '--output', self.plans / 'user-config.json')
        self.assertFalse(any(path.exists() for path in (state, claude, codex)))

    def test_invalid_configuration_declaration_never_applies_partial_setup(self):
        self.config_source()
        declaration = self.source / 'templates/adapters/test-policy.json'
        declaration.write_text('{"schema_version":1,"entries":[],"extra":"not supported"}')
        self.assert_rejected_preserving_project('plan', '--source', self.source, '--target', self.project,
            '--allow-capabilities', 'config:decision', '--output', self.plans / 'malformed-config.json')

    def test_state_manifest_symlink_and_invalid_plan_schema_never_authorize_writes(self):
        state = self.project / '.rpi'
        state.mkdir()
        (state / 'manifest.json').symlink_to(self.outside)
        self.assert_rejected_preserving_project('check', '--source', self.source, '--target', self.project)
        artifact = self.plans / 'invalid-plan.json'
        artifact.write_text('{"schema_version":99,"request":{}}')
        self.assert_rejected_preserving_project('apply', '--plan', artifact)

    def test_invalid_persisted_scope_route_and_schema_cannot_authorize_detach(self):
        self.apply_ready()
        manifest = self.project / '.rpi/manifest.json'
        original = json.loads(manifest.read_text())
        cases = [{'scope': 'user', 'root_ids': ['claude-user-skills'], 'entries': []},
                 {'schema_version': 99},
                 {'installations': {'codex': {'route': 'unknown', 'domains': []}}},
                 {'entries': [{**original['entries'][0], 'destination': '../outside'}]}]
        for change in cases:
            with self.subTest(change=change):
                manifest.write_text(json.dumps({**original, **change}))
                self.assert_rejected_preserving_project('check', '--source', self.source, '--target', self.project)

    def test_owned_symlink_update_is_not_permission_to_replace_it(self):
        path, _ = self.owned_link()
        plan, artifact = self.plan('update')
        self.assertEqual(plan['status'], 'conflict')
        self.assertTrue(any('unproven symlink destination' in c['reason'] for c in plan['conflicts']))
        self.assert_rejected_preserving_project('apply', '--plan', artifact)
        self.assertTrue(path.is_symlink())

    def test_unproven_legacy_directory_is_retained_even_with_matching_name(self):
        path = self.write(self.project, '.claude/commands/plan.md/custom.txt', 'Unowned legacy directory content.\n')
        plan = self.apply_ready()
        self.assertTrue(any(c['reason'] == 'unproven legacy directory retained' for c in plan['retained']))
        self.assertEqual(path.read_text(), 'Unowned legacy directory content.\n')

    def test_legacy_alias_with_symlink_parent_blocks_without_following_it(self):
        parent = self.project / '.claude/commands'
        parent.parent.mkdir()
        parent.symlink_to(self.outside)
        plan, artifact = self.plan()
        self.assertEqual(plan['status'], 'conflict')
        self.assertTrue(any('symlink parent' in c['reason'] for c in plan['conflicts']))
        self.assert_rejected_preserving_project('apply', '--plan', artifact)
        self.assertTrue(parent.is_symlink())

    def test_mixed_native_routes_retain_each_harness_selection(self):
        self.apply_ready('install', '--route', 'plugin', '--harness', 'claude')
        self.apply_ready('install', '--harness', 'codex')
        artifact = self.plans / 'mixed-selection.json'
        planned = self.invoke('plan', '--source', self.source, '--target', self.project, '--harness', 'both',
                              '--action', 'update', '--output', artifact)
        self.assertEqual(planned.returncode, 0, planned.stdout + planned.stderr)
        self.assertEqual(self.invoke('apply', '--plan', artifact).returncode, 0)
        before = self.snapshot(include_local=True)
        result = self.invoke('check', '--source', self.source, '--target', self.project, '--harness', 'both')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(include_local=True), before)
        self.assertTrue((self.project / '.agents/skills/rpi-plan/SKILL.md').exists())
        self.assertFalse((self.project / '.claude/skills/rpi-plan/SKILL.md').exists())

    def native_resource(self):
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        source = self.write(self.source, 'templates/native.rules', 'prefix_rule(pattern=["git", "push"], decision="prompt")\n')
        manifest['components'].append({'id': 'resource:native', 'kind': 'resource', 'scope': 'project',
            'selection': 'default', 'harnesses': ['codex'], 'dependencies': [], 'capability': True,
            'source': 'templates/native.rules', 'outputs': {'codex': '.codex/rules/rpi.rules'},
            'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'}})
        manifest_path.write_text(json.dumps(manifest))
        return source, self.project / '.codex/rules/rpi.rules'

    def test_native_capability_file_add_change_and_same_version_setup_scope(self):
        source, destination = self.native_resource()
        plan, artifact = self.plan()
        self.assertEqual(plan['status'], 'conflict')
        self.assert_rejected_preserving_project('apply', '--plan', artifact)
        self.assertFalse(destination.exists())
        self.apply_ready('install', '--allow-capabilities', 'resource:native')
        same = self.apply_ready('update')
        self.assertEqual(same['status'], 'noop')
        source.write_text('prefix_rule(pattern=["git", "push"], decision="forbidden")\n')
        plan, artifact = self.plan('update')
        self.assertEqual(plan['status'], 'conflict')
        self.assert_rejected_preserving_project('apply', '--plan', artifact)
        self.apply_ready('update', '--allow-capabilities', 'resource:native')
        self.assertEqual(destination.read_bytes(), source.read_bytes())

    def test_retired_native_capability_file_requires_setup_scope(self):
        _, destination = self.native_resource()
        self.apply_ready('install', '--allow-capabilities', 'resource:native')
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['components'] = [c for c in manifest['components'] if c['id'] != 'resource:native']
        manifest_path.write_text(json.dumps(manifest))
        plan, artifact = self.plan('update')
        self.assertEqual(plan['status'], 'conflict')
        self.assert_rejected_preserving_project('apply', '--plan', artifact)
        self.assertTrue(destination.is_file())
        self.apply_ready('update', '--allow-capabilities', 'resource:native')
        self.assertFalse(destination.exists())

    def test_capability_flag_downgrade_cannot_remove_existing_setup_boundary(self):
        source, destination = self.native_resource()
        self.apply_ready('install', '--allow-capabilities', 'resource:native')
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        next(c for c in manifest['components'] if c['id'] == 'resource:native').pop('capability')
        manifest_path.write_text(json.dumps(manifest))
        source.write_text('prefix_rule(pattern=["git", "push"], decision="forbidden")\n')
        plan, artifact = self.plan('update')
        self.assertEqual(plan['status'], 'conflict')
        self.assert_rejected_preserving_project('apply', '--plan', artifact)
        self.apply_ready('update', '--allow-capabilities', 'resource:native')
        self.assertEqual(destination.read_bytes(), source.read_bytes())
        installed = json.loads((self.project / '.rpi/manifest.json').read_text())
        entry = next(e for e in installed['entries'] if e['component_id'] == 'resource:native')
        self.assertIs(entry['capability'], True)
        source.write_text('prefix_rule(pattern=["git"], decision="prompt")\n')
        plan, artifact = self.plan('update')
        self.assertEqual(plan['status'], 'conflict')
        self.assert_rejected_preserving_project('apply', '--plan', artifact)

    def test_explicit_detach_removes_only_exact_owned_capability_file(self):
        _, destination = self.native_resource()
        self.apply_ready('install', '--allow-capabilities', 'resource:native')
        owner = self.write(self.project, '.codex/rules/owner.rules', 'Owner policy.\n')
        self.apply_ready('detach')
        self.assertFalse(destination.exists())
        self.assertEqual(owner.read_text(), 'Owner policy.\n')

    def test_unselected_harness_capability_scope_is_rejected_before_write(self):
        self.native_resource()
        self.assert_rejected_preserving_project('plan', '--source', self.source, '--target', self.project,
            '--harness', 'claude', '--allow-capabilities', 'resource:native',
            '--output', self.plans / 'unselected-native-capability.json')

    def test_missing_cli_authority_inputs_never_create_installation_state(self):
        for args in [('apply',), ('rollback',), ('plan', '--source', self.source),
                     ('plan', '--source', self.source, '--target', self.project)]:
            with self.subTest(args=args):
                self.assert_rejected_preserving_project(*args)
        self.assertFalse((self.project / '.rpi').exists())

    def test_existing_plan_artifact_is_never_overwritten(self):
        _, artifact = self.plan()
        before = artifact.read_bytes()
        self.assert_rejected_preserving_project('plan', '--source', self.source, '--target', self.project,
                                               '--output', artifact)
        self.assertEqual(artifact.read_bytes(), before)

    def test_explicit_user_scope_defaults_are_bound_without_touching_global_state(self):
        engine = module('rpi-distribution')
        selected_user = self.workspace / 'synthetic-user'
        artifact = self.plans / 'default-user-roots.json'
        argv = ['rpi-distribution', 'plan', '--source', str(self.source), '--scope', 'user',
                '--harness', 'codex', '--output', str(artifact)]
        with (patch.object(Path, 'home', return_value=selected_user), patch.object(sys, 'argv', argv),
              patch.dict(sys.modules, {engine.__name__: engine}), redirect_stdout(io.StringIO())):
            self.assertEqual(engine.main(), 0)
        request = json.loads(artifact.read_text())['request']
        self.assertEqual(Path(request['target']), selected_user / '.config/cc-rpi/installations/user')
        self.assertEqual(Path(request['codex_skill_root']), selected_user / '.agents/skills')
        self.assertFalse(selected_user.exists())
