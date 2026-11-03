"""Resource policy reaches task-only users and survives real installation updates."""
import json
import unittest

import test_distribution as renderer
import test_lifecycle_adopters as adopters


class ResourceRuleTests(unittest.TestCase):
    def test_task_without_dockerfile_and_nested_stack_paths_load_the_rule(self):
        manifest = renderer.distribution.load_manifest(adopters.ROOT)
        for path, task in (
            ('README.md', 'local stack'),
            ('README.md', 'database tests'),
            ('README.md', 'Supabase start'),
            ('README.md', 'resource cleanup'),
            ('apps/web/supabase/config.toml', ''),
            ('infra/compose.test.yaml', ''),
        ):
            with self.subTest(path=path, task=task):
                self.assertIn('rule:resource-lifecycle',
                              renderer.distribution.applicable_rules(manifest, path, task=task))
        self.assertNotIn('rule:resource-lifecycle',
                         renderer.distribution.applicable_rules(manifest, 'src/button.css', task='styling'))


class ResourceUpdateTests(unittest.TestCase):
    setUp = adopters.LifecycleAdopterTests.setUp
    write = adopters.LifecycleAdopterTests.write
    make_source = adopters.LifecycleAdopterTests.make_source
    git = adopters.LifecycleAdopterTests.git
    commit_source = adopters.LifecycleAdopterTests.commit_source
    invoke = adopters.LifecycleAdopterTests.invoke
    plan = adopters.LifecycleAdopterTests.plan
    apply_ready = adopters.LifecycleAdopterTests.apply_ready

    def test_update_installs_both_harness_rules_without_owning_project_resource_data(self):
        self.apply_ready()
        contract = self.write(self.project, 'docs/development/resource-lifecycle.md',
                              'Persistent database: owner-data. Never delete during task cleanup.\n')
        receipt = self.write(self.project, '.rpi/local/resources/active.json',
                             '{"disposable": false, "reason": "recovery hold"}\n')
        before = {path: path.read_bytes() for path in (contract, receipt)}
        product = json.loads((adopters.ROOT / 'templates/distribution.json').read_text())
        component = next(c for c in product['components'] if c['id'] == 'rule:resource-lifecycle')
        source_manifest = self.source / 'templates/distribution.json'
        manifest = json.loads(source_manifest.read_text())
        manifest['components'].append(component)
        source_manifest.write_text(json.dumps(manifest))
        rule = (adopters.ROOT / component['source']).read_bytes()
        self.write(self.source, component['source'], rule.decode())
        self.write(self.source, 'templates/instructions/policy.md',
                   (adopters.ROOT / 'templates/instructions/rule-map.md').read_text())
        self.apply_ready('update')
        for name in ('.rpi/rules/resource-lifecycle.md', '.claude/rules/resource-lifecycle.md'):
            self.assertEqual((self.project / name).read_bytes(), rule)
        agents = (self.project / 'AGENTS.md').read_text()
        self.assertIn('.rpi/rules/resource-lifecycle.md', agents)
        self.assertIn('local stacks', agents)
        self.assertIn('@AGENTS.md', (self.project / 'CLAUDE.md').read_text())
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(self.plan('update')[0]['status'], 'noop')
        self.apply_ready('detach')
        self.assertFalse((self.project / '.rpi/rules/resource-lifecycle.md').exists())
        self.assertEqual({path: path.read_bytes() for path in before}, before)


if __name__ == '__main__':
    unittest.main()
