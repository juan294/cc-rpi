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
        # Without a record of what the install created (an older installation) nothing is pruned or deleted.
        self.assertEqual(json.loads(detached['content']), {'permissions': {'ask': []}})
        # WB2R3-L-2: with the record, the containers the install created go, and so does a file it created that is now empty.
        made = {'permission:publish': [['permissions'], ['permissions', 'ask']]}
        recorded = reconcile(local, [record()], [], allow_removal=True, created=made, file_created=True)
        self.assertIsNone(recorded['content'])
        owner_file = reconcile(local, [record()], [], allow_removal=True, created=made, file_created=False)
        self.assertEqual(json.loads(owner_file['content']), {}, 'a file the owner had is never deleted')

    def test_removing_an_owned_entry_prunes_only_the_containers_the_install_created(self):
        owned = record()
        both = {'permission:publish': [['permissions'], ['permissions', 'ask']]}
        ask_only = {'permission:publish': [['permissions', 'ask']]}
        cases = [(b'{"model":"x","permissions":{"ask":["Bash(git push:*)"]}}', both, {'model': 'x'}),
                 (b'{"permissions":{"ask":["Bash(git push:*)","mine"]}}', both, {'permissions': {'ask': ['mine']}}),
                 (b'{"permissions":{"ask":["Bash(git push:*)"],"deny":["Read(.env)"]}}', both, {'permissions': {'deny': ['Read(.env)']}}),
                 # The owner's own empty containers are not the install's to remove.
                 (b'{"permissions":{"ask":["Bash(git push:*)"],"deny":[]}}', both, {'permissions': {'deny': []}}),
                 (b'{"permissions":{"ask":["Bash(git push:*)"]}}', ask_only, {'permissions': {}}),
                 (b'{"permissions":{"ask":["Bash(git push:*)"]}}', {}, {'permissions': {'ask': []}})]
        for local, made, expected in cases:
            with self.subTest(local=local, made=made):
                result = reconcile(local, [owned], [], allow_removal=True, created=made)
                self.assertEqual(json.loads(result['content']), expected)
        scalar = {'id': 'option:flag', 'pointer': ['env', 'deep', 'flag'], 'mode': 'value', 'value': True}
        made = {'option:flag': [['env'], ['env', 'deep']]}
        self.assertEqual(json.loads(reconcile(b'{"model":"x","env":{"deep":{"flag":true}}}', [scalar], [], allow_removal=True, created=made)['content']), {'model': 'x'})
        self.assertEqual(json.loads(reconcile(b'{"env":{"deep":{"flag":true,"other":1}}}', [scalar], [], allow_removal=True, created=made)['content']),
                         {'env': {'deep': {'other': 1}}})
        self.assertIsNone(reconcile(b'{"env":{"deep":{"flag":true}}}', [scalar], [], allow_removal=True, created=made, file_created=True)['content'])
        # An owner file with nothing to remove is left exactly as it was, whatever was recorded.
        untouched = b'{"permissions":{"ask":[]}}'
        self.assertEqual(reconcile(untouched, [], [], allow_removal=True, created=both, file_created=True)['content'], untouched)

    def test_adding_an_owned_entry_reports_the_containers_it_created(self):
        added = reconcile(b'{"permissions":{"deny":[]}}', [], [record()], allow_capabilities=True)
        self.assertEqual(added['created'], {'permission:publish': [['permissions', 'ask']]})
        fresh = reconcile(None, [], [record()], allow_capabilities=True)
        self.assertEqual(fresh['created'], {'permission:publish': [['permissions'], ['permissions', 'ask']]})
        existing = reconcile(b'{"permissions":{"ask":["mine"]}}', [], [record()], allow_capabilities=True)
        self.assertEqual(existing['created'], {})
        scalar = {'id': 'option:flag', 'pointer': ['env', 'deep', 'flag'], 'mode': 'value', 'value': True}
        self.assertEqual(reconcile(b'{"env":{}}', [], [scalar], allow_capabilities=True)['created'], {'option:flag': [['env', 'deep']]})

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


    def hook(self, command, **extra):
        value = {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': command, **extra}]}
        return {'id': 'hook:guard', 'pointer': ['hooks', 'PreToolUse'], 'mode': 'entry', 'value': value}

    def test_owner_applied_new_template_value_is_accepted_without_duplication(self):
        old, new = self.hook('old'), self.hook('new')
        local = json.dumps({'hooks': {'PreToolUse': [{'matcher': 'Write'}, new['value']]}}).encode()
        result = reconcile(local, [old], [new])
        self.assertEqual(result['conflicts'], [])
        self.assertEqual(result['entries'], [new])
        self.assertEqual(result['content'], local)
        doubled = json.dumps({'hooks': {'PreToolUse': [new['value'], new['value']]}}).encode()
        self.assertTrue(reconcile(doubled, [old], [new], allow_capabilities=True)['conflicts'])

    def test_both_changed_conflict_carries_previous_and_desired_values(self):
        old, new = self.hook('old'), self.hook('new')
        local = json.dumps({'hooks': {'PreToolUse': [self.hook('old', timeout=20)['value']]}}).encode()
        result = reconcile(local, [old], [new], allow_capabilities=True)
        self.assertEqual(result['content'], local)
        self.assertEqual(result['conflicts'], [{'id': 'hook:guard', 'reason': 'local and template both changed an owned entry',
                                                'previous': old['value'], 'desired': new['value'],
                                                'current': self.hook('old', timeout=20)['value']}])

    def test_both_changed_conflict_names_current_value_only_when_identifiable(self):
        scalar = {'id': 'flag', 'pointer': ['flag'], 'mode': 'value', 'value': 'old'}
        result = reconcile(b'{"flag":"owner"}', [scalar], [dict(scalar, value='new')], allow_capabilities=True)
        self.assertEqual(result['conflicts'][0]['current'], 'owner')
        old, new = self.hook('old'), self.hook('new')
        twins = [self.hook('old', timeout=20)['value'], self.hook('old', timeout=30)['value']]
        ambiguous = reconcile(json.dumps({'hooks': {'PreToolUse': twins}}).encode(), [old], [new], allow_capabilities=True)
        self.assertNotIn('current', ambiguous['conflicts'][0])

    def test_removal_conflict_carries_the_boundary_value(self):
        blocked = reconcile(b'{"permissions":{"ask":["Bash(git push:*)"]}}', [record()], [])
        self.assertEqual(blocked['conflicts'][0]['previous'], 'Bash(git push:*)')

    def test_edited_owned_boundary_is_retained_with_its_record_and_value(self):
        deny = {'id': 'deny-env', 'pointer': ['permissions', 'deny'], 'mode': 'entry', 'value': 'Read(.env)'}
        result = reconcile(b'{"permissions":{"deny":["Read(.env.example)"]}}', [deny], [deny])
        self.assertEqual(result['conflicts'], [])
        self.assertEqual([(item['id'], item['value']) for item in result['retained']], [('deny-env', 'Read(.env)')])
        self.assertIn('not in effect', result['retained'][0]['reason'])


if __name__ == '__main__':
    unittest.main()
