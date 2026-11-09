"""Second-round exploratory findings on the lifecycle engine (WB2-L-1 to WB2-L-13).

Every message is exercised through the public CLI. A printed FIX is executed verbatim
where it is a command, so a repair that does not work, or that loses owner data, fails here.
"""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import unittest
from unittest import mock

import test_lifecycle_adopters as adopters


def engine_module(name):
    spec = importlib.util.spec_from_file_location('wb2_' + name.replace('-', '_'), adopters.ENGINE.with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Wb2Base(unittest.TestCase):
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

    def shell(self, command):
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, command + '\n' + result.stdout + result.stderr)
        return result

    def plan_json(self, *arguments, output=None):
        self.plan_number += 1
        output = output or self.plans / ('wb2-%d.json' % self.plan_number)
        result = self.invoke('plan', '--source', self.source, '--target', self.project, '--output', output, *arguments)
        return result, json.loads(result.stdout), output

    def replan_from(self, fix):
        """Run the 'create a new plan with ...' command a printed FIX ends with; returns (result, plan summary, plan path)."""
        command = shlex.split(fix.rsplit('then create a new plan with ', 1)[1])
        result = subprocess.run(command, capture_output=True, text=True)
        return result, json.loads(result.stdout), Path(command[command.index('--output') + 1])


class RollbackInterruptionTests(Wb2Base):
    # WB2-L-1 and WB2-L-12: a rollback that was cut off is named and finishable; a running one is waited for.

    def cut_rollback(self, after_calls):
        """Crash the rollback of the latest journal after it rewrote `after_calls` files (the marker counts as one)."""
        module = engine_module('rpi-lifecycle')
        real, calls = module.atomic_node, {'n': 0}

        def crash(path, node):
            calls['n'] += 1
            if calls['n'] > after_calls:
                raise KeyboardInterrupt('killed')
            return real(path, node)
        journal = self.journals('complete')[-1]
        with mock.patch.object(module, 'atomic_node', crash):
            with self.assertRaises(KeyboardInterrupt):
                module.rollback(journal)
        return journal

    def test_a_rollback_cut_off_midway_is_named_by_check_and_its_fix_finishes_it(self):
        self.apply_ready('install', '--harness', 'claude')
        journal = self.cut_rollback(6)
        self.assertEqual(json.loads(journal.read_text())['status'], 'complete', 'the journal alone cannot tell')
        checked = self.conflict(self.check())
        self.assertEqual(checked['status'], 'action-needed')
        fix = checked['fix']
        self.assertIn('a rollback stopped before completing', fix)
        self.assertIn('rollback --journal', fix)
        self.assertIn(shlex.quote(str(journal)), fix)
        self.assertNotIn('moving it aside', fix)
        self.assertNotIn('mv --', fix)
        self.assertEqual(checked['interrupted_transactions'], [str(journal)])
        planned = self.invoke('plan', '--source', self.source, '--target', self.project, '--output', self.plans / 'during.json')
        self.assertIn('rollback --journal', json.loads(planned.stdout)['fix'])
        self.shell(fix.split('finish it with ', 1)[1].rsplit(', then create a new plan', 1)[0])
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')
        self.assertNotIn('rollback_in_progress', json.loads(journal.read_text()))
        self.assertFalse((self.project / '.claude/skills').exists())
        again = self.conflict(self.check())  # Nothing is installed now: an install, not an update, is the next step.
        self.assertIn('--action install', again['fix'])
        self.assertNotIn('interrupted_transactions', again)

    def test_a_rollback_cut_off_before_it_touched_a_file_is_also_finishable(self):
        self.apply_ready('install', '--harness', 'claude')
        journal = self.cut_rollback(1)  # Only the marker was written.
        checked = self.conflict(self.check())
        self.assertIn('a rollback stopped before completing', checked['fix'])
        self.assertEqual(self.invoke('rollback', '--journal', journal).returncode, 0)
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')

    def test_a_rolled_back_journal_and_a_healthy_install_carry_no_marker_and_check_stays_healthy(self):
        self.apply_ready('install', '--harness', 'claude')
        self.assertNotIn('rollback_in_progress', json.loads(self.journals()[-1].read_text()))
        self.assertEqual(json.loads(self.check().stdout)['status'], 'healthy')

    def test_a_running_rollback_means_wait_for_check_and_plan_and_rollback(self):
        self.apply_ready('install', '--harness', 'claude')
        journal = self.journals('complete')[-1]
        value = json.loads(journal.read_text())
        value['rollback_in_progress'] = True  # What a live rollback has written before it starts changing files.
        journal.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
        descriptor = os.open(self.project / '.rpi/local/lock', os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(os.close, descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        checked = self.conflict(self.check())
        self.assertIn('wait for it to finish', checked['fix'])
        self.assertNotIn('rollback --journal', checked['fix'])
        self.assertIn('a running lifecycle operation', checked.get('active_operation', ''))
        planned = self.invoke('plan', '--source', self.source, '--target', self.project, '--output', self.plans / 'busy.json')
        self.assertIn('wait', json.loads(planned.stdout)['fix'])
        other = self.conflict(self.invoke('rollback', '--journal', journal))
        self.assertIn('wait for the other lifecycle operation to finish', other['fix'])
        self.assertIn('rollback --journal', other['fix'])  # The same rollback, to run again afterwards.
        fcntl.flock(descriptor, fcntl.LOCK_UN)  # The other operation finished.
        self.shell(other['fix'].rsplit(': ', 1)[1])
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')


class RepairTests(Wb2Base):
    # WB2-L-2: every conflict class carries a repair that works, and one class never hides the others' repairs.

    def run_repair(self, conflict):
        self.shell(conflict['move_aside_command'])

    def test_a_symlink_where_an_owned_file_goes_is_moved_aside_and_the_install_then_plans(self):
        target = self.workspace / 'secret.txt'
        target.write_text('outside content\n')
        link = self.project / '.claude/skills/rpi-plan/SKILL.md'
        link.parent.mkdir(parents=True)
        link.symlink_to(target)
        result, summary, _ = self.plan_json('--harness', 'claude', '--route', 'direct')
        self.assertEqual(result.returncode, 2, result.stdout)
        item = next(c for c in summary['conflicts'] if c['destination'] == '.claude/skills/rpi-plan/SKILL.md')
        self.assertIn('symbolic link', item['fix'])
        self.assertIn(item['move_aside_command'], summary['fix'])
        self.assertNotIn('Inspect the local plan', summary['fix'])
        self.run_repair(item)
        self.assertFalse(link.is_symlink())
        self.assertEqual(target.read_text(), 'outside content\n', 'the link target is never touched')
        kept = [path for path in (self.project / '.rpi/local/saved-edits').rglob('SKILL.md.*') if path.is_symlink()]
        self.assertEqual(len(kept), 1)
        self.assertEqual(os.readlink(kept[0]), str(target))
        _, replanned, path = self.replan_from(summary['fix'])
        self.assertEqual(replanned['status'], 'ready', replanned.get('conflicts'))
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        self.assertTrue(link.is_file() and not link.is_symlink())

    def test_a_directory_where_an_owned_file_goes_is_moved_aside_whole_and_the_install_then_plans(self):
        directory = self.project / '.claude/skills/rpi-plan/SKILL.md'
        directory.mkdir(parents=True)
        (directory / 'mine.txt').write_text('owner file inside\n')
        result, summary, _ = self.plan_json('--harness', 'claude', '--route', 'direct')
        self.assertEqual(result.returncode, 2, result.stdout)
        item = next(c for c in summary['conflicts'] if c['destination'] == '.claude/skills/rpi-plan/SKILL.md')
        self.assertIn('directory', item['fix'])
        self.assertIn(item['move_aside_command'], summary['fix'])
        self.run_repair(item)
        moved = list((self.project / '.rpi/local/saved-edits').rglob('mine.txt'))
        self.assertEqual([path.read_text() for path in moved], ['owner file inside\n'])
        _, replanned, path = self.replan_from(summary['fix'])
        self.assertEqual(replanned['status'], 'ready', replanned.get('conflicts'))
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)

    def test_an_owned_file_replaced_after_install_is_repaired_in_update_and_detach_plans(self):
        for replacement in ('directory', 'symlink'):
            for action in ('update', 'detach'):
                with self.subTest(replacement=replacement, action=action):
                    shutil.rmtree(self.project)
                    self.project.mkdir()
                    self.apply_ready('install', '--harness', 'claude')
                    owned = self.project / '.claude/skills/rpi-plan/SKILL.md'
                    owned.unlink()
                    if replacement == 'directory':
                        owned.mkdir()
                        (owned / 'x').write_text('x\n')
                    else:
                        owned.symlink_to(self.outside)
                    result, summary, _ = self.plan_json('--harness', 'claude', '--action', action)
                    if replacement == 'symlink' and action == 'detach':
                        # A link the engine does not own is retained on detach, never followed: no repair is needed.
                        self.assertEqual(result.returncode, 0, result.stdout)
                        continue
                    self.assertEqual(result.returncode, 2, result.stdout)
                    item = next(c for c in summary['conflicts'] if c['destination'] == '.claude/skills/rpi-plan/SKILL.md')
                    self.assertIn(item['move_aside_command'], summary['fix'])
                    self.assertNotIn('Inspect the local plan', summary['fix'])
                    self.run_repair(item)
                    _, replanned, path = self.replan_from(summary['fix'])
                    self.assertIn(replanned['status'], ('ready', 'noop'), replanned.get('conflicts'))
                    self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
                    self.assertEqual(self.outside.read_bytes(), b'Outside every bound installation root.\n')

    def test_a_symlinked_settings_file_is_replaced_by_a_regular_copy_and_the_plan_then_works(self):
        real = self.workspace / 'real-settings.json'
        real.write_text('{"model": "owner-choice"}\n')
        settings = self.project / '.claude/settings.json'
        settings.parent.mkdir()
        settings.symlink_to(real)
        result, summary, _ = self.plan_json('--harness', 'claude', '--route', 'direct')
        self.assertEqual(result.returncode, 2, result.stdout)
        item = summary['conflicts'][0]
        self.assertIn('symbolic link', item['fix'])
        self.assertIn(item['repair_command'], summary['fix'])
        self.assertNotIn('Inspect the local plan', summary['fix'])
        self.shell(item['repair_command'])
        self.assertTrue(settings.is_file() and not settings.is_symlink())
        self.assertEqual(json.loads(settings.read_text()), {'model': 'owner-choice'})
        self.assertEqual(real.read_text(), '{"model": "owner-choice"}\n')
        _, replanned, path = self.replan_from(summary['fix'])
        self.assertEqual(replanned['status'], 'ready', replanned.get('conflicts'))
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        self.assertEqual(json.loads(settings.read_text())['model'], 'owner-choice')

    def test_a_symlinked_state_directory_is_replaced_by_a_real_one_and_the_plan_then_works(self):
        elsewhere = self.workspace / 'shared-state'
        elsewhere.mkdir()
        (elsewhere / 'keep.txt').write_text('kept\n')
        (self.project / '.rpi').symlink_to(elsewhere, target_is_directory=True)
        result, summary, _ = self.plan_json('--harness', 'claude', '--route', 'direct')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        item = summary['conflicts'][0]
        self.assertIn('is a symbolic link to ' + str(elsewhere.resolve()), item['fix'])
        self.assertIn(item['repair_command'], summary['fix'])
        self.assertNotIn('Inspect the local plan', summary['fix'])
        self.shell(item['repair_command'])
        self.assertTrue((self.project / '.rpi').is_dir() and not (self.project / '.rpi').is_symlink())
        self.assertEqual((elsewhere / 'keep.txt').read_text(), 'kept\n')
        self.assertEqual((self.project / '.rpi/keep.txt').read_text(), 'kept\n')
        _, replanned, path = self.replan_from(summary['fix'])
        self.assertEqual(replanned['status'], 'ready', replanned.get('conflicts'))
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
        self.assertEqual(sorted(path.name for path in elsewhere.iterdir()), ['keep.txt'], 'nothing was written through the link')

    def test_one_conflict_without_a_specific_command_never_hides_the_repair_of_another(self):
        link = self.project / '.claude/skills/rpi-plan/SKILL.md'
        link.parent.mkdir(parents=True)
        link.symlink_to(self.outside)
        marker = '<!-- rpi:policy:start -->\nA\n<!-- rpi:policy:end -->\n'
        (self.project / 'AGENTS.md').write_text(marker + marker)  # Two copies of one managed block: ambiguous.
        result, summary, _ = self.plan_json('--harness', 'claude', '--route', 'direct')
        self.assertEqual(result.returncode, 2, result.stdout)
        reasons = [c['reason'] for c in summary['conflicts']]
        self.assertTrue(any('duplicate or incomplete managed instruction markers' in reason for reason in reasons), reasons)
        self.assertIn('.claude/skills/rpi-plan/SKILL.md', summary['fix'])
        self.assertIn('symbolic link', summary['fix'])
        self.assertIn('AGENTS.md', summary['fix'])
        self.assertIn('exactly one start line', summary['fix'])
        self.assertNotIn('Inspect the local plan', summary['fix'])

    def test_a_directory_in_place_of_the_settings_file_names_its_repair(self):
        (self.project / '.claude/settings.json').mkdir(parents=True)
        result, summary, _ = self.plan_json('--harness', 'claude', '--route', 'direct')
        self.assertEqual(result.returncode, 2, result.stdout)
        item = summary['conflicts'][0]
        self.assertIn('not a regular file', item['fix'])
        self.shell(item['repair_command'])
        _, replanned, _ = self.replan_from(summary['fix'])
        self.assertEqual(replanned['status'], 'ready', replanned.get('conflicts'))


class LockAndInputFixTests(Wb2Base):
    # WB2-L-3: failures on the adopter side name the adopter-side repair, never the cc-rpi source manifest.

    def lock_scenario(self, kind):
        _, path = self.plan('install', '--harness', 'claude')
        local = self.project / '.rpi/local'
        local.mkdir(parents=True, exist_ok=True)
        lock = local / 'lock'
        if kind == 'directory':
            lock.mkdir()
        elif kind == 'symlink':
            lock.symlink_to(self.outside)
        elif kind == 'content':
            lock.write_text('12345\n')
        elif kind == 'hardlink':
            lock.write_text('')
            os.link(lock, local / 'lock-other-name')
        return path, lock

    def test_an_unusable_lock_names_the_lock_and_its_repair_and_the_apply_then_succeeds(self):
        for kind in ('directory', 'symlink', 'content', 'hardlink'):
            with self.subTest(lock=kind):
                shutil.rmtree(self.project)
                self.project.mkdir()
                path, lock = self.lock_scenario(kind)
                result = self.invoke('apply', '--plan', path)
                summary = self.conflict(result)
                named = lock.parent.resolve() / lock.name
                self.assertIn(str(named), summary['reason'])
                self.assertIn(shlex.quote(str(named)), summary['fix'])
                self.assertNotIn('distribution.json', summary['fix'])
                self.assertNotIn('distribution.json', result.stderr)
                self.assertEqual(list((self.project / '.claude').glob('**/*')) if (self.project / '.claude').exists() else [], [], 'nothing was written')
                command = summary['fix'].split('then set the lock file aside with ', 1)[1].split(' (its content', 1)[0]
                self.shell(command)
                self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)
                self.assertEqual(self.outside.read_bytes(), b'Outside every bound installation root.\n')

    def test_a_hand_edited_plan_is_replaced_by_a_new_plan_not_by_editing_the_source(self):
        broken = self.plans / 'hand-edited.json'
        broken.write_text(json.dumps({'schema_version': 1, 'request': {'source': str(self.source), 'target': str(self.project)}}))
        result = self.invoke('apply', '--plan', broken)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('distribution.json', result.stderr)
        self.assertNotIn('rpi-distribution.py validate', result.stderr)
        self.assertIn('create a new plan with', result.stderr)
        self.assertIn(shlex.quote(str(self.project)), result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        command = result.stderr.split('create a new plan with ', 1)[1].split(' (from the project root', 1)[0]
        created = self.shell(command)  # The printed command makes a plan that applies.
        output = Path(shlex.split(command)[shlex.split(command).index('--output') + 1])
        self.assertEqual(self.invoke('apply', '--plan', output).returncode, 0, created.stdout)

    def test_diagnose_of_a_missing_target_names_the_target_not_the_source_manifest(self):
        result = self.invoke('diagnose', '--target', self.workspace / 'does-not-exist')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('--target', result.stderr.split('FIX:', 1)[1])
        self.assertNotIn('distribution.json', result.stderr)
        again = self.invoke('diagnose')
        self.assertEqual(again.returncode, 1)
        self.assertIn('--target', again.stderr.split('FIX:', 1)[1])

    def test_a_source_that_does_not_load_still_points_at_the_source(self):
        not_a_source = self.workspace / 'not-a-checkout'
        not_a_source.mkdir()
        result = self.invoke('plan', '--source', not_a_source, '--target', self.project, '--output', self.plans / 'x.json')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        fix = result.stderr.split('FIX:', 1)[1]
        self.assertIn('--source', fix)
        self.assertIn('validate', fix)
        validated = subprocess.run(fix.split(' or run ', 1)[1].strip(), shell=True, capture_output=True, text=True)  # The printed diagnostic runs.
        self.assertEqual(validated.returncode, 1)
        self.assertIn('BLOCKED / WHY:', validated.stderr)

    def test_an_unwritable_project_failure_names_the_condition_not_the_source(self):
        _, path = self.plan('install', '--harness', 'claude')
        (self.project / '.claude').write_text('a file where the native directory goes\n')
        result = self.invoke('apply', '--plan', path)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('distribution.json', result.stderr)


class RollbackJournalArgumentTests(Wb2Base):
    # WB2-L-4: a journal argument of any shape ends in BLOCKED / WHY / FIX, never a traceback.

    def test_unusable_journal_arguments_are_refused_with_a_fix(self):
        directory = self.workspace / 'a-directory'
        directory.mkdir()
        (self.workspace / 'text.json').write_text('hello')
        for argument in ('/nonexistent', 'relative.json', str(directory), str(self.workspace / 'text.json'), '/dev/null', '/etc/hosts', ''):
            with self.subTest(journal=argument):
                result = subprocess.run([sys.executable, str(adopters.ENGINE), 'rollback', '--journal', argument],
                                        capture_output=True, text=True, cwd='/')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertIn('BLOCKED / WHY:', result.stderr)
                self.assertIn(' / FIX: ', result.stderr)

    def test_the_installer_entry_gives_the_same_refusal(self):
        result = subprocess.run(['bash', str(adopters.ROOT / 'scripts/install.sh'), '--rollback', '/nonexistent'],
                                capture_output=True, text=True, env={**os.environ, 'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH']})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertIn('FIX: ', result.stderr)

    def test_a_wrong_name_inside_a_project_offers_the_latest_transaction_and_it_works(self):
        self.apply_ready('install', '--harness', 'claude')
        result = subprocess.run([sys.executable, str(adopters.ENGINE), 'rollback', '--journal', 'relative.json'], capture_output=True, text=True, cwd=self.project)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.shell(result.stderr.split('undo the most recent transaction with ', 1)[1].strip())
        self.assertEqual(json.loads(self.journals()[-1].read_text())['status'], 'rolled-back')

    def test_a_transaction_directory_points_at_the_journal_inside_it(self):
        self.apply_ready('install', '--harness', 'claude')
        journal = self.journals()[-1]
        result = self.invoke('rollback', '--journal', journal.parent)
        self.assertEqual(result.returncode, 1)
        command = result.stderr.split('pass the journal file inside that directory: ', 1)[1].strip()
        self.shell(command)
        self.assertEqual(json.loads(journal.read_text())['status'], 'rolled-back')


class UserScopeAndDiagnosticsTests(Wb2Base):
    def enable_plugin(self, value=True):
        path = self.workspace / 'user-claude/settings.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'enabledPlugins': {'cc-rpi@market': value}}))
        return path

    def engine(self, *arguments):
        return subprocess.run([sys.executable, str(adopters.ENGINE), *map(str, arguments)], capture_output=True, text=True,
                              env={**os.environ, 'CLAUDE_CONFIG_DIR': str(self.workspace / 'user-claude')})

    def user_plan(self, name):
        output = self.plans / name
        result = self.engine('plan', '--source', self.source, '--scope', 'user', '--harness', 'claude', '--route', 'direct', '--action', 'install',
                             '--state-root', self.workspace / 'ustate', '--claude-skill-root', self.workspace / 'uskills',
                             '--codex-skill-root', self.workspace / 'uagents', '--output', output)
        return result, json.loads(result.stdout)

    # WB2-L-5

    def test_user_scope_direct_install_is_blocked_while_the_plugin_is_enabled(self):
        settings = self.enable_plugin(True)
        result, summary = self.user_plan('user-dup.json')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        item = next(c for c in summary['conflicts'] if 'plugin is enabled' in c['reason'])
        self.assertEqual(os.path.realpath(item['destination']), os.path.realpath(settings))
        self.assertIn('"cc-rpi@market": false', item['fix'])
        self.assertFalse((self.workspace / 'uskills').exists(), 'nothing was installed')
        self.enable_plugin(False)  # The printed repair.
        result, summary = self.user_plan('user-ok.json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(summary['status'], 'ready')

    # WB2-L-6

    def diagnose(self, *extra):
        result = self.engine('diagnose', '--target', self.project, '--source', self.source, *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_an_owner_skill_named_like_rpi_is_not_a_duplicate_registration(self):
        self.enable_plugin(True)
        mine = self.project / '.claude/skills/rpi-mine/SKILL.md'
        mine.parent.mkdir(parents=True)
        mine.write_text('---\nname: rpi-mine\ndescription: mine\n---\nOwner skill.\n')
        report = self.diagnose()
        self.assertEqual([i for i in report['config_issues'] if i.get('id') == 'duplicate-registration'], [])
        # A skill that cc-rpi itself exports, found directly while the plugin is enabled, is still reported.
        stray = self.project / '.claude/skills/rpi-plan/SKILL.md'
        stray.parent.mkdir(parents=True)
        stray.write_text('---\nname: rpi-plan\ndescription: direct copy\n---\n')
        report = self.diagnose()
        self.assertEqual(len([i for i in report['config_issues'] if i.get('id') == 'duplicate-registration']), 1)

    def test_a_detached_project_is_reported_detached_by_diagnose(self):
        self.apply_ready('install', '--harness', 'claude')
        self.assertEqual(self.diagnose()['installation']['status'], 'installed')
        self.apply_ready('detach')
        self.assertEqual(self.diagnose()['installation']['status'], 'detached')

    def test_an_interrupted_install_is_reported_with_its_journal_and_recovery(self):
        _, path = self.plan('install', '--harness', 'claude')
        failed = self.invoke('apply', '--plan', path, '--fail-after', '3')
        self.assertNotEqual(failed.returncode, 0)
        installation = self.diagnose()['installation']
        journal = self.journals('applying')[-1]
        self.assertEqual(installation['status'], 'interrupted')
        self.assertEqual(installation['interrupted_transactions'], [str(journal)])
        self.assertIn('rollback --journal', installation['recovery'])
        self.shell(installation['recovery'].split('undo it exactly with ', 1)[1].rsplit(', then create a new plan', 1)[0])
        self.assertEqual(self.diagnose()['installation']['status'], 'untracked')

    def test_an_unreadable_plugin_settings_file_is_reported_not_silently_ignored(self):
        path = self.workspace / 'user-claude/settings.json'
        path.parent.mkdir(parents=True)
        path.write_text('{"enabledPlugins": {"cc-rpi@market": true},}\n')  # A trailing comma: invalid JSON.
        report = self.diagnose()
        issue = next(i for i in report['config_issues'] if i.get('id') == 'plugin-settings-unreadable')
        self.assertEqual(issue['path'], str(path))
        broken = self.engine('plan', '--source', self.source, '--target', self.project, '--harness', 'claude', '--route', 'direct',
                             '--action', 'install', '--output', self.plans / 'unreadable2.json')
        self.assertEqual(broken.returncode, 0, broken.stdout + broken.stderr)
        notices = json.loads(broken.stdout)['notices']
        self.assertEqual([n['plugin_settings'] for n in notices], ['unreadable'])
        self.assertIn(str(path), notices[0]['reason'])


class SettingsSkeletonTests(Wb2Base):
    # WB2-L-7: detach leaves no empty native skeleton behind, and never adds empty keys to the owner's settings.

    def add_policy_component(self, entries, harness='claude', destination='.claude/settings.json'):
        manifest_path = self.source / 'templates/distribution.json'
        manifest = json.loads(manifest_path.read_text())
        self.write(self.source, 'templates/adapters/policy.json', json.dumps({'schema_version': 1, 'entries': entries}))
        manifest['components'].append({'id': 'config:policy', 'kind': 'config', 'scope': 'project',
            'selection': 'default', 'harnesses': [harness], 'dependencies': [],
            'source': 'templates/adapters/policy.json', 'outputs': {harness: 'configuration/policy.json'},
            'destinations': {harness: destination}, 'ownership': {'direct': 'cc-rpi', 'plugin': 'cc-rpi'}})
        manifest_path.write_text(json.dumps(manifest))

    ENTRIES = [{'id': 'ask-push', 'pointer': ['permissions', 'ask'], 'mode': 'entry', 'value': 'Bash(git push:*)'},
               {'id': 'deny-env', 'pointer': ['permissions', 'deny'], 'mode': 'entry', 'value': 'Read(.env)'},
               {'id': 'hook-guard', 'pointer': ['hooks', 'PreToolUse'], 'mode': 'entry',
                'value': {'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'guard'}]}}]

    def test_detach_removes_the_settings_file_and_directory_the_install_created(self):
        self.add_policy_component(self.ENTRIES)
        before = self.snapshot()
        self.apply_ready('install', '--harness', 'claude', '--allow-capabilities', 'config:policy')
        self.assertTrue((self.project / '.claude/settings.json').is_file())
        self.apply_ready('detach')
        self.assertFalse((self.project / '.claude/settings.json').exists())
        self.assertFalse((self.project / '.claude').exists(), 'the directory the install created is removed too')
        self.assertEqual({k: v for k, v in self.snapshot().items() if not k.startswith('.rpi/')}, before)

    def test_detach_keeps_exactly_the_owners_settings_without_empty_keys(self):
        self.add_policy_component(self.ENTRIES)
        settings = self.project / '.claude/settings.json'
        settings.parent.mkdir()
        settings.write_text('{\n  "model": "owner-choice",\n  "permissions": {\n    "deny": ["Read(private/**)"]\n  }\n}\n')
        self.apply_ready('install', '--harness', 'claude', '--allow-capabilities', 'config:policy')
        self.assertIn('Bash(git push:*)', settings.read_text())
        self.apply_ready('detach')
        self.assertEqual(json.loads(settings.read_text()), {'model': 'owner-choice', 'permissions': {'deny': ['Read(private/**)']}})

    def test_rollback_of_a_detach_restores_the_removed_settings_file(self):
        self.add_policy_component(self.ENTRIES)
        self.apply_ready('install', '--harness', 'claude', '--allow-capabilities', 'config:policy')
        installed = (self.project / '.claude/settings.json').read_bytes()
        self.apply_ready('detach')
        self.assertEqual(self.invoke('rollback', '--journal', self.journals('complete')[-1]).returncode, 0)
        self.assertEqual((self.project / '.claude/settings.json').read_bytes(), installed)


class FileModeTests(Wb2Base):
    # WB2-L-8: owned files are 0644 (0755 when the source is executable); a different mode is drift that update repairs.

    def setUp(self):
        super().setUp()
        self.script = self.source / 'templates/skills/rpi-plan/scripts/validate.py'
        self.script.chmod(0o755)
        self.installed_script = self.project / '.claude/skills/rpi-plan/scripts/validate.py'
        self.installed_doc = self.project / '.claude/skills/rpi-plan/references/playbook.md'

    def mode(self, path):
        return stat.S_IMODE(path.stat().st_mode)

    def test_a_chmod_of_installed_files_is_reported_by_check_and_repaired_by_update(self):
        self.apply_ready('install', '--harness', 'claude')
        self.assertEqual((self.mode(self.installed_script), self.mode(self.installed_doc)), (0o755, 0o644))
        self.installed_doc.chmod(0o600)
        self.installed_script.chmod(0o644)
        checked = self.check()
        self.assertEqual(checked.returncode, 2, checked.stdout + checked.stderr)
        summary = json.loads(checked.stdout)
        self.assertEqual(summary['status'], 'action-needed')
        self.assertEqual(sorted(op['destination'] for op in summary['operations']),
                         ['.claude/skills/rpi-plan/references/playbook.md', '.claude/skills/rpi-plan/scripts/validate.py'])
        match = re.search(r'create the update plan with (.*?), review it, then apply it with (.*)$', summary['fix'], re.S)
        self.assertTrue(match, summary['fix'])
        self.shell(match.group(1))  # The printed fix is itself runnable and repairs the modes.
        self.shell(match.group(2))
        self.assertEqual((self.mode(self.installed_script), self.mode(self.installed_doc)), (0o755, 0o644))
        self.installed_doc.chmod(0o600)
        self.installed_script.chmod(0o644)
        diagnosed = json.loads(subprocess.run([sys.executable, str(adopters.ENGINE), 'diagnose', '--target', self.project, '--source', self.source],
                                              capture_output=True, text=True).stdout)
        drift = {item['destination']: item for item in diagnosed['installation']['drift']}
        self.assertEqual(drift['.claude/skills/rpi-plan/references/playbook.md']['status'], 'mode-drift')
        self.assertEqual(drift['.claude/skills/rpi-plan/scripts/validate.py']['wanted_mode'], '755')
        content = (self.installed_doc.read_bytes(), self.installed_script.read_bytes())
        self.apply_ready('update')
        self.assertEqual((self.mode(self.installed_script), self.mode(self.installed_doc)), (0o755, 0o644))
        self.assertEqual((self.installed_doc.read_bytes(), self.installed_script.read_bytes()), content)
        self.assertEqual(json.loads(self.check().stdout)['status'], 'healthy')
        # Rollback puts the owner's modes back exactly as they were.
        self.assertEqual(self.invoke('rollback', '--journal', self.journals('complete')[-1]).returncode, 0)
        self.assertEqual((self.mode(self.installed_script), self.mode(self.installed_doc)), (0o644, 0o600))

    def test_an_executable_bit_on_an_ordinary_file_is_removed_by_update(self):
        self.apply_ready('install', '--harness', 'claude')
        self.installed_doc.chmod(0o755)
        self.assertEqual(self.check().returncode, 2)
        self.apply_ready('update')
        self.assertEqual(self.mode(self.installed_doc), 0o644)

    def test_a_source_whose_executable_bit_changed_with_the_same_bytes_reaches_the_installation(self):
        self.apply_ready('install', '--harness', 'claude')
        self.script.chmod(0o644)  # The source stops being executable; its bytes do not change.
        self.apply_ready('update')
        self.assertEqual(self.mode(self.installed_script), 0o644)
        self.script.chmod(0o755)
        self.apply_ready('update')
        self.assertEqual(self.mode(self.installed_script), 0o755)

    def test_modes_are_normalized_whatever_the_umask_on_update_too(self):
        self.apply_ready('install', '--harness', 'claude')
        previous = os.umask(0o002)
        try:
            self.installed_doc.chmod(0o664)
            self.apply_ready('update')
        finally:
            os.umask(previous)
        self.assertEqual(self.mode(self.installed_doc), 0o644)

    def test_a_chmod_alone_does_not_touch_owner_content_or_other_files(self):
        self.apply_ready('install', '--harness', 'claude')
        self.installed_doc.write_text(self.installed_doc.read_text() + 'Owner line.\n')
        self.installed_doc.chmod(0o600)
        self.apply_ready('update')
        self.assertIn('Owner line.', self.installed_doc.read_text())
        self.assertEqual(self.mode(self.installed_doc), 0o644)


class RepairKeepsOwnerEditTests(Wb2Base):
    # WB2-L-9

    def test_block_conflict_fix_saves_the_owner_file_first(self):
        self.apply_ready('install', '--harness', 'claude')
        agents = self.project / 'AGENTS.md'
        original = agents.read_text()
        self.assertIn('Keep local verification and bounded work.', original)
        agents.write_text(original.replace('Keep local verification and bounded work.', 'Owner changed this line.'))
        self.write(self.source, 'templates/instructions/policy.md', 'Upstream changed this line.\n')
        result, summary, _ = self.plan_json('--harness', 'claude', '--action', 'update')
        self.assertEqual(result.returncode, 2, result.stdout)
        item = next(c for c in summary['conflicts'] if c['destination'] == 'AGENTS.md')
        self.assertIn('save_command', item)
        self.assertIn(item['save_command'], item['fix'])
        edited = agents.read_bytes()
        self.shell(item['save_command'])
        self.assertEqual([path.read_bytes() for path in (self.project / '.rpi/local/saved-edits').rglob('AGENTS.md.*')], [edited])


class LifecycleMessageTests(Wb2Base):
    # WB2-L-13

    def test_a_new_plan_name_replaces_the_time_stamp_instead_of_stacking_a_second_one(self):
        module = engine_module('rpi-lifecycle')
        for stem in ('update-20261109-101010', 'update-20261109-101010-20261109-101011', 'plan'):
            with self.subTest(stem=stem):
                saved = self.plans / (stem + '.json')
                name = module.next_plan_output(self.project / '.rpi', 'update', saved).name
                self.assertEqual(len(re.findall(r'\d{8}-\d{6}', name)), 1, name)
                self.assertTrue(name.startswith(re.sub(r'(?:-\d{8}-\d{6})+$', '', stem)), name)
        link = self.project / '.claude/skills/rpi-plan/SKILL.md'
        link.parent.mkdir(parents=True)
        link.symlink_to(self.outside)
        saved = self.plans / 'update-20261109-101010.json'
        _, summary, _ = self.plan_json('--harness', 'claude', output=saved)
        self.assertEqual(len(re.findall(r'\d{8}-\d{6}', summary['fix'].rsplit('--output ', 1)[1])), 1, summary['fix'])

    def test_a_plan_into_a_read_only_directory_is_a_conflict_at_plan_time_not_a_failure_at_apply_time(self):
        self.apply_ready('install', '--harness', 'claude')
        rules = self.project / '.claude/skills/rpi-plan/references'
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        rules.chmod(0o555)
        self.addCleanup(rules.chmod, 0o755)
        if os.access(rules, os.W_OK):
            self.skipTest('a privileged user can write a read-only directory, so there is no failure to report')
        result, summary, path = self.plan_json('--harness', 'claude', '--action', 'update')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        item = next(c for c in summary['conflicts'] if c['reason'].startswith('not writable: '))
        self.assertIn('chmod u+wx', item['fix'])
        self.assertIn(item['fix'], summary['fix'])
        applied = self.invoke('apply', '--plan', path)
        self.assertEqual(applied.returncode, 2, 'the same exit code as every other refused plan: ' + applied.stdout + applied.stderr)
        self.assertEqual(self.snapshot()['.claude/skills/rpi-plan/references/playbook.md'], b'# Required independent fixture resource: references/playbook.md\n')
        command = item['fix'].split('make the directory writable with ', 1)[1].split(' (it is mode', 1)[0]
        self.shell(command)
        _, replanned, path = self.replan_from(summary['fix'])
        self.assertEqual(replanned['status'], 'ready', replanned.get('conflicts'))
        self.assertEqual(self.invoke('apply', '--plan', path).returncode, 0)

    def test_a_stale_sibling_plan_of_a_healthy_installation_does_not_ask_for_a_new_plan(self):
        _, first = self.plan('install', '--harness', 'claude')
        _, sibling = self.plan('install', '--harness', 'claude')
        self.assertEqual(self.invoke('apply', '--plan', first).returncode, 0)
        summary = self.conflict(self.invoke('apply', '--plan', sibling))
        self.assertIn('plan changed or source/installation preimages changed', summary['reason'])
        self.assertIn('healthy now', summary['reason'])
        self.assertNotIn('create a new plan', summary['reason'])
        self.assertIn('nothing needs applying', summary['fix'])
        self.shell(summary['fix'].split('confirm with ', 1)[1].split(', and create a new plan', 1)[0])
        self.assertEqual(json.loads(self.check().stdout)['status'], 'healthy')

    def test_a_stale_plan_of_a_drifted_installation_still_asks_for_a_new_plan(self):
        _, first = self.plan('install', '--harness', 'claude')
        _, sibling = self.plan('install', '--harness', 'claude')
        self.assertEqual(self.invoke('apply', '--plan', first).returncode, 0)
        (self.project / '.claude/skills/rpi-plan/SKILL.md').write_text('# edited\n')
        self.write(self.source, 'templates/skills/rpi-plan/references/playbook.md', 'Upstream planning change.\n')
        summary = self.conflict(self.invoke('apply', '--plan', sibling))
        self.assertIn('create a new plan', summary['reason'])


class InstallerEntryTests(unittest.TestCase):
    # WB2-L-10: the entry point finds its checkout through symbolic links, on bash 3.2 too.

    def fake_checkout(self, root):
        checkout = root / 'real checkout'
        (checkout / 'scripts').mkdir(parents=True)
        shutil.copy2(adopters.ROOT / 'scripts/install.sh', checkout / 'scripts/install.sh')
        engine = checkout / 'templates/scripts/rpi-distribution.py'
        engine.parent.mkdir(parents=True)
        engine.write_text('import sys\nprint("ENGINE", repr(sys.argv[1:]))\n')
        return checkout

    def run_entry(self, entry):
        env = {**os.environ, 'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH']}
        return subprocess.run(['bash', str(entry), '--target', '/tmp/wb2-project', '--output', '/tmp/wb2-plan.json'], capture_output=True, text=True, env=env)

    def test_the_entry_resolves_absolute_relative_and_chained_symbolic_links(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='rpi link ') as temporary:
            root = Path(temporary).resolve()
            checkout = self.fake_checkout(root)
            (root / 'bin').mkdir()
            (root / 'bin/absolute.sh').symlink_to(checkout / 'scripts/install.sh')
            (root / 'bin/relative.sh').symlink_to(Path('..') / 'real checkout/scripts/install.sh')
            (root / 'bin/chained.sh').symlink_to('relative.sh')
            (root / 'links').mkdir()
            (root / 'links/dir-link').symlink_to(checkout / 'scripts', target_is_directory=True)
            for entry in (root / 'bin/absolute.sh', root / 'bin/relative.sh', root / 'bin/chained.sh', root / 'links/dir-link/install.sh'):
                with self.subTest(entry=entry.name):
                    result = self.run_entry(entry)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('--source', result.stdout)
                    self.assertIn(str(checkout), result.stdout)


if __name__ == '__main__':
    unittest.main()
