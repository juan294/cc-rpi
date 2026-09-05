"""Mixed native configuration preserves every entry without proven ownership."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def reconcile(*args, **kwargs):
    spec = importlib.util.spec_from_file_location('rpi_config', ROOT / 'templates/scripts/rpi-config.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.reconcile(*args, **kwargs)


def record(identity='permission:publish', value='Bash(git push:*)', **extra):
    return {'id': identity, 'pointer': ['permissions', 'ask'], 'mode': 'entry', 'value': value, **extra}


class ConfigurationOwnershipTests(unittest.TestCase):
    def test_new_capability_requires_explicit_setup_scope(self):
        local = b'{"env":{"TOKEN":"private sentinel"}}\n'
        result = reconcile(local, [], [record()])
        self.assertTrue(result['conflicts'])
        self.assertEqual(result['content'], local)
        result = reconcile(local, [], [record()], allow_capabilities=True)
        self.assertEqual(json.loads(result['content'])['env']['TOKEN'], 'private sentinel')
        self.assertNotIn('private sentinel', json.dumps(result['entries']))

    def test_unknown_native_entries_and_order_survive_update_and_detach(self):
        local = json.dumps({'permissions': {'ask': ['user first', 'Bash(git push:*)', 'user last'],
                                           'deny': ['private deny']}, 'mcpServers': {'user': 'private'}}).encode()
        changed = record(value='Bash(git push *)')
        updated = reconcile(local, [record()], [changed], allow_capabilities=True)
        self.assertFalse(updated['conflicts'])
        self.assertEqual(json.loads(updated['content'])['permissions']['ask'], ['user first', 'Bash(git push *)', 'user last'])
        detached = reconcile(updated['content'], updated['entries'], [], allow_removal=True)
        self.assertEqual(json.loads(detached['content'])['permissions']['ask'], ['user first', 'user last'])
        self.assertEqual(json.loads(detached['content'])['mcpServers'], {'user': 'private'})
        again = reconcile(detached['content'], [], [])
        self.assertEqual(again['content'], detached['content'])

    def test_matching_unknown_value_is_not_claimed(self):
        local = b'{ "permissions": {"ask": ["Bash(git push:*)"]}}\n'
        result = reconcile(local, [], [record()], allow_capabilities=True)
        self.assertEqual(result['entries'], [])
        self.assertEqual(result['content'], local)
        self.assertEqual(reconcile(local, result['entries'], [])['content'], local)

    def test_modified_hook_is_preserved_on_detach_and_conflicts_on_update(self):
        old = record('hook:guard', {'matcher': 'Bash', 'hooks': [{'command': 'old'}]})
        old['pointer'] = ['hooks', 'PreToolUse']
        new = {**old, 'value': {'matcher': 'Bash', 'hooks': [{'command': 'new'}]}}
        local = b'{"hooks":{"PreToolUse":[{"matcher":"Bash","hooks":[{"command":"user edit"}]}]}}'
        self.assertEqual(reconcile(local, [old], [])['content'], local)
        result = reconcile(local, [old], [new], allow_capabilities=True)
        self.assertTrue(result['conflicts'])
        self.assertEqual(result['content'], local)

    def test_explicit_agent_teams_opt_in_survives_template_removal(self):
        old = {'id': 'env:agent-teams', 'pointer': ['env', 'CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS'],
               'mode': 'value', 'value': '1', 'retain_on_remove': True}
        local = b'{"env":{"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS":"1"}}'
        result = reconcile(local, [old], [])
        self.assertEqual(result['content'], local)
        self.assertEqual(result['entries'], [])

    def test_malformed_configuration_and_ownership_are_rejected(self):
        for local in (b'{', b'[]', b'{"permissions":{"ask":"wrong type"}}', b'{"env":{},"env":{"lost":true}}'):
            with self.subTest(local=local), self.assertRaises(ValueError):
                reconcile(local, [], [record()], allow_capabilities=True)
        for bad in ([record(), record()], [{**record(), 'pointer': []}],
                    [{**record(), 'mode': 'value', 'value': {'full': 'settings'}}]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                reconcile(b'{}', [], bad, allow_capabilities=True)

    def test_duplicate_array_members_do_not_prove_which_one_is_owned(self):
        local = b'{"permissions":{"ask":["Bash(git push:*)","Bash(git push:*)"]}}'
        result = reconcile(local, [record()], [])
        self.assertTrue(result['conflicts'])
        self.assertEqual(result['content'], local)

    def test_native_boolean_is_not_owned_as_an_integer(self):
        old = {'id': 'option:flag', 'pointer': ['flag'], 'mode': 'value', 'value': True}
        local = b'{"flag":1}'
        result = reconcile(local, [old], [])
        self.assertEqual(result['content'], local)

    def test_source_retirement_cannot_remove_permission_boundary_without_setup_scope(self):
        local = b'{"permissions":{"ask":["Bash(git push:*)"]}}'
        blocked = reconcile(local, [record()], [])
        self.assertTrue(blocked['conflicts'])
        self.assertEqual(blocked['content'], local)
        detached = reconcile(local, [record()], [], allow_removal=True)
        self.assertFalse(detached['conflicts'])
        self.assertEqual(json.loads(detached['content'])['permissions']['ask'], [])

    def test_update_does_not_claim_matching_unowned_array_entry(self):
        local = b'{"permissions":{"ask":["old","new"]}}'
        result = reconcile(local, [record(value='old')], [record(value='new')], allow_capabilities=True)
        self.assertTrue(result['conflicts'])
        self.assertEqual(result['content'], local)

    def test_boolean_to_integer_change_updates_actual_bytes(self):
        old = {'id': 'option:flag', 'pointer': ['flag'], 'mode': 'value', 'value': True}
        new = {**old, 'value': 1}
        result = reconcile(b'{"flag":true}', [old], [new], allow_capabilities=True)
        self.assertIs(type(json.loads(result['content'])['flag']), int)
        self.assertEqual(result['entries'], [new])

    def test_non_finite_json_constants_are_malformed(self):
        for constant in ('NaN', 'Infinity', '-Infinity'):
            with self.subTest(constant=constant), self.assertRaises(ValueError):
                reconcile(('{"private":' + constant + '}').encode(), [], [])

    def test_conflict_prevents_independent_capability_write(self):
        local = b'{"permissions":{"ask":["custom changed"]}}'
        result = reconcile(local, [record()], [record(value='new'), record('permission:other', 'other')], allow_capabilities=True)
        self.assertTrue(result['conflicts'])
        self.assertEqual(result['content'], local)


if __name__ == '__main__':
    unittest.main()
