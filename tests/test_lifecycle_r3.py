"""Round three review findings on the lifecycle engine (WB2R3-L-1 to WB2R3-L-7).

Every printed repair is executed verbatim; owner data must survive each of them.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import unittest

import test_lifecycle_adopters as adopters
import test_lifecycle_wb2 as wb2


class R3Base(wb2.Wb2Base):
    pass


class LockCauseTests(R3Base):
    # WB2R3-L-1: the repair matches the cause.

    def test_a_directory_that_is_not_writable_gets_a_chmod_never_a_move_of_a_lock_that_does_not_exist(self):
        module = wb2.engine_module('rpi-lifecycle')
        self.project = self.project.resolve()
        local = self.project / '.rpi/local'
        local.mkdir(parents=True)
        local.chmod(0o555)
        self.addCleanup(local.chmod, 0o755)
        if os.access(local, os.W_OK):
            self.skipTest('a privileged user can write a read-only directory')
        with self.assertRaises(module.Conflict) as caught:
            module.acquire_lock(str(self.project / '.rpi'))
        error = caught.exception
        self.assertIn('Permission denied', str(error))
        self.assertIn('chmod u+wx', error.fix)
        self.assertIn(str(local), error.fix)
        self.assertNotIn('mv --', error.fix)
        self.assertIn('nothing to move aside', error.fix)
        self.shell(error.fix.split('make it writable with ', 1)[1].split(' (set it back', 1)[0])
        os.close(module.acquire_lock(str(self.project / '.rpi')))

    def test_an_apply_into_a_read_only_state_directory_is_refused_and_its_repair_works(self):
        _, path = self.plan('install', '--harness', 'claude')
        local = self.project / '.rpi/local'
        local.mkdir(parents=True)
        local.chmod(0o555)
        self.addCleanup(local.chmod, 0o755)
        if os.access(local, os.W_OK):
            self.skipTest('a privileged user can write a read-only directory')
        refused = self.conflict(self.invoke('apply', '--plan', path))
        self.assertNotIn('mv --', refused['fix'])
        self.assertFalse((self.project / '.claude').exists(), 'nothing was written')
        # A fresh plan reports the directory at plan time, with the same chmod.
        result, summary, _ = self.plan_json('--harness', 'claude', '--route', 'direct')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        item = next(c for c in summary['conflicts'] if c['reason'].startswith('not writable: '))
        self.assertIn(str(local.resolve()), item['reason'])
        self.shell(item['fix'].split('make the directory writable with ', 1)[1].split(' (it is mode', 1)[0])
        _, replanned, path = self.replan_from(summary['fix'])
        self.assertEqual(replanned['status'], 'ready', replanned.get('conflicts'))
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)

    def test_a_lock_that_occupies_the_path_still_gets_the_move_aside(self):
        _, path = self.plan('install', '--harness', 'claude')
        (self.project / '.rpi/local').mkdir(parents=True)
        (self.project / '.rpi/local/lock').mkdir()
        summary = self.conflict(self.invoke('apply', '--plan', path))
        self.assertIn('then set the lock file aside with mv --', summary['fix'])

    def test_a_missing_state_root_under_a_read_only_parent_is_a_plan_time_conflict(self):
        # WB2R3-L-6: the nearest existing directory is checked even above a root that does not exist yet.
        parent = self.workspace / 'read-only-parent'
        parent.mkdir()
        parent.chmod(0o555)
        self.addCleanup(parent.chmod, 0o755)
        if os.access(parent, os.W_OK):
            self.skipTest('a privileged user can write a read-only directory')
        output = self.plans / 'user-ro.json'
        result = subprocess.run([sys.executable, str(adopters.ENGINE), 'plan', '--source', self.source, '--scope', 'user', '--harness', 'claude',
                                 '--route', 'direct', '--action', 'install', '--state-root', parent / 'deep/er/state',
                                 '--claude-skill-root', self.workspace / 'writable-skills', '--codex-skill-root', self.workspace / 'writable-agents',
                                 '--output', output], capture_output=True, text=True,
                                env={**os.environ, 'CLAUDE_CONFIG_DIR': str(self.workspace / 'user-claude')})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        items = [c for c in json.loads(result.stdout)['conflicts'] if c['reason'].startswith('not writable: ')]
        self.assertEqual([c['reason'].split(' (mode')[0] for c in items], ['not writable: ' + str(parent.resolve())])
        self.shell(items[0]['fix'].split('make the directory writable with ', 1)[1].split(' (it is mode', 1)[0])


class OwnerSettingsTests(R3Base):
    # WB2R3-L-2: record what the install created; prune only that; never delete or drop owner content.

    ENTRIES = wb2.SettingsSkeletonTests.ENTRIES

    def add_policy_component(self, entries):
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        self.write(self.source, 'templates/adapters/policy.json', json.dumps({'schema_version': 1, 'entries': entries}))
        if not any(component['id'] == 'config:policy' for component in manifest['components']):
            manifest['components'].append({'id': 'config:policy', 'kind': 'config', 'scope': 'project',
                'selection': 'default', 'harnesses': ['claude'], 'dependencies': [],
                'source': 'templates/adapters/policy.json', 'outputs': {'claude': 'configuration/policy.json'},
                'destinations': {'claude': '.claude/settings.json'}, 'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'}})
            manifest_path.write_text(json.dumps(manifest))

    def settings(self):
        return self.project / '.claude/settings.json'

    def install_and_detach(self, owner_text):
        self.add_policy_component(self.ENTRIES)
        path = self.settings()
        if owner_text is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(owner_text)
        self.apply_ready('install', '--harness', 'claude', '--allow-capabilities', 'config:policy')
        self.assertIn('Bash(git push:*)', path.read_text())
        self.apply_ready('detach')
        return path

    def test_an_owner_settings_file_with_only_empty_containers_is_never_deleted_or_emptied_further(self):
        for owner in ('{}', '{"permissions": {"ask": []}}', '{"hooks": {}}', '{"permissions": {"ask": [], "deny": []}, "hooks": {"PreToolUse": []}}'):
            with self.subTest(owner=owner):
                shutil.rmtree(self.project)
                self.project.mkdir()
                path = self.install_and_detach(owner)
                self.assertTrue(path.is_file(), 'the owner file survives detach')
                self.assertEqual(json.loads(path.read_text()), json.loads(owner))

    def test_the_owners_own_empty_array_is_kept_next_to_the_entries_the_install_added(self):
        owner = {'permissions': {'deny': ['Read(private/**)'], 'ask': []}, 'model': 'opus'}
        path = self.install_and_detach(json.dumps(owner, indent=2) + '\n')
        self.assertEqual(json.loads(path.read_text()), owner)
        self.assertEqual(path.read_text(), json.dumps(owner, indent=2) + '\n', 'the owner indentation survives')

    def test_the_manifest_records_what_the_install_created_and_detach_uses_only_that(self):
        self.add_policy_component(self.ENTRIES)
        self.apply_ready('install', '--harness', 'claude', '--allow-capabilities', 'config:policy')
        entries = [e for e in json.loads((self.project / '.rpi/manifest.json').read_text())['entries'] if 'config_record' in e]
        self.assertTrue(all(e['created']['file'] for e in entries), entries)
        self.assertIn(['permissions', 'ask'], [c for e in entries for c in e['created']['containers']])
        self.apply_ready('detach')
        self.assertFalse(self.settings().exists())

    def test_a_file_the_owner_had_is_not_marked_created_and_one_the_install_made_is(self):
        self.add_policy_component(self.ENTRIES)
        self.settings().parent.mkdir()
        self.settings().write_text('{"model": "opus"}\n')
        self.apply_ready('install', '--harness', 'claude', '--allow-capabilities', 'config:policy')
        entries = [e for e in json.loads((self.project / '.rpi/manifest.json').read_text())['entries'] if 'config_record' in e]
        self.assertFalse(any((e.get('created') or {}).get('file') for e in entries))

    def test_an_installation_recorded_without_creation_data_prunes_and_deletes_nothing(self):
        self.add_policy_component(self.ENTRIES)
        self.apply_ready('install', '--harness', 'claude', '--allow-capabilities', 'config:policy')
        manifest_path = self.project / '.rpi/manifest.json'
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest['entries']:
            entry.pop('created', None)  # An installation recorded before creation was tracked.
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        self.apply_ready('detach')
        remaining = json.loads(self.settings().read_text())
        self.assertNotIn('Bash(git push:*)', json.dumps(remaining))
        self.assertTrue(self.settings().is_file(), 'owner-or-unknown files are never deleted')

    def test_an_update_that_retires_one_record_prunes_only_what_that_record_created(self):
        self.add_policy_component(self.ENTRIES)
        self.apply_ready('install', '--harness', 'claude', '--allow-capabilities', 'config:policy')
        self.add_policy_component([self.ENTRIES[0], self.ENTRIES[2]])  # The deny record is retired.
        self.apply_ready('update', '--harness', 'claude', '--allow-capabilities', 'config:policy')
        document = json.loads(self.settings().read_text())
        self.assertNotIn('deny', document['permissions'])
        self.assertEqual(document['permissions']['ask'], ['Bash(git push:*)'])
        self.apply_ready('detach')
        self.assertFalse(self.settings().exists())


class ForeignInstalledCopyTests(R3Base):
    # WB2R3-L-4

    def installed_copy(self):
        """What an installed project carries under .rpi: scripts, adapters and the packaged manifest, but no source checkout."""
        shutil.copytree(adopters.ROOT / 'generated/claude/.rpi', self.project / '.rpi', dirs_exist_ok=True)
        return self.project / '.rpi/scripts/rpi-distribution.py'

    def diagnose(self, engine, **environment):
        result = subprocess.run([sys.executable, str(engine), 'diagnose', '--target', str(self.project)], capture_output=True, text=True,
                                env={**os.environ, 'CLAUDE_CONFIG_DIR': str(self.workspace / 'user-claude'), **environment})
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def duplicates(self, report):
        return [i for i in report['config_issues'] if i.get('id') == 'duplicate-registration']

    def test_an_owner_skill_is_not_counted_when_diagnose_runs_from_the_installed_copy(self):
        self.apply_ready('install', '--harness', 'claude', '--route', 'plugin')
        engine = self.installed_copy()
        mine = self.project / '.claude/skills/rpi-mine/SKILL.md'
        mine.parent.mkdir(parents=True)
        mine.write_text('---\nname: rpi-mine\ndescription: mine\n---\nOwner skill.\n')
        report = self.diagnose(engine)
        self.assertEqual(report['installation']['source'], {'status': 'invalid source or missing declared resources'}, 'no source checkout here')
        self.assertEqual(self.duplicates(report), [])

    def test_a_direct_skill_the_installation_recorded_is_still_found_without_a_source(self):
        self.apply_ready('install', '--harness', 'claude', '--route', 'direct')
        engine = self.installed_copy()
        user = self.workspace / 'user-claude'
        user.mkdir()
        (user / 'settings.json').write_text(json.dumps({'enabledPlugins': {'cc-rpi@market': True}}))
        report = self.diagnose(engine)
        self.assertEqual(len(self.duplicates(report)), 1)


class MessageTests(R3Base):
    # WB2R3-L-7

    def test_a_running_rollback_is_called_a_rollback_and_a_running_apply_keeps_its_wording(self):
        self.apply_ready('install', '--harness', 'claude')
        journal = self.journals('complete')[-1]
        value = json.loads(journal.read_text())
        descriptor = os.open(self.project / '.rpi/local/lock', os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        value['rollback_in_progress'] = True
        journal.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
        fix = self.conflict(self.check())['fix']
        self.assertIn('a running rollback holds the lock', fix)
        self.assertNotIn('a transaction that completes is healthy', fix)
        value.pop('rollback_in_progress')
        value['status'] = 'applying'  # An apply that is still running.
        journal.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
        fix = self.conflict(self.check())['fix']
        self.assertIn('a transaction that completes is healthy', fix)

    def test_an_apply_after_a_file_replaced_the_local_directory_gets_a_concrete_repair_that_works(self):
        _, path = self.plan('install', '--harness', 'claude')
        (self.project / '.rpi').mkdir()
        (self.project / '.rpi/local').write_text('x\n')
        summary = self.conflict(self.invoke('apply', '--plan', path))
        self.assertIn('non-directory parent', summary['reason'])
        self.assertNotIn('Inspect the local plan', summary['fix'])
        command = re.search(r'by running (mv -- .*?), then re-plan', summary['fix']).group(1)
        self.shell(command)
        self.shell(summary['fix'].split('then run the same apply again: ', 1)[1])
        self.assertTrue((self.project / '.claude/skills/rpi-plan/SKILL.md').is_file())
        self.assertEqual([p.read_text() for p in (self.project / '.rpi').glob('local.saved.*')], ['x\n'])

    def test_an_input_the_engine_did_not_expect_prints_an_accurate_why_and_a_runnable_traceback_command(self):
        broken = self.plans / 'broken.json'
        broken.write_text(json.dumps({'schema_version': 1, 'request': {'source': str(self.source), 'target': str(self.project)}}))
        result = self.invoke('apply', '--plan', broken)
        self.assertEqual(result.returncode, 1, result.stderr)
        why = result.stderr.split('BLOCKED / WHY: ', 1)[1].split(' / FIX:', 1)[0]
        self.assertRegex(why, r"unexpected KeyError 'scope' at rpi-lifecycle\.py:\d+ in \w+")
        self.assertNotIn('correct the input named above', result.stderr)
        self.assertIn('RPI_TRACEBACK=1', result.stderr)
        command = result.stderr.split('with: ', 1)[1].strip()
        traced = subprocess.run(command, shell=True, capture_output=True, text=True, env={**os.environ, 'CLAUDE_CONFIG_DIR': str(self.workspace / 'x')})
        self.assertIn('Traceback (most recent call last)', traced.stderr)
        self.assertIn('KeyError', traced.stderr)

    def test_many_conflicts_give_a_bounded_fix_that_keeps_every_kind(self):
        module = wb2.engine_module('rpi-lifecycle')
        request = {'source': str(self.source), 'target': str(self.project), 'harnesses': ['claude'], 'scope': 'project', 'action': 'update'}
        conflicts = ([{'destination': 'a/%d.md' % n, 'reason': 'not a regular file: /x/a/%d.md' % n, 'fix': 'move it aside with ' + 'mv -- x y ' * 20, 'component_id': 'c'}
                      for n in range(12)] +
                     [{'destination': 'b/%d.md' % n, 'reason': 'unproven symlink destination; preserve entry and target', 'fix': 'move the link aside ' * 5}
                      for n in range(11)] +
                     [{'destination': 'AGENTS.md', 'reason': 'duplicate or incomplete managed instruction markers: policy'}])
        fix = module.conflict_fix(request, conflicts, Path('/p/plan.json'), Path('/p/next.json'))
        self.assertLess(len(fix), 6000, len(fix))
        for kind in ('a/0.md', 'b/0.md', 'AGENTS.md'):
            self.assertIn(kind, fix)
        self.assertIn('more conflicts of the kinds above', fix)
        self.assertIn('/p/plan.json', fix)
        self.assertEqual(fix.count('; then create a new plan with '), 1)
        few = module.conflict_fix(request, conflicts[:3], Path('/p/plan.json'), Path('/p/next.json'))
        self.assertNotIn('more conflicts', few)

    def test_a_new_plan_name_drops_a_counter_suffix_with_the_time_stamps(self):
        module = wb2.engine_module('rpi-lifecycle')
        for stem in ('update-20261109-101010-2', 'update-20261109-101010-20261109-101011-3'):
            name = module.next_plan_output(self.project / '.rpi', 'update', self.plans / (stem + '.json')).name
            self.assertRegex(name, r'^update-\d{8}-\d{6}\.json$', name)

    def test_saved_copies_never_reuse_a_name_within_the_same_second(self):
        module = wb2.engine_module('rpi-lifecycle')
        self.project = self.project.resolve()
        roots = {'project': str(self.project)}
        state = str(self.project / '.rpi')
        target = self.project / 'notes.md'
        commands = [module.move_aside_command(state, roots, 'project', 'notes.md')]
        for command in commands:
            for number in range(3):
                target.write_text('owner version %d\n' % number)
                self.shell(command)
        saved = sorted(p.read_text() for p in (self.project / '.rpi/local/saved-edits/plan/project').glob('notes.md.*'))
        self.assertEqual(saved, ['owner version 0\n', 'owner version 1\n', 'owner version 2\n'])
        link = self.project / 'linked'
        for number in range(2):
            link.symlink_to(self.outside)
            self.shell(module.replace_link_command(link))
            link.unlink(missing_ok=True)
        self.assertEqual(len(list(self.project.glob('linked.saved.*'))), 2)

    def test_overlapping_edit_restore_never_overwrites_an_earlier_saved_copy(self):
        self.apply_ready('install', '--harness', 'claude')
        installed = self.project / '.claude/skills/rpi-plan/references/playbook.md'
        original = installed.read_text()
        installed.write_text(original.replace('Required', 'Owner'))
        source = self.source / 'templates/skills/rpi-plan/references/playbook.md'
        source.write_text(source.read_text().replace('Required', 'Upstream'))
        _, summary, _ = self.plan_json('--harness', 'claude', '--action', 'update')
        item = next(c for c in summary['conflicts'] if c['destination'].endswith('playbook.md'))
        self.shell(item['restore_command'])
        installed.write_text(original.replace('Required', 'Second owner edit'))
        self.shell(item['restore_command'])
        saved = sorted(p.read_text() for p in (self.project / '.rpi/local/saved-edits/plan/project').rglob('playbook.md.*'))
        self.assertEqual(len(saved), 2, saved)
        self.assertTrue(any('Owner' in text for text in saved) and any('Second owner edit' in text for text in saved), saved)

    def test_a_rollback_cut_off_before_its_directory_cleanup_is_finishable(self):
        # The created directories go before the status is written: a kill in between leaves a marker, not a rolled-back journal.
        self.apply_ready('install', '--harness', 'claude')
        journal = self.journals('complete')[-1]
        module = wb2.engine_module('rpi-lifecycle')

        def killed(*arguments):
            raise KeyboardInterrupt('killed during directory cleanup')
        from unittest import mock
        with mock.patch.object(module, 'remove_created_directories', killed):
            with self.assertRaises(KeyboardInterrupt):
                module.rollback(journal)
        value = json.loads(journal.read_text())
        self.assertEqual((value['status'], value.get('rollback_in_progress')), ('complete', True))
        fix = self.conflict(self.check())['fix']
        self.assertIn('a rollback stopped before completing', fix)
        self.shell(fix.split('finish it with ', 1)[1].rsplit(', then create a new plan', 1)[0])
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')
        self.assertFalse((self.project / '.claude').exists(), 'the directories the install created are gone')


if __name__ == '__main__':
    unittest.main()
