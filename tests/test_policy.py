"""Native event and execution sentinels; every Git remote/deployer is fake."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'templates/scripts/rpi-policy.py'


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rpi policy é ' & ")
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name).resolve()
        self.project = self.workspace / 'project'
        self.project.mkdir()
        self.fakebin = self.workspace / 'bin'
        self.fakebin.mkdir()
        self.sentinel = self.workspace / 'executed.txt'
        self.environment = {**os.environ, 'PATH': str(self.fakebin) + os.pathsep + str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
                            'RPI_REAL_GIT': shutil.which('git'), 'RPI_SENTINEL': str(self.sentinel)}
        fake = '''#!/usr/bin/env python3
import os,sys
from pathlib import Path
name=Path(sys.argv[0]).name
if name=='git' and not any(arg in ('push','pull') for arg in sys.argv[1:]):
    os.execv(os.environ['RPI_REAL_GIT'], ['git',*sys.argv[1:]])
Path(os.environ['RPI_SENTINEL']).write_text(name+' executed')
'''
        for name in ('git', 'gh', 'vercel', 'vc'):
            path = self.fakebin / name
            path.write_text(fake)
            path.chmod(0o755)
        self.git('init', '-qb', 'develop')
        (self.project / 'README.md').write_text('# Fixture\n')
        (self.project / '.gitignore').write_text('.rpi/local/\n')
        (self.project / '.rpi').mkdir()
        (self.project / '.rpi/policy.json').write_text(json.dumps({'schema_version': 1, 'integration_branch': 'develop',
            'remote': 'origin', 'verification_checks': self.expected_checks(), 'verification_command': ['bash', 'scripts/verify-local.sh']}))
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture')
        self.git('remote', 'add', 'origin', 'https://example.invalid/never-contacted.git')

    def git(self, *arguments):
        result = subprocess.run([self.environment['RPI_REAL_GIT'], '-C', str(self.project), *arguments], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def event(self, command):
        return {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'session_id': 'fixture-session',
                'cwd': str(self.project), 'permission_mode': 'default', 'tool_input': {'command': command}}

    def invoke(self, command=None, harness='claude', event=None, environment=None):
        return subprocess.run([sys.executable, str(POLICY), '--harness', harness],
                              input=json.dumps(event if event is not None else self.event(command)),
                              capture_output=True, text=True, cwd=self.project,
                              env=environment or self.environment)

    def execute(self, command, harness='claude', native_authorized=True):
        result = self.invoke(command, harness)
        if result.returncode == 0 and native_authorized:
            subprocess.run(['bash', '-c', command], cwd=self.project, env=self.environment, check=True)
        return result

    def expected_checks(self):
        return [{'name': 'fixture-tests', 'argv': ['python3', '-m', 'unittest']},
                {'name': 'fixture-build', 'argv': ['bash', 'build.sh']}]

    def evidence(self):
        spec = importlib.util.spec_from_file_location('policy_candidate_fixture', ROOT / 'templates/scripts/rpi-candidate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        identity = module.identity(self.project)
        report = {'schema_version': 1, 'suite': 'ci-equivalent', 'passed': True,
                  'identity': identity, 'identity_after': identity, 'identity_unchanged': True,
                  'environment': module.environment(self.environment), 'environment_after': module.environment(self.environment), 'environment_unchanged': True,
                  'checks': [dict(check, exit_code=0) for check in self.expected_checks()]}
        path = self.project / '.rpi/local/verification.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report))
        return path

    def assert_blocked(self, command, harness='claude'):
        result = self.execute(command, harness)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('BLOCKED / WHY:', result.stderr)
        self.assertIn('/ FIX:', result.stderr)
        self.assertFalse(self.sentinel.exists(), command)

    def test_local_work_and_literal_command_text_remain_allowed(self):
        for command in ('git status --short', 'printf "%s" "git push origin feature/test"',
                        "printf '%s' 'vercel deploy --target preview'", 'echo git push --tags'):
            self.assertEqual(self.invoke(command).returncode, 0, command)
        command = 'printf local > ' + subprocess.list2cmdline([str(self.sentinel)])
        self.assertEqual(self.execute(command).returncode, 0)
        self.assertEqual(self.sentinel.read_text(), 'local')

    def test_executed_substitution_and_newline_are_distinct_from_literal_text(self):
        for command in ('echo "$(git push origin feature/substitution)"',
                        'echo `git push origin feature/backtick`',
                        'git status\ngit push origin feature/newline'):
            self.assert_blocked(command)
        for command in ("echo '$(git push origin feature/literal)'",
                        "printf '%s;%s' ';' 'git push origin feature/literal'",
                        "cat <<'TEXT'\ngit push origin feature/literal\nTEXT\n"):
            self.assertEqual(self.invoke(command).returncode, 0, command)

    def test_feature_publication_is_denied_in_refspecs_chains_and_wrappers(self):
        for command in ('git push origin feature/work', 'git push origin HEAD:refs/heads/feature/work',
                        'git status && git push origin feature/work', 'env TEST=1 command git push origin feature/work',
                        "bash -lc 'git push origin feature/work'", 'git -C . push origin feature/work'):
            with self.subTest(command=command):
                self.assert_blocked(command)

    def test_preview_default_bare_alias_and_wrapped_forms_never_execute(self):
        for command in ('vercel', 'vc', 'vercel deploy', 'vercel deploy --target preview',
                        'vercel deploy --target=preview --prod', 'npx --no-install vercel deploy',
                        'pnpm exec vercel', 'env MODE=x vercel .'):
            with self.subTest(command=command):
                self.assert_blocked(command)

    def test_all_tags_follow_tags_and_destructive_publication_are_denied(self):
        self.evidence()
        for command in ('git push --tags --follow-tags', 'git push origin --follow-tags',
                        'git push origin --all', 'git push --mirror', 'git push origin +HEAD:develop',
                        'git push --force origin develop', 'git push origin :old-branch'):
            with self.subTest(command=command):
                self.assert_blocked(command)

    def test_dirty_pull_is_checked_in_git_c_directory(self):
        (self.project / 'README.md').write_text('Uncommitted work.\n')
        self.assert_blocked('git -C . pull --rebase')
        self.assert_blocked('git pull')

    def test_clean_pull_can_execute_fake_transport(self):
        self.assertEqual(self.execute('git pull --rebase').returncode, 0)
        self.assertEqual(self.sentinel.read_text(), 'git executed')

    def test_integration_needs_current_complete_gate_evidence(self):
        self.assert_blocked('git push origin develop')
        path = self.evidence()
        report = json.loads(path.read_text())
        report['suite'] = 'custom'
        path.write_text(json.dumps(report))
        self.assert_blocked('git push origin develop')
        self.evidence()
        (self.project / 'README.md').write_text('Changed after verification.\n')
        self.assert_blocked('git push origin develop')

    def test_structural_pass_never_manufactures_native_authorization(self):
        self.evidence()
        result = self.execute('git push origin develop', native_authorized=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"allow"', result.stdout)
        self.assertFalse(self.sentinel.exists(), 'fake trusted boundary withheld approval')
        self.assertEqual(self.execute('git push origin develop', native_authorized=True).returncode, 0)
        self.assertTrue(self.sentinel.exists())

    def test_named_tag_at_verified_head_can_reach_claude_native_permission(self):
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'tag', '-a', 'v9.9.9', '-m', 'Release fixture')
        self.evidence()
        self.assertEqual(self.execute('git push origin v9.9.9').returncode, 0)
        self.assertTrue(self.sentinel.exists())

    def test_codex_remote_automation_stays_blocked_without_trusted_ask(self):
        self.evidence()
        self.assert_blocked('git push origin develop', 'codex')
        self.assert_blocked('vercel deploy --prod', 'codex')
        self.assertEqual(self.invoke('git status', 'codex').returncode, 0)

    def test_codex_loaded_prompt_contract_preserves_actual_native_decision(self):
        rules = self.project / '.codex/rules/rpi.rules'
        rules.parent.mkdir(parents=True)
        rules.write_bytes((ROOT / 'templates/adapters/codex-permissions.rules').read_bytes())
        self.git('add', '.codex')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Explicit native setup')
        client = self.fakebin / 'codex'
        client.write_text("#!/usr/bin/env python3\nimport json,sys\nprint('codex-cli 0.153.4' if '--version' in sys.argv else json.dumps({'decision': 'prompt'}))\n")
        client.chmod(0o755)
        self.evidence()
        event = {**self.event('git push origin develop'), 'permission_mode': 'default'}
        result = self.invoke(harness='codex', event=event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('"allow"', result.stdout)
        self.assertFalse(self.sentinel.exists(), 'the hook never executes or approves the publication')
        client.write_text("#!/usr/bin/env python3\nimport json,sys\nprint('codex-cli 0.153.4' if '--version' in sys.argv else json.dumps({'decision': 'allow'}))\n")
        rejected = self.invoke(harness='codex', event=event)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn('Native rules do not require approval', rejected.stderr)
        event['permission_mode'] = 'bypassPermissions'
        self.assertEqual(self.invoke(harness='codex', event=event).returncode, 2)

    def test_wrapper_runtime_failures_emit_native_blocking_stderr(self):
        wrapper = ROOT / 'templates/hooks/guard-bash.sh'
        result = subprocess.run(['/bin/bash', str(wrapper)], input=json.dumps(self.event('git push')),
                                text=True, capture_output=True, env={**self.environment, 'PATH': '/nonexistent-fixture-path'})
        self.assertEqual(result.returncode, 2)
        self.assertIn('Python 3', result.stderr)
        self.assertIn('/ FIX:', result.stderr)
        old_runtime = self.workspace / 'old-runtime'
        old_runtime.mkdir()
        executable = old_runtime / 'python3'
        executable.write_text('#!/bin/sh\nexit 1\n')
        executable.chmod(0o755)
        result = subprocess.run(['/bin/bash', str(wrapper)], input=json.dumps(self.event('git push')),
                                text=True, capture_output=True, env={**self.environment, 'PATH': str(old_runtime)})
        self.assertEqual(result.returncode, 2)
        self.assertIn('Python 3.11 or newer', result.stderr)
        broken = self.workspace / 'hooks/guard-bash.sh'
        broken.parent.mkdir()
        shutil.copyfile(wrapper, broken)
        result = subprocess.run(['/bin/bash', str(broken)], input=json.dumps(self.event('git push')),
                                text=True, capture_output=True, env=self.environment)
        self.assertEqual(result.returncode, 2)
        self.assertIn('rpi-policy.py dependency is missing', result.stderr)

    def test_registered_wrapper_resolves_nested_cwd_without_git_for_local_text(self):
        for name, executable in (('python3', sys.executable), ('bash', shutil.which('bash'))):
            (self.fakebin / name).symlink_to(executable)
        (self.fakebin / 'git').unlink()
        runtime = self.project / '.rpi/scripts'
        runtime.mkdir(parents=True)
        shutil.copyfile(POLICY, runtime / POLICY.name)
        nested = self.project / 'nested'
        nested.mkdir()
        for harness, adapter in (('claude', 'claude-policy.json'), ('codex', 'codex-hooks.json')):
            hooks = self.project / ('.' + harness) / 'hooks'
            hooks.mkdir(parents=True)
            shutil.copyfile(ROOT / 'templates/hooks/guard-bash.sh', hooks / 'guard-bash.sh')
            records = json.loads((ROOT / 'templates/adapters' / adapter).read_text())['entries']
            registration = next(record['value']['hooks'][0]['command'] for record in records if record['id'] == 'pre-tool-policy')
            environment = {**self.environment, 'PATH': str(self.fakebin)}
            result = subprocess.run(['/bin/bash', '-c', registration], input=json.dumps(self.event('printf local')),
                                    capture_output=True, text=True, cwd=nested, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((runtime / '__pycache__').exists())

    def test_optional_telemetry_failure_does_not_change_policy_result(self):
        sink = self.project / '.rpi/local/contract-events.jsonl'
        sink.mkdir(parents=True)
        result = self.invoke('git pull --rebase')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('TELEMETRY UNAVAILABLE', result.stderr)

    def test_implicit_upstream_cannot_publish_working_branch(self):
        self.git('checkout', '-qb', 'feature/implicit')
        self.git('config', 'branch.feature/implicit.remote', 'origin')
        self.git('config', 'branch.feature/implicit.merge', 'refs/heads/feature/implicit')
        self.evidence()
        self.assert_blocked('git push')

    def test_policy_sensitive_ambiguity_and_malformed_events_fail_closed(self):
        for command in ('eval "git push origin develop"', 'git push origin "$DEST"',
                        'git push origin $(cat target.txt)', 'git -c alias.ship=push ship origin develop'):
            with self.subTest(command=command):
                self.assert_blocked(command)
        for event in ({'tool_name': 'Bash'}, {'tool_name': 'Bash', 'tool_input': {'command': ['git', 'push']}},
                      {**self.event('git push'), 'cwd': '/nonexistent-policy-fixture'}):
            result = self.invoke(event=event)
            self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.invoke(event={'tool_name': 'Read', 'tool_input': {'file_path': 'README.md'}}).returncode, 0)

    def test_missing_git_dependency_is_blocked_for_git_and_not_for_local_text(self):
        environment = {**self.environment, 'PATH': str(self.workspace / 'empty-path')}
        self.assertEqual(self.invoke('git push origin develop', environment=environment).returncode, 2)
        self.assertEqual(self.invoke('printf local', environment=environment).returncode, 0)

    def test_partial_and_reordered_project_gate_reports_are_rejected(self):
        path = self.evidence()
        valid = json.loads(path.read_text())
        for checks in (valid['checks'][:1], list(reversed(valid['checks'])),
                       [dict(item, argv=['true']) for item in valid['checks']]):
            path.write_text(json.dumps(dict(valid, checks=checks)))
            self.assert_blocked('git push origin develop')
        path.write_text('[]')
        self.assert_blocked('git push origin develop')

    def test_unknown_or_missing_claude_permission_mode_cannot_publish(self):
        self.evidence()
        for mode in (None, 'unknown', 'bypassPermissions', 'dontAsk'):
            event = self.event('git push origin develop')
            event['permission_mode'] = mode
            self.assertEqual(self.invoke(event=event).returncode, 2)

    def test_lightweight_tag_is_not_a_release_candidate(self):
        self.git('tag', 'v9.9.9')
        self.evidence()
        self.assert_blocked('git push origin v9.9.9')

    def test_ordinary_packages_groups_and_assignment_literals_remain_local(self):
        for command in ('npm test', 'npx eslint .', '(printf local)', 'echo GIT_DIR=x git', 'gh run watch 123 --exit-status'):
            self.assertEqual(self.invoke(command).returncode, 0, command)

    def test_canonical_release_creation_preserves_native_approval(self):
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'tag', '-a', 'v9.9.9', '-m', 'Release fixture')
        notes = self.project / '.rpi/local/release-notes.md'
        notes.parent.mkdir(parents=True, exist_ok=True)
        notes.write_text('Verified fixture release.\n')
        self.evidence()
        command = "gh release create v9.9.9 --verify-tag --title 'v9.9.9' --notes-file .rpi/local/release-notes.md"
        result = self.execute(command, native_authorized=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('allow', result.stdout)
        self.assertFalse(self.sentinel.exists())
        self.assertEqual(self.execute(command).returncode, 0)
        self.sentinel.unlink()
        for suffix in (' --repo other/project', ' --target other', ' --verify-tag'):
            self.assert_blocked(command + suffix)
        self.assert_blocked(command.replace('--verify-tag ', ''))
        self.assert_blocked(command.replace('release-notes.md', 'missing.md'))
        for name in ('GH_REPO', 'GH_HOST'):
            result = self.invoke(command, environment={**self.environment, name: 'wrong-destination'})
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse(self.sentinel.exists())
            self.assert_blocked(name + '=wrong-destination ' + command)
        link = notes.with_name('linked-notes.md')
        link.symlink_to(notes)
        self.assert_blocked(command.replace('release-notes.md', 'linked-notes.md'))
        self.git('config', 'remote.origin.gh-resolved', 'wrong/project')
        self.assert_blocked(command)
        self.git('config', '--unset', 'remote.origin.gh-resolved')
        self.git('remote', 'add', 'upstream', 'https://example.invalid/wrong/project.git')
        self.assert_blocked(command)
        self.git('remote', 'remove', 'upstream')
        self.git('config', 'remote.origin.pushurl', 'https://example.invalid/wrong/push.git')
        self.assert_blocked(command)

    def test_sensitive_remote_gh_entries_are_classified(self):
        for command in ('gh pr create', 'gh workflow run validate.yml', 'gh release create v9.9.9'):
            self.assert_blocked(command)

    def test_readonly_issue_and_label_inspection_is_allowed(self):
        for command in ('gh issue list', 'gh issue view 12', 'gh issue status', 'gh label list'):
            self.assertEqual(self.invoke(command).returncode, 0, command)

    def test_issue_creation_needs_a_literal_title_and_local_body(self):
        body = self.project / 'issue-body.md'
        body.write_text('Reproduction and expected behavior.\n')
        allowed = 'gh issue create --title "Guard rejects inert gh reads" --body-file issue-body.md'
        self.assertEqual(self.invoke(allowed).returncode, 0, allowed)

    def test_issue_creation_cannot_retarget_another_repository_or_escape_the_project(self):
        body = self.project / 'issue-body.md'
        body.write_text('Reproduction and expected behavior.\n')
        for command in ('gh issue create --title T --body-file issue-body.md --repo other/repo',
                        'gh issue create --title T --body-file ../outside.md',
                        'gh issue create --title T',
                        'gh issue create --body-file issue-body.md',
                        'gh issue create --title T --body-file issue-body.md --web'):
            self.assert_blocked(command)
        environment = dict(self.environment, GH_REPO='other/repo')
        result = self.invoke('gh issue create --title T --body-file issue-body.md', environment=environment)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def trust(self, payload=None):
        path = self.project / '.rpi/local/publication-trust.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {'schema_version': 1, 'publication_without_prompt': True,
                  'authorized_on': '2026-09-06'} if payload is None else payload
        path.write_text(json.dumps(record) if isinstance(record, dict) else record)
        return path

    def publication_event(self, command, mode):
        return dict(self.event(command), permission_mode=mode)

    def test_non_prompting_mode_cannot_publish_without_standing_authorization(self):
        self.evidence()
        for mode in ('bypassPermissions', 'dontAsk', 'auto'):
            result = self.invoke(event=self.publication_event('git push origin develop', mode))
            self.assertEqual(result.returncode, 2, mode)

    def test_standing_authorization_lets_a_non_prompting_mode_publish(self):
        self.evidence()
        self.trust()
        for mode in ('bypassPermissions', 'dontAsk', 'auto'):
            result = self.invoke(event=self.publication_event('git push origin develop', mode))
            self.assertEqual(result.returncode, 0, mode + ': ' + result.stdout + result.stderr)

    def test_malformed_or_redirected_authorization_never_grants_publication(self):
        self.evidence()
        path = self.trust()
        for payload in ('not json', {'schema_version': 2, 'publication_without_prompt': True},
                        {'schema_version': 1, 'publication_without_prompt': False},
                        {'schema_version': 1}):
            self.trust(payload)
            result = self.invoke(event=self.publication_event('git push origin develop', 'bypassPermissions'))
            self.assertEqual(result.returncode, 2, str(payload))
        path.unlink()
        outside = self.workspace / 'trust.json'
        outside.write_text(json.dumps({'schema_version': 1, 'publication_without_prompt': True}))
        path.symlink_to(outside)
        result = self.invoke(event=self.publication_event('git push origin develop', 'bypassPermissions'))
        self.assertEqual(result.returncode, 2, 'a redirected authorization must not grant publication')

    def test_standing_authorization_does_not_bypass_candidate_verification(self):
        self.evidence()
        self.trust()
        (self.project / 'uncommitted.txt').write_text('dirty candidate\n')
        result = self.invoke(event=self.publication_event('git push origin develop', 'bypassPermissions'))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('clean completed integration candidate', result.stderr)


if __name__ == '__main__':
    unittest.main()
