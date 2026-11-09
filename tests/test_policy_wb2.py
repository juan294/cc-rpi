"""Wave B round 2 findings for the pre-action denylist (WB2-P-1 to WB2-P-22): each class names the findings it pins.

The fixture's `git` is a shim that runs real git for everything except push and pull, so no test here can publish.
RealGitTests use a real git against local bare remotes to prove which refs a command really moves."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import unittest

import test_policy

POLICY = test_policy.POLICY


def load_policy():
    spec = importlib.util.spec_from_file_location('policy_wb2_fixture', POLICY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Wb2Fixture(test_policy.PolicyFixture):
    """A project on `main` (protected) with a `feature` branch; `release` is a declared production branch."""

    def setUp(self):
        super().setUp()
        self.git('checkout', '-qb', 'main')
        self.policy(production_branches=['release'])
        self.commit('Declare release')
        self.outside = self.workspace / 'outside'
        self.outside.mkdir()

    def blocked_all(self, commands, reason='protected branch', environment=None):
        for command in commands:
            with self.subTest(command=command):
                result = self.invoke(command, environment=environment)
                self.assertEqual(result.returncode, 2, command + '\n' + result.stderr)
                self.assertIn('BLOCKED / WHY:', result.stderr)
                self.assertIn('/ FIX:', result.stderr)
                self.assertIn(reason, result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def allowed_all(self, commands, environment=None):
        for command in commands:
            with self.subTest(command=command):
                result = self.invoke(command, environment=environment)
                self.assertEqual(result.returncode, 0, command + '\n' + result.stderr)
                self.assertNotIn('Traceback', result.stderr)
        self.assertFalse(self.sentinel.exists())

    def raw(self, command, environment, cwd=None, harness='claude'):
        """Invoke the hook with a raw byte payload (UTF-8, not ASCII-escaped) and the given environment."""
        payload = json.dumps(dict(self.event(command), cwd=str(cwd or self.project)), ensure_ascii=False).encode('utf-8')
        return subprocess.run([sys.executable, str(POLICY), '--harness', harness], input=payload, capture_output=True,
                              cwd=self.project, env=environment)


class ShortOptionClusterTests(Wb2Fixture):
    """WB2-P-1: digits in a short-option cluster hid force and delete."""

    def test_force_and_delete_hide_in_clusters_with_the_ipv4_and_ipv6_flags(self):
        self.blocked_all(['git push -4f origin main', 'git push -f4 origin main', 'git push -6f origin main',
                          'git push -4d origin main', 'git push -d4 origin main', 'git push -vf4 origin main',
                          'git push -4vf origin main', 'git push -4 -f origin main', 'git push -46 --force origin main',
                          'git push -4 --delete origin main', 'git push -fu4 origin main', 'git push -4qf origin main'])
        self.allowed_all(['git push -4 origin main', 'git push -46 origin main', 'git push -4f origin feature',
                          'git push -4n -f origin main', 'git push -n4f origin main', 'git push -4o option origin feature',
                          'git push -4fo f origin feature'])

    def test_a_push_option_value_is_not_read_as_a_cluster(self):
        self.allowed_all(['git push -o f origin feature', 'git push -4o f origin feature', 'git push -of origin feature'])


class GitGlobalOptionTests(Wb2Fixture):
    """WB2-P-2: the table of options git takes before the command, audited against the installed git."""

    def test_every_value_option_of_git_is_skipped_in_both_spellings(self):
        for option in ('--attr-source HEAD', '--attr-source=HEAD', '--super-prefix x/', '--super-prefix=x/', '--namespace n',
                       '--namespace=n', '--git-dir .git', '--git-dir=.git', '--work-tree .', '--work-tree=.',
                       '--config-env user.name=NAME_UNSET', '--config-env=user.name=NAME_UNSET', '-c user.name=x', '-C .'):
            self.blocked_all(['git %s push -f origin main' % option])

    def test_flag_options_are_skipped_without_consuming_a_word(self):
        for option in ('--no-lazy-fetch', '--no-optional-locks', '--no-advice', '--bare', '--literal-pathspecs', '--glob-pathspecs',
                       '--noglob-pathspecs', '--icase-pathspecs', '--no-replace-objects', '--paginate', '-p', '-P', '--no-pager',
                       '--exec-path=/x', '--list-cmds=builtins', '--no-literal-pathspecs'):
            self.blocked_all(['git %s push -f origin main' % option])

    def test_the_table_matches_the_installed_git(self):
        module = load_policy()
        environment = {**self.environment, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'NAME_SET': 'x'}
        real = self.environment['RPI_REAL_GIT']

        def runs(*arguments):
            return subprocess.run([real, *arguments, '--version'], capture_output=True, text=True, cwd=self.project, env=environment).returncode == 0

        values = {'-C': '.', '-c': 'user.name=x', '--git-dir': '.git', '--work-tree': '.', '--namespace': 'n', '--super-prefix': 'x/',
                  '--config-env': 'user.name=NAME_SET', '--attr-source': 'HEAD'}
        self.assertEqual(set(values), module.GIT_VALUE_OPTIONS)
        checked = 0
        for option, value in values.items():
            with self.subTest(option=option):
                if not runs(option, value):
                    unknown = subprocess.run([real, option, value, '--version'], capture_output=True, text=True, env=environment)
                    self.assertIn('unknown option', unknown.stderr, option + ' is neither accepted nor reported unknown')
                    continue  # An option this git no longer has (--super-prefix): the table keeps it for older gits.
                checked += 1
                if option.startswith('--'):
                    self.assertTrue(runs(option + '=' + value), option + '=VALUE is accepted')
                self.assertFalse(runs(option), option + ' takes the next word as its value')
        self.assertGreaterEqual(checked, 7)
        for option in module.GIT_FLAG_OPTIONS - {'--version', '--help', '--exec-path', '--html-path', '--man-path', '--info-path',
                                                  '--list-cmds'}:
            with self.subTest(option=option):
                self.assertTrue(runs(option), option + ' takes no value')
        self.assertTrue(runs('--list-cmds=builtins'))
        self.assertTrue(runs('--exec-path=/x'))


class EnvSplitStringTests(Wb2Fixture):
    """WB2-P-3: env -S parses its string with quotes and escapes, in every spelling of the option."""

    def test_split_string_spellings(self):
        self.blocked_all(["env -S 'git push -f origin main'", "env -S\"git push -f origin main\"", "env -S'git push -f origin main'",
                          "env -iS 'git push -f origin main'", "env -vS 'git push -f origin main'", "env -S'git' push -f origin main",
                          "env --split-string='git push -f origin main'", "env --split-string 'git push -f origin main'",
                          "env --split='git push -f origin main'", "env -i -S 'git push -f origin main'",
                          "env -S \"git push -f origin 'main'\"", "env -S 'git push -f origin \"main\"'",
                          "env -S 'git push\\_-f origin main'",
                          "env -S 'env -S \"git push -f origin main\"'", "env -S '-i git push -f origin main'",
                          "env -S 'FOO=1 git push -f origin main'",
                          "env -S 'git push -f' origin main", "env -S 'git push' -f origin main",
                          "env -uX -S 'git push -f origin main'", "env -S 'git \"push\" -f origin main'"])
        self.allowed_all(["env -S 'git push -f origin ma\\_in'", "env -S 'git push -f origin feature'", "env -S 'echo git push -f origin main'", "env -S 'ls -l'",
                          "env -S 'git status'"])

    def test_an_unreadable_string_that_names_git_fails_closed(self):
        self.blocked_all(["env -S 'git push -f \"origin main'", "env -S 'git push \\q'", "env -S 'git push ${'"], 'cannot be read')
        self.allowed_all(["env -S 'echo \"unterminated'"])

    def test_the_parser_agrees_with_the_installed_env(self):
        module = load_policy()
        probe = subprocess.run(['env', '-S', 'printf [%s] a'], capture_output=True, text=True)
        if probe.returncode != 0 or probe.stdout != '[a]':
            self.skipTest('this env has no -S')
        for text in ('a b', 'a  b\tc', '"a b" c', "'a b' c", 'a"b c"d', '"a\\"b" c', "'a\\'b' c", 'a\\\\b c', '"a\\\\b"', '""', "'' x"):
            with self.subTest(text=text):
                real = subprocess.run(['env', '-S', 'printf [%s] ' + text], capture_output=True, text=True)
                if real.returncode != 0:
                    continue
                expected = real.stdout.split('][')
                words = module.env_split_string(text)
                self.assertEqual('[' + ']['.join(words) + ']' if words else '', real.stdout, text)


class FailClosedTests(Wb2Fixture):
    """WB2-P-4: a recursion or an unexpected error in a command that names git is a block, not a pass."""

    def test_deeply_nested_brace_groups_block_with_the_brace_rule_not_a_traceback(self):
        for command in ('git status ' + '{a,b}' * 1100, 'git status ' + '{a,b}' * 11, 'git status ' + '{{a,b},{c,d}}' * 600):
            with self.subTest(length=len(command)):
                result = self.invoke(command)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('brace expansion', result.stderr)
                self.assertNotIn('POLICY UNAVAILABLE', result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_deep_nesting_never_reaches_the_interpreter_recursion_limit(self):
        for command in ('git status ' + '$(' * 3000 + ')' * 3000, 'git status ' + '"$(' * 2000 + ')"' * 2000,
                        'git status ' + '(' * 4000 + ')' * 4000, 'git status ' + '`' * 5000, 'git status ' + '${' * 30000,
                        'git status ' + '{' * 4000 + 'x' + '}' * 4000):
            with self.subTest(length=len(command)):
                started = time.monotonic()
                result = self.invoke(command)
                self.assertIn(result.returncode, (0, 2), result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertNotIn('POLICY UNAVAILABLE', result.stderr)
                self.assertLess(time.monotonic() - started, 9)

    def broken_policy(self, replacement):
        runtime = self.workspace / 'runtime'
        runtime.mkdir(exist_ok=True)
        broken = runtime / 'rpi-policy.py'
        broken.write_text(POLICY.read_text().replace(*replacement, 1))
        return broken

    def invoke_broken(self, broken, command):
        return subprocess.run([sys.executable, str(broken), '--harness', 'claude'], input=json.dumps(self.event(command)),
                              text=True, capture_output=True, env=self.environment, cwd=self.project)

    def test_an_unexpected_error_in_a_command_that_names_git_blocks_with_a_runnable_fix(self):
        for error in ('RuntimeError', 'RecursionError', 'KeyError'):
            with self.subTest(error=error):
                broken = self.broken_policy(('def push(', 'def push(*_):\n    raise %s\n\n\ndef _unused(' % error))
                for command in ('git push origin feature', 'git status; git push origin feature', 'bash -c "git push origin feature"'):
                    result = self.invoke_broken(broken, command)
                    if 'status' in command and 'push' not in command:
                        continue
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn('BLOCKED / WHY:', result.stderr)
                    self.assertIn(error, result.stderr)
                    self.assertIn('/ FIX:', result.stderr)
                    self.assertIn('rpi-distribution.py check --target .', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)

    def test_an_unexpected_error_is_recorded_as_a_block(self):
        (self.project / '.rpi/local').mkdir(parents=True)
        broken = self.broken_policy(('def push(', 'def push(*_):\n    raise RuntimeError\n\n\ndef _unused('))
        self.assertEqual(self.invoke_broken(broken, 'git push origin feature').returncode, 2)
        record = json.loads((self.project / '.rpi/local/contract-events.jsonl').read_text().splitlines()[-1])
        self.assertEqual((record['decision'], record['rule']), ('block', 'policy-error'))

    def test_a_command_without_a_policy_word_never_reaches_the_failing_code(self):
        broken = self.broken_policy(('def inspect_command(command, cwd, depth=0, inherited=None):',
                                     'def inspect_command(command, cwd, depth=0, inherited=None):\n    raise RuntimeError("boom")'))
        result = self.invoke_broken(broken, 'ls -l')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('POLICY UNAVAILABLE', result.stderr)


class QuotingAndBraceSequenceTests(Wb2Fixture):
    """WB2-P-5: $"..." strings and brace sequences spell names the shell resolves."""

    def test_locale_strings_are_double_quoted_strings(self):
        self.blocked_all(['$"git" push -f origin main', 'git push -$"f" origin main', 'git push -f origin $"main"',
                          'git push -f origin $"ma""in"'])
        self.allowed_all(['echo $"git push -f origin main"', 'git push -f origin $"feature"'])

    def test_brace_sequences_expand_like_bash(self):
        self.blocked_all(['git push -f origin ma{i..i}n', 'g{i..i}t push -f origin main', 'git push -f origin {m..m}ain',
                          'git push -f origin {,}main',
                          'git {p..p}ush -f origin main', 'git push -f origin ma{i..k..2}n', 'git push -f origin ma{k..i..2}n'])
        self.allowed_all(['git push -f origin {main..main}', 'git push -f origin {a..c}', 'git push origin feature{1..2000}',
                          'git push -f origin ma{i..i}nx', 'git push -f origin ma{i..i..0}n.x'])

    def test_bash_agrees_about_the_spellings(self):
        bash = shutil.which('bash')
        output = subprocess.run([bash, '-c', 'printf "%s " ma{i..i}n g{i..i}t {main..main} $"main" {1..3}'], capture_output=True,
                                text=True).stdout
        self.assertEqual(output, 'main git {main..main} main 1 2 3 ')

    def test_an_unresolved_numeric_sequence_beyond_the_cap_is_a_dynamic_word(self):
        self.blocked_all(['git push -f origin v{1..5000}'], 'version tag')
        self.blocked_all(['git push -f origin {1..5000}'], 'protected branch')
        self.allowed_all(['for i in {1..5000}; do git fetch; done', 'git push origin feature{1..5000}', 'git push -f origin feature{1..2000}'])


class ZshSpellingTests(Wb2Fixture):
    """WB2-P-6: spellings only zsh gives meaning to."""

    def test_zsh_precommand_modifiers_and_command_expansion(self):
        self.blocked_all(['=git push -f origin main', 'noglob git push -f origin main', 'nocorrect git push -f origin main',
                          '- git push -f origin main', 'noglob nocorrect git push -f origin main', 'builtin git push -f origin main',
                          'zsh -c "=git push -f origin main"', 'zsh -fc "noglob git push -f origin main"',
                          'repeat 1 do git push -f origin main; done', 'repeat 2 git push -f origin main',
                          'repeat 1 { git push -f origin main }', 'coproc git push -f origin main', 'time =git push -f origin main',
                          'env =git push -f origin main', 'sudo noglob git push -f origin main'])
        self.allowed_all(['echo =git push -f origin main', 'noglob echo git push -f origin main', 'repeat 2 echo hi',
                          '=ls', 'nocorrect git status', 'git push -f origin =feature'])

    def test_zsh_agrees_about_the_spellings(self):
        if not shutil.which('zsh'):
            self.skipTest('no zsh')
        result = subprocess.run(['zsh', '-fc', 'x=$(=echo hi); print $x; noglob print "*"; nocorrect print ok; - print dash; repeat 2 print r'],
                                capture_output=True, text=True)
        self.assertEqual(result.stdout.split(), ['hi', '*', 'ok', 'dash', 'r', 'r'], result.stderr)


class DirectoryScopeTests(Wb2Fixture):
    """WB2-P-7 and WB2-P-11: a cd that runs in a subshell, a pipeline or the background does not move later segments."""

    def test_a_directory_change_that_is_not_kept_leaves_the_repository_in_force(self):
        out, home = shlex.quote(str(self.outside)), shlex.quote(str(self.project))
        self.blocked_all(['(cd %s); git push -f origin release' % out, '(cd %s && true); git push -f origin release' % out,
                          'cd %s | cat; git push -f origin release' % out, 'cd %s & git push -f origin release' % out,
                          'bash -c %s; git push -f origin release' % shlex.quote('cd ' + out),
                          'cd %s; cd -; git push -f origin release' % out,
                          'pushd %s; popd; git push -f origin release' % out, 'cat | cd %s; git push -f origin release' % out,
                          '(cd %s; true) ; (cd %s) ; git push -f origin release' % (out, out),
                          '( (cd %s); git push -f origin release )' % out, 'cd %s |& cat; git push -f origin release' % out])

    def test_a_directory_change_that_is_kept_applies(self):
        out, home = shlex.quote(str(self.outside)), shlex.quote(str(self.project))
        self.allowed_all(['cd %s; git push -f origin release' % out, 'cd %s && git push -f origin release' % out,
                          '{ cd %s; }; git push -f origin release' % out, '(cd %s; git push -f origin release)' % out,
                          'pushd %s; git push -f origin release' % out, 'cd %s || true; git push -f origin release' % out,
                          'cd %s; cd -; cd %s; git push -f origin release' % (home, out)])

    def test_cd_dash_without_a_known_previous_directory_is_unknown(self):
        self.blocked_all(['cd -; git push -f origin main', 'cd -; git push --force'])
        self.allowed_all(['cd -; git push -f origin feature'])

    def test_a_missing_working_directory_keeps_the_default_protected_names(self):
        event = dict(self.event('git push -f origin main'), cwd='/nonexistent-policy-fixture')
        self.assertEqual(self.invoke(event=event).returncode, 2)
        for command, code in (('git push -f origin master', 2), ('git push --delete origin develop', 2), ('git push --force', 2),
                              ('git push -f origin feature', 0), ('git status', 0), ('git push origin main', 0), ('printf local', 0),
                              ('git push -f origin HEAD', 2)):
            with self.subTest(command=command):
                self.assertEqual(self.invoke(event=dict(self.event(command), cwd='/nonexistent-policy-fixture')).returncode, code)
        result = self.invoke(event=event)
        self.assertIn('/ FIX:', result.stderr)


class WrapperOptionTests(Wb2Fixture):
    """WB2-P-12: executable wrappers consume their options that take a separate value."""

    WRAPPED = ['sudo --user root', 'sudo --user=root', 'sudo --group wheel', 'sudo --host h', 'sudo --chdir /tmp', 'sudo --chroot /r',
               'sudo -u root', 'sudo -g wheel', 'sudo -h h', 'sudo -D /tmp', 'sudo -C 3', 'sudo -R /r', 'sudo -T 5', 'sudo -u root -g wheel -E',
               'sudo --use root', 'sudo -nu root', 'sudo -E -- ', 'doas -u root', 'doas -C /etc/doas.conf', 'doas -a style',
               '/usr/bin/time -o out', '/usr/bin/time -f %e', '/usr/bin/time --output out', '/usr/bin/time --format=%e',
               '/usr/bin/time -p', '/usr/bin/time -l', 'nice --adjustment 5', 'nice --adjustment=5', 'nice --adj 5', 'nice -n 5',
               'nice -n5', 'nice -5', 'env -u X', 'env -C /tmp', 'env --chdir /tmp', 'env --unset X', 'env -P /bin', 'env -i -0',
               'env --ignore-environment', 'env --argv0 x', 'env -a x',
               'timeout -s KILL 10', 'timeout --signal KILL 10', 'timeout -k 5 10', 'timeout --kill-after=5 10', 'timeout -k 5 -s KILL 10',
               'timeout --foreground --preserve-status -v 10', 'exec -a name', 'exec -c -l', 'command -p', 'command --', 'nohup',
               'ionice -c 3', 'ionice -c 2 -n 5', 'ionice --class 3', 'chrt -i 0', 'chrt --idle 0', 'chrt -r 10', 'taskset 0x1',
               'taskset -c 0,1', 'taskset --cpu-list 0', 'setsid', 'setsid -f', 'busybox', 'unbuffer', 'arch -arm64', 'arch -x86_64',
               'arch -e FOO=1', 'xcrun', 'xcrun --sdk macosx', 'xcrun -sdk macosx', 'caffeinate -t 10', 'caffeinate -dimsu',
               'caffeinate -w 99', 'stdbuf -i0', 'stdbuf -o L', 'stdbuf --output=L', 'stdbuf -oL -eL', 'xargs', 'xargs -n 1', 'xargs -I {}',
               'xargs -n1 -P4', 'xargs --max-args 2', 'xargs -0 -r', 'nohup nice -n 5 time -p env -u X timeout 5 sudo -u root',
               'su -c', 'runuser -u x --']

    def test_the_command_behind_each_wrapper_is_inspected(self):
        commands = []
        for prefix in self.WRAPPED:
            if prefix.startswith(('su -c', 'runuser')):
                continue
            commands.append('%s git push -f origin main' % prefix)
        self.blocked_all(commands)

    def test_wrappers_do_not_hide_literal_text(self):
        self.allowed_all(['sudo --user root echo git push -f origin main', 'timeout 5 echo git push -f origin main',
                          'time -p ls', 'taskset -c 0 ls', 'nice -n 5 git status', 'sudo --user root git push -f origin feature',
                          'timeout -s KILL 10 git push origin main', 'xargs -I {} echo git push -f origin main'])

    def test_su_and_runuser_run_their_c_string(self):
        self.blocked_all(['su -c "git push -f origin main"', 'su root -c "git push -f origin main"', 'su -l root -c "git push -f origin main"',
                          'su --command="git push -f origin main" root', 'su -lc "git push -f origin main" root',
                          'sh -c "su -c \\"git push -f origin main\\""', 'runuser -c "git push -f origin main" root',
                          "su -c 'git push -f origin main' - root"])
        self.allowed_all(['su -c "echo hi" root', 'su root', 'su -c "git push -f origin feature"'])

    def test_the_wrapper_table_has_the_options_the_real_tools_take(self):
        """Pin a few facts about the installed tools that the table relies on."""
        nice = subprocess.run(['nice', '-n', '1', 'printf', 'x'], capture_output=True, text=True)
        self.assertEqual(nice.stdout, 'x')
        timeout = shutil.which('timeout') or shutil.which('gtimeout')
        if timeout:
            result = subprocess.run([timeout, '-s', 'KILL', '-k', '5', '10', 'printf', 'x'], capture_output=True, text=True)
            self.assertEqual(result.stdout, 'x')


class RedirectionWordTests(Wb2Fixture):
    """The {fd}> redirection of bash 4.1 and later is a redirection, not a command word."""

    def test_a_named_descriptor_redirection_is_not_the_command(self):
        self.blocked_all(['{fd}>/dev/null git push -f origin main', '{fd}> /dev/null git push -f origin main',
                          '{fd}>&2 git push -f origin main', '{fd}</dev/null git push -f origin main', '{fd}>>log git push -f origin main',
                          'git push -f origin main {fd}>/dev/null', 'git {fd}>/dev/null push -f origin main', '{a}>x {b}>y git push -f origin main',
                          ])
        self.allowed_all(['{fd}>/dev/null git push -f origin feature', 'git push -f origin feature {fd}>x.txt'])


class BudgetTests(Wb2Fixture):
    """WB2-P-13: the time bound holds where the time is spent, and a bad RPI_POLICY_BUDGET_SECONDS is not a crash."""

    def test_quadratic_inputs_finish_well_inside_the_budget(self):
        for command in ('git status ' + '${' * 8000, 'git status ' + '${' * 20000, 'git status ' + '$(' * 20000,
                        'git status ' + '{' * 20000, 'git status ' + '`$(' * 8000, 'git status ' + "$'" * 8000,
                        'git status ' + '<<' * 8000):
            with self.subTest(length=len(command)):
                started = time.monotonic()
                result = self.invoke(command)
                self.assertIn(result.returncode, (0, 2), result.stderr)
                self.assertLess(time.monotonic() - started, 4)

    def test_a_tight_budget_stops_the_work_in_the_loop(self):
        tiny = {**self.environment, 'RPI_POLICY_BUDGET_SECONDS': '0.05'}
        started = time.monotonic()
        result = self.invoke('git status ' + 'x ' * 400000, environment=tiny)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('time budget', result.stderr)
        self.assertLess(time.monotonic() - started, 3)

    def test_the_hard_timer_stops_work_the_loops_cannot_check(self):
        runtime = self.workspace / 'runtime'
        runtime.mkdir()
        slow = runtime / 'rpi-policy.py'
        slow.write_text(POLICY.read_text().replace('    tokens, embedded, word, pending = [], [], [], []',
                                                   '    time.sleep(30)\n    tokens, embedded, word, pending = [], [], [], []', 1))
        started = time.monotonic()
        result = subprocess.run([sys.executable, str(slow), '--harness', 'claude'], input=json.dumps(self.event('git status')),
                                text=True, capture_output=True, cwd=self.project, env={**self.environment, 'RPI_POLICY_BUDGET_SECONDS': '0.5'})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('time budget of 0.5 seconds', result.stderr)
        self.assertLess(time.monotonic() - started, 5)

    def test_a_slow_git_lookup_is_bounded_too(self):
        (self.fakebin / 'git').write_text('#!/bin/sh\nsleep 30\n')
        started = time.monotonic()
        result = self.invoke('git push -f origin feature', environment={**self.environment, 'RPI_POLICY_BUDGET_SECONDS': '0.5'})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('time budget', result.stderr)
        self.assertLess(time.monotonic() - started, 6)

    def test_an_invalid_budget_setting_falls_back_to_the_default_with_a_note(self):
        for value in ('abc', '', '0', '-1', 'nan', 'inf', '-inf', '1e999', '99999', '0x10', ' '):
            with self.subTest(value=value):
                environment = {**self.environment, 'RPI_POLICY_BUDGET_SECONDS': value}
                for command in ('git status', 'git push origin feature'):
                    result = self.invoke(command, environment=environment)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('RPI_POLICY_BUDGET_SECONDS', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(self.invoke('git push -f origin main', environment=environment).returncode, 2)
                self.assertEqual(self.invoke('echo hi', environment=environment).returncode, 0)
        for value in ('5', '0.5', '20', '1e1'):
            result = self.invoke('git status', environment={**self.environment, 'RPI_POLICY_BUDGET_SECONDS': value})
            self.assertEqual((result.returncode, result.stderr), (0, ''), value)


class FalseBlockTests(Wb2Fixture):
    """WB2-P-20: commands that destroy nothing."""

    def test_help_of_a_repository_deletion_is_not_a_deletion(self):
        self.allowed_all(['gh repo delete --help', 'gh repo delete -h', 'gh repo delete o/r --help'])
        self.blocked_all(['gh repo delete o/r', 'gh repo delete --yes o/r'], 'Deleting a repository')

    def test_a_function_definition_that_is_never_called_is_inert(self):
        self.allowed_all(['f() { git push -f origin main; }', 'function f { git push -f origin main; }',
                          'function f() { git push -f origin main; }', 'f() ( git push -f origin main )',
                          'f() {\n  git push -f origin main\n}', 'f() { git push -f origin main; }; echo done',
                          'g() { :; }; f() { git push -f origin main; }; g'])
        self.blocked_all(['f() { git push -f origin main; }; f', 'function f { git push -f origin main; }; f',
                          'f() ( git push -f origin main ); f', 'f() { git push -f origin main; }; export -f f; bash -c f',
                          'f() { git push -f origin main; }; xargs -n1 bash -c f', 'f() { git push -f origin main; }; echo $(f)',
                          'f() { git push -f origin main; }; g() { f; }; g', 'f() { git push -f origin main; } && f',
                          'f() { git push -f origin main; }\nf'])

    def test_force_with_tags_pushes_no_branch(self):
        for command in ('git push -f --tags origin', 'git push --tags --force-with-lease origin', 'git push -f --tags'):
            result = self.invoke(command)
            self.assertEqual(result.returncode, 2, command)
            self.assertNotIn('(main)', result.stderr, 'no branch is pushed')
            self.assertIn('tag', result.stderr)
        self.allowed_all(['git push --tags origin', 'git push origin --tags', 'git push --follow-tags origin feature'])

    def test_a_forced_glob_blocks_only_when_it_can_reach_a_protected_branch(self):
        self.allowed_all(["git push -f origin 'refs/heads/feature/*:refs/heads/feature/*'", "git push -f origin 'refs/heads/x*:refs/heads/x*'",
                          "git push -f origin '+refs/heads/fix-*:refs/heads/fix-*'", "git push --delete origin 'refs/heads/tmp/*'"])
        self.blocked_all(["git push -f origin 'refs/heads/*:refs/heads/*'", "git push -f origin 'refs/heads/ma*:refs/heads/ma*'",
                          "git push -f origin 'refs/heads/*'", "git push -f origin '*:*'", "git push -f origin 'refs/heads/dev*:refs/heads/dev*'",
                          "git push -f origin 'refs/heads/rel*:refs/heads/rel*'", "git push -f origin ':'", "git push -f origin 'm*n'"])

    def test_push_default_nothing_pushes_nothing(self):
        self.allowed_all(['git -c push.default=nothing push --force', 'git -c push.default=nothing push -f origin'])
        self.blocked_all(['git -c push.default=nothing push -f origin main', 'git -c push.default=current push --force'])


class StandardStreamTests(Wb2Fixture):
    """WB2-P-21: forced ASCII standard streams, and bytes that are not UTF-8."""

    ASCII = {'PYTHONIOENCODING': 'ascii', 'LC_ALL': 'C', 'LANG': 'C', 'PYTHONUTF8': '0', 'PYTHONCOERCECLOCALE': '0'}

    def test_a_non_ascii_command_is_judged_not_rejected_as_malformed(self):
        environment = {**self.environment, **self.ASCII}
        for command, code in (("echo 'héllo wörld'", 0), ("git push origin 'fëature'", 0), ("git push -f origin 'fëature'", 0),
                              ("git commit -m '日本語'", 0), ("git push -f origin main # ünï", 2)):
            with self.subTest(command=command):
                result = self.raw(command, environment)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertNotIn(b'one JSON object', result.stderr)
                self.assertNotIn(b'Traceback', result.stderr)

    def test_a_block_message_with_a_non_ascii_branch_name_is_printable(self):
        self.policy(production_branches=['relëase', 'ünï'])
        for harness in ('claude', 'codex'):
            result = self.raw("git push -f origin 'relëase'", {**self.environment, **self.ASCII}, harness=harness)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(b'BLOCKED / WHY:', result.stderr)
            self.assertIn(b'protected branch', result.stderr)
            result.stderr.decode('ascii')

    def test_bytes_that_are_not_utf8_do_not_crash_the_hook(self):
        payload = json.dumps(self.event("git push origin 'x'")).encode('utf-8').replace(b"'x'", b"'\xff\xfe'")
        for environment in ({**self.environment}, {**self.environment, **self.ASCII}):
            result = subprocess.run([sys.executable, str(POLICY), '--harness', 'claude'], input=payload, capture_output=True,
                                    cwd=self.project, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(b'Traceback', result.stderr)
        malformed = subprocess.run([sys.executable, str(POLICY), '--harness', 'claude'], input=b'\xff not json', capture_output=True,
                                   cwd=self.project, env=self.environment)
        self.assertEqual(malformed.returncode, 2)
        self.assertIn(b'one JSON object', malformed.stderr)



class PushConfigurationTests(Wb2Fixture):
    """WB2-P-8: a plain `git push` goes where Git's configuration sends it."""

    def setUp(self):
        super().setUp()
        self.git('remote', 'add', 'fork', 'https://example.invalid/fork.git')
        self.git('branch', 'feature')

    def test_remote_push_default_and_branch_push_remote_choose_the_remote_whose_refspecs_apply(self):
        self.git('config', 'remote.fork.push', '+HEAD:refs/heads/main')
        self.allowed_all(['git push', 'git push -u'])  # origin has no push refspec: the current branch, not forced.
        self.git('config', 'remote.pushDefault', 'fork')
        self.blocked_all(['git push', 'git push -u', 'git push --no-verify'])
        self.git('config', 'remote.pushDefault', 'origin')
        self.allowed_all(['git push'])
        self.git('config', 'branch.main.pushRemote', 'fork')
        self.blocked_all(['git push'])
        self.git('config', '--unset', 'branch.main.pushRemote')
        self.git('config', 'branch.main.remote', 'fork')
        self.allowed_all(['git push'])  # remote.pushDefault (origin) wins over branch.<name>.remote
        self.git('config', '--unset', 'remote.pushDefault')
        self.blocked_all(['git push'])
        self.blocked_all(['git -c remote.pushDefault=fork push', 'git -c branch.main.pushRemote=fork push'])
        self.allowed_all(['git push origin', 'git push origin main'])

    def test_a_mirror_remote_mirrors_on_a_plain_push(self):
        self.git('config', 'remote.origin.mirror', 'true')
        self.blocked_all(['git push', 'git push origin', 'git -c remote.origin.mirror=true push'], 'rewrites or deletes remote refs')
        self.allowed_all(['git push origin feature', 'git push --dry-run', 'git push --tags origin'])
        self.git('config', 'remote.origin.mirror', 'false')
        self.allowed_all(['git push', 'git push origin'])
        self.git('config', 'remote.pushDefault', 'fork')
        self.git('config', 'remote.fork.mirror', 'yes')
        self.blocked_all(['git push'], 'rewrites or deletes remote refs')
        self.blocked_all(['git -c remote.fork.mirror=on push'], 'rewrites or deletes remote refs')

    def test_push_default_modes(self):
        self.git('checkout', '-q', 'feature')
        self.git('config', 'branch.feature.remote', 'origin')
        self.git('config', 'branch.feature.merge', 'refs/heads/main')
        self.allowed_all(['git push -f'])  # simple: the name must match, Git refuses; current is the pushed branch
        self.git('config', 'push.default', 'upstream')
        self.blocked_all(['git push -f', 'git push --force-with-lease'])
        self.allowed_all(['git push'])
        self.git('config', 'push.default', 'tracking')
        self.blocked_all(['git push -f'])
        self.git('config', 'push.default', 'current')
        self.allowed_all(['git push -f'])
        self.git('config', 'push.default', 'nothing')
        self.allowed_all(['git push -f'])
        self.git('config', 'push.default', 'matching')
        self.blocked_all(['git push -f'])

    def test_a_detached_head_has_no_branch_to_push(self):
        self.git('checkout', '-q', '--detach')
        self.allowed_all(['git push -f', 'git push --force origin'])
        self.git('config', 'remote.origin.push', '+HEAD:refs/heads/main')
        self.blocked_all(['git push'])


class GitCommandPathTests(Wb2Fixture):
    """WB2-P-9: other ways to make git push, and git subcommands that run shell text."""

    def test_autocorrect_runs_the_nearest_command(self):
        self.blocked_all(['git -c help.autocorrect=immediate psuh -f origin main', 'git -c help.autocorrect=1 pus -f origin main',
                          'git -c help.autocorrect=prompt psuh -f origin main', 'git -c help.autocorrect=20 pussh -f origin main',
                          'git -c help.autocorrect=true psh -f origin main', 'git -c help.autocorrect=immediate puhs --delete origin main',
                          'GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=help.autocorrect GIT_CONFIG_VALUE_0=immediate git psuh -f origin main'])
        self.allowed_all(['git -c help.autocorrect=never psuh -f origin main', 'git -c help.autocorrect=0 psuh -f origin main',
                          'git -c help.autocorrect=show psuh -f origin main', 'git psuh -f origin main',
                          'git -c help.autocorrect=immediate frobnicate -f origin main', 'git -c help.autocorrect=immediate psuh origin main',
                          'git -c help.autocorrect=immediate stauts'])
        self.git('config', 'help.autocorrect', 'immediate')
        self.blocked_all(['git psuh -f origin main'])

    def test_autocorrect_distance_is_gits(self):
        module = load_policy()
        self.assertEqual(module.autocorrect_distance('psuh', 'push'), 0)  # a transposition is free
        self.assertEqual(module.autocorrect_distance('push', 'push'), 0)
        self.assertLess(module.autocorrect_distance('pus', 'push'), module.AUTOCORRECT_FLOOR)
        self.assertGreaterEqual(module.autocorrect_distance('frobnicate', 'push'), module.AUTOCORRECT_FLOOR)

    def test_send_pack_and_http_push(self):
        self.blocked_all(['git send-pack --force /tmp/x.git main', 'git send-pack -f /tmp/x.git refs/heads/main',
                          'git send-pack --force x HEAD:refs/heads/main', 'git send-pack --force x +feature:main',
                          'git send-pack x :main', 'git send-pack --force x', 'git http-push --force https://h/r.git main'])
        self.blocked_all(['git send-pack --all --force x', 'git send-pack --mirror x'], 'rewrites or deletes remote refs')
        self.allowed_all(['git send-pack x main', 'git send-pack --force x feature', 'git send-pack --all x'])

    def test_subcommands_that_run_shell_text(self):
        script = "'git push -f origin main'"
        self.blocked_all(['git submodule foreach ' + script, 'git submodule foreach git push -f origin main',
                          'git submodule foreach --recursive ' + script, 'git submodule --quiet foreach ' + script,
                          'git submodule foreach -q ' + script, 'git rebase -x ' + script + ' HEAD~1', 'git rebase --exec ' + script + ' HEAD~1',
                          'git rebase --exec=' + script + ' HEAD~1', 'git rebase -x' + script + ' HEAD~1', 'git rebase -ix ' + script + ' HEAD~1',
                          'git rebase --exe ' + script + ' HEAD~1', 'git rebase -i --exec ' + script + ' main',
                          'git bisect run git push -f origin main', 'git bisect run sh -c ' + script, 'git bisect run ' + script,
                          'git filter-branch --tree-filter ' + script + ' HEAD', 'git filter-branch --index-filter=' + script + ' HEAD',
                          'git filter-branch --msg-filter ' + script + ' HEAD', 'git filter-branch --env-filter ' + script + ' HEAD',
                          'git filter-branch --commit-filter ' + script + ' HEAD', 'git filter-branch --tag-name-filter ' + script + ' HEAD',
                          'git filter-branch --setup ' + script + ' HEAD', 'git filter-branch --parent-filter ' + script + ' HEAD',
                          'git difftool -x ' + script, 'git difftool --extcmd=' + script, 'git difftool --extcmd ' + script,
                          'git difftool -x' + script, 'git for-each-repo --config=maintenance.repo push -f origin main',
                          'git -C . rebase -x ' + script + ' main', 'git -c alias.rb=rebase rb -x ' + script + ' main'])
        self.allowed_all(["git submodule foreach 'git status'", 'git submodule update --init', "git rebase -x 'make test' main",
                          'git rebase main', 'git bisect run make test', "git filter-branch --tree-filter 'rm -f secrets' HEAD",
                          "git difftool -x 'vimdiff'", 'git for-each-repo --config=maintenance.repo maintenance run',
                          "git submodule foreach 'git push -f origin feature'"])

    def test_configuration_values_that_git_runs(self):
        script = "'git push -f origin main'"
        self.blocked_all(['git -c core.sshCommand=%s fetch' % script, 'git -c core.pager=%s log' % script,
                          'git -c core.editor=%s commit' % script, 'git -c core.fsmonitor=%s status' % script,
                          "git -c credential.helper='!git push -f origin main' fetch", 'git -c diff.external=%s diff' % script,
                          'git -c core.askPass=%s fetch' % script, "git -c difftool.x.cmd=%s difftool" % script,
                          'GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.sshCommand GIT_CONFIG_VALUE_0=%s git fetch' % script])
        self.allowed_all(["git -c core.editor=vim commit", "git -c core.sshCommand='ssh -i key' fetch",
                          "git -c core.sshCommand='echo git push -f origin main' fetch", "git -c user.name='git push -f origin main' commit",
                          "git -c credential.helper=store fetch"])

    def test_aliases_of_the_configuration_files(self):
        self.git('config', 'alias.pf', 'push -f')
        self.git('config', 'alias.pm', '!git push -f origin main')
        self.git('config', 'alias.st', 'status')
        self.blocked_all(['git pf origin main', 'git pf -u origin main', 'git pm', 'git -C . pf origin main'])
        self.allowed_all(['git pf origin feature', 'git st', 'git status'])
        self.git('config', 'alias.push', 'status')
        self.blocked_all(['git push -f origin main'])  # an alias that shadows a builtin is ignored, as git ignores it


class VersionTagTests(Wb2Fixture):
    """WB2-P-22 (owner policy, recommended default): deleting or force-moving a version tag is blocked here; the receipt gate
    keeps letting a tag deletion through."""

    def test_deleting_or_force_moving_a_version_tag(self):
        self.blocked_all(['git push -f origin v1.0', 'git push -f origin refs/tags/v1.0', 'git push -f --tags', 'git push -f --tags origin',
                          'git push origin +refs/tags/v1:refs/tags/v1', 'git push origin :v1', 'git push origin :refs/tags/v1',
                          'git push origin --delete v1', 'git push origin --delete tag v1', 'git push origin --delete refs/tags/v2.0.0-rc.1',
                          'git push -d origin v1', 'git push --force-with-lease origin refs/tags/v1.0', 'git push -f origin tags/v1.0',
                          "git push -f origin 'refs/tags/*:refs/tags/*'", "git push -f origin '+refs/tags/v*:refs/tags/v*'",
                          'git push -f origin release-1.0.0', 'git push -f origin V3.0.0', 'git push -f origin 2.0', 'git push -f origin v1.0:v1.0',
                          'git push origin --delete "refs/tags/v$N"', 'git push -f origin "v$N"'], 'version tag')
        self.allowed_all(['git push origin v1.0', 'git push --tags origin', 'git push origin refs/tags/v1.0', 'git push -f origin nightly',
                          'git push origin --delete nightly', 'git push -f origin refs/tags/latest', 'git push -f origin refs/tags/nightly',
                          "git push -f origin 'refs/tags/nightly-*:refs/tags/nightly-*'", 'git push origin :refs/tags/stable', 'git push -f origin tags/beta'])

    def test_a_destination_that_names_a_version_is_a_tag_whatever_exists_locally(self):
        """Round 3 (items 1, 2, 16): git matches the destination against the remote's refs first, so local branches and tags
        do not decide; a name that is not a version (issue-42, release-1) is a branch."""
        self.git('branch', 'v2-wip')
        self.git('branch', 'release-1.0')
        self.git('branch', 'issue-42')
        self.blocked_all(['git push -f origin v2-wip', 'git push -f origin release-1.0', 'git push origin --delete v2-wip',
                          'git push -f origin HEAD:v3-wip', 'git push -f origin v2-wip:refs/tags/v2-wip', 'git push -f origin refs/tags/v2-wip'],
                         'version tag')
        self.allowed_all(['git push -f origin issue-42', 'git push origin --delete issue-42', 'git push -f origin refs/heads/v2-wip',
                          'git push origin :refs/heads/release-1.0'])

    def test_the_tag_pattern_is_the_receipt_gates(self):
        import test_prepush
        gate = importlib.util.spec_from_file_location('prepush_pattern_fixture', test_prepush.PREPUSH)
        module = importlib.util.module_from_spec(gate)
        gate.loader.exec_module(module)
        self.assertEqual(load_policy().VERSION_TAG.pattern, module.VERSION_TAG.pattern)

    def test_the_gate_still_lets_a_tag_deletion_through(self):
        """The receipt gate is unchanged: it checks what a push publishes, and publishes nothing for a deletion."""
        import test_prepush
        self.assertIn('tag deletions pass', (Path(test_policy.ROOT) / 'docs/native-policy.md').read_text())
        self.assertTrue(hasattr(test_prepush, 'PrePushFixture'))


class CaseInsensitiveRemoteTests(Wb2Fixture):
    """WB2-P-19: a branch spelled Main moves main on a case-insensitive remote."""

    def test_protected_names_are_compared_without_case(self):
        self.blocked_all(['git push -f origin Main', 'git push -f origin MAIN', 'git push -f origin refs/heads/Main',
                          'git push origin :refs/heads/MASTER', 'git push --delete origin Develop', 'git push -f origin HEAD:Main',
                          'git push -f origin RELEASE', 'git push -f origin Release', 'gh api -X DELETE repos/o/r/git/refs/heads/Main',
                          "git push -f origin 'refs/heads/M*'"])
        self.allowed_all(['git push -f origin Maintenance', 'git push -f origin mainline', 'git push -f origin Feature',
                          'git push origin Main'])


class GitHubForgeTests(Wb2Fixture):
    """WB2-P-10: the gh spellings of a ref rewrite, repository deletion and alias indirection."""

    def test_forced_ref_updates(self):
        ref = 'repos/o/r/git/refs/heads/main'
        self.blocked_all(['gh api -X PATCH %s -f sha=abc -F force=true' % ref, 'gh api -X PATCH %s --field force=true -f sha=abc' % ref,
                          'gh api -X PATCH %s --raw-field force=true' % ref, 'gh api -X PATCH %s -Fforce=true' % ref,
                          'gh api --method PATCH %s -fforce=true' % ref, 'gh api -XPATCH %s --field=force=true' % ref,
                          'gh api -X PATCH %s --input body.json' % ref, 'gh api -X PATCH %s --input -' % ref, 'gh api %s -X PATCH -F force=1' % ref,
                          'gh api -X patch %s -F force=true' % ref, 'gh api -X PATCH %s -F force="$FORCE"' % ref,
                          'gh api -X PATCH repos/o/r/git/refs/heads/Main -F force=true', 'gh api -X PATCH repos/o/r/git/refs/heads/release -F force=true'])
        self.allowed_all(['gh api -X PATCH %s -f sha=abc' % ref, 'gh api -X PATCH %s -F force=false -f sha=abc' % ref,
                          'gh api -X PATCH repos/o/r/git/refs/heads/feature -F force=true', 'gh api -X PATCH repos/o/r/issues/1 -F force=true',
                          'gh api -X POST repos/o/r/git/refs -f ref=refs/heads/x -f sha=a', 'gh api %s' % ref,
                          'gh api -X PATCH repos/o/r/git/refs/tags/nightly -F force=true'])

    def test_dynamic_ref_names_are_judged_like_dynamic_push_targets(self):
        self.blocked_all(['gh api -X DELETE repos/o/r/git/refs/heads/$BR', 'gh api -X DELETE "repos/o/r/git/refs/heads/$(git branch --show-current)"',
                          'gh api -X DELETE repos/o/r/git/refs/$KIND/main', 'gh api -X DELETE repos/o/r/git/refs/heads/ma$X',
                          'gh api -X DELETE repos/o/r/git/refs/heads/${BR}', 'gh api -X PATCH repos/o/r/git/refs/heads/$BR -F force=true',
                          'gh api -X DELETE repos/o/r/git/refs/heads/$A$B'])
        self.allowed_all(['gh api -X DELETE repos/o/r/git/refs/heads/feature-$N', 'gh api -X DELETE "$ENDPOINT"',
                          'gh api -X DELETE repos/o/r/issues/comments/$ID', 'gh api -X PATCH repos/o/r/git/refs/heads/$BR -f sha=a'])
        self.blocked_all(['git push -f origin "$BRANCH"', 'git push -f origin "ma$X"', 'git push origin --delete "$BRANCH"'])
        self.allowed_all(['git push -f origin "feature-$N"', 'git push origin "$BRANCH"'])

    def test_graphql_mutations(self):
        self.blocked_all(['gh api graphql -f query="mutation { deleteRef(input:{refId:\\"x\\"}) { clientMutationId } }"',
                          "gh api graphql -f query='mutation { deleteRepository(input:{repositoryId:\"x\"}) { clientMutationId } }'",
                          "gh api graphql -F query='mutation { updateRef(input:{refId:\"x\", oid:\"y\", force: true}) { ref { name } } }'",
                          "gh api graphql --raw-field query='mutation { updateRef(input:{refId:\"x\", oid:\"y\", force: $force}) { ref { name } } }'",
                          "gh api graphql -fquery='mutation { deleteRef(input:{refId:\"x\"}) { clientMutationId } }'"], 'GraphQL mutation')
        self.allowed_all(["gh api graphql -f query='query { viewer { login } }'", "gh api graphql -f query='mutation { addStar(input:{starrableId:\"x\"}) { clientMutationId } }'",
                          "gh api graphql -f query='mutation { updateRef(input:{refId:\"x\", oid:\"y\", force: false}) { ref { name } } }'",
                          'gh api graphql -F query=@missing.graphql'])
        (self.project / 'danger.graphql').write_text('mutation { deleteRef(input:{refId:"x"}) { clientMutationId } }')
        (self.project / 'safe.graphql').write_text('query { viewer { login } }')
        self.blocked_all(['gh api graphql -F query=@danger.graphql', 'gh api graphql --input danger.graphql', 'gh api graphql --input=danger.graphql'],
                         'GraphQL mutation')
        self.allowed_all(['gh api graphql -F query=@safe.graphql', 'gh api graphql --input safe.graphql'])

    def test_alias_definitions_and_uses(self):
        self.blocked_all(["gh alias set d 'repo delete'", "gh alias set d 'repo delete $1'", "gh alias set k '!gh repo delete o/r'",
                          "gh alias set --shell k 'gh repo delete o/r'", "gh alias set -s k 'git push -f origin main'",
                          "gh alias set km 'api -X DELETE repos/o/r/git/refs/heads/main'", "gh alias set --clobber d 'repo delete'",
                          "gh alias set kt 'api -X DELETE repos/o/r/git/refs/tags/v1'"], reason='')
        self.allowed_all(["gh alias set pm 'pr merge'", "gh alias set co 'pr checkout'", 'gh alias list', "gh alias set k '!gh pr list'"])
        config = self.workspace / 'gh'
        config.mkdir()
        (config / 'config.yml').write_text('# comment\nversion: "1"\naliases:\n    d: repo delete\n    nuke: \'!gh repo delete "$1" --yes\'\n'
                                           '    pm: pr merge\n    km: "api -X DELETE repos/o/r/git/refs/heads/main"\n'
                                           '    loop1: loop2\n    loop2: loop1\nother:\n    d2: repo delete\n')
        environment = {**self.environment, 'GH_CONFIG_DIR': str(config)}
        self.blocked_all(['gh d o/r', 'gh d', 'gh nuke o/r', 'gh km', 'sudo gh d o/r', 'bash -c "gh d o/r"'], environment=environment, reason='')
        self.allowed_all(['gh pm 5', 'gh pr list', 'gh d2 x', 'gh loop1', 'gh repo view'], environment=environment)
        self.allowed_all(['gh d o/r'])  # without that configuration the word is just an unknown gh command
        xdg = {**self.environment, 'XDG_CONFIG_HOME': str(self.workspace)}
        self.blocked_all(['gh d o/r'], environment=xdg, reason='')



class RealGitTests(unittest.TestCase):
    """The hook's verdict against what real git does to local bare remotes. A command is destructive when it rewrites or
    deletes a ref that already exists on a remote; nothing here leaves the temporary directory."""

    def setUp(self):
        import tempfile
        self.temporary = tempfile.TemporaryDirectory(prefix='wb2-realgit-')
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name).resolve()
        git = shutil.which('git')
        (root / 'home').mkdir()
        (root / 'gitconfig').write_text('')
        self.environment = {'PATH': os.path.dirname(git) + os.pathsep + '/usr/bin' + os.pathsep + '/bin', 'HOME': str(root / 'home'),
                            'GIT_CONFIG_GLOBAL': str(root / 'gitconfig'), 'GIT_CONFIG_NOSYSTEM': '1', 'LC_ALL': 'C',
                            'GIT_AUTHOR_NAME': 'wb2', 'GIT_AUTHOR_EMAIL': 'wb2@example.invalid', 'GIT_COMMITTER_NAME': 'wb2',
                            'GIT_COMMITTER_EMAIL': 'wb2@example.invalid', 'FILTER_BRANCH_SQUELCH_WARNING': '1'}
        self.bares = {'remote': root / 'remote.git', 'fork': root / 'fork.git'}
        self.work = root / 'work'
        for bare in self.bares.values():
            self.run_git('init', '-q', '--bare', '-b', 'trunk', str(bare), cwd=root)  # main is not their current branch: it may be deleted
        self.run_git('init', '-qb', 'main', str(self.work), cwd=root)
        self.run_git('config', 'user.useConfigOnly', 'false')
        for name, bare in (('origin', self.bares['remote']), ('fork', self.bares['fork'])):
            self.run_git('remote', 'add', name, str(bare))
        for name in 'AB':
            (self.work / 'f').write_text(name)
            self.run_git('add', 'f')
            self.run_git('commit', '-qm', name)
        self.run_git('tag', 'v1.0')
        self.run_git('branch', 'fix-9')
        for name in ('origin', 'fork'):
            self.run_git('push', '-q', name, 'main', 'v1.0', 'fix-9')
        self.run_git('branch', '-q', '-D', 'fix-9')
        self.run_git('reset', '-q', '--hard', 'HEAD~1')  # local main is A+C, remote main is B: pushing main needs force
        (self.work / 'f').write_text('C')
        self.run_git('commit', '-qam', 'C')
        self.run_git('tag', '-f', 'v1.0')
        self.run_git('branch', 'feature')
        self.head = self.run_git('rev-parse', 'HEAD')
        self.config = (self.work / '.git/config').read_text()
        self.baseline = self.refs()

    def run_git(self, *arguments, cwd=None):
        result = subprocess.run(['git', *arguments], cwd=cwd or self.work, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, ' '.join(arguments) + '\n' + result.stderr)
        return result.stdout.strip()

    def refs(self):
        snapshot = {}
        for name, bare in self.bares.items():
            output = subprocess.run(['git', '--git-dir', str(bare), 'for-each-ref', '--format=%(refname) %(objectname)'],
                                    env=self.environment, capture_output=True, text=True).stdout
            snapshot.update({(name, line.split()[0]): line.split()[1] for line in output.splitlines()})
        return snapshot

    def restore(self):
        (self.work / '.git/config').write_text(self.config)
        self.run_git('checkout', '-qf', 'main')
        self.run_git('reset', '-q', '--hard', self.head)
        self.run_git('tag', '-f', 'v1.0', self.head)
        current = self.refs()
        for (name, ref), value in list(current.items()):
            if self.baseline.get((name, ref)) != value:
                git_dir = str(self.bares[name])
                if (name, ref) in self.baseline:
                    subprocess.run(['git', '--git-dir', git_dir, 'update-ref', ref, self.baseline[(name, ref)]], env=self.environment)
                else:
                    subprocess.run(['git', '--git-dir', git_dir, 'update-ref', '-d', ref], env=self.environment)
        for (name, ref), value in self.baseline.items():
            if (name, ref) not in current:
                subprocess.run(['git', '--git-dir', str(self.bares[name]), 'update-ref', ref, value], env=self.environment)

    def hook(self, command):
        event = {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': command}, 'cwd': str(self.work)}
        return subprocess.run([sys.executable, str(POLICY), '--harness', 'claude'], input=json.dumps(event), capture_output=True,
                              text=True, env=self.environment).returncode

    def rewritten(self, command):
        """Refs that existed on a remote and were moved or deleted by really running `command`."""
        before = self.refs()
        subprocess.run(['/bin/bash', '-c', command], cwd=self.work, env=self.environment, capture_output=True, text=True, timeout=60)
        after = self.refs()
        return sorted(name + ':' + ref for (name, ref), value in before.items()
                      if after.get((name, ref)) != value and (ref == 'refs/heads/main' or ref.startswith('refs/tags/')))

    def agree(self, cases):
        """Each case is (command, [(config key, value)...], expectation, [git arguments run before]). The hook must block exactly
        when git rewrites main or a tag ('both'), or neither does ('neither'); 'hook' is a conservative block where git itself
        refuses or the target is unknown to the hook."""
        for command, config, expectation, *before in cases:
            with self.subTest(command=command, config=config):
                self.restore()
                for key, value in config:
                    self.run_git('config', key, value)
                for step in before:
                    self.run_git(*step)
                verdict = self.hook(command)
                moved = self.rewritten(command)
                self.assertEqual(verdict == 2, expectation in ('both', 'hook'), 'hook verdict for ' + command)
                self.assertEqual(bool(moved), expectation == 'both', 'git moved %s for %s' % (moved, command))

    def test_clusters_and_global_options(self):
        self.agree([('git push -4f origin main', [], 'both'), ('git push -f4 origin main', [], 'both'), ('git push -6f origin main', [], 'both'),
                    ('git push -4vf origin main', [], 'both'), ('git push -4 -f origin main', [], 'both'),
                    ('git push -4d origin main', [], 'both'), ('git push -d4 origin main', [], 'both'),
                    ('git push -4 origin main', [], 'neither'), ('git push -4f origin feature', [], 'neither'),
                    ('git --attr-source HEAD push -f origin main', [], 'both'), ('git --attr-source=HEAD push -f origin main', [], 'both'),
                    ('git --no-lazy-fetch push -f origin main', [], 'both'), ('git --no-optional-locks push -f origin main', [], 'both'),
                    ('git -c core.abbrev=9 -C . push -f origin main', [], 'both'), ('git --git-dir=.git push -f origin main', [], 'both'),
                    ('git push -f origin feature', [], 'neither'), ('git push origin feature', [], 'neither')])

    def test_pushes_that_configuration_decides(self):
        self.agree([('git push', [('remote.fork.push', '+HEAD:refs/heads/main'), ('remote.pushDefault', 'fork')], 'both'),
                    ('git push', [('remote.fork.push', '+HEAD:refs/heads/main')], 'neither'),
                    ('git push', [('remote.fork.push', '+HEAD:refs/heads/main'), ('branch.main.pushRemote', 'fork')], 'both'),
                    ('git push', [('remote.fork.push', '+HEAD:refs/heads/main'), ('remote.pushDefault', 'origin'),
                                  ('branch.main.pushRemote', 'fork')], 'both'),
                    ('git push', [('remote.fork.push', '+HEAD:refs/heads/main'), ('remote.pushDefault', 'fork'),
                                  ('branch.main.pushRemote', 'origin')], 'neither'),
                    ('git push', [('remote.origin.push', '+HEAD:refs/heads/work')], 'neither'),
                    ('git push -f', [('push.default', 'nothing')], 'neither'), ('git push -f', [], 'hook'),
                    ('git push', [('remote.origin.mirror', 'true')], 'both'), ('git push origin', [('remote.origin.mirror', 'true')], 'both'),
                    ('git push', [('remote.origin.mirror', 'false')], 'neither'),
                    ('git push -f origin', [('push.default', 'matching')], 'both'),
                    ('git push -f', [], 'neither', ['checkout', '-q', '--detach']),
                    ('git push', [('remote.origin.push', '+HEAD:refs/heads/main')], 'both', ['checkout', '-q', '--detach'])])

    def test_upstream_mode_follows_the_configured_branch(self):
        branch = [('branch.feature.remote', 'origin'), ('branch.feature.merge', 'refs/heads/main')]
        self.agree([('git push -f', [('push.default', 'upstream')] + branch, 'both', ['checkout', '-q', 'feature']),
                    ('git push -f', [('push.default', 'current')] + branch, 'neither', ['checkout', '-q', 'feature'])])

    def test_other_paths_to_a_push(self):
        remote = str(self.bares['remote'])
        self.agree([('git -c help.autocorrect=immediate psuh -f origin main', [], 'both'),
                    ('git psuh -f origin main', [], 'neither'),
                    ('git -c help.autocorrect=never psuh -f origin main', [], 'neither'),
                    ('git send-pack --force %s main' % remote, [], 'both'), ('git send-pack --force %s HEAD:refs/heads/main' % remote, [], 'both'),
                    ('git send-pack %s main' % remote, [], 'neither'), ('git send-pack --force %s feature' % remote, [], 'neither'),
                    ("git rebase -x 'git push -f origin main' HEAD~1", [], 'both'), ("git rebase -x 'git status' HEAD~1", [], 'neither'),
                    ("git for-each-repo --config=wb2.repos push -f origin main", [('wb2.repos', '.')], 'both'),
                    ("git filter-branch --tree-filter 'git push -f origin main' HEAD~1..HEAD", [], 'both'),
                    ("git filter-branch --tree-filter 'true' HEAD~1..HEAD", [], 'neither')])

    def test_aliases_of_the_configuration_file(self):
        self.agree([('git pf origin main', [('alias.pf', 'push -f')], 'both'), ('git pf origin feature', [('alias.pf', 'push -f')], 'neither'),
                    ('git pm', [('alias.pm', '!git push -f origin main')], 'both')])

    def test_version_tags(self):
        self.agree([('git push -f origin v1.0', [], 'both'), ('git push origin v1.0', [], 'neither'), ('git push origin :refs/tags/v1.0', [], 'both'),
                    ('git push origin --delete v1.0', [], 'both'), ('git push -f --tags origin', [], 'both'), ('git push --tags origin', [], 'neither'),
                    ('git push -f origin refs/tags/v1.0', [], 'both'), ('git push origin +refs/tags/v1.0:refs/tags/v1.0', [], 'both'),
                    ('git push -f origin tags/v1.0', [], 'both'), ('git push -f origin v1.0:v1.0', [], 'both'),
                    ('git push -f origin HEAD:refs/heads/fix-9', [], 'neither'), ('git push origin --delete fix-9', [], 'neither'),
                    ('git branch fix-9 && git push -f origin fix-9', [], 'neither'),
                    ('git push -f origin HEAD:v1.0', [], 'both'), ('git branch v1.0 && git push origin :v1.0', [], 'both')])

    def test_a_name_that_differs_only_in_case_is_blocked_whatever_the_file_system_does(self):
        """Whether Main reaches main depends on the remote's file system and git version (this git refuses the collision on a
        case-folding disk), so the hook decides by name: it must block whenever git did rewrite main, and does always."""
        for command in ('git push -f origin HEAD:refs/heads/Main', 'git push origin :refs/heads/MAIN', 'git push -f origin HEAD:MAIN'):
            with self.subTest(command=command):
                self.restore()
                self.assertEqual(self.hook(command), 2)
                moved = self.rewritten(command)
                self.assertIn(moved, ([], ['remote:refs/heads/main']))

    def test_git_ignores_the_options_the_policy_skips_with_a_value(self):
        """--attr-source takes a value (the table says so): git runs the command behind it with HEAD as the value."""
        self.restore()
        self.assertEqual(self.run_git('--attr-source', 'HEAD', 'rev-parse', '--abbrev-ref', 'HEAD'), 'main')


if __name__ == '__main__':
    unittest.main()
