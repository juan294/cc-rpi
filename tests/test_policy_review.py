"""Regressions for commands the v2.0 fail-closed parser blocked in adopter fleets.

Each command below was a recorded false positive (rules `unsupported`,
`remote-compute`, `github-api-*`, `git-alias`, `dirty-pull`, ...). None is
destructive, so each must pass to the client's native permissions.
"""
import shlex
import unittest

import test_policy


class PolicyFalsePositiveTests(test_policy.PolicyFixture):
    def allowed(self, command, harness='claude'):
        self.assertEqual(self.assert_allowed(command, harness).stdout, '')

    def test_read_only_shell_loops_and_substitutions(self):
        for command in ('for d in */; do git -C "$d" log --oneline -1; done',
                        'x=$(git log --oneline -100 | grep -c fix); echo $x',
                        'cd ~/code && git status', 'cd missing-directory && git status',
                        'while read -r d; do git -C "$d" fetch; done < repos.txt',
                        'eval "git status"', 'wrapper git status', 'xargs -n1 git -C',
                        'if git diff --quiet; then echo clean; fi',
                        'git log --format="%h $(date)"', '{ git status; git diff; }',
                        'git status "unterminated', 'git status\\', 'echo $(git status',
                        'npm run deploy', 'npx git status', 'make push'):
            with self.subTest(command=command):
                self.allowed(command)

    def test_git_aliases_options_and_environment(self):
        self.git('config', 'alias.st', 'status')
        for command in ('git st', 'git -c core.pager=cat log', 'git --git-dir=.git status',
                        'GIT_PAGER=cat git log', 'env GIT_DIR=.git git status', 'git --no-pager diff'):
            with self.subTest(command=command):
                self.allowed(command)

    def test_github_cli_reads_and_ordinary_mutations(self):
        for command in ('gh api repos/fixture/project/actions/runs', 'gh api graphql -f query=q',
                        "gh api repos/o/r/pulls --jq '.[].number'", 'gh pr checkout 12',
                        'gh pr review 12 --approve', 'gh pr comment 12 --body ok', 'gh pr edit 12 --add-label x',
                        'gh issue comment 3 --body ok', 'gh issue close 3', 'gh secret list',
                        'gh run download 1', 'gh repo clone o/r', 'gh search prs x', 'gh extension list',
                        'GH_REPO=o/r gh pr list', 'gh pr create --repo other/repo --fill'):
            with self.subTest(command=command):
                self.allowed(command)

    def test_codex_harness_matches_claude(self):
        for command in ('git push origin develop', 'gh pr merge 1', 'vercel --prod'):
            with self.subTest(command=command):
                self.allowed(command, 'codex')

    def test_deep_nesting_passes_instead_of_blocking(self):
        command = 'git status'
        for _ in range(8):
            command = 'bash -c ' + shlex.quote(command)
        self.allowed(command)


if __name__ == '__main__':
    unittest.main()
