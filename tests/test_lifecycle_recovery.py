"""Operator-facing recovery guidance: detached projects, blocked rollbacks, repeated applies.

Every message is exercised through the public CLI. A printed FIX is executed
verbatim where it is a command, so a repair that does not work fails here.
"""
import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import unittest

import test_lifecycle_adopters as adopters


class RecoveryGuidanceTests(unittest.TestCase):
    setUp = adopters.LifecycleAdopterTests.setUp
    write = adopters.LifecycleAdopterTests.write
    make_source = adopters.LifecycleAdopterTests.make_source
    git = adopters.LifecycleAdopterTests.git
    commit_source = adopters.LifecycleAdopterTests.commit_source
    invoke = adopters.LifecycleAdopterTests.invoke
    plan = adopters.LifecycleAdopterTests.plan
    apply_ready = adopters.LifecycleAdopterTests.apply_ready
    snapshot = adopters.LifecycleAdopterTests.snapshot

    def check(self, *extra):
        return self.invoke('check', '--source', self.source, '--target', self.project, *extra)

    def journals(self, status=None):
        found = sorted((self.project / '.rpi/local/transactions').glob('*/journal.json'),
                       key=lambda path: json.loads(path.read_text())['sequence'])
        return [path.resolve() for path in found if status is None or json.loads(path.read_text())['status'] == status]

    def conflict(self, result):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        return json.loads(result.stdout)

    # A-1: a project that was detached on purpose is reported as detached.

    def detached_project(self):
        self.apply_ready('install', '--harness', 'claude')
        skill = self.project / '.claude/skills/rpi-plan/SKILL.md'
        skill.write_text(skill.read_text() + 'Owner line kept through detach.\n')
        self.apply_ready('detach')
        self.assertEqual(json.loads((self.project / '.rpi/manifest.json').read_text())['route'], 'detached')
        self.assertTrue(skill.is_file())
        return skill

    def test_check_reports_a_detached_project_as_detached_and_exits_zero(self):
        skill = self.detached_project()
        before = self.snapshot(include_local=True)
        for extra in ((), ('--harness', 'claude', '--route', 'direct')):  # The second form is the launcher's.
            with self.subTest(extra=extra):
                result = self.check(*extra)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                summary = json.loads(result.stdout)
                self.assertEqual(summary['status'], 'detached')
                self.assertEqual(summary['conflicts'], [])
                self.assertNotIn('fix', summary)
                self.assertIn('retained', summary['note'])
                self.assertIn('baselines', summary['note'])
                self.assertIn('plan --source', summary['note'])
                self.assertIn('--action install', summary['note'])
                self.assertIn('appear in that plan as conflicts to reconcile', summary['note'])
                self.assertEqual(result.stderr, '')
                self.assertEqual(self.snapshot(include_local=True), before, 'check is read-only')
        self.assertIn('Owner line kept', skill.read_text())

    def test_the_detached_note_names_a_reinstall_that_plans(self):
        self.detached_project()
        note = json.loads(self.check().stdout)['note']
        argv = shlex.split(note.split('create a reviewable plan with ', 1)[1].split(', review it', 1)[0])
        output = Path(argv[-1])
        self.assertEqual(argv[argv.index('--action') + 1], 'install')
        self.assertFalse(output.exists())
        result = subprocess.run(argv, capture_output=True, text=True)  # The printed command, verbatim.
        self.assertIn(result.returncode, (0, 2), result.stdout + result.stderr)
        self.assertTrue(output.is_file(), 'the printed re-install request produces a reviewable plan')

    def test_a_half_detached_project_is_still_action_needed_with_a_different_fix(self):
        self.apply_ready('install', '--harness', 'claude')
        manifest_path = self.project / '.rpi/manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest.update({'route': 'detached', 'harnesses': [], 'installations': {}})
        self.assertTrue(manifest['entries'], 'owned entries remain after the interrupted detach')
        manifest_path.write_text(json.dumps(manifest))
        result = self.check()
        summary = self.conflict(result)
        self.assertEqual(summary['status'], 'action-needed')
        self.assertNotRegex(summary['fix'], r'rpi-distribution\.py check')
        self.assertIn('--action detach', summary['fix'])
        self.assertIn('apply --plan', summary['fix'])

    def test_a_detached_project_with_an_unfinished_transaction_is_not_reported_detached(self):
        self.detached_project()
        journal = self.journals('complete')[-1]
        value = json.loads(journal.read_text())
        value['status'] = 'applying'
        journal.write_text(json.dumps(value))
        summary = self.conflict(self.check())
        self.assertEqual(summary['status'], 'action-needed')
        self.assertIn('an apply stopped before completing', summary['fix'])
        self.assertIn('rollback --journal', summary['fix'])

    def test_a_project_that_was_never_installed_keeps_its_existing_check_result(self):
        result = self.check()
        summary = self.conflict(result)
        self.assertEqual(summary['status'], 'action-needed')

    # A-2: a blocked rollback tells the owner how to keep their edit and proceed.

    def interrupted(self, action):
        before = self.snapshot()
        plan, path = self.plan(action)
        self.assertEqual(self.invoke('apply', '--plan', path, '--fail-after', '1').returncode, 2)
        operation = plan['operations'][0]
        self.assertEqual(operation['root_id'], 'project')
        return before, operation['destination'], self.journals('applying')[-1]

    def follow(self, fix):
        self.assertEqual(fix.count('; run: '), 1, fix)
        return subprocess.run(fix.split('; run: ', 1)[1], shell=True, capture_output=True, text=True, cwd=self.workspace)

    def saved_edits(self, destination):
        return sorted((self.project / '.rpi/local/saved-edits').glob('*/*/project/' + destination))

    def test_owner_edit_over_an_interrupted_update_is_kept_and_rollback_proceeds(self):
        self.apply_ready()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        before, destination, journal = self.interrupted('update')
        target = self.project / destination
        target.write_bytes(target.read_bytes() + b'Owner edit made after the interruption.\n')
        edited = target.read_bytes()
        frozen = self.snapshot(include_local=True)
        summary = self.conflict(self.invoke('rollback', '--journal', journal))
        self.assertEqual(self.snapshot(include_local=True), frozen, 'a refused rollback writes nothing')
        self.assertIn(destination, summary['reason'])
        fix = summary['fix']
        self.assertIn(destination, fix)
        self.assertNotRegex(fix, r'rpi-distribution\.py check')
        self.assertNotIn('Inspect the local plan/journal conflicts', fix)
        self.assertTrue(fix.endswith(shlex.join([sys.executable, str(adopters.ENGINE),
                                                         'rollback', '--journal', str(journal)])), fix)
        followed = self.follow(fix)
        self.assertEqual(followed.returncode, 0, followed.stdout + followed.stderr)
        self.assertEqual(self.snapshot(), before, 'the tree matches the pre-update state')
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')
        saved = self.saved_edits(destination)
        self.assertEqual([path.read_bytes() for path in saved], [edited], 'the owner edit is intact')
        # Following the same instructions again is harmless and never overwrites the saved edit.
        again = self.follow(fix)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual([path.read_bytes() for path in self.saved_edits(destination)], [edited])
        self.assertEqual(self.snapshot(), before)

    def test_owner_edit_of_a_file_the_transaction_created_is_moved_aside(self):
        before, destination, journal = self.interrupted('install')
        target = self.project / destination
        self.assertTrue(target.is_file())
        target.write_bytes(target.read_bytes() + b'Owner note on a file the install created.\n')
        edited = target.read_bytes()
        summary = self.conflict(self.invoke('rollback', '--journal', journal))
        self.assertIn(destination, summary['fix'])
        followed = self.follow(summary['fix'])
        self.assertEqual(followed.returncode, 0, followed.stdout + followed.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual([path.read_bytes() for path in self.saved_edits(destination)], [edited])

    def test_every_edited_file_is_named_not_only_the_first(self):
        self.apply_ready()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        plan, path = self.plan('update')
        projects = [op['destination'] for op in plan['operations'] if op['root_id'] == 'project']
        self.assertGreaterEqual(len(projects), 2, projects)
        self.assertEqual(self.invoke('apply', '--plan', path, '--fail-after', str(len(projects))).returncode, 2)
        for destination in projects:
            (self.project / destination).write_bytes(b'Owner replaced ' + destination.encode() + b'\n')
        summary = self.conflict(self.invoke('rollback', '--journal', self.journals('applying')[-1]))
        for destination in projects:
            self.assertIn(destination, summary['reason'])
            self.assertIn(destination, summary['fix'])

    # A-4: repeating an apply explains what happened.

    def test_repeating_an_applied_plan_says_it_was_applied_and_needs_nothing(self):
        _, path = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        journal = self.journals('complete')[-1]
        frozen = self.snapshot(include_local=True)
        result = self.invoke('apply', '--plan', path)
        summary = self.conflict(result)  # The exit code of this refusal is unchanged.
        self.assertIn('already applied', summary['reason'])
        self.assertIn(str(journal), summary['reason'])
        self.assertNotIn('create a new plan', summary['reason'])
        self.assertIn('nothing needs doing', summary['reason'])
        self.assertIn('no action is needed', summary['fix'])
        self.assertIn('rpi-distribution.py check', summary['fix'])
        self.assertEqual(self.snapshot(include_local=True), frozen)

    def test_repeating_a_superseded_plan_names_the_journal_and_the_later_work(self):
        _, first = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', first).returncode, 0)
        first_journal = self.journals('complete')[-1]
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        self.apply_ready('update')
        summary = self.conflict(self.invoke('apply', '--plan', first))
        self.assertIn('already applied', summary['reason'])
        self.assertIn(str(first_journal), summary['reason'])
        self.assertIn('later', summary['reason'])
        self.assertNotIn('nothing needs doing', summary['reason'])
        self.assertIn('check', summary['fix'])

    def test_a_plan_that_was_never_applied_keeps_the_stale_plan_message(self):
        self.apply_ready()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        _, stale = self.plan('update')
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'A second upstream change.\n')
        summary = self.conflict(self.invoke('apply', '--plan', stale))
        self.assertIn('plan changed or source/installation preimages changed; create a new plan', summary['reason'])
        self.assertNotIn('already applied', summary['reason'])

    def test_lock_held_message_says_to_check_and_replan_instead_of_retrying(self):
        _, path = self.plan()
        local = self.project / '.rpi/local'
        local.mkdir(parents=True)
        descriptor = os.open(local / 'lock', os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        summary = self.conflict(self.invoke('apply', '--plan', path))
        self.assertIn('actively locked', summary['reason'])
        self.assertIn('wait', summary['reason'])
        self.assertNotIn('then retry', summary['reason'])
        self.assertIn('run check', summary['reason'])
        self.assertIn('create a new plan', summary['reason'])
        self.assertIn('rpi-distribution.py check', summary['fix'])
        self.assertIn('--target', summary['fix'])


if __name__ == '__main__':
    unittest.main()
