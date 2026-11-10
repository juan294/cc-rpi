"""Project policy input to the denylist; the receipt gate is tested in test_prepush."""
import json
import unittest

import test_policy


class PolicyFileTests(test_policy.PolicyFixture):
    def test_receipt_opt_in_never_gates_the_pre_action_hook(self):
        self.opt_in()
        (self.project / 'README.md').write_text('Dirty, unverified.\n')
        self.tag('v9.9.9')
        for command in ('git push origin develop', 'git push', 'git push --all origin', 'git push --tags',
                        "git push origin 'refs/heads/*'", 'vercel --prod', 'gh release create v9.9.9 --notes x'):
            with self.subTest(command=command):
                self.assert_allowed(command)
        self.assert_blocked('git push -f origin develop', 'protected branch')

    def test_project_without_policy_file_keeps_default_protection(self):
        (self.project / '.rpi/policy.json').unlink()
        self.assert_allowed('git push origin develop')
        self.assert_blocked('git push -f origin develop', 'protected branch')
        self.assert_blocked('git push -f origin main', 'protected branch')

    def test_an_unusable_policy_file_warns_and_keeps_the_default_protection(self):
        path = self.project / '.rpi/policy.json'
        for data in ('not json', '[]', '{"schema_version": 2}', '{"schema_version": 1, "unknown": 1}',
                     json.dumps({'schema_version': 1, 'integration_branch': ['release']})):
            with self.subTest(data=data):
                path.write_text(data)
                result = self.assert_allowed('git push -f origin feature/work')
                self.assertIn('POLICY NOTE', result.stderr)
                self.assert_blocked('git push -f origin main', 'protected branch')
                for command in ('git status', 'git push origin develop', 'gh pr create --fill', 'vercel --prod'):
                    self.assert_allowed(command)
        path.unlink()
        path.mkdir()
        self.assert_allowed('git push --delete origin feature/old')
        self.assert_blocked('git push --delete origin develop', 'protected branch')


if __name__ == '__main__':
    unittest.main()
