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

    def test_invalid_policy_messages_name_the_cause(self):
        path = self.project / '.rpi/policy.json'
        path.write_text('not json')
        self.assert_blocked('git push -f origin feature/work', 'not valid JSON')
        path.write_text(json.dumps({'schema_version': 1, 'integration_branch': ['release']}))
        self.assert_blocked('git push -f origin release', 'integration_branch')

    def test_unreadable_policy_file_blocks_policy_dependent_commands(self):
        path = self.project / '.rpi/policy.json'
        path.unlink()
        path.mkdir()
        self.assert_blocked('git push --delete origin feature/old', '.rpi/policy.json')
        self.assert_allowed('git status')

    def test_invalid_policy_file_blocks_only_policy_dependent_commands(self):
        path = self.project / '.rpi/policy.json'
        for data in ('not json', '[]', '{"schema_version": 2}', '{"schema_version": 1, "unknown": 1}'):
            with self.subTest(data=data):
                path.write_text(data)
                self.assert_blocked('git push -f origin feature/work', '.rpi/policy.json')
                for command in ('git status', 'git push origin develop', 'gh pr create --fill',
                                'gh release create v7.7.7 --notes x', 'vercel --prod'):
                    self.assert_allowed(command)
        copied = self.workspace / 'policy.json'
        copied.write_text('{"schema_version": 1}')
        path.unlink()
        path.symlink_to(copied)
        self.assert_blocked('git push -f origin feature/work', 'regular file')


if __name__ == '__main__':
    unittest.main()
