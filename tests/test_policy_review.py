"""Independent publication regressions; all transport executables are sentinels."""
import shlex
import subprocess
import unittest

import test_policy


class PolicyReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_policy.PolicyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        # No package manager in these tests can download or deploy anything.
        for name in ('npx', 'pnpm', 'npm', 'yarn'):
            executable = self.fixture.fakebin / name
            executable.write_bytes((self.fixture.fakebin / 'vercel').read_bytes())
            executable.chmod(0o755)

    def invoke(self, command):
        event = self.fixture.event(command)
        event['permission_mode'] = 'default'
        return self.fixture.invoke(event=event)

    def deny(self, command):
        self.fixture.sentinel.unlink(missing_ok=True)
        result = self.invoke(command)
        if result.returncode == 0:
            # Demonstrate that a missed denial reaches only a fake transport.
            subprocess.run(['bash', '-c', command], cwd=self.fixture.project,
                           env=self.fixture.environment, check=True)
        self.assertEqual(result.returncode, 2, command + '\n' + result.stderr)
        self.assertIn('BLOCKED / WHY:', result.stderr)
        self.assertFalse(self.fixture.sentinel.exists(), command)

    def test_static_shell_spelling_cannot_hide_guarded_executable(self):
        for executable in ("g'it'", 'g"it"', r'g\it'):
            with self.subTest(executable=executable):
                self.deny(executable + ' push origin feature/hidden')
        for literal in ("printf '%s' \"g'it' push origin feature/literal\"",
                        "printf '%s' 'g\\it push origin feature/literal'"):
            self.assertEqual(self.invoke(literal).returncode, 0)

    def test_remote_ci_and_merge_mutations_do_not_fall_through(self):
        for command in ('gh run rerun 123', 'gh pr merge 1',
                        'gh api -X POST repos/fixture/project/actions/workflows/test/dispatches'):
            with self.subTest(command=command):
                self.deny(command)
        self.assertEqual(self.invoke('gh run view 123').returncode, 0)

    def test_package_wrapper_preserves_explicit_production_arguments(self):
        self.fixture.evidence()
        for command in ('npx --yes vercel deploy --prod',
                        'npx --no-install vercel deploy --target production'):
            result = self.invoke(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('"allow"', result.stdout)
        self.assertFalse(self.fixture.sentinel.exists(), 'the policy must never launch a deployment')

    def test_implicit_refspec_cannot_publish_configured_working_branch(self):
        self.fixture.git('branch', 'feature/hidden')
        self.fixture.git('config', 'remote.origin.push', 'refs/heads/feature/hidden:refs/heads/feature/hidden')
        self.fixture.evidence()
        self.deny('git push origin')

    def test_explicit_tag_source_cannot_publish_a_branch_namespace(self):
        self.fixture.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                         'tag', '-a', 'v2.0.0', '-m', 'Release fixture')
        self.fixture.evidence()
        self.deny('git push origin v2.0.0:refs/heads/v2.0.0')

    def test_git_config_cannot_silently_expand_one_ref_to_tags(self):
        self.fixture.git('config', 'push.followTags', 'true')
        self.fixture.evidence()
        self.deny('git push origin develop')

    def test_environment_cannot_redirect_guarded_git_state(self):
        self.fixture.evidence()
        directory = shlex.quote(str(self.fixture.project / '.git'))
        for prefix in ('GIT_DIR=' + directory,
                       'env GIT_WORK_TREE=' + shlex.quote(str(self.fixture.project)),
                       'env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=push.followTags GIT_CONFIG_VALUE_0=true'):
            with self.subTest(prefix=prefix):
                self.deny(prefix + ' git push origin develop')
        self.assertEqual(self.invoke('env TEST=1 git status --short').returncode, 0)


if __name__ == '__main__':
    unittest.main()
