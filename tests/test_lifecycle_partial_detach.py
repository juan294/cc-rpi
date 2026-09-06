"""Partial lifecycle actions preserve resources still owned by another harness."""
import json
import shutil
import unittest

import test_lifecycle_adopters as adopters


class PartialDetachTests(unittest.TestCase):
    write = adopters.LifecycleAdopterTests.write
    make_source = adopters.LifecycleAdopterTests.make_source
    git = adopters.LifecycleAdopterTests.git
    commit_source = adopters.LifecycleAdopterTests.commit_source
    invoke = adopters.LifecycleAdopterTests.invoke
    plan = adopters.LifecycleAdopterTests.plan
    apply_ready = adopters.LifecycleAdopterTests.apply_ready
    snapshot = adopters.LifecycleAdopterTests.snapshot

    def setUp(self):
        adopters.LifecycleAdopterTests.setUp(self)
        self.shared = {
            '.rpi/scripts/shared-runtime.py': b'# Shared runtime required by both clients.\n',
            '.rpi/adapters/shared.json': b'{"shared":true}\n',
            'support/runtime.txt': b'Shared ownership is not limited to a directory prefix.\n',
        }
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        for index, (destination, data) in enumerate(self.shared.items()):
            source = 'templates/shared-' + str(index) + '.txt'
            self.write(self.source, source, data.decode())
            manifest['components'].append({
                'id': 'resource:shared-' + str(index), 'kind': 'resource',
                'scope': 'project', 'selection': 'default', 'dependencies': [],
                'harnesses': ['claude', 'codex'], 'source': source,
                'outputs': {'claude': destination, 'codex': destination},
                'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'},
            })
        manifest_path.write_text(json.dumps(manifest))
        self.owner = {
            'AGENTS.md': b'# Project-owned knowledge\nKeep owner facts.\n',
            'CLAUDE.md': b'# Owner Claude guidance\n',
            '.rpi/scripts/owner-extension.py': b'# Owner extension must survive.\n',
            'support/owner.txt': b'Owner support file.\n',
        }
        for destination, data in self.owner.items():
            self.write(self.project, destination, data.decode())

    def assert_healthy_noop(self, harness, route, source=None):
        source = source or self.source
        before = self.snapshot(include_local=True)
        result = self.invoke('check', '--source', source, '--target', self.project,
                             '--harness', harness, '--route', route)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(include_local=True), before)
        plan, _ = self.plan('update', '--harness', harness, '--route', route, '--source', source)
        self.assertEqual(plan['status'], 'noop', plan.get('operations'))
        self.assertEqual(plan['operations'], [])
        self.assertEqual(self.snapshot(include_local=True), before)

    def assert_shared_present(self):
        for destination, data in self.shared.items():
            self.assertTrue((self.project / destination).is_file(), destination)
            self.assertEqual((self.project / destination).read_bytes(), data, destination)

    def exercise_detach(self, detached, routes, *, legacy=False):
        if len(set(routes.values())) == 1:
            self.apply_ready('install', '--route', routes['claude'])
        else:
            for harness, route in routes.items():
                self.apply_ready('install', '--harness', harness, '--route', route)
        if legacy:
            manifest_path = self.project / '.rpi/manifest.json'
            receipt = json.loads(manifest_path.read_text())
            codex_adapter = next(entry['adapter'] for entry in receipt['entries']
                                 if entry['adapter']['harness'] == 'codex')
            for entry in receipt['entries']:
                entry.pop('consumers', None)
                # Older receipts attributed common outputs to the last adapter.
                if entry['destination'] in self.shared:
                    entry['adapter'] = dict(codex_adapter)
            manifest_path.write_text(json.dumps(receipt))
        remaining = 'codex' if detached == 'claude' else 'claude'
        roots = {'claude': '.claude/skills', 'codex': '.agents/skills'}
        remaining_files = self.snapshot(self.project / roots[remaining])
        self.assert_shared_present()
        self.apply_ready('detach', '--harness', detached, '--route', routes[detached])
        self.assert_shared_present()
        state = json.loads((self.project / '.rpi/manifest.json').read_text())
        self.assertEqual(set(state['installations']), {remaining})
        self.assertEqual(state['installations'][remaining]['route'], routes[remaining])
        self.assertFalse((self.project / roots[detached] / 'rpi-plan/SKILL.md').exists())
        self.assertEqual(self.snapshot(self.project / roots[remaining]), remaining_files)
        self.assert_healthy_noop(remaining, routes[remaining])
        self.apply_ready('detach', '--harness', remaining, '--route', routes[remaining])
        for destination in self.shared:
            self.assertFalse((self.project / destination).exists(), destination)
        for destination, data in self.owner.items():
            actual = (self.project / destination).read_bytes()
            if destination == 'CLAUDE.md':
                self.assertTrue(actual.startswith(data), destination)
                self.assertIn(b'@AGENTS.md', actual)
            else:
                self.assertEqual(actual, data, destination)
        self.assertEqual(json.loads((self.project / '.rpi/manifest.json').read_text())['installations'], {})

    def test_direct_detach_claude_preserves_codex_until_last_detach(self):
        self.exercise_detach('claude', {'claude': 'direct', 'codex': 'direct'})

    def test_direct_detach_codex_preserves_claude_until_last_detach(self):
        self.exercise_detach('codex', {'claude': 'direct', 'codex': 'direct'})

    def test_plugin_detach_claude_preserves_codex_project_resources(self):
        self.exercise_detach('claude', {'claude': 'plugin', 'codex': 'plugin'})

    def test_plugin_detach_codex_preserves_claude_project_resources(self):
        self.exercise_detach('codex', {'claude': 'plugin', 'codex': 'plugin'})

    def test_mixed_detach_direct_claude_preserves_plugin_codex(self):
        self.exercise_detach('claude', {'claude': 'direct', 'codex': 'plugin'})

    def test_mixed_detach_plugin_codex_preserves_direct_claude(self):
        self.exercise_detach('codex', {'claude': 'direct', 'codex': 'plugin'})

    def test_legacy_receipt_without_consumers_preserves_remaining_claude(self):
        self.exercise_detach('codex', {'claude': 'direct', 'codex': 'direct'}, legacy=True)

    def test_single_harness_update_cannot_retire_another_harness_resource(self):
        self.apply_ready()
        prior_source = self.workspace / 'untouched Claude source'
        shutil.copytree(self.source, prior_source)
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        for component in manifest['components']:
            if component['id'].startswith('resource:shared-'):
                component['harnesses'] = ['claude']
                component['outputs'].pop('codex')
        manifest_path.write_text(json.dumps(manifest))
        self.apply_ready('update', '--harness', 'codex')
        self.assert_shared_present()
        self.assert_healthy_noop('claude', 'direct', prior_source)

    def test_source_retirement_preserves_untouched_harness_installed_baseline(self):
        self.apply_ready()
        prior_source = self.workspace / 'untouched Claude source'
        shutil.copytree(self.source, prior_source)
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['components'] = [component for component in manifest['components']
                                  if not component['id'].startswith('resource:shared-')]
        manifest_path.write_text(json.dumps(manifest))
        self.apply_ready('update', '--harness', 'codex')
        self.assert_shared_present()
        self.assert_healthy_noop('claude', 'direct', prior_source)
        # Only the remaining consumer's explicit update may now retire them.
        self.apply_ready('update', '--harness', 'claude')
        for destination in self.shared:
            self.assertFalse((self.project / destination).exists(), destination)
        for destination in ('.rpi/scripts/owner-extension.py', 'support/owner.txt'):
            self.assertEqual((self.project / destination).read_bytes(), self.owner[destination])

    def test_invalid_consumers_fail_before_any_project_write(self):
        self.apply_ready()
        manifest_path = self.project / '.rpi/manifest.json'
        original = json.loads(manifest_path.read_text())
        shared_index = next(index for index, entry in enumerate(original['entries'])
                            if entry['destination'] == '.rpi/scripts/shared-runtime.py')
        adapter = original['entries'][shared_index]['adapter']['harness']
        other = 'claude' if adapter == 'codex' else 'codex'
        for consumers in (None, [], 'claude', {}, ['unknown'], ['claude', 'claude'],
                          [other], [True], [['claude']]):
            with self.subTest(consumers=consumers):
                changed = json.loads(json.dumps(original))
                changed['entries'][shared_index]['consumers'] = consumers
                manifest_path.write_text(json.dumps(changed))
                before = self.snapshot(include_local=True)
                result = self.invoke('plan', '--source', self.source, '--target', self.project,
                                     '--harness', 'both', '--action', 'detach',
                                     '--output', self.plans / 'malformed-consumers.json')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('invalid component consumers', result.stdout + result.stderr)
                self.assertEqual(self.snapshot(include_local=True), before)
                self.assertFalse((self.plans / 'malformed-consumers.json').exists())


if __name__ == '__main__':
    unittest.main()
