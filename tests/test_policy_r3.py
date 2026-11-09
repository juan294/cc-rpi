"""Round 3 review findings for the pre-action denylist and the receipt gate (items 1 to 18 of the policy review).

Same fixture as test_policy_wb2: the fixture's `git` runs real git for everything except push and pull."""
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
import unittest

import test_policy
import test_policy_wb2
import test_prepush

POLICY = test_policy.POLICY
PREPUSH = test_prepush.PREPUSH


def load(path=POLICY):
    return test_policy_wb2.load_policy() if path == POLICY else None


class VersionTagTests(test_policy_wb2.Wb2Fixture):
    """Items 1, 2, 16, 18: one strict version-tag pattern; a destination that names a version is a tag, whatever its source."""

    VERSIONS = ('v1', 'v1.0', 'V3.0.0', 'v2.0.0rc1', 'v5.0.0_x', 'v1.2.3-beta.1+build.5', '1.2.3.4', '2.0', 'release-1.0.0', 'release-v1',
                'v1.2.3-rc.1', 'v1x', 'rel_2.1')
    BRANCHES = ('issue-42', 'fix-123', 'feature-2', 'release-1', '1', '2026-11-09', 'nightly', 'latest', 'release-candidate', 'v', 'x',
                '1password', 'v1.', '1.1.1.', 'main', 'feature/v1.0', 'fix_7', 'sprint-12')

    def test_the_pattern_separates_versions_from_branch_names(self):
        pattern = load().VERSION_TAG
        for name in self.VERSIONS:
            self.assertTrue(pattern.fullmatch(name), name)
        for name in self.BRANCHES:
            self.assertFalse(pattern.fullmatch(name), name)

    def test_the_gate_and_the_hook_share_the_pattern(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('prepush_r3_fixture', PREPUSH)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        self.assertEqual(load().VERSION_TAG.pattern, gate.VERSION_TAG.pattern)
        self.assertEqual({name for name in self.VERSIONS if gate.VERSION_TAG.fullmatch(name)}, set(self.VERSIONS))

    def test_matching_does_not_backtrack(self):
        pattern = load().VERSION_TAG
        started = time.monotonic()
        for name in ('1.' * 20000 + '!', 'v' + '1.' * 20000 + '!', 'a-' + '1.' * 20000 + '!', '1' * 40000 + '!', 'a' * 40000 + '-' + '1' * 40000):
            self.assertIsNone(pattern.fullmatch(name))
        self.assertLess(time.monotonic() - started, 0.5)
        started = time.monotonic()
        result = self.invoke('git push origin :' + '1.' * 20000 + '!')
        self.assertIn(result.returncode, (0, 2), result.stderr)
        self.assertLess(time.monotonic() - started, 2)

    def test_a_branch_source_cannot_move_a_tag(self):
        self.git('branch', 'feat2')
        self.blocked_all(['git push -f origin feat2:v1.0', 'git push -f origin HEAD:v1.0', 'git push -f origin feat2:2.0',
                          'git push origin +feat2:v1.0', 'git push -f origin HEAD:release-1.0.0', 'git push -f origin feat2:release-v1',
                          'git push --force-with-lease origin feat2:V3.0.0'], 'version tag')
        self.allowed_all(['git push -f origin feat2:refs/heads/v1.0', 'git push -f origin feat2:heads/v1.0', 'git push origin feat2:v1.0',
                          'git push -f origin feat2:feat2', 'git push -f origin HEAD:issue-42'])

    def test_a_remote_tag_is_deleted_whatever_local_branches_exist(self):
        self.git('branch', 'v1.0')
        self.git('branch', 'release-1.0.0')
        self.blocked_all(['git push origin :v1.0', 'git push --delete origin v1.0', 'git push -d origin release-1.0.0',
                          'git push -f origin v1.0'], 'version tag')
        self.allowed_all(['git push origin :refs/heads/v1.0', 'git push --delete origin refs/heads/v1.0'])

    def test_ordinary_branch_names_are_deleted_and_forced_freely(self):
        self.allowed_all(['git push origin --delete issue-42', 'git push origin :feature-2', 'git push -d origin fix-123',
                          'git push -f origin release-1', 'git push -f origin issue-42', 'git push -f origin 1',
                          'git push origin --delete sprint-12', 'git push -f origin 2026-11-09', 'git push origin :fix_7',
                          'git push -f origin "feature-$N"'])

    def test_the_gate_gates_the_same_tags(self):
        class Gate(test_prepush.PrePushFixture):
            def runTest(self):
                pass
        gate = Gate()
        gate.setUp()
        self.addCleanup(gate.doCleanups)
        gate.policy(require_verification_receipt=True)
        gate.commit('Opt in')
        head = gate.git('rev-parse', 'HEAD')
        for name in ('v1.0', 'release-v1', '2.0', 'V3.0.0-rc.1'):
            gate.assert_refused(gate.line('refs/tags/' + name, head), reason='verification evidence is missing')
        for name in ('release-1', '1', 'issue-42', '2026-11-09', 'nightly'):
            gate.assert_passes(gate.line('refs/tags/' + name, head))


class FunctionSkipTests(test_policy_wb2.Wb2Fixture):
    """Item 3: a definition is inert only when nothing can call it, including by a dynamic or decoded name."""

    DEFINITION = 'f() { git push -f origin main; }; '

    def test_calls_that_do_not_spell_the_bare_name(self):
        self.blocked_all([self.DEFINITION + command for command in ('${X:-f}', "$'\\x66'", '$(echo f)', '"$X"', 'eval "$X"', 'bash -c "$X"',
                                                                  '`echo f`', "$'f'", '\\f', '"f"', 'xargs sh -c "$X"')])

    def test_a_definition_nothing_can_call_stays_inert(self):
        self.allowed_all([self.DEFINITION.rstrip('; '), self.DEFINITION + 'echo "$HOME"', self.DEFINITION + 'ls', self.DEFINITION + 'echo done',
                          self.DEFINITION + 'cd /tmp'])


class NestingTests(test_policy_wb2.Wb2Fixture):
    """Item 4: a command nested deeper than the cap that names git is blocked, not passed."""

    @staticmethod
    def nested_substitution(levels):
        command = 'git push -f origin main'
        for _ in range(levels):
            command = 'echo $(' + command + ')'
        return command

    @staticmethod
    def nested_eval(levels):
        return 'eval ' * levels + 'git push -f origin main'  # eval joins its words and reads them again, one level per word

    def test_the_cap_is_exact_and_beyond_it_blocks(self):
        for build in (self.nested_substitution, self.nested_eval):
            with self.subTest(build=build.__name__):
                self.blocked_all([build(50), build(100)], 'protected branch')
                self.blocked_all([build(101), build(150)], 'levels deep')
                result = self.invoke(build(101))
                self.assertIn('/ FIX:', result.stderr)

    def test_deep_nesting_without_a_policy_word_costs_nothing(self):
        command = 'echo hi'
        for _ in range(150):
            command = 'echo $(' + command + ')'
        self.allowed_all([command])


class WrapperSpellingTests(test_policy_wb2.Wb2Fixture):
    """Item 5."""

    def test_arch_and_the_homebrew_gnu_prefixes(self):
        self.blocked_all(['arch -arch arm64 git push -f origin main', 'arch -arch x86_64 git push -f origin main',
                          'gtimeout 5 git push -f origin main', 'gtimeout -s KILL 5 git push -f origin main', 'gnice -n 5 git push -f origin main',
                          'genv -u X git push -f origin main', 'genv -S "git push -f origin main"', 'gstdbuf -oL git push -f origin main',
                          'gnohup git push -f origin main', 'gxargs -n1 git push -f origin main', 'gtime -p git push -f origin main',
                          'gtimeout 5 gnice gnohup git push -f origin main'])
        self.allowed_all(['gtimeout 5 git push -f origin feature', 'gnice -n 5 echo git push -f origin main', 'genv FOO=1 ls'])


class SubstitutionDirectoryTests(test_policy_wb2.Wb2Fixture):
    """Item 9: a substitution runs after the cd that precedes it."""

    def setUp(self):
        super().setUp()
        self.other = self.workspace / 'cfg-a'
        self.other.mkdir()
        subprocess.run([self.environment['RPI_REAL_GIT'], '-C', str(self.other), 'init', '-qb', 'main'], check=True)
        for arguments in (('remote', 'add', 'origin', 'https://example.invalid/a.git'), ('config', 'remote.origin.push', '+HEAD:refs/heads/main')):
            subprocess.run([self.environment['RPI_REAL_GIT'], '-C', str(self.other), *arguments], check=True)

    def test_substitutions_and_backticks_see_the_changed_directory(self):
        other = shlex.quote(str(self.other))
        self.blocked_all(['cd %s && git push' % other, 'cd %s && echo "$(git push)"' % other, 'cd %s && echo `git push`' % other,
                          '(cd %s && echo "$(git push)")' % other, 'cd %s; x=$(git push)' % other, 'cd %s; echo "$(echo "$(git push)")"' % other,
                          'cd %s && cat <(git push)' % other, 'cd %s && cat <<EOF\n$(git push)\nEOF' % other])

    def test_a_substitution_before_the_cd_keeps_the_old_directory(self):
        other = shlex.quote(str(self.other))
        self.allowed_all(['echo "$(git push)"; cd %s' % other, 'echo "$(git push)"', '(cd %s); echo "$(git push)"' % other,
                          'cd %s | cat; echo "$(git push)"' % other])


class BudgetAndErrorTests(test_policy_wb2.Wb2Fixture):
    """Items 10, 13, 14, 15."""

    def test_a_hung_git_is_reported_as_a_hung_git(self):
        (self.fakebin / 'git').write_text('#!/bin/sh\nsleep 30\n')
        result = self.invoke('git push -f origin feature', environment={**self.environment, 'RPI_POLICY_BUDGET_SECONDS': '0.8'})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('git did not answer within the hook time budget of 0.8 seconds', result.stderr)
        self.assertNotIn('too large', result.stderr)
        self.assertNotIn('Split it', result.stderr)
        self.assertIn('/ FIX: Check that git responds', result.stderr)

    def test_the_whole_hook_fits_inside_the_budget(self):
        (self.fakebin / 'git').write_text('#!/bin/sh\nsleep 30\n')
        for budget, limit in (('2', 2.7), ('1', 1.7)):
            started = time.monotonic()
            result = self.invoke('git push -f origin feature', environment={**self.environment, 'RPI_POLICY_BUDGET_SECONDS': budget})
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertLess(time.monotonic() - started, limit, 'budget ' + budget)

    def test_the_budget_stays_below_the_host_hook_timeout(self):
        module = test_policy_wb2.load_policy()
        timeouts = []
        for name in ('codex-hooks.json', 'claude-policy.json'):
            text = (test_policy.ROOT / 'templates/adapters' / name).read_text()
            timeouts += [int(value) for value in __import__('re').findall(r'"timeout":\s*(\d+)', text)]
        self.assertTrue(timeouts, 'the adapters declare a hook timeout')
        self.assertLess(module.MAX_BUDGET_SECONDS + 1.0, min(timeouts))
        for value, note in (('20', False), ('25', True), ('600', True), ('28', True)):
            result = self.invoke('git status', environment={**self.environment, 'RPI_POLICY_BUDGET_SECONDS': value})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual('RPI_POLICY_BUDGET_SECONDS' in result.stderr, note, value)

    def test_evaluate_puts_back_the_alarm_handler_and_the_caches(self):
        module = test_policy_wb2.load_policy()
        fired = []
        original = signal.signal(signal.SIGALRM, lambda number, frame: fired.append(number))
        self.addCleanup(signal.signal, signal.SIGALRM, original)
        self.addCleanup(signal.setitimer, signal.ITIMER_REAL, 0)
        event = dict(self.event('git status'))
        signal.alarm(30)
        module.evaluate(event)
        remaining = signal.setitimer(signal.ITIMER_REAL, 0)[0]
        self.assertTrue(0 < remaining <= 30, 'an earlier timer keeps running')
        self.assertEqual(signal.getsignal(signal.SIGALRM).__name__, '<lambda>')
        self.assertEqual(module._GIT_CACHE, {})
        signal.setitimer(signal.ITIMER_REAL, 0.05)
        time.sleep(0.3)
        self.assertEqual(fired, [signal.SIGALRM], 'a later alarm reaches its own handler, not BudgetExceeded')

    def test_evaluate_leaves_no_handler_behind_when_there_was_none(self):
        module = test_policy_wb2.load_policy()
        original = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        self.addCleanup(signal.signal, signal.SIGALRM, original)
        module.evaluate(dict(self.event('git status')))
        self.assertEqual(signal.getsignal(signal.SIGALRM), signal.SIG_DFL)
        self.assertEqual(signal.setitimer(signal.ITIMER_REAL, 0)[0], 0)

    def test_a_sequence_with_thousands_of_digits_is_one_unresolved_word(self):
        digits = '9' * 5000
        for command in ('git status {1..%s}' % digits, 'git status {%s..1}' % digits, 'git status {1..2..%s}' % digits):
            result = self.invoke(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('could not evaluate', result.stderr)
        result = self.invoke('git push -f origin {1..%s}' % digits)
        self.assertEqual(result.returncode, 2)
        self.assertIn('protected branch', result.stderr)
        self.assertNotIn('could not evaluate', result.stderr)

    def test_every_way_out_of_the_error_handler_is_closed(self):
        runtime = self.workspace / 'runtime'
        runtime.mkdir()
        broken = runtime / 'rpi-policy.py'
        text = POLICY.read_text().replace('def push(', 'def push(*_):\n    raise RuntimeError\n\n\ndef _unused(', 1)
        text = text.replace('def names_a_policy_word(event):', 'def names_a_policy_word(event):\n    raise BudgetExceeded()', 1)
        broken.write_text(text)
        result = subprocess.run([sys.executable, str(broken), '--harness', 'claude'], input=json.dumps(self.event('git push origin feature')),
                                text=True, capture_output=True, env=self.environment, cwd=self.project)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('BLOCKED / WHY:', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


class LauncherTests(test_policy_wb2.Wb2Fixture):
    """Item 17: the practical launchers that run a command, and a GraphQL query the hook cannot read."""

    def test_launchers_that_run_a_command(self):
        script = "'git push -f origin main'"
        self.blocked_all(['fish -c ' + script, 'fish --command=' + script, 'fish --command ' + script, 'tcsh -c ' + script, 'csh -c ' + script,
                          'runuser -u root -- git push -f origin main', 'runuser -u root git push -f origin main',
                          'runuser --user=root -- git push -f origin main', 'runuser -u root -g wheel -- git push -f origin main',
                          'trap ' + script + ' EXIT', 'trap "git push -f origin main" INT TERM', 'trap -- ' + script + ' EXIT',
                          'watch git push -f origin main', 'watch -n 5 git push -f origin main', 'watch -d -n 1 git push -f origin main',
                          'flock /tmp/x git push -f origin main', 'flock -w 5 /tmp/x git push -f origin main', 'flock -n /tmp/x -c ' + script,
                          'flock --timeout 5 /tmp/x git push -f origin main', 'parallel git push -f origin main ::: a',
                          "parallel -j 4 'git push -f origin {}' ::: main", 'echo main | parallel git push -f origin', 'parallel --jobs 2 git push -f origin main',
                          'sudo trap ' + script + ' EXIT', 'nohup fish -c ' + script])
        self.allowed_all(['fish -c "echo hi"', 'trap - EXIT', 'trap -p', 'trap "echo bye" EXIT', 'trap', 'watch -n 5 git status', 'watch ls',
                          'flock /tmp/x git status', 'flock -n /tmp/x -c "echo hi"', 'parallel echo ::: a b', 'parallel -j 2 git fetch ::: a b',
                          'runuser -u root -- git status', 'runuser root -c "echo hi"', 'fish -c ' + "'git push -f origin feature'"])

    def test_graphql_queries_the_hook_cannot_read_fail_closed(self):
        self.blocked_all(['gh api graphql -f query="$Q"', 'gh api graphql -F query=@$PWD/q.graphql', 'gh api graphql --input -',
                          'gh api graphql -f query=@-', 'gh api graphql -F query=@-', 'gh api graphql -f query="$(cat q.graphql)"',
                          'gh api graphql --input "$FILE"', 'gh api graphql --input=-', 'cat q | gh api graphql --input -',
                          'gh api graphql -f query="query { $FIELD }"'], 'cannot be ruled out')
        (self.project / 'safe.graphql').write_text('query { viewer { login } }')
        self.allowed_all(["gh api graphql -f query='query { viewer { login } }'", "gh api graphql -f query='query { viewer { login } }' -F owner=\"$OWNER\"",
                          "gh api graphql -f query='query($o: String!) { organization(login: $o) { id } }' -f o=\"$ORG\"", 'gh api graphql -F query=@safe.graphql',
                          'gh api graphql -F query=@missing.graphql', 'gh api user', 'gh api graphql --paginate -f query=\'query { viewer { login } }\''])

    def test_launchers_that_stay_documented_limits(self):
        """Pinned: these pass, as docs/native-policy.md says (the command runs somewhere the parser does not read)."""
        self.allowed_all(["ssh host 'git push -f origin main'", "find . -exec git push -f origin main ';'", "script -q /dev/null git push -f origin main",
                          "at now <<< 'git push -f origin main'", "echo 'git push -f origin main' | bash",
                          "nsenter -t 1 git push -f origin main", "docker run --rm img git push -f origin main"])


if __name__ == '__main__':
    unittest.main()
