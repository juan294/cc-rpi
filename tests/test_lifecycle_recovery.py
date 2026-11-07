"""Operator-facing recovery guidance: detached projects, blocked rollbacks, repeated applies.

Every message is exercised through the public CLI. A printed FIX is executed
verbatim where it is a command, so a repair that does not work fails here.
"""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import unittest

import test_lifecycle_adopters as adopters


def adopters_module(name):
    spec = importlib.util.spec_from_file_location('recovery_' + name.replace('-', '_'), adopters.ENGINE.with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def test_check_after_a_full_rollback_of_a_fresh_install_says_install(self):
        self.apply_ready()
        for journal in reversed(self.journals('complete')):
            self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        summary = self.conflict(self.check())
        self.assertIn('--action install', summary['fix'])
        self.assertNotIn('--action update', summary['fix'])
        self.assertIn('create the install plan', summary['fix'])
        # An installed project keeps the update wording.
        self.apply_ready()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        drift = self.conflict(self.check())
        self.assertIn('--action update', drift['fix'])

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

    def follow(self, fix, cwd=None):
        self.assertEqual(fix.count('; run: '), 1, fix)
        return subprocess.run(fix.split('; run: ', 1)[1], shell=True, capture_output=True, text=True, cwd=cwd or self.workspace)

    @staticmethod
    def owner_edit(target):
        target.write_bytes(target.read_bytes() + b'Owner edit.\n')

    def saved_edits(self, destination):
        return sorted((self.project / '.rpi/local/saved-edits').glob('*/*/project/' + destination + '*'))

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
        # The journal is rolled back, so a second run refuses and changes nothing.
        self.assertNotEqual(again.returncode, 0)
        self.assertIn('already rolled back', again.stderr)
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

    def blocked_update(self):
        self.apply_ready()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        before, destination, journal = self.interrupted('update')
        return before, destination, journal, self.project / destination

    def refused(self, journal):
        return self.conflict(self.invoke('rollback', '--journal', journal))['fix']

    def test_a_symlink_edit_is_set_aside_and_never_written_through(self):
        before, destination, journal, target = self.blocked_update()
        outside = self.workspace / 'outside-owner-file.txt'
        outside.write_bytes(b'Outside the project; must never change.\n')
        target.unlink()
        target.symlink_to(outside)
        frozen = self.snapshot(include_local=True)
        fix = self.refused(journal)
        self.assertEqual(self.snapshot(include_local=True), frozen)
        followed = self.follow(fix)
        self.assertEqual(followed.returncode, 0, followed.stdout + followed.stderr)
        self.assertEqual(outside.read_bytes(), b'Outside the project; must never change.\n')
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(target.is_symlink())
        saved = self.saved_edits(destination)
        self.assertEqual(len(saved), 1)
        self.assertTrue(saved[0].is_symlink(), 'the saved edit is the link itself')
        self.assertEqual(Path(os.readlink(saved[0])), outside)
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')

    def test_restored_file_has_the_recorded_mode_and_replaces_the_path_atomically(self):
        before, destination, journal, target = self.blocked_update()
        recorded = json.loads(journal.read_text())['operations'][0]['before']['mode']
        self.owner_edit(target)
        target.chmod(0o600 if recorded != 0o600 else 0o644)
        followed = self.follow(self.refused(journal))
        self.assertEqual(followed.returncode, 0, followed.stdout + followed.stderr)
        self.assertEqual(target.stat().st_mode & 0o777, recorded)
        self.assertEqual(sorted(path.name for path in target.parent.iterdir() if path.name.startswith('.rpi-restore')), [])

    def test_a_second_edit_after_a_failed_rollback_never_replaces_the_first_saved_copy(self):
        before, destination, journal, target = self.blocked_update()
        target.write_bytes(target.read_bytes() + b'First owner edit.\n')
        first = target.read_bytes()
        fix = self.refused(journal)
        lock = self.project / '.rpi/local/lock'
        lock.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(lambda: os.close(descriptor) if descriptor is not None else None)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        failed = self.follow(fix)  # Saves and restores, then the rollback itself is refused by the held lock.
        self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
        self.assertEqual([path.read_bytes() for path in self.saved_edits(destination)], [first])
        target.write_bytes(target.read_bytes() + b'Second owner edit.\n')
        second = target.read_bytes()
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        stale = self.follow(fix)  # The same printed line: the path is no longer as reported, so it touches nothing.
        self.assertIn('noop', stale.stdout)
        self.assertEqual(target.read_bytes(), second)
        self.assertEqual([path.read_bytes() for path in self.saved_edits(destination)], [first])
        again = self.follow(self.refused(journal))  # A fresh fix for the new state.
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(sorted(path.read_bytes() for path in self.saved_edits(destination)), sorted([first, second]))
        self.assertEqual(self.snapshot(), before)

    def test_a_deleted_file_is_restored_without_a_failing_save_step(self):
        before, destination, journal, target = self.blocked_update()
        target.unlink()
        fix = self.refused(journal)
        self.assertIn(destination, fix)
        followed = self.follow(fix)
        self.assertEqual(followed.returncode, 0, followed.stdout + followed.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.saved_edits(destination), [])

    def test_a_directory_in_place_of_the_file_is_set_aside_with_its_own_fix(self):
        before, destination, journal, target = self.blocked_update()
        target.unlink()
        target.mkdir()
        (target / 'owner-notes.txt').write_text('Owner notes inside a directory.\n')
        frozen = self.snapshot(include_local=True)
        summary = self.conflict(self.invoke('rollback', '--journal', journal))
        self.assertEqual(self.snapshot(include_local=True), frozen)
        self.assertIn(destination, summary['reason'])
        self.assertNotIn('Inspect the local plan/journal conflicts', summary['fix'])
        followed = self.follow(summary['fix'])
        self.assertEqual(followed.returncode, 0, followed.stdout + followed.stderr)
        self.assertEqual(self.snapshot(), before)
        saved = self.saved_edits(destination)
        self.assertEqual([path.is_dir() for path in saved], [True])
        self.assertEqual((saved[0] / 'owner-notes.txt').read_text(), 'Owner notes inside a directory.\n')

    # S-3: temporary names are unique and never left behind.

    def helper(self, journal, index, live, saved, *, prelude='', expected=None):
        lifecycle = adopters_module('rpi-lifecycle')
        code = 'import os, sys\n' + prelude + '\n' + lifecycle.RESTORE_PREIMAGE
        expected = lifecycle.path_signature(live) if expected is None else expected  # What the conflict would have reported.
        return subprocess.run([sys.executable, '-c', code, str(journal), str(index), str(live), str(saved), expected],
                              capture_output=True, text=True)

    def synthetic_journal(self, before):
        path = self.workspace / 'synthetic-journal.json'
        path.write_text(json.dumps({'operations': [{'before': before}]}))
        return path

    def test_symlink_preimage_restore_survives_a_stale_temporary_name(self):
        parent = self.workspace.resolve() / 'restore-parent'
        parent.mkdir()
        live = parent / 'link'
        live.write_text('Owner file that must be kept.\n')
        (parent / 'link.rpi-restore').write_text('stale temporary name\n')
        journal = self.synthetic_journal({'kind': 'symlink', 'target': '../somewhere'})
        result = self.helper(journal, 0, live, self.workspace / 'kept/link')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(os.readlink(live), '../somewhere')
        self.assertEqual((self.workspace / 'kept/link').read_text(), 'Owner file that must be kept.\n')
        self.assertEqual((parent / 'link.rpi-restore').read_text(), 'stale temporary name\n')

    def test_a_failure_after_the_temporary_write_leaves_no_temporary_file_and_a_rerun_works(self):
        data = adopters.base64.b64encode(b'Recorded content.\n').decode()
        cases = {'file': {'kind': 'file', 'data': data, 'mode': 0o644, 'sha256': adopters.hashlib.sha256(b'Recorded content.\n').hexdigest()},
                 'symlink': {'kind': 'symlink', 'target': 'elsewhere'}}
        for kind, before in cases.items():
            with self.subTest(kind=kind):
                parent = self.workspace.resolve() / ('fail-' + kind)
                parent.mkdir()
                live = parent / 'target'
                live.write_text('Owner version.\n')
                journal = self.synthetic_journal(before)
                failing = "def boom(*a, **k):\n    raise OSError('injected failure')\nos.replace = boom"
                result = self.helper(journal, 0, live, self.workspace / ('kept-' + kind) / 'target', prelude=failing)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(sorted(path.name for path in parent.iterdir()), [], 'no temporary file is left behind')
                self.assertEqual((self.workspace / ('kept-' + kind) / 'target').read_text(), 'Owner version.\n')
                again = self.helper(journal, 0, live, self.workspace / ('kept-' + kind) / 'target')
                self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
                self.assertEqual(sorted(path.name for path in parent.iterdir()), ['target'])

    # S-5: a symlinked parent is refused with its own message.

    def test_a_symlinked_parent_directory_is_refused_with_its_own_message(self):
        before, destination, journal, target = self.blocked_update()
        parent = self.project.resolve() / Path(destination).parent
        outside = self.workspace / 'outside-dir'
        outside.mkdir()
        (outside / 'keep.txt').write_text('Outside the project.\n')
        parent.rename(parent.with_name('references-aside'))
        parent.symlink_to(outside)
        frozen = self.snapshot(include_local=True)
        summary = self.conflict(self.invoke('rollback', '--journal', journal))
        self.assertEqual(self.snapshot(include_local=True), frozen)
        self.assertIn('symlink parent', summary['reason'])
        self.assertIn(str(parent), summary['fix'])
        self.assertNotIn('Inspect the local plan/journal conflicts', summary['fix'])
        self.assertIn('rollback --journal', summary['fix'])
        self.assertEqual(sorted(path.name for path in outside.iterdir()), ['keep.txt'])

    def test_the_restore_helper_refuses_a_parent_that_became_a_symlink(self):
        outside = self.workspace.resolve() / 'outside-dir'
        outside.mkdir()
        parent = self.workspace.resolve() / 'linked-parent'
        parent.symlink_to(outside)
        journal = self.synthetic_journal({'kind': 'missing'})
        result = self.helper(journal, 0, parent / 'file', self.workspace / 'kept/file')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('symlinked parent', result.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    # S-7: hostile inputs, each executing the printed FIX.

    def run_fix_for(self, journal, cwd=None):
        return self.follow(self.refused(journal), cwd)

    def test_a_hard_link_to_an_outside_file_is_replaced_not_written_through(self):
        before, destination, journal, target = self.blocked_update()
        outside = self.workspace / 'outside-hardlink.txt'
        outside.write_bytes(b'Content of the other link.\n')
        target.unlink()
        os.link(outside, target)
        old_inode = outside.stat().st_ino
        result = self.run_fix_for(journal)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(outside.read_bytes(), b'Content of the other link.\n')
        self.assertNotEqual(target.stat().st_ino, old_inode)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.saved_edits(destination)[0].stat().st_ino, old_inode)

    def test_the_restore_replaces_the_path_instead_of_rewriting_its_inode(self):
        before, destination, journal, target = self.blocked_update()
        self.owner_edit(target)
        old_inode = target.stat().st_ino
        result = self.run_fix_for(journal)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotEqual(target.stat().st_ino, old_inode, 'the recorded content is a new file renamed into place')
        self.assertEqual(self.saved_edits(destination)[0].stat().st_ino, old_inode, 'the edit keeps its inode')

    def test_a_symlink_to_a_directory_is_set_aside(self):
        before, destination, journal, target = self.blocked_update()
        outside = self.workspace / 'outside-directory'
        outside.mkdir()
        (outside / 'inside.txt').write_text('Untouched.\n')
        target.unlink()
        target.symlink_to(outside, target_is_directory=True)
        result = self.run_fix_for(journal)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(sorted(path.name for path in outside.iterdir()), ['inside.txt'])
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.saved_edits(destination)[0].is_symlink())

    def test_a_fifo_is_set_aside(self):
        before, destination, journal, target = self.blocked_update()
        target.unlink()
        os.mkfifo(target)
        result = self.run_fix_for(journal)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(stat.S_ISFIFO(self.saved_edits(destination)[0].lstat().st_mode))

    def test_a_read_only_edit_is_replaced_with_the_recorded_mode(self):
        before, destination, journal, target = self.blocked_update()
        recorded = json.loads(journal.read_text())['operations'][0]['before']['mode']
        self.owner_edit(target)
        target.chmod(0o444)
        result = self.run_fix_for(journal)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(target.stat().st_mode & 0o777, recorded)
        self.assertEqual(self.snapshot(), before)

    def test_a_deleted_parent_directory_is_recreated(self):
        before, destination, journal, target = self.blocked_update()
        shutil.rmtree(target.parent)  # The owner's deletion of the neighbouring files is theirs; only the recorded path returns.
        result = self.run_fix_for(journal)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(target.read_bytes(), before[destination])
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')

    def test_the_fix_runs_from_any_working_directory(self):
        before, destination, journal, target = self.blocked_update()
        self.owner_edit(target)
        result = self.run_fix_for(journal, cwd='/')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_a_project_path_with_shell_metacharacters_is_handled(self):
        self.project.rmdir()
        self.project = self.workspace / 'p $HOME `touch PWNED` "q" \'s\' é ; & (x)'
        self.project.mkdir()
        before, destination, journal, target = self.blocked_update()
        self.owner_edit(target)
        result = self.run_fix_for(journal)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.workspace / 'PWNED').exists())
        self.assertFalse(Path('/PWNED').exists())

    # S-6: the plan identifier is not enough on its own.

    def test_a_plan_whose_operations_were_edited_keeping_its_identifier_is_not_reported_as_applied(self):
        plan, path = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        edited = json.loads(path.read_text())
        edited['operations'][0]['destination'] = 'elsewhere/' + edited['operations'][0]['destination']
        path.write_text(json.dumps(edited))
        summary = self.conflict(self.invoke('apply', '--plan', path))
        self.assertIn('plan changed or source/installation preimages changed', summary['reason'])
        self.assertNotIn('already applied', summary['reason'])

    def test_an_installation_that_drifted_after_apply_is_not_called_complete(self):
        _, path = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        (self.project / '.claude/skills/rpi-plan/SKILL.md').unlink()
        summary = self.conflict(self.invoke('apply', '--plan', path))
        self.assertIn('already applied', summary['reason'])
        self.assertNotIn('nothing needs doing', summary['reason'])
        self.assertIn('run check', summary['reason'])
        self.assertIn('rpi-distribution.py check', summary['fix'])
        check = self.invoke('check', '--source', self.source, '--target', self.project)
        self.assertEqual(check.returncode, 2, 'check reports the drift the apply message does not claim is absent')

    def test_the_printed_line_carries_the_restore_script_once_however_many_paths_are_blocked(self):
        self.apply_ready()
        for name in ('references/playbook.md', 'references/nested/detail.md', 'scripts/validate.py'):
            self.write(self.source, 'templates/skills/rpi-plan/' + name, 'Upstream change to ' + name + '.\n')
        before = self.snapshot()
        plan, path = self.plan('update')
        paths = [op['destination'] for op in plan['operations'] if op['root_id'] == 'project']
        self.assertGreaterEqual(len(paths), 6, paths)
        self.assertEqual(self.invoke('apply', '--plan', path, '--fail-after', str(len(paths))).returncode, 2)
        journal = self.journals('applying')[-1]
        lengths = {}
        for count in (1, len(paths)):
            for destination in paths[:count]:
                (self.project / destination).write_bytes(b'Owner edit of ' + destination.encode() + b'\n')
            lengths[count] = len(self.refused(journal))
        fix = self.refused(journal)
        self.assertEqual(fix.count('import base64'), 1, 'the script is not repeated per path')
        self.assertLess((lengths[len(paths)] - lengths[1]) / (len(paths) - 1), 700, 'only arguments are added per path')
        followed = self.follow(fix)
        self.assertEqual(followed.returncode, 0, followed.stdout + followed.stderr)
        self.assertEqual(self.snapshot(), before)
        for destination in paths:
            saved = self.saved_edits(destination)
            self.assertEqual([entry.read_bytes() for entry in saved], [b'Owner edit of ' + destination.encode() + b'\n'])

    def test_a_failure_on_one_path_stops_the_line_before_the_rollback(self):
        before, destination, journal, target = self.blocked_update()
        self.owner_edit(target)
        fix = self.refused(journal)
        line = fix.split('; run: ', 1)[1]
        failing = line.replace(shlex.quote(str(journal)), shlex.quote(str(self.workspace / 'missing-journal.json')), 1)
        self.assertNotEqual(failing, line)
        result = subprocess.run(failing, shell=True, capture_output=True, text=True, cwd=self.workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(journal.read_text())['status'], 'applying', 'the && chain stopped before the rollback')

    def test_a_finished_rollback_makes_the_printed_script_refuse_and_touch_nothing(self):
        before, destination, journal, target = self.blocked_update()
        self.owner_edit(target)
        fix = self.refused(journal)
        self.assertEqual(self.follow(fix).returncode, 0)
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')
        target.write_text('a new owner file\n')
        again = self.follow(fix)
        self.assertNotEqual(again.returncode, 0)
        self.assertIn('already rolled back', again.stderr)
        self.assertEqual(target.read_text(), 'a new owner file\n')
        self.assertEqual([path.read_bytes() for path in self.saved_edits(destination)][1:], [], 'no second copy')

    def test_the_script_only_touches_a_path_that_is_still_as_reported(self):
        before, destination, journal, target = self.blocked_update()
        self.owner_edit(target)
        fix = self.refused(journal)
        target.write_bytes(b'Edited again before the line was run.\n')
        result = self.follow(fix)
        self.assertIn('noop', result.stdout)
        self.assertEqual(target.read_bytes(), b'Edited again before the line was run.\n')
        self.assertEqual(self.saved_edits(destination), [])
        self.assertEqual(json.loads(journal.read_text())['status'], 'applying')

    def test_the_literal_run_marker_occurs_once_so_first_and_last_split_agree(self):
        before, destination, journal, target = self.blocked_update()
        self.owner_edit(target)
        fix = self.refused(journal)
        self.assertEqual(fix.count('run: '), 1, fix)
        self.assertEqual(fix.split('run: ', 1)[1], fix.rsplit('run: ', 1)[1])

    # WB-L-3: a live operation is waited for, never rolled back.

    def test_a_held_lock_means_wait_not_roll_back(self):
        self.apply_ready()
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        _, path = self.plan('update')
        self.assertEqual(self.invoke('apply', '--plan', path, '--fail-after', '1').returncode, 2)
        lock = self.project / '.rpi/local/lock'
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(lambda: os.close(descriptor) if descriptor is not None else None)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        check = self.conflict(self.check())
        self.assertEqual(check['status'], 'action-needed')
        self.assertIn('running lifecycle operation', check['active_operation'])
        self.assertNotIn('rollback --journal', check['fix'])
        self.assertIn('wait', check['fix'])
        planned, _ = self.plan('update')
        reasons = ' '.join(item['reason'] + item.get('fix', '') for item in planned['conflicts'])
        self.assertIn('locked by a running lifecycle operation', reasons)
        self.assertNotIn('rollback --journal', reasons)
        applied = self.conflict(self.invoke('apply', '--plan', path))
        self.assertIn('locked by a running lifecycle operation', applied['reason'])
        self.assertNotIn('rollback --journal', applied['fix'])
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
        descriptor = None
        released = self.conflict(self.check())
        self.assertIn('rollback --journal', released['fix'])
        self.assertNotIn('active_operation', released)

    # WB-L-5: a project moved during an unfinished apply can still be recovered.

    def moved_interrupted_project(self):
        plan, path = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', path, '--fail-after', '2').returncode, 2)
        original = self.project
        moved = self.workspace / 'moved-project'
        shutil.move(str(original), str(moved))
        self.project = moved
        return original, moved

    def test_check_and_plan_name_the_move_and_how_to_undo_it(self):
        original, moved = self.moved_interrupted_project()
        check = self.conflict(self.check())
        self.assertEqual(len(check['interrupted_transactions']), 1)
        self.assertIn(str(moved.resolve()), check['interrupted_transactions'][0])
        self.assertIn('moved while a transaction', check['fix'])
        self.assertIn(shlex.join(['mv', '--', str(moved.resolve()), str(original.resolve())]), check['fix'])
        self.assertIn('rollback --journal', check['fix'])
        self.assertNotIn(shlex.join(['rm', str(moved.resolve() / '.rpi/local/root-binding.json')]), check['fix'])
        planned, _ = self.plan()
        self.assertEqual(planned['status'], 'conflict')
        self.assertEqual(len(planned['conflicts']), 1, 'one clear conflict, not one per file')
        self.assertIn('moved while a transaction', planned['conflicts'][0]['reason'])

    def test_rollback_of_a_moved_journal_names_the_move_back_and_it_works(self):
        original, moved = self.moved_interrupted_project()
        journal = next((moved / '.rpi/local/transactions').glob('*/journal.json'))
        failed = self.conflict(self.invoke('rollback', '--journal', journal))
        fix = failed['fix']
        self.assertNotIn(shlex.join([sys.executable, str(adopters.ENGINE), 'rollback', '--journal', str(journal)]), fix, 'not the command that failed')
        self.assertIn(shlex.join(['mv', '--', str(moved.resolve()), str(original.resolve())]), fix)
        result = subprocess.run(fix.split(' (if the recorded path')[0].split('undo the transaction there: ', 1)[1], shell=True,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(original.is_dir() and not moved.exists())
        self.project = original
        self.assertEqual(self.snapshot(), {})

    def test_a_project_moved_back_after_the_old_rebind_step_can_still_be_rolled_back(self):
        original, moved = self.moved_interrupted_project()
        (moved / '.rpi/local/root-binding.json').unlink()  # What the old hint told the owner to do.
        shutil.move(str(moved), str(original))
        self.project = original
        journal = next((original / '.rpi/local/transactions').glob('*/journal.json'))
        result = self.invoke('rollback', '--journal', journal)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), {})

    # WB-L-6: directories the engine created do not outlive the files in them.

    def empty_directories(self):
        return sorted(str(path.relative_to(self.project)) for path in self.project.rglob('*')
                      if path.is_dir() and not path.is_symlink() and not any(path.iterdir()) and '.rpi/local' not in path.as_posix())

    def prepare_owner_directories(self):
        (self.project / 'docs/notes').mkdir(parents=True)                       # Pre-existing and empty.
        (self.project / '.claude/skills/owner-skill').mkdir(parents=True)        # Pre-existing and used by the owner.
        (self.project / '.claude/skills/owner-skill/SKILL.md').write_text('Owner skill.\n')
        return {'docs/notes', '.claude/skills/owner-skill'}

    def test_rollback_removes_the_empty_directories_it_created_and_keeps_every_other(self):
        kept = self.prepare_owner_directories()
        self.apply_ready('install', '--harness', 'claude')
        self.assertGreater(len(self.journals('complete')), 0)
        self.assertEqual(self.invoke('rollback', '--journal', self.journals('complete')[-1]).returncode, 0)
        self.assertEqual(self.empty_directories(), ['docs/notes'], 'only the directory that was there before and is empty remains')
        for name in kept:
            self.assertTrue((self.project / name).is_dir(), name)
        self.assertEqual((self.project / '.claude/skills/owner-skill/SKILL.md').read_text(), 'Owner skill.\n')
        self.assertFalse((self.project / '.claude/skills/rpi-plan').exists())

    def test_a_directory_that_gained_other_content_is_never_removed(self):
        self.apply_ready('install', '--harness', 'claude')
        (self.project / '.claude/skills/rpi-plan/notes.txt').write_text('Owner note.\n')
        self.assertEqual(self.invoke('rollback', '--journal', self.journals('complete')[-1]).returncode, 0)
        self.assertEqual((self.project / '.claude/skills/rpi-plan/notes.txt').read_text(), 'Owner note.\n')

    def test_detach_removes_the_empty_directories_an_install_created(self):
        kept = self.prepare_owner_directories()
        self.apply_ready('install', '--harness', 'claude')
        self.apply_ready('detach')
        leftovers = [name for name in self.empty_directories() if name != 'docs/notes']
        self.assertEqual(leftovers, [])
        for name in kept:
            self.assertTrue((self.project / name).is_dir(), name)
        self.assertEqual(json.loads((self.project / '.rpi/manifest.json').read_text())['route'], 'detached')

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
        self.assertNotIn('nothing needs doing', summary['reason'], 'the installation can drift after a plan was applied')
        self.assertIn('check', summary['reason'])
        self.assertIn('needs no further apply', summary['fix'])
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

    def test_a_replanned_install_with_identical_operations_is_not_reported_as_applied(self):
        first_plan, first = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', first).returncode, 0)
        first_journal = self.journals('complete')[-1]
        self.apply_ready('detach')
        # A later plan whose operations coincide with the first one's but that was never applied.
        third_plan = dict(first_plan, plan_id='f' * 32)
        third = self.plans / 'third.json'
        third.write_text(json.dumps(third_plan))
        self.assertEqual(third_plan['operations'], first_plan['operations'])
        summary = self.conflict(self.invoke('apply', '--plan', third))
        self.assertIn('plan changed or source/installation preimages changed; create a new plan', summary['reason'])
        self.assertNotIn('already applied', summary['reason'])
        again = self.conflict(self.invoke('apply', '--plan', first))
        self.assertIn('already applied by transaction journal ' + str(first_journal), again['reason'])
        self.assertIn('later transactions', again['reason'])

    def test_a_journal_without_a_plan_identifier_never_claims_the_plan_was_applied(self):
        _, path = self.plan()
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        journal = self.journals('complete')[-1]
        for name in ('journal.json', 'receipt.json'):  # As written before plans carried an identifier.
            file = journal.with_name(name)
            value = json.loads(file.read_text())
            value.pop('plan_id', None)
            file.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
        summary = self.conflict(self.invoke('apply', '--plan', path))
        self.assertIn('plan changed or source/installation preimages changed', summary['reason'])
        self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)

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
