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


class PolicyFixture(unittest.TestCase):
    """Shared fixture; test classes derive from it and add only tests."""

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
        self.commit('Fixture')
        self.git('remote', 'add', 'origin', 'https://github.com/fixture/project.git')

    def git(self, *arguments):
        result = subprocess.run([self.environment['RPI_REAL_GIT'], '-C', str(self.project), *arguments], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self, message='Fixture change'):
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '--allow-empty', '-qm', message)

    def tag(self, name='v9.9.9'):
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'tag', '-a', name, '-m', 'Fixture tag')

    def event(self, command):
        return {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'session_id': 'fixture-session',
                'cwd': str(self.project), 'permission_mode': 'default', 'tool_input': {'command': command}}

    def invoke(self, command=None, harness='claude', event=None, environment=None):
        return subprocess.run([sys.executable, str(POLICY), '--harness', harness],
                              input=json.dumps(event if event is not None else self.event(command)),
                              capture_output=True, text=True, cwd=self.project,
                              env=environment or self.environment)

    def execute(self, command, harness='claude'):
        result = self.invoke(command, harness)
        if result.returncode == 0:
            subprocess.run(['bash', '-c', command], cwd=self.project, env=self.environment, check=True)
        return result

    def expected_checks(self):
        return [{'name': 'fixture-tests', 'argv': ['python3', '-m', 'unittest']},
                {'name': 'fixture-build', 'argv': ['bash', 'build.sh']}]

    def policy(self, **changes):
        path = self.project / '.rpi/policy.json'
        value = json.loads(path.read_text())
        value.update(changes)
        path.write_text(json.dumps(value))
        return path

    def opt_in(self):
        """Opt into the receipt gate and commit, so the candidate is clean."""
        self.policy(require_verification_receipt=True)
        self.commit('Opt in')

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

    def assert_allowed(self, command, harness='claude', **kwargs):
        result = self.invoke(command, harness, **kwargs)
        self.assertEqual(result.returncode, 0, command + '\n' + result.stderr)
        self.assertNotIn('"allow"', result.stdout, 'a pass never manufactures native approval')
        self.assertFalse(self.sentinel.exists(), 'the policy never executes the command')
        return result

    def assert_blocked(self, command, reason=''):
        result = self.execute(command)
        self.assertEqual(result.returncode, 2, command + '\n' + result.stdout + result.stderr)
        self.assertIn('BLOCKED / WHY:', result.stderr)
        self.assertIn('/ FIX:', result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertFalse(self.sentinel.exists(), command)
        return result


class PolicyTests(PolicyFixture):
    def test_ordinary_publication_passes_to_native_permissions(self):
        # Pushes, PRs and workflow dispatch belong to the client's own permission
        # rules and the user; the policy neither blocks nor approves them.
        for command in ('git push', 'git push origin develop', 'git push -u origin feature/work',
                        'git push origin HEAD', 'git push --tags', 'git push origin --follow-tags',
                        'git push origin feature/work --force', 'git push -f origin feature/work',
                        'git push --force-with-lease origin HEAD:refs/heads/fix/thing',
                        'git push origin --delete feature/old', 'git push origin :feature/old',
                        'gh pr create --fill', 'gh pr merge 12 --squash --delete-branch',
                        'gh pr update-branch 12', 'gh workflow run ci.yml', 'gh run rerun 123',
                        'gh api -X POST repos/fixture/project/issues/1/comments -f body=hi',
                        'gh release create v1.0.0 --generate-notes', 'gh release edit v1.0.0 --draft=false',
                        'gh issue create --title T', 'gh repo view', 'gh label create bug'):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_every_permission_mode_passes_to_native_permissions(self):
        for mode in (None, 'default', 'acceptEdits', 'plan', 'auto', 'dontAsk', 'bypassPermissions'):
            with self.subTest(mode=mode):
                event = dict(self.event('git push origin develop'), permission_mode=mode)
                self.assertEqual(self.invoke(event=event).returncode, 0)
                self.assertEqual(self.invoke(event=event, harness='codex').returncode, 0)

    def test_force_or_deletion_of_a_protected_branch_is_blocked(self):
        for command in ('git push --force origin develop', 'git push -f origin develop',
                        'git push origin develop --force-with-lease', 'git push origin +develop',
                        'git push origin +HEAD:develop', 'git push origin HEAD:refs/heads/main --force',
                        'git push -fu origin master', 'git push origin --delete main',
                        'git push origin -d develop', 'git push origin :main',
                        'git push origin :refs/heads/develop', 'git push --force'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')

    def test_declared_production_branches_are_protected(self):
        self.policy(production_branches=['release'])
        self.assert_blocked('git push --force origin release', 'protected branch')
        self.assert_allowed('git push --force origin feature/release')

    def test_force_on_a_working_branch_uses_its_current_branch(self):
        self.git('checkout', '-qb', 'feature/work')
        self.assert_allowed('git push --force')
        self.assert_allowed('git push --force-with-lease origin HEAD')
        self.git('checkout', '-q', 'develop')
        self.assert_blocked('git push --force origin HEAD', 'protected branch')

    def test_force_with_an_unresolvable_target_is_blocked(self):
        self.assert_blocked('git push --force origin "$BRANCH"', 'protected branch')
        self.assert_blocked('git push -f origin $(git branch --show-current)', 'protected branch')
        self.assert_allowed('git push origin "$BRANCH"')

    def test_mirror_prune_and_forced_all_rewrite_the_remote(self):
        for command in ('git push --mirror', 'git push origin --mirror', 'git push --prune origin',
                        'git push --all --force origin', 'git push origin --all -f'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'rewrites or deletes remote refs')
        self.assert_allowed('git push --all origin')

    def test_repository_deletion_is_blocked(self):
        self.assert_blocked('gh repo delete fixture/project --yes', 'Deleting a repository')
        self.assert_allowed('gh repo view fixture/project')

    def test_preview_default_bare_alias_and_wrapped_forms_never_execute(self):
        for command in ('vercel', 'vc', 'vercel deploy', 'vercel deploy --target preview',
                        'vercel deploy --target=preview --prod', 'vercel deploy --target',
                        'npx --no-install vercel deploy', 'pnpm exec vercel', 'pnpm dlx vercel .',
                        'env MODE=x vercel .', 'vercel ./app', 'vercel --yes'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'Vercel Preview')

    def test_vercel_production_and_other_subcommands_pass_to_native_permissions(self):
        for command in ('vercel --prod', 'vercel deploy --prod', 'vc deploy --target production',
                        'npx --yes vercel deploy --prod', 'vercel inspect fixture', 'vercel env ls',
                        'vercel env add NAME production', 'vercel promote dpl_1', 'vercel logs x', 'vc --version'):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_destructive_forms_are_found_in_chains_substitutions_and_wrappers(self):
        for command in ('git status && git push -f origin develop', 'git status; git push -f origin develop',
                        'git status\ngit push -f origin develop', 'echo "$(git push -f origin develop)"',
                        'echo `git push -f origin develop`', "bash -lc 'git push -f origin develop'",
                        'env TEST=1 command git push -f origin develop', 'git -C . push -f origin develop',
                        'git --no-pager -c color.ui=never push -f origin develop', 'cd . && git push -f origin develop',
                        '(git push -f origin develop)', 'git push -o ci.skip -f origin develop',
                        'GIT_TRACE=1 git push -f origin develop', 'git status | git push -f origin develop'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')

    def test_redirections_are_not_refspecs(self):
        for command in ('git push --force origin 2>&1 | tail -20', 'git push --force origin >/dev/null',
                        'git push --force origin 2>/dev/null', 'git push --force-with-lease origin > /tmp/out.log',
                        'git push -f &>/dev/null', 'git push -f origin main 2>&1'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')
        self.git('checkout', '-qb', 'feature/work')
        self.assert_allowed('git push --force origin 2>&1 | tail -20')

    def test_repo_option_names_the_remote(self):
        self.git('checkout', '-qb', 'feature/work')
        for command in ('git push --repo=origin main -f', 'git push --repo origin main -f'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')

    def test_attached_push_option_values_are_not_flags(self):
        self.assert_allowed('git push -oskipdeploy origin develop')
        self.assert_blocked('git push -fo ci.skip origin develop', 'protected branch')
        self.assert_allowed('git push --force-if-includes origin develop')

    def test_common_wrappers_are_unwrapped(self):
        for command in ('timeout 120 git push -f origin develop', 'timeout -k 5 60s git push -f origin develop',
                        'nice -n 10 git push -f origin develop', 'sudo -u me git push -f origin develop'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'protected branch')

    def test_pinned_vercel_packages_and_global_options(self):
        for command in ('npx vercel@latest', 'npx vercel@latest deploy', 'pnpm dlx vercel@latest deploy',
                        'vercel --token=abc', 'vercel --scope myteam --yes'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'Vercel Preview')
        for command in ('vercel --token=abc pull --yes --environment=preview', 'vercel --scope myteam link',
                        'vercel --cwd apps/web build', 'vercel -t abc env pull', 'vercel --scope myteam env ls',
                        'vercel link', 'vercel pull', 'vc dev', 'vercel build', 'npx vercel@latest --prod'):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_literal_text_never_triggers_a_block(self):
        for command in ('printf "%s" "git push -f origin develop"', "echo 'git push --mirror'",
                        "echo '$(git push -f origin develop)'", 'echo gh repo delete x',
                        "cat <<'TEXT'\ngit push -f origin develop\nTEXT\n",
                        'git commit -m "$(cat <<\'EOF\'\nfix: stop git push -f origin develop\nEOF\n)"',
                        "grep -rn 'git push --force origin main' docs", 'rg "vercel deploy"',
                        'git log --grep="push -f"'):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_local_work_executes_normally(self):
        command = 'printf local > ' + subprocess.list2cmdline([str(self.sentinel)])
        self.assertEqual(self.execute(command).returncode, 0)
        self.assertEqual(self.sentinel.read_text(), 'local')

    def test_pull_is_never_blocked(self):
        (self.project / 'README.md').write_text('Uncommitted work.\n')
        (self.project / 'untracked.txt').write_text('scratch\n')
        self.assert_allowed('git pull --rebase')
        self.assert_allowed('git -C . pull')

    def test_unsupported_adapter_arguments_fail_closed(self):
        for arguments in ([], ['--harness'], ['--harness', 'other'], ['--other', 'claude']):
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, str(POLICY), *arguments], input='{}',
                                        text=True, capture_output=True, env=self.environment)
                self.assertEqual(result.returncode, 2)
                self.assertIn('/ FIX:', result.stderr)

    def test_malformed_events_fail_closed_with_repair_text(self):
        for data in ('{"tool_name":"Bash","tool_name":"Read"}', '{"tool_name": NaN}', '[]', '{}',
                     json.dumps({'tool_name': 'Bash'}),
                     json.dumps({'tool_name': 'Bash', 'hook_event_name': 'PreToolUse', 'tool_input': {'command': ['git']}})):
            with self.subTest(data=data):
                result = subprocess.run([sys.executable, str(POLICY), '--harness', 'claude'], input=data,
                                        text=True, capture_output=True, cwd=self.project, env=self.environment)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('BLOCKED / WHY:', result.stderr)
                self.assertIn('/ FIX:', result.stderr)
        self.assertEqual(self.invoke(event={'tool_name': 'Read', 'tool_input': {'file_path': 'README.md'}}).returncode, 0)

    def test_missing_cwd_and_missing_git_pass_through(self):
        # A removed worktree or absent Git must not block every shell command.
        event = dict(self.event('git push -f origin develop'), cwd='/nonexistent-policy-fixture')
        self.assertEqual(self.invoke(event=event).returncode, 0)
        environment = {**self.environment, 'PATH': str(self.workspace / 'empty-path')}
        self.assertEqual(self.invoke('git push origin develop', environment=environment).returncode, 0)
        self.assertEqual(self.invoke('printf local', environment=environment).returncode, 0)

    def test_unexpected_evaluation_errors_fail_open_with_a_warning(self):
        runtime = self.workspace / 'runtime'
        runtime.mkdir()
        broken = runtime / 'rpi-policy.py'
        broken.write_text(POLICY.read_text().replace('def push(', 'def push(*_):\n    raise RuntimeError\n\n\ndef _unused(', 1))
        result = subprocess.run([sys.executable, str(broken), '--harness', 'claude'],
                                input=json.dumps(self.event('git push origin develop')),
                                text=True, capture_output=True, env=self.environment, cwd=self.project)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('POLICY UNAVAILABLE', result.stderr)

    def test_wrapper_runtime_failures_warn_without_blocking(self):
        wrapper = ROOT / 'templates/hooks/guard-bash.sh'
        result = subprocess.run(['/bin/bash', str(wrapper)], input=json.dumps(self.event('git push')),
                                text=True, capture_output=True, env={**self.environment, 'PATH': '/nonexistent-fixture-path'})
        self.assertEqual(result.returncode, 0)
        self.assertIn('Python 3', result.stderr)
        # The engine checks its own runtime; an old interpreter passes through.
        old_runtime = ('import runpy, sys; sys.version_info = (3, 10, 0); '
                       'sys.argv = [sys.argv[1], "--harness", "claude"]; runpy.run_path(sys.argv[0], run_name="__main__")')
        result = subprocess.run([sys.executable, '-c', old_runtime, str(POLICY)], input=json.dumps(self.event('git push -f origin develop')),
                                text=True, capture_output=True, env=self.environment, cwd=self.project)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Python 3.11 or newer', result.stderr)
        broken = self.workspace / 'hooks/guard-bash.sh'
        broken.parent.mkdir()
        shutil.copyfile(wrapper, broken)
        result = subprocess.run(['/bin/bash', str(broken)], input=json.dumps(self.event('git push')),
                                text=True, capture_output=True, env=self.environment)
        self.assertEqual(result.returncode, 0)
        self.assertIn('rpi-policy.py', result.stderr)

    def test_wrapper_passes_through_policy_blocks(self):
        wrapper = self.project / '.claude/hooks/guard-bash.sh'
        wrapper.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'templates/hooks/guard-bash.sh', wrapper)
        runtime = self.project / '.rpi/scripts'
        runtime.mkdir(parents=True)
        shutil.copyfile(POLICY, runtime / POLICY.name)
        result = subprocess.run(['/bin/bash', str(wrapper)], input=json.dumps(self.event('git push -f origin develop')),
                                text=True, capture_output=True, env=self.environment)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('protected branch', result.stderr)

    def test_registered_wrapper_resolves_nested_cwd_and_missing_install_passes(self):
        for name, executable in (('python3', sys.executable), ('bash', shutil.which('bash'))):
            (self.fakebin / name).symlink_to(executable)
        (self.fakebin / 'git').unlink()
        runtime = self.project / '.rpi/scripts'
        runtime.mkdir(parents=True)
        shutil.copyfile(POLICY, runtime / POLICY.name)
        nested = self.project / 'nested'
        nested.mkdir()
        outside = self.workspace / 'outside'
        outside.mkdir()
        for harness, adapter in (('claude', 'claude-policy.json'), ('codex', 'codex-hooks.json')):
            hooks = self.project / ('.' + harness) / 'hooks'
            hooks.mkdir(parents=True)
            shutil.copyfile(ROOT / 'templates/hooks/guard-bash.sh', hooks / 'guard-bash.sh')
            records = json.loads((ROOT / 'templates/adapters' / adapter).read_text())['entries']
            registration = next(record['value']['hooks'][0]['command'] for record in records if record['id'] == 'pre-tool-policy')
            environment = {**self.environment, 'PATH': str(self.fakebin)}
            for cwd in (nested, outside):
                with self.subTest(harness=harness, cwd=cwd.name):
                    result = subprocess.run(['/bin/bash', '-c', registration], input=json.dumps(self.event('printf local')),
                                            capture_output=True, text=True, cwd=cwd, env=environment)
                    self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((runtime / '__pycache__').exists())

    def test_optional_telemetry_failure_does_not_change_policy_result(self):
        sink = self.project / '.rpi/local/contract-events.jsonl'
        sink.mkdir(parents=True)
        result = self.invoke('git push -f origin develop')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('TELEMETRY UNAVAILABLE', result.stderr)

    def test_blocks_are_recorded_in_the_contract_event_stream(self):
        self.invoke('git push -f origin develop')
        self.invoke('git status')
        lines = (self.project / '.rpi/local/contract-events.jsonl').read_text().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(set(record), {'ts', 'session_id', 'hook', 'decision', 'rule', 'file'})
        self.assertEqual((record['decision'], record['rule']), ('block', 'protected-branch'))


if __name__ == '__main__':
    unittest.main()
