"""Branch-name spelling and shell/gh spelling coverage of the pre-action denylist."""
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
        self.assertTrue({'release', 'prod', 'prod2'} <= module.protected_branches(self.project))


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
                        'gh api -X DELETE repos/o/r/./git/refs/heads/main'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
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


class GateScalingAndTagTests(test_prepush.PrePushFixture):
    def setUp(self):
        super().setUp()
        self.policy(require_verification_receipt=True)
        self.commit('Opt in')

    def test_cost_is_per_distinct_commit_not_per_pushed_ref(self):
        log = self.workspace / 'gate-git.log'
        wrapper = self.fakebin / 'git'
        wrapper.write_text(wrapper.read_text().replace("name=Path(sys.argv[0]).name\n", "name=Path(sys.argv[0]).name\nopen(os.environ['RPI_GIT_LOG'],'a').write(' '.join(sys.argv[1:])+'\\n')\n"))
        self.evidence()
        head = self.git('rev-parse', 'HEAD')
        lines = [self.line('refs/heads/feature/n%d' % number, head) for number in range(3000)]
        lines.append(self.line('refs/heads/develop', head))
        result = self.gate(*lines, environment={**self.environment, 'RPI_GIT_LOG': str(log)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(len(log.read_text().splitlines()), 40, 'git lookups are shared by refs that name the same commit')

    def test_version_tags_of_every_common_shape_are_gated_and_other_tags_are_not(self):
        tag_object = self.git('rev-parse', 'HEAD')
        for name in ('v1.2.3.4', 'v2.0.0rc1', 'v1.0', 'v5.0.0_x', 'V3.0.0', 'release-1.0.0', 'v1', '2.0', '1.2.3', 'v1.2.3-beta.1+build.5'):
            with self.subTest(tag=name):
                self.assert_refused(self.line('refs/tags/' + name, tag_object), reason='verification evidence is missing')
        for name in ('nightly', 'latest', 'release-candidate', 'stable', 'beta', 'x'):
            with self.subTest(tag=name):
                self.assert_passes(self.line('refs/tags/' + name, tag_object))

    def test_the_dirty_list_caps_its_names_and_counts_the_rest(self):
        self.evidence()
        for number in range(30):
            (self.project / ('file%02d.txt' % number)).write_text('x')
        result = self.assert_refused(self.line('refs/heads/develop'), reason='clean')
        why, fix = result.stderr.strip().split(' / FIX: ', 1)
        self.assertIn('30 changed paths', why)
        self.assertIn('file00.txt', why)
        self.assertIn('file19.txt', why)
        self.assertNotIn('file20.txt', why)
        self.assertIn('and 10 more', why)
        self.assertIn('git status --short', fix)

    def test_unusual_names_are_escaped_unambiguously(self):
        self.evidence()
        (self.project / 'a,b.txt').write_text('x')
        (self.project / 'tab\tname.txt').write_text('x')
        (self.project / 'quote"name.txt').write_text('x')
        (self.project / 'line\nbreak.txt').write_text('x')
        result = self.assert_refused(self.line('refs/heads/develop'), reason='clean')
        why = result.stderr.strip().split(' / FIX: ', 1)[0]
        self.assertIn('4 changed paths', why)
        for shown in ('"a,b.txt"', '"tab\\tname.txt"', '"quote\\"name.txt"', '"line\\nbreak.txt"'):
            self.assertIn(shown, why)
        self.assertEqual(result.stderr.count('\n'), 1, 'one line: no raw newline from a file name')
        self.assertNotIn('\t', result.stderr)


class DirtyTreeRefusalTests(test_prepush.PrePushFixture):
    def test_dirty_tree_refusal_lists_tracked_and_untracked_names_in_full(self):
        self.policy(require_verification_receipt=True)
        self.commit('Opt in')
        self.evidence()
        (self.project / 'README.md').write_text('Changed after verification.\n')
        (self.project / 'new file.txt').write_text('Untracked.\n')
        result = self.assert_refused(self.line('refs/heads/develop'), reason='clean')
        reason = result.stderr.split(' / FIX:')[0]
        self.assertIn('2 changed paths: README.md, new file.txt)', reason)
        self.git('checkout', '--', 'README.md')
        (self.project / 'new file.txt').unlink()
        (self.project / 'a.txt').write_text('Untracked only.\n')
        result = self.assert_refused(self.line('refs/heads/develop'), reason='clean')
        self.assertIn('1 changed path: a.txt)', result.stderr.split(' / FIX:')[0])


if __name__ == '__main__':
    unittest.main()
