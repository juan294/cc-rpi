"""Branch-name spelling and shell/gh spelling coverage of the pre-action denylist."""
import json
import subprocess
import unittest

import test_policy
import test_prepush


class BranchSpellingTests(test_policy.PolicyFixture):
    PREFIXED = {'integration_branch': 'refs/heads/release', 'production_branches': ['prod', 'refs/heads/prod2']}

    def test_refs_heads_prefixed_policy_branches_are_protected(self):
        self.policy(**self.PREFIXED)
        for command in ('git push -f origin release', 'git push -f origin prod', 'git push -f origin prod2',
                        'git push origin +HEAD:refs/heads/prod2', 'git push --delete origin release',
                        'gh api -X DELETE repos/o/r/git/refs/heads/release',
                        'gh api -X DELETE repos/o/r/git/refs/heads/prod2'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
        for command in ('git push -f origin feature', 'git push origin release', 'git push origin prod2',
                        'gh api -X DELETE repos/o/r/git/refs/heads/feature'):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_plain_name_policy_behaves_as_before(self):
        self.policy(integration_branch='release', production_branches=['prod'])
        for command in ('git push -f origin release', 'git push -f origin prod',
                        'gh api -X DELETE repos/o/r/git/refs/heads/release'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
        self.assert_allowed('git push -f origin feature')

    def test_a_prefixed_name_is_one_normalization_for_every_consumer(self):
        # The same declaration the receipt gate accepts must protect the same branch here.
        self.policy(**self.PREFIXED)
        import importlib.util
        spec = importlib.util.spec_from_file_location('policy_branch_fixture', test_policy.POLICY)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        policy = json.loads((self.project / '.rpi/policy.json').read_text())
        self.assertEqual(module.integration_branch(self.project, policy), 'release')
        self.assertEqual(module.production_branches(policy), {'prod', 'prod2'})


class ShellAndApiSpellingTests(test_policy.PolicyFixture):
    def setUp(self):
        super().setUp()
        self.git('checkout', '-qb', 'main')

    def test_shell_spellings_with_options_before_or_after_c_are_inspected(self):
        script = "'git push -f origin main'"
        for prefix in ('bash -c', 'bash -ec', 'bash -xec', 'bash -o pipefail -c', 'bash -O extglob -c', 'sh -e -c',
                       'bash -c -e', 'bash -c -x', 'bash -e -c -x', 'zsh -c -e', 'bash -c +e', 'bash -o pipefail -c -e',
                       'bash -c -o pipefail', 'bash -c -O extglob', 'sh -c --', 'bash --norc -c'):
            with self.subTest(prefix=prefix):
                self.assert_blocked(prefix + ' ' + script, 'protected branch')

    def test_value_taking_long_options_do_not_hide_the_script(self):
        script = "'git push -f origin main'"
        for prefix in ('bash --rcfile rc -c', 'bash --init-file rc -c', 'bash --rcfile=rc -c', 'bash --init-file=rc -c',
                       'bash --norc --noprofile -c', 'bash -c --rcfile rc', 'bash --posix --rcfile rc -e -c',
                       'zsh -o pipefail --login -c', 'bash --debugger --verbose -c'):
            with self.subTest(prefix=prefix):
                self.assert_blocked(prefix + ' ' + script, 'protected branch')
        self.assert_allowed("bash --rcfile rc script.sh 'git push -f origin main'")  # script.sh is the script, not -c text

    def test_a_shell_without_c_does_not_inspect_its_first_word_as_a_script(self):
        self.assert_allowed("bash -e 'git push -f origin main'")  # A script file name, not a -c command.
        self.assert_allowed("bash -c 'git status'")

    def test_api_delete_attached_and_separate_method_spellings(self):
        for method in ('-X DELETE', '-XDELETE', '-Xdelete', '--method DELETE',
                       '--method=DELETE', '--method=delete', '-X=DELETE'):
            with self.subTest(method=method):
                self.assert_blocked('gh api ' + method + ' repos/o/r', 'irreversible')
                self.assert_blocked('gh api repos/o/r/git/refs/heads/main ' + method, 'protected branch')
        self.assert_allowed('gh api -XGET repos/o/r')
        self.assert_allowed('gh api -XPOST repos/o/r/issues')
        self.assert_allowed('gh api -XDELETE repos/o/r/git/refs/heads/feature/old')


class GitCommandLineConfigTests(test_policy.PolicyFixture):
    """`git -c key=value` settings change what a push does, so they are evaluated, not skipped."""

    def setUp(self):
        super().setUp()
        self.git('checkout', '-qb', 'feature/work')

    def test_command_line_aliases_are_expanded(self):
        for command in ("git -c alias.p=push p -f origin main", "git -c alias.p='push -f' p origin main",
                        "git -c alias.p='push --force-with-lease origin' p main",
                        "git -c alias.p='!git push -f origin main' p", "git -c alias.q=p -c alias.p=push q --force origin develop",
                        "git -C . -c alias.p=push p -f origin main"):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
        for command in ("git -c alias.p=push p origin feature/work", "git -c alias.p=push p -f origin feature/work",
                        "git -c alias.p=status p -f", "git -c alias.p='!git push origin main' p", "git -c alias.p=push p origin main"):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_an_alias_that_shadows_a_git_builtin_is_ignored_as_git_does(self):
        for command in ("git -c alias.push=true push -f origin main", "git -c alias.push=status push -f origin develop",
                        "git -c alias.push='!true' push --force origin main", "git -c alias.p=push p -f origin main"):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
        for command in ("git -c alias.status=push status", "git -c alias.log='push -f origin main' log",
                        "git -c alias.commit='!git push -f origin main' commit -m x"):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_environment_injected_git_configuration_is_applied_like_git_c(self):
        for command in ("GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0='push -f' git p origin main",
                        "GIT_CONFIG_PARAMETERS=\"'alias.p'='push -f'\" git p origin main",
                        "PUSHF='push -f' git --config-env=alias.p=PUSHF p origin main",
                        "PUSHF='push -f' git --config-env alias.p=PUSHF p origin main",
                        "env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0='push -f' git p origin main",
                        "GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=user.name GIT_CONFIG_VALUE_0=x GIT_CONFIG_KEY_1=push.default "
                        "GIT_CONFIG_VALUE_1=matching git push -f",
                        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.push GIT_CONFIG_VALUE_0=+HEAD:main git push",
                        "GIT_CONFIG_PARAMETERS=\"'remote.origin.push'='+HEAD:main'\" git push"):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
        for command in ("GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=user.name GIT_CONFIG_VALUE_0=x git push origin feature/work",
                        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.status GIT_CONFIG_VALUE_0=push git status",
                        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.push GIT_CONFIG_VALUE_0=status git push origin feature/work",
                        "GIT_CONFIG_COUNT=0 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0='push -f' git p origin main",
                        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0='push -f' git p origin feature/work",
                        "git --config-env=alias.p=NOT_SET_HERE p -f origin main",
                        "GIT_CONFIG_PARAMETERS=\"'user.name'='x'\" git push origin feature/work",
                        "FOO=bar git push origin feature/work"):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_builtins_outside_the_static_list_come_from_git_itself(self):
        listed = subprocess.run(['git', '--list-cmds=builtins'], capture_output=True, text=True).stdout.split()
        if 'maintenance' not in listed:
            self.skipTest('this git does not list maintenance as a builtin')
        self.assert_allowed("git -c alias.maintenance='push -f origin main' maintenance")

    def test_command_line_push_configuration_is_applied_to_unnamed_pushes(self):
        for command in ("git -c push.default=matching push -f", "git -c push.default=matching push --force origin",
                        "git -c remote.origin.push=+refs/heads/*:refs/heads/* push",
                        "git -c remote.origin.push=+HEAD:main push", "git -c remote.origin.push=:main push",
                        "git -c remote.origin.push=refs/heads/feature/work:main push -f",
                        "git -c remote.origin.push=refs/heads/*:refs/heads/* push -f"):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
        for command in ("git -c push.default=current push -f", "git -c push.default=matching push",
                        "git -c remote.origin.push=+refs/heads/feature/work:refs/heads/feature/work push",
                        "git -c user.name=x push -f", "git -c remote.other.push=+HEAD:main push -f origin"):
            with self.subTest(command=command):
                self.assert_allowed(command)


class ReceiptGateAgreesWithPolicyHookTests(test_prepush.PrePushFixture):
    def test_prefixed_integration_branch_is_the_branch_the_gate_guards(self):
        self.policy(integration_branch='refs/heads/release', require_verification_receipt=True)
        self.commit('Opt in on a prefixed integration branch')
        self.assert_refused(self.line('refs/heads/release'), reason='verification evidence is missing')
        self.assert_passes(self.line('refs/heads/feature'))
        self.evidence()
        self.assert_passes(self.line('refs/heads/release'))
        # And the pre-action hook protects the same branch from a rewrite.
        self.assert_blocked('git push -f origin release', 'protected branch')


    def test_dirty_tree_refusal_prints_the_full_first_file_name(self):
        self.policy(require_verification_receipt=True)
        self.commit('Opt in')
        self.evidence()
        (self.project / 'README.md').write_text('Changed after verification.\n')
        (self.project / 'new file.txt').write_text('Untracked.\n')
        result = self.assert_refused(self.line('refs/heads/develop'), reason='clean')
        reason = result.stderr.split(' / FIX:')[0]
        self.assertIn('(README.md, new file.txt)', reason)
        self.git('checkout', '--', 'README.md')
        (self.project / 'new file.txt').unlink()
        (self.project / 'a.txt').write_text('Untracked only.\n')
        result = self.assert_refused(self.line('refs/heads/develop'), reason='clean')
        self.assertIn('(a.txt)', result.stderr.split(' / FIX:')[0])


if __name__ == '__main__':
    unittest.main()
