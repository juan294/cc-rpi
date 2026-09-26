"""Opt-in Git pre-push receipt gate; every remote is a temporary local bare repository."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import unittest

import test_policy

PREPUSH = test_policy.ROOT / 'templates/scripts/rpi-prepush.py'
ZERO = '0' * 40
DOCS = test_policy.ROOT / 'docs/native-policy.md'
# The documented enable command, verbatim: a shared (or committed) wrapper that runs the
# pushing worktree's own gate and refuses with BLOCKED / WHY / FIX when that checkout has none.
INSTALL = r'''hooks=$(git config --type=path --get core.hooksPath || echo "$(git rev-parse --path-format=absolute --git-common-dir)/hooks")
mkdir -p "$hooks" && cat > "$hooks/pre-push" <<'EOF'
#!/bin/sh
top=$(git rev-parse --show-toplevel 2>/dev/null)
gate="$top/.rpi/scripts/rpi-prepush.py"
case $0 in /*) hook=$0 ;; *) hook=$PWD/$0 ;; esac
if [ ! -f "$gate" ]; then
  echo "BLOCKED / WHY: this checkout has no .rpi/scripts/rpi-prepush.py receipt gate. / FIX: push from a checkout that contains it, such as the integration worktree; or restore it with a reviewed update (RPI_SOURCE is your cc-rpi checkout): bash \"\$RPI_SOURCE/scripts/install.sh\" --target \"$top\" --action update --output \"$top/.rpi/local/plans/restore.json\"; review it, then bash \"\$RPI_SOURCE/scripts/install.sh\" --apply \"$top/.rpi/local/plans/restore.json\"; or, if this project no longer opts in, remove this hook: rm \"$hook\"" >&2
  exit 1
fi
for python in python3.14 python3.13 python3.12 python3.11 python3; do
  command -v "$python" >/dev/null 2>&1 && break
  python=
done
if [ -z "$python" ] || ! "$python" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
  echo "BLOCKED / WHY: the receipt gate needs Python 3.11 or newer; the first of python3.14, python3.13, python3.12, python3.11 and python3 on PATH is ${python:-missing}. / FIX: install Python 3.11 or newer so python3.11 (or newer) is on PATH (brew install python@3.13, or sudo apt-get install python3.11), then push again." >&2
  exit 1
fi
exec "$python" "$gate" "$@"
EOF
chmod +x "$hooks/pre-push"
'''


class PrePushFixture(test_policy.PolicyFixture):
    def gate(self, *lines, script=PREPUSH, environment=None, remote='origin'):
        return subprocess.run([sys.executable, str(script), remote, 'https://github.com/fixture/project.git'],
                              input=''.join(line + '\n' for line in lines), capture_output=True, text=True,
                              cwd=self.project, env=environment or self.environment)

    def line(self, remote_ref, local_sha=None, local_ref=None, remote_sha=ZERO):
        local_sha = local_sha or self.git('rev-parse', 'HEAD')
        return ' '.join((local_ref or remote_ref, local_sha, remote_ref, remote_sha))

    def assert_passes(self, *lines, **kwargs):
        result = self.gate(*lines, **kwargs)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def assert_refused(self, *lines, reason='', **kwargs):
        result = self.gate(*lines, **kwargs)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('BLOCKED / WHY:', result.stderr)
        self.assertIn('/ FIX:', result.stderr)
        self.assertIn(reason, result.stderr)
        return result


class PrePushTests(PrePushFixture):
    def test_projects_that_do_not_opt_in_pass_immediately(self):
        (self.project / 'README.md').write_text('Dirty, unverified.\n')
        self.assert_passes(self.line('refs/heads/develop'), self.line('refs/tags/v9.9.9'))
        (self.project / '.rpi/policy.json').unlink()
        self.assert_passes(self.line('refs/heads/develop'), self.line('refs/heads/develop', ZERO))

    def test_integration_push_needs_current_complete_evidence(self):
        self.opt_in()
        result = self.assert_refused(self.line('refs/heads/develop'), reason='verification evidence is missing')
        self.assertIn('bash scripts/verify-local.sh', result.stderr)
        path = self.evidence()
        self.assert_passes(self.line('refs/heads/develop'))
        self.assert_passes('', self.line('refs/heads/develop', local_ref='HEAD'))
        report = json.loads(path.read_text())
        for mutation in (dict(report, suite='custom'), dict(report, passed=False),
                         dict(report, checks=report['checks'][:1]),
                         dict(report, checks=list(reversed(report['checks']))),
                         dict(report, checks=[dict(item, exit_code=1) for item in report['checks']])):
            with self.subTest(mutation=mutation):
                path.write_text(json.dumps(mutation))
                self.assert_refused(self.line('refs/heads/develop'), reason='does not attest')
        self.evidence()
        (self.project / 'README.md').write_text('Changed after verification.\n')
        self.assert_refused(self.line('refs/heads/develop'), reason='clean')

    def test_working_branches_and_nothing_to_push_are_never_gated(self):
        self.opt_in()
        (self.project / 'scratch.txt').write_text('in progress\n')
        self.assert_passes()
        self.assert_passes(self.line('refs/heads/feature/work'), self.line('refs/heads/feature/old', ZERO),
                           self.line('refs/tags/nightly'), self.line('refs/notes/commits'))

    def test_every_line_of_a_bulk_push_is_checked(self):
        self.opt_in()
        verified = self.git('rev-parse', 'HEAD')
        self.evidence()
        feature = self.line('refs/heads/feature/work')
        self.assert_passes(feature, self.line('refs/heads/develop'), self.line('refs/heads/release/x'))
        self.commit('Unverified change')
        result = self.assert_refused(feature, self.line('refs/heads/develop'), reason='does not attest')
        self.assertIn('bash scripts/verify-local.sh', result.stderr)
        self.git('reset', '-q', '--hard', verified)
        other = self.git('commit-tree', '-m', 'Unverified', self.git('rev-parse', 'HEAD^{tree}'))
        result = self.assert_refused(feature, self.line('refs/heads/develop', other), reason='differs from the verified candidate')
        fix = result.stderr.split('/ FIX:')[1]
        self.assertIn('git push origin HEAD:refs/heads/develop', fix)
        self.assertIn('git switch --detach ' + other, fix)

    def test_mismatched_integration_fix_never_repeats_the_refused_push(self):
        self.opt_in()
        integration = self.git('rev-parse', 'HEAD')
        self.git('switch', '-qc', 'feat')
        self.commit('Verified feature work')
        self.evidence()
        result = self.assert_refused(self.line('refs/heads/develop', integration, 'refs/heads/develop'),
                                     reason='differs from the verified candidate')
        fix = result.stderr.split('/ FIX:')[1].strip()
        self.assertTrue(fix.startswith('Publish the verified HEAD: git push origin HEAD:refs/heads/develop;'), fix)
        self.assertIn('git switch develop, run bash scripts/verify-local.sh, then git push origin develop', fix)
        self.assertNotIn('Push the verified commit: git push origin develop', fix)

    def test_version_tags_must_peel_to_the_verified_commit(self):
        self.opt_in()
        self.tag('v9.9.9')
        tag_object = self.git('rev-parse', 'refs/tags/v9.9.9')
        self.assertNotEqual(tag_object, self.git('rev-parse', 'HEAD'), 'the fixture tag is annotated')
        self.evidence()
        self.assert_passes(self.line('refs/tags/v9.9.9', tag_object))
        self.assert_passes(self.line('refs/tags/2.0.0-rc.1'))
        self.commit('Moves HEAD past the tag')
        self.evidence()
        result = self.assert_refused(self.line('refs/tags/v9.9.9', tag_object), reason='differs from the verified candidate')
        fix = result.stderr.split('/ FIX:')[1]
        self.assertIn('git switch --detach v9.9.9', fix)
        self.assertIn('git push origin refs/tags/v9.9.9', fix)
        self.assertNotIn('git push origin develop', fix)
        self.assert_passes(self.line('refs/tags/v9.9.9', ZERO))  # Deleting a remote tag publishes nothing.
        self.assert_passes(self.line('refs/tags/release-candidate', tag_object))

    def test_version_tags_follow_the_policy_committed_in_the_tagged_commit(self):
        self.tag('v0.9.0')  # Before the project opted in.
        old = self.git('rev-parse', 'refs/tags/v0.9.0')
        self.opt_in()
        opted = self.git('rev-parse', 'HEAD')
        self.commit('Unverified after opt-in')
        self.evidence()
        self.assert_passes(self.line('refs/tags/v0.9.0', old))
        # Moving an existing opted-in remote tag onto the old commit is still gated.
        self.assert_refused(self.line('refs/tags/v0.9.0', old, remote_sha=opted), reason='differs from the verified candidate')
        self.assert_refused(self.line('refs/tags/v1.0.0', opted), reason='differs from the verified candidate')

    def test_replaced_remote_commit_policy_gates_an_opt_out_push(self):
        self.opt_in()
        published = self.git('rev-parse', 'HEAD')
        self.policy(require_verification_receipt=False)
        self.commit('Opt out without verification')
        self.assert_refused(self.line('refs/heads/develop', remote_sha=published), reason='verification evidence is missing')
        self.assert_passes(self.line('refs/heads/develop', remote_sha='1' * 40))  # An unfetched remote object cannot be read.
        self.evidence()
        self.assert_passes(self.line('refs/heads/develop', remote_sha=published))  # One verified push turns it off.
        (self.project / '.rpi/local/verification.json').unlink()
        (self.project / '.rpi/policy.json').unlink()
        self.commit('Remove the policy')
        self.assert_refused(self.line('refs/heads/develop', remote_sha=published), reason='verification evidence is missing')

    def test_receipt_directory_never_dirties_the_candidate(self):
        # A clone whose own .gitignore does not ignore .rpi/local/ must not loop on its receipt.
        (self.project / '.gitignore').write_text('')
        self.opt_in()
        self.evidence()
        self.assertIn('.rpi/local/', self.git('status', '--porcelain', '--untracked-files=all'))
        self.assert_passes(self.line('refs/heads/develop'))
        (self.project / 'scratch.txt').write_text('unfinished\n')
        result = self.assert_refused(self.line('refs/heads/develop'), reason='clean')
        self.assertIn('scratch.txt', result.stderr)
        self.assertNotIn('.rpi/local', result.stderr.split('/ FIX:')[0])

    def test_refs_heads_prefix_names_the_same_integration_branch(self):
        self.policy(integration_branch='refs/heads/develop')
        self.opt_in()
        self.assert_refused(self.line('refs/heads/develop'), reason='verification evidence is missing')
        self.assert_refused(self.line('refs/heads/develop', ZERO, '(delete)'), reason='Deleting the integration branch (develop)')
        self.evidence()
        self.assert_passes(self.line('refs/heads/develop'), self.line('refs/heads/refs/heads/develop'))
        self.policy(integration_branch='refs/heads/')
        self.commit('Empty branch name')
        self.assert_refused(self.line('refs/heads/feature/work'), reason='integration_branch')

    def test_policy_committed_in_the_pushed_commit_opts_in(self):
        self.opt_in()
        opted = self.git('rev-parse', 'HEAD')
        self.policy(require_verification_receipt=False)
        self.commit('Checkout that predates the opt-in')
        self.evidence()
        result = self.assert_refused(self.line('refs/heads/develop', opted), reason='differs from the verified candidate')
        self.assertIn(opted[:12], result.stderr)
        self.assert_refused(self.line('refs/tags/v2.0.0', opted), reason='differs from the verified candidate')
        self.assert_passes(self.line('refs/heads/develop'), self.line('refs/heads/feature/work', opted))
        (self.project / '.rpi/local/verification.json').unlink()
        self.assert_refused(self.line('refs/heads/develop', opted), reason='verification evidence is missing')
        self.policy(require_verification_receipt=True, integration_branch=7)
        self.commit('Broken committed policy')
        broken = self.git('rev-parse', 'HEAD')
        self.policy(require_verification_receipt=False, integration_branch='develop')
        self.commit('Repaired checkout')
        self.assert_refused(self.line('refs/heads/develop', broken), reason='committed in ' + broken[:12])

    def test_deleting_the_integration_branch_is_refused(self):
        self.opt_in()
        self.evidence()
        self.assert_refused(self.line('refs/heads/develop', ZERO, '(delete)'), reason='Deleting the integration branch')

    def test_invalid_policy_fails_closed(self):
        path = self.project / '.rpi/policy.json'
        base = json.loads(path.read_text())
        for data, reason in (('not json', 'not valid JSON'), ('[]', 'Invalid project policy'),
                             ('{"schema_version": 1, "unknown": 1}', 'Invalid project policy'),
                             ('{"schema_version": 1, "require_verification_receipt": "yes"}', 'true or false'),
                             (json.dumps(dict(base, require_verification_receipt=True, integration_branch=['main'])), 'integration_branch'),
                             (json.dumps({k: v for k, v in dict(base, require_verification_receipt=True).items() if k != 'integration_branch'}),
                              'integration_branch'),
                             (json.dumps(dict(base, require_verification_receipt=True, remote=7)), 'remote'),
                             (json.dumps(dict(base, require_verification_receipt=True, verification_command=[])), 'verification command'),
                             (json.dumps(dict(base, require_verification_receipt=True, verification_checks=[])), 'verification inventory'),
                             (json.dumps(dict(base, require_verification_receipt=True, verification_checks=[{'name': 't', 'argv': [None]}])),
                              'unique names and literal argv')):
            with self.subTest(data=data):
                path.write_text(data)
                self.assert_refused(self.line('refs/heads/feature/work'), reason=reason)
        copied = self.workspace / 'policy.json'
        copied.write_text(json.dumps(dict(base, require_verification_receipt=True)))
        path.unlink()
        path.symlink_to(copied)
        self.assert_refused(self.line('refs/heads/develop'), reason='regular file')

    def test_malformed_input_fails_closed_when_opted_in(self):
        self.opt_in()
        self.evidence()
        self.assert_refused('refs/heads/develop only-three fields', reason='pre-push input')
        result = subprocess.run([sys.executable, str(PREPUSH)], input='', capture_output=True, text=True,
                                cwd=self.project, env=self.environment)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('remote name and URL', result.stderr)

    def runtime(self, helper=None):
        runtime = self.workspace / 'runtime'
        runtime.mkdir()
        script = runtime / 'rpi-prepush.py'
        script.write_bytes(PREPUSH.read_bytes())
        if helper is not None:
            (runtime / 'rpi-candidate.py').write_text(helper)
        return script

    def test_missing_candidate_helper_fails_closed_only_when_opted_in(self):
        script = self.runtime()
        self.assert_passes(self.line('refs/heads/develop'), script=script)
        self.opt_in()
        self.evidence()
        self.assert_refused(self.line('refs/heads/develop'), script=script, reason='candidate identity helper is missing')

    def test_unexpected_gate_errors_fail_closed(self):
        script = self.runtime('def identity(root):\n    raise RuntimeError\n\ndef environment(*_):\n    return {}\n')
        self.opt_in()
        self.evidence()
        result = self.assert_refused(self.line('refs/heads/develop'), script=script, reason='Receipt verification failed')
        self.assertIn('bash "$RPI_SOURCE/scripts/install.sh" --check --target', result.stderr)
        self.assertNotIn('rpi-distribution.py check --target .', result.stderr)

    def test_changed_settings_cannot_reuse_a_passing_receipt(self):
        self.opt_in()
        self.evidence()
        changed = {**self.environment, 'LC_ALL': 'C.UTF-8', 'TZ': 'Etc/GMT+3'}
        result = self.assert_refused(self.line('refs/heads/develop'), environment=changed, reason='locale, timezone or Python')
        self.assertIn('LC_ALL=C.UTF-8', result.stderr)
        self.assertIn('TZ=Etc/GMT+3', result.stderr)
        path = self.project / '.rpi/local/verification.json'
        report = json.loads(path.read_text())
        for key in ('environment', 'environment_after'):
            report[key] = dict(report[key], executables=dict(report[key]['executables'], gh={'path': '/opt/old/gh', 'size': 1, 'mtime_ns': 1}))
        path.write_text(json.dumps(report))
        result = self.assert_refused(self.line('refs/heads/develop'), reason='executables.gh')
        self.assertNotIn('LC_ALL', result.stderr)

    def test_interpreter_only_difference_names_both_interpreters(self):
        self.opt_in()
        path = self.evidence()
        report = json.loads(path.read_text())
        for key in ('environment', 'environment_after'):
            report[key] = dict(report[key], python='3.99.0', executable='/opt/verified/bin/python3.99')
        path.write_text(json.dumps(report))
        result = self.assert_refused(self.line('refs/heads/develop'), reason='differs only in its Python interpreter')
        self.assertIn('/opt/verified/bin/python3.99 (Python 3.99.0)', result.stderr)
        self.assertIn(os.path.realpath(sys.executable), result.stderr)
        self.assertIn('Run exactly ' + shlex.join([sys.executable, '.rpi/scripts/rpi-verify.py']), result.stderr.split('/ FIX:')[1])

    def test_python_runner_fixes_name_the_hook_interpreter(self):
        self.policy(verification_command=['python3', '.rpi/scripts/rpi-verify.py'])
        self.opt_in()
        exact = shlex.join([sys.executable, '.rpi/scripts/rpi-verify.py'])
        result = self.assert_refused(self.line('refs/heads/develop'), reason='verification evidence is missing')
        self.assertIn('Run ' + exact, result.stderr)
        path = self.evidence()
        report = json.loads(path.read_text())
        for key in ('environment', 'environment_after'):
            report[key] = dict(report[key], executables=dict(report[key]['executables'],
                                                             python3={'path': '/opt/shim/python3', 'size': 1, 'mtime_ns': 1}))
        path.write_text(json.dumps(report))
        result = self.assert_refused(self.line('refs/heads/develop'), reason='python3 first on PATH')
        self.assertIn('/opt/shim/python3', result.stderr)
        self.assertIn('Run exactly ' + exact + ' in the shell that runs git push', result.stderr)

    def test_git_exec_path_prepended_by_git_does_not_change_the_runtime(self):
        self.opt_in()
        self.evidence()
        exec_path = self.workspace / 'git-core'
        exec_path.mkdir()
        (exec_path / 'git').symlink_to(self.environment['RPI_REAL_GIT'])
        hooked = {**self.environment, 'GIT_EXEC_PATH': str(exec_path),
                  'PATH': str(exec_path) + os.pathsep + self.environment['PATH']}
        self.assert_passes(self.line('refs/heads/develop'), environment=hooked)


class InstalledHookTests(PrePushFixture):
    """The documented wrapper under a real git push to a temporary bare remote."""

    def setUp(self):
        super().setUp()
        interpreter = self.workspace / 'python-bin'
        interpreter.mkdir()
        for name in ('python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3'):
            shim = interpreter / name  # Exec keeps the runner's own (possibly virtual) environment.
            shim.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
            shim.chmod(0o755)
        # Real Git first: the fixture's fake git would intercept the push.
        self.environment = {**self.environment, 'PATH': str(interpreter) + os.pathsep +
                            self.environment['PATH'].split(os.pathsep, 1)[1]}
        self.remote = self.workspace / 'remote.git'
        subprocess.run([self.environment['RPI_REAL_GIT'], 'init', '-q', '--bare', str(self.remote)], check=True)
        scripts = self.project / '.rpi/scripts'
        scripts.mkdir()
        for name in ('rpi-prepush.py', 'rpi-candidate.py', 'rpi-verify.py'):
            shutil.copyfile(test_policy.ROOT / 'templates/scripts' / name, scripts / name)
        self.opt_in()

    def install(self):
        """Run the documented enable command from the repository root."""
        subprocess.run(['bash', '-c', INSTALL], cwd=self.project, env=self.environment, check=True)

    def git_in(self, cwd, *arguments):
        subprocess.run([self.environment['RPI_REAL_GIT'], '-C', str(cwd), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.invalid', *arguments], check=True, capture_output=True)

    def test_documented_command_is_the_tested_command(self):
        self.assertIn('```bash\n' + INSTALL + '```', DOCS.read_text())

    def push(self, *arguments, cwd=None):
        return subprocess.run([self.environment['RPI_REAL_GIT'], 'push', '--porcelain', str(self.remote), *arguments],
                              cwd=cwd or self.project, env=self.environment, capture_output=True, text=True)

    def remote_ref(self, ref):
        result = subprocess.run([self.environment['RPI_REAL_GIT'], '-C', str(self.remote), 'rev-parse', '--verify', '--quiet', ref],
                                capture_output=True, text=True)
        return result.stdout.strip() or None

    def test_real_pushes_are_gated_by_the_refs_git_reports(self):
        self.install()
        self.git('branch', 'feature/work')
        self.assertEqual(self.push('feature/work').returncode, 0)
        for arguments in (('develop',), ('--all',), ('HEAD:refs/heads/develop',), ('refs/heads/*:refs/heads/*',)):
            with self.subTest(arguments=arguments):
                result = self.push(*arguments)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('verification evidence is missing', result.stderr)
                self.assertIsNone(self.remote_ref('refs/heads/develop'))
        self.evidence()
        result = self.push('--all')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_ref('refs/heads/develop'), self.git('rev-parse', 'HEAD'))

    def test_bulk_tag_push_checks_each_version_tag(self):
        self.install()
        self.tag('v1.0.0')
        self.commit('After the old tag')
        self.evidence()
        result = self.push('--tags')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('differs from the verified candidate', result.stderr)
        self.assertIsNone(self.remote_ref('refs/tags/v1.0.0'))
        self.tag('v1.1.0')
        result = self.push('refs/tags/v1.1.0')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_worktree_push_uses_that_worktree_candidate(self):
        self.install()  # core.hooksPath unset: the clone's common hooks directory, outside every worktree.
        self.assertTrue((Path(self.git('rev-parse', '--path-format=absolute', '--git-common-dir')) / 'hooks/pre-push').is_file())
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.evidence()
        linked = self.workspace / 'linked'
        self.git('worktree', 'add', '-q', '-b', 'feature/linked', str(linked))
        result = self.push('HEAD:refs/heads/develop', cwd=linked)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('verification evidence is missing', result.stderr)
        self.assertEqual(self.push('feature/linked', cwd=linked).returncode, 0)

    def verify(self, cwd):
        return subprocess.run([sys.executable, '.rpi/scripts/rpi-verify.py'], cwd=cwd, env=self.environment,
                              capture_output=True, text=True, timeout=60)

    def test_verified_push_succeeds_without_a_project_ignore_rule(self):
        # Fresh clones and linked worktrees whose .gitignore does not list .rpi/local/.
        self.install()
        (self.project / '.gitignore').write_text('')
        self.policy(verification_checks=[{'name': 'ok', 'argv': ['python3', '-c', 'pass']}])
        self.commit('Real checks, no project ignore rule')
        result = self.verify(self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.project / '.rpi/local/.gitignore').read_text(), '*\n')
        self.assertEqual(self.git('status', '--porcelain', '--untracked-files=all'), '')
        result = self.push('develop')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        linked = self.workspace / 'linked'
        self.git('worktree', 'add', '-q', '-b', 'feature/linked', str(linked))
        (linked / 'change.txt').write_text('Integrated in a linked worktree.\n')
        self.git_in(linked, 'add', '.')
        self.git_in(linked, 'commit', '-qm', 'Linked')
        result = self.verify(linked)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.push('HEAD:refs/heads/develop', cwd=linked)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_ref('refs/heads/develop'), self.git('rev-parse', 'feature/linked'))

    def test_pre_opt_in_worktree_cannot_publish_the_opted_in_branch(self):
        self.install()
        stale = self.workspace / 'stale'
        self.git('worktree', 'add', '-q', '-b', 'old', str(stale))
        stale_policy = stale / '.rpi/policy.json'
        stale_policy.write_text(json.dumps(dict(json.loads(stale_policy.read_text()), require_verification_receipt=False)))
        self.git_in(stale, 'commit', '-qam', 'Pre-opt-in policy')
        for arguments in (('develop',), ('--all',)):
            with self.subTest(arguments=arguments):
                result = self.push(*arguments, cwd=stale)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('verification evidence is missing', result.stderr)
                self.assertIsNone(self.remote_ref('refs/heads/develop'))
        self.assertEqual(self.push('old', cwd=stale).returncode, 0)

    def test_checkout_without_the_gate_refuses_with_a_runnable_fix(self):
        self.install()
        hook = Path(self.git('rev-parse', '--path-format=absolute', '--git-common-dir')) / 'hooks/pre-push'
        old = self.workspace / 'no-scripts'
        self.git('worktree', 'add', '-q', '-b', 'ancient', str(old), 'HEAD~1')
        self.assertFalse((old / '.rpi/scripts/rpi-prepush.py').exists())
        for arguments in (('HEAD:refs/heads/develop',), ('ancient',)):
            with self.subTest(arguments=arguments):
                result = self.push(*arguments, cwd=old)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('BLOCKED / WHY: this checkout has no .rpi/scripts/rpi-prepush.py', result.stderr)
                self.assertIn('/ FIX:', result.stderr)
                self.assertIn('bash "$RPI_SOURCE/scripts/install.sh" --target "' + str(old) + '" --action update', result.stderr)
                self.assertIn('rm "' + str(hook) + '"', result.stderr)
                self.assertNotIn("can't open file", result.stderr)
        self.assertIsNone(self.remote_ref('refs/heads/develop'))
        subprocess.run(['sh', '-c', 'rm "' + str(hook) + '"'], check=True)  # The printed way out works.
        self.assertEqual(self.push('ancient', cwd=old).returncode, 0)

    def test_main_worktree_missing_gate_prints_an_absolute_hook_path(self):
        self.install()
        hook = Path(self.git('rev-parse', '--path-format=absolute', '--git-common-dir')) / 'hooks/pre-push'
        (self.project / '.rpi/scripts/rpi-prepush.py').unlink()
        result = self.push('develop')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('rm "' + str(hook) + '"', result.stderr)

    def narrow_path(self, **scripts):
        """The fixture environment with PATH holding real Git plus only the given interpreter scripts."""
        directory = self.workspace / 'narrow-bin'
        directory.mkdir()
        (directory / 'git').symlink_to(self.environment['RPI_REAL_GIT'])
        for name, body in scripts.items():
            (directory / name).write_text('#!/bin/sh\n' + body + '\n')
            (directory / name).chmod(0o755)
        return {**self.environment, 'PATH': str(directory)}

    def test_wrapper_selects_a_supported_interpreter_before_an_old_python3(self):
        self.install()
        old = 'exit 1'  # A pre-3.11 python3 fails the wrapper's version probe and must never run the gate.
        self.environment = self.narrow_path(**{'python3.12': 'exec ' + shlex.quote(sys.executable) + ' "$@"', 'python3': old})
        self.evidence()
        result = self.push('develop')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.remote_ref('refs/heads/develop'), self.git('rev-parse', 'HEAD'))

    def test_wrapper_refuses_when_no_supported_interpreter_exists(self):
        self.install()
        self.environment = self.narrow_path(python3='exit 1')
        result = self.push('develop')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('BLOCKED / WHY: the receipt gate needs Python 3.11 or newer', result.stderr)
        self.assertIn('/ FIX: install Python 3.11 or newer', result.stderr)
        self.assertIsNone(self.remote_ref('refs/heads/develop'))

    def test_opt_out_push_needs_one_verified_push(self):
        self.install()
        self.evidence()
        self.assertEqual(self.push('develop').returncode, 0)
        published = self.remote_ref('refs/heads/develop')
        self.policy(require_verification_receipt=False)
        self.commit('Opt out without verification')
        result = self.push('develop')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('does not attest this exact complete candidate', result.stderr)
        self.assertEqual(self.remote_ref('refs/heads/develop'), published)

    def test_pre_opt_in_version_tags_publish_to_a_new_mirror(self):
        self.install()
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'tag', '-a', 'v0.9.0', '-m', 'Old', 'HEAD~1')
        self.tag('v1.0.0')
        self.evidence()
        result = self.push('--tags')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIsNotNone(self.remote_ref('refs/tags/v0.9.0'))
        self.assertIsNotNone(self.remote_ref('refs/tags/v1.0.0'))

    def test_relative_hooks_path_wrapper_is_committed_for_every_worktree(self):
        self.git('config', 'core.hooksPath', '.githooks')
        self.install()
        self.assertTrue((self.project / '.githooks/pre-push').is_file())
        self.assertIn('.githooks/', self.git('status', '--porcelain'))
        self.commit('Commit the shared pre-push wrapper')  # As documented for a relative core.hooksPath.
        self.assertEqual(self.git('status', '--porcelain'), '')
        linked = self.workspace / 'linked'
        self.git('worktree', 'add', '-q', '-b', 'feature/linked', str(linked))
        self.assertTrue((linked / '.githooks/pre-push').is_file())
        result = self.push('HEAD:refs/heads/develop', cwd=linked)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('verification evidence is missing', result.stderr)
        self.assertIsNone(self.remote_ref('refs/heads/develop'))


if __name__ == '__main__':
    unittest.main()
