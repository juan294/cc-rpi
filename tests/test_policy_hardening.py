"""Branch-name spelling and shell/gh spelling coverage of the pre-action denylist."""
import json
import os
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

    def test_api_delete_in_clusters_urls_and_encoded_paths(self):
        blocked = {
            'gh api -iX DELETE repos/o/r/git/refs/heads/main': 'protected branch',
            'gh api -iXDELETE repos/o/r/git/refs/heads/main': 'protected branch',
            'gh api -iiX DELETE repos/o/r/git/refs/heads/main': 'protected branch',
            'gh api -X DELETE https://api.github.com/repos/o/r/git/refs/heads/main': 'protected branch',
            'gh api -X DELETE https://ghe.example.com/api/v3/repos/o/r/git/refs/heads/main': 'protected branch',
            'gh api -X DELETE repos/o/r/git/refs/heads%2Fmain': 'protected branch',
            'gh api -X DELETE repos/o/r/git/refs/heads/%6Dain': 'protected branch',
            'gh api -X DELETE "repos/o/r/git/refs/heads/main?x=1"': 'protected branch',
            'gh api -X DELETE "repos/o/r/git/refs/heads/main#frag"': 'protected branch',
            'gh api -X DELETE /repos/o/r/git/refs/heads/main/': 'protected branch',
            'gh api -iX DELETE https://api.github.com/repos/o/r': 'irreversible',
            'gh api -X DELETE "repos/o/r?x=1"': 'irreversible',
            'gh api -X DELETE repos/o/r%2F': 'irreversible',
        }
        for command, reason in blocked.items():
            with self.subTest(command=command):
                self.assert_blocked(command, reason)
        for command in ('gh api -X GET repos/o/r/git/refs/heads/main', 'gh api -iX GET repos/o/r', 'gh api -iXGET repos/o/r',
                        'gh api repos/o/r/pulls', 'gh api -iX DELETE repos/o/r/git/refs/heads/feature%2Fold',
                        'gh api -X DELETE https://api.github.com/repos/o/r/issues/comments/1', 'gh api -i repos/o/r',
                        'gh api -X DELETE "repos/o/r/git/refs/heads/feature?x=main"'):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_api_delete_paths_are_normalised_before_matching(self):
        for command in ('gh api -X DELETE repos/o/r/git/refs/heads//main', 'gh api -X DELETE repos/o/r/git/refs/heads/./main',
                        'gh api -X DELETE repos/o/r/git/refs/heads/x/../main', 'gh api -X DELETE //repos/o/r/git/refs/heads/main',
                        'gh api -X DELETE https://api.github.com//repos/o/r/git/refs/heads/main',
                        'gh api -X DELETE https://api.github.com/repos//o/r/git/refs/heads/main',
                        'gh api -X DELETE repos/o/r/git/refs/heads/x/%2e%2e/main',
                        'gh api -X DELETE repos/o/r/git/refs/heads/x/%2E%2E%2Fmain',
                        'gh api -X DELETE repos/o/r/git/refs/heads/../../../../../../../../x',
                        'gh api -X DELETE repos/o/r/./git/refs/heads/main'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
        self.assert_blocked('gh api -X DELETE repos/o/r/git/refs/heads/../../..', 'irreversible')
        self.assert_blocked('gh api -X DELETE repos//o/r', 'irreversible')
        for command in ('gh api -X DELETE repos/o/r/git/refs/heads/feature', 'gh api repos/o/r/pulls',
                        'gh api -X GET repos/o/r/git/refs/heads//main', 'gh api -X DELETE repos/o/r/git/refs/heads/x/../feature',
                        'gh api -X DELETE repos/o/r/issues/comments/../comments/1'):
            with self.subTest(command=command):
                self.assert_allowed(command)

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

    @staticmethod
    def chain(length, tail, *, bang=False, first='a1'):
        """-c options for a chain a1 -> a2 -> ... -> aN, whose last alias runs `tail` (a git command line)."""
        links = ["-c 'alias.a%d=%sa%d'" % (number, '!git ' if bang else '', number + 1) for number in range(1, length)]
        links.append("-c 'alias.a%d=%s'" % (length, ('!git ' if bang else '') + tail))
        return ' '.join(links), first

    def test_alias_chains_of_any_realistic_length_are_followed(self):
        for length in (6, 10, 50):
            options, first = self.chain(length, 'push -f origin main')
            with self.subTest(length=length, form='plain'):
                self.assert_blocked('git %s %s' % (options, first), 'protected branch')
            options, first = self.chain(length, 'push -f origin main', bang=True)
            with self.subTest(length=length, form='shell'):
                self.assert_blocked('git %s %s' % (options, first), 'protected branch')
        for length in (6, 10, 50):
            for bang in (False, True):
                options, first = self.chain(length, 'push -f origin feature/work', bang=bang)
                with self.subTest(length=length, bang=bang, allowed=True):
                    self.assert_allowed('git %s %s' % (options, first))

    def test_alias_cycles_terminate_and_are_not_pushes(self):
        for command in ("git -c alias.a=b -c alias.b=a a", "git -c alias.a=b -c alias.b=a status",
                        "git -c alias.a='!git b' -c alias.b='!git a' a", "git -c alias.a=a a -f origin main",
                        "git -c alias.a='!git a' a"):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_a_chain_beyond_the_hard_cap_is_unclassifiable_and_passes(self):
        options, first = self.chain(150, 'push -f origin main')
        self.assert_allowed('git %s %s' % (options, first))

    def test_environment_forms_follow_chains_the_same_way(self):
        pairs = ['GIT_CONFIG_KEY_%d=alias.a%d GIT_CONFIG_VALUE_%d=%s' % (number, number + 1, number, 'a%d' % (number + 2) if number < 7 else 'push')
                 for number in range(0, 8)]
        env = 'GIT_CONFIG_COUNT=8 ' + ' '.join(pairs)
        self.assert_blocked(env + ' git a1 -f origin main', 'protected branch')
        self.assert_allowed(env + ' git a1 -f origin feature/work')
        variables = ' '.join('V%d=a%d' % (number, number + 1) for number in range(1, 7)) + ' V7=push'
        options = ' '.join('--config-env=alias.a%d=V%d' % (number, number) for number in range(1, 8))
        self.assert_blocked('%s git %s a1 -f origin main' % (variables, options), 'protected branch')
        self.assert_allowed('%s git %s a1 -f origin feature/work' % (variables, options))

    def test_an_alias_value_that_starts_with_global_options_is_re_stripped(self):
        for command in ("git -c 'alias.p=-c a.b=c push' p -f origin main", "git -c 'alias.p=-p push' p -f origin main",
                        "git -c 'alias.p=-C . push' p -f origin main", "git -c 'alias.p=--no-pager -c a.b=c push -f' p origin main",
                        "git -c 'alias.q=-c a.b=c p' -c alias.p=push q -f origin develop",
                        "git -c 'alias.p=-c alias.r=push r' p -f origin main"):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
        for command in ("git -c 'alias.p=-c a.b=c push' p -f origin feature/work", "git -c 'alias.p=-p push' p origin main",
                        "git -c 'alias.p=-c a.b=c status' p -f origin main"):
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


class TokenizerHardeningTests(test_policy.PolicyFixture):
    """Shell spellings that name the same command or branch as a plain one (Wave B policy findings)."""

    def setUp(self):
        super().setUp()
        self.git('checkout', '-qb', 'main')

    def blocked_all(self, commands, reason='protected branch'):
        for command in commands:
            with self.subTest(command=command):
                self.sentinel.unlink(missing_ok=True)
                result = self.invoke(command)
                self.assertEqual(result.returncode, 2, command + '\n' + result.stderr)
                self.assertIn(reason, result.stderr)

    def allowed_all(self, commands):
        for command in commands:
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_a_command_name_split_by_quotes_or_escapes_is_still_inspected(self):
        self.blocked_all(['g\\it push -f origin main', 'gi"t" push -f origin main', "g''it push -f origin main",
                          'g\\\nit push -f origin main', '"g"i\\t push -f origin main'])
        self.blocked_all(['ver\\cel deploy', "'vercel' deploy", 'v"er"cel deploy'], 'Preview')
        self.blocked_all(['g\\h repo delete x'], 'irreversible')
        self.allowed_all(['echo "g it"', 'gi"t" status', 'echo g\\it'])

    def test_ansi_c_quoted_words_are_decoded(self):
        self.blocked_all(["$'git' push -f origin main", "git $'push' -f origin main", "git push $'-f' origin main",
                          "git push -f origin $'ma\\x69n'", "git push -f origin $'\\155ain'", "git push -f origin $'ma\\u0069n'",
                          "$'g\\x69t' push -f origin main", "git push -f origin $'main'"])
        self.allowed_all(["git push -f origin $'feature'", "git push -f origin $'a\\nmain'", "echo $'git push -f origin main'"])

    def test_short_ref_spellings_name_the_same_branch(self):
        self.blocked_all(['git push -f origin HEAD:heads/main', 'git push origin :heads/main', 'git push origin +HEAD:heads/main',
                          'git push -f origin x:refs/heads/main', 'git push -f origin x:main', 'git push -f origin HEAD:refs/heads/main'])
        self.allowed_all(['git push -f origin HEAD:heads/feature', 'git push origin :heads/feature/old',
                          'git push -f origin HEAD:tags/main'])

    def test_unambiguous_long_option_prefixes_are_recognised(self):
        self.blocked_all(['git push --dele origin main', 'git push --delet origin main', 'git push --force-w origin main',
                          'git push --force-with origin main', 'git push --force-with-l origin main', 'git push --fo origin main',
                          'git push --mir', 'git push --mirr origin', 'git push --prun origin', 'git push --al --force origin',
                          'git push --all --forc origin', 'git push --delete origin main', 'git push --forc origin main'], reason='')
        self.allowed_all(['git push --verb origin main', 'git push --tag origin v1.0.0', 'git push --dry origin main',
                          'git push --set-u origin feature/work', 'git push --follow origin feature/work',
                          'git push --force-with-lease --dry-run origin main', 'git push --dr -f origin main'])

    def test_the_static_push_option_list_covers_the_installed_git(self):
        lifecycle = subprocess.run([self.environment['RPI_REAL_GIT'], 'push', '--git-completion-helper'], capture_output=True, text=True,
                                   cwd=self.project, env={**os.environ, 'GIT_CONFIG_NOSYSTEM': '1'})
        if lifecycle.returncode != 0 or not lifecycle.stdout.strip():
            self.skipTest('this git has no push completion helper')
        import importlib.util
        spec = importlib.util.spec_from_file_location('policy_options_fixture', test_policy.POLICY)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        real = {word.rstrip('=') for word in lifecycle.stdout.split() if word.startswith('--') and word != '--'}
        self.assertEqual(sorted(real - module.PUSH_LONG_OPTIONS), [], 'a new git push option is missing from the hook list')

    def test_redirections_glued_to_a_word_are_not_part_of_it(self):
        self.blocked_all(['git push -f origin main>/dev/null', 'git push -f origin main>&2', 'git push -f origin main</dev/null',
                          'git push -f origin main>>log', 'git push -f origin main 2>/dev/null', 'git push -f origin main>/dev/null 2>&1',
                          'git push origin :main>/dev/null', 'git push>/dev/null -f origin main'])
        self.allowed_all(['git push -f origin feature/work>/dev/null', 'git push origin feature/work>out.txt'])

    def test_static_brace_lists_are_expanded(self):
        self.blocked_all(['git push -f origin {main,x}', 'git push -f origin ma{in,}', 'git push -f origin {,+}main',
                          'git push origin {,+}main', 'git push origin :{main,x}', 'git push --delete origin {main,feature}',
                          'git push {-f,-u} origin main', 'git push -f origin {x,{main,y}}', '{git,push} -f origin main',
                          'gh api -X DELETE repos/o/r/git/refs/heads/{main,x}', 'git push -f origin {,a}{,}main'])
        self.allowed_all(['git push -f origin {x,y}', 'git push -f origin "{main,x}"', "git push -f origin '{main,x}'",
                          'git push -f origin {main}', 'git push -f origin {feature,hotfix}/a', 'echo {git,push} -f origin main'])

    def test_a_brace_expansion_over_the_cap_fails_closed(self):
        huge = 'git push -f origin ' + ''.join('{a,b}' for _ in range(11))
        result = self.invoke(huge)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('brace expansion', result.stderr)
        self.assertFalse(self.sentinel.exists())

    def test_quoted_heredoc_markers_in_comments_and_strings_do_not_hide_commands(self):
        self.blocked_all(["# cat <<'EOF'\ngit push -f origin main\nEOF", "echo \"cat <<'EOF'\"\ngit push -f origin main\nEOF",
                          "echo 'x' # cat <<'EOF'\ngit push -f origin main\nEOF",
                          "cat <<'EOF'\nhello\nEOF\ngit push -f origin main",
                          "cat <<-'EOF'\n\thello\n\tEOF\ngit push -f origin main",
                          "function f { git push -f origin main; }; f", "f() { git push -f origin main; }; f",
                          "function f() { git push -f origin main; }; f"])

    def test_heredoc_bodies_are_text_unless_a_shell_consumes_them(self):
        self.allowed_all(["git commit -F - <<'EOF'\nfix: docs\n\ngit push -f origin main is forbidden\nEOF",
                          "gh pr create --body-file - <<'EOF'\nUse git push -f origin main never.\nEOF",
                          "ruby <<'RB'\nputs 'git push -f origin main'\nRB",
                          "cat <<EOF\ngit push -f origin main\nEOF", "cat <<'EOF'\n$(git push -f origin main)\nEOF",
                          "tee notes.txt <<EOF\ngit push -f origin main\nEOF",
                          "cat <<'EOF'\ngit push -f origin main"])
        self.blocked_all(["bash <<'EOF'\ngit push -f origin main\nEOF", "sh <<EOF\ngit push -f origin main\nEOF",
                          "cat <<'EOF' | bash\ngit push -f origin main\nEOF", "cat <<'EOF' | sudo bash -s\ngit push -f origin main\nEOF",
                          "cat <<'EOF' | tr a b | zsh\ngit push -f origin main\nEOF", "bash -s <<'EOF'\ngit push -f origin main\nEOF",
                          ". /dev/stdin <<'EOF'\ngit push -f origin main\nEOF", "source /dev/stdin <<'EOF'\ngit push -f origin main\nEOF",
                          "cat <<EOF\n$(git push -f origin main)\nEOF", "cat <<EOF\n`git push -f origin main`\nEOF",
                          "xargs sh -c <<'EOF'\ngit push -f origin main\nEOF"])

    def test_alias_chain_boundary_is_exactly_the_documented_cap(self):
        def chain(length):
            links = ['-c alias.a%d=a%d' % (number, number + 1) for number in range(length - 1)]
            return 'git ' + ' '.join(links) + ' -c alias.a%d=push a0 -f origin main' % (length - 1)
        self.blocked_all([chain(100)])
        self.allowed_all([chain(101)])

    def test_many_segments_cost_few_git_lookups_and_a_budget_fails_closed(self):
        log = self.workspace / 'git-calls.log'
        wrapper = self.fakebin / 'git'
        original = wrapper.read_text()
        wrapper.write_text(original.replace("name=Path(sys.argv[0]).name\n", "name=Path(sys.argv[0]).name\nopen(os.environ['RPI_GIT_LOG'],'a').write(' '.join(sys.argv[1:])+'\\n')\n"))
        env = {**self.environment, 'RPI_GIT_LOG': str(log)}
        command = '; '.join(['git push -f origin feature/work'] * 400)
        result = self.invoke(command, environment=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(len(log.read_text().splitlines()), 12, 'git lookups are cached per hook invocation')
        tiny = {**self.environment, 'RPI_POLICY_BUDGET_SECONDS': '0.000001'}
        blocked = self.invoke('git status', environment=tiny)
        self.assertEqual(blocked.returncode, 2, blocked.stderr)
        self.assertIn('time budget', blocked.stderr)
        self.assertEqual(self.invoke('echo hello', environment=tiny).returncode, 0, 'commands without a policy word cost nothing')


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


class DirtyTreeRefusalTests(test_prepush.PrePushFixture):
    def test_dirty_tree_refusal_lists_tracked_and_untracked_names_in_full(self):
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
