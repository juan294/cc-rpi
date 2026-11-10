"""Version-tag protection in the pre-action denylist, and the pattern it shares with the receipt gate.

The fixture's `git` runs real git for everything except push and pull, so no test here can publish."""
import importlib.util
import time
import unittest

import test_policy
import test_prepush


def load(path):
    spec = importlib.util.spec_from_file_location('policy_tags_' + path.stem.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TagFixture(test_policy.PolicyFixture):
    """A project on `main` (protected) with `release` declared as a production branch."""

    def setUp(self):
        super().setUp()
        self.git('checkout', '-qb', 'main')
        self.policy(production_branches=['release'])
        self.commit('Declare release')

    def blocked_all(self, commands, reason):
        for command in commands:
            with self.subTest(command=command):
                self.assert_blocked(command, reason)

    def allowed_all(self, commands):
        for command in commands:
            with self.subTest(command=command):
                self.assert_allowed(command)


class VersionTagTests(TagFixture):
    VERSIONS = ('v1', 'v1.0', 'V3.0.0', 'v2.0.0rc1', 'v5.0.0_x', 'v1.2.3-beta.1+build.5', '1.2.3.4', '2.0', 'release-1.0.0', 'release-v1',
                'v1.2.3-rc.1', 'v1x', 'rel_2.1')
    BRANCHES = ('issue-42', 'fix-123', 'feature-2', 'release-1', '1', '2026-11-09', 'nightly', 'latest', 'release-candidate', 'v', 'x',
                '1password', 'v1.', '1.1.1.', 'main', 'feature/v1.0', 'fix_7', 'sprint-12')

    def test_the_pattern_separates_versions_from_branch_names(self):
        pattern = load(test_policy.POLICY).VERSION_TAG
        for name in self.VERSIONS:
            self.assertTrue(pattern.fullmatch(name), name)
        for name in self.BRANCHES:
            self.assertFalse(pattern.fullmatch(name), name)

    def test_the_gate_and_the_hook_share_the_pattern(self):
        self.assertEqual(load(test_policy.POLICY).VERSION_TAG.pattern, load(test_prepush.PREPUSH).VERSION_TAG.pattern)

    def test_matching_does_not_backtrack(self):
        pattern = load(test_policy.POLICY).VERSION_TAG
        started = time.monotonic()
        for name in ('1.' * 20000 + '!', 'v' + '1.' * 20000 + '!', '1' * 40000 + '!', 'a' * 40000 + '-' + '1' * 40000):
            self.assertIsNone(pattern.fullmatch(name))
        self.assertLess(time.monotonic() - started, 0.5)

    def test_deleting_or_force_moving_a_version_tag(self):
        self.blocked_all(['git push -f origin v1.0', 'git push -f origin refs/tags/v1.0', 'git push -f --tags', 'git push -f --tags origin',
                          'git push origin +refs/tags/v1:refs/tags/v1', 'git push origin :v1', 'git push origin :refs/tags/v1',
                          'git push origin --delete v1', 'git push origin --delete tag v1', 'git push -d origin v1',
                          'git push --force-with-lease origin refs/tags/v1.0', 'git push -f origin tags/v1.0',
                          "git push -f origin 'refs/tags/*:refs/tags/*'", "git push -f origin '+refs/tags/v*:refs/tags/v*'",
                          'git push -f origin release-1.0.0', 'git push -f origin V3.0.0', 'git push -f origin 2.0',
                          'git push origin --delete "refs/tags/v$N"', 'git push -f origin "v$N"',
                          'git push -f origin HEAD:v1.0', 'git push -f origin feat2:release-v1',
                          'gh release delete v1.0 --cleanup-tag --yes', 'gh api -X DELETE repos/o/r/git/refs/tags/v1.0'], 'version tag')

    def test_ordinary_tags_and_branch_names_pass(self):
        self.allowed_all(['git push origin v1.0', 'git push --tags origin', 'git push origin refs/tags/v1.0', 'git push -f origin nightly',
                          'git push origin --delete nightly', 'git push -f origin refs/tags/latest',
                          "git push -f origin 'refs/tags/nightly-*:refs/tags/nightly-*'", 'git push origin :refs/tags/stable',
                          'git push -f origin feat2:refs/heads/v1.0', 'git push origin :refs/heads/v1.0',
                          'git push origin --delete issue-42', 'git push -d origin fix-123', 'git push -f origin release-1',
                          'git push -f origin 2026-11-09', 'git push -f origin "feature-$N"', 'gh release delete v1.0 --yes'])

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


class CaseInsensitiveRemoteTests(TagFixture):
    def test_protected_names_are_compared_without_case(self):
        self.blocked_all(['git push -f origin Main', 'git push origin :MAIN', 'git push -f origin Release'], 'protected branch')


if __name__ == '__main__':
    unittest.main()
