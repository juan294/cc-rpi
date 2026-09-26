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
# The documented installation: a wrapper that runs the pushing worktree's own gate.
WRAPPER = '#!/bin/sh\nexec python3 "$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py" "$@"\n'


class PrePushFixture(test_policy.PolicyFixture):
    def gate(self, *lines, script=PREPUSH, environment=None, remote='origin'):
        return subprocess.run([sys.executable, str(script), remote, 'https://github.com/fixture/project.git'],
                              input=''.join(line + '\n' for line in lines), capture_output=True, text=True,
                              cwd=self.project, env=environment or self.environment)

    def line(self, remote_ref, local_sha=None, local_ref=None):
        local_sha = local_sha or self.git('rev-parse', 'HEAD')
        return ' '.join((local_ref or remote_ref, local_sha, remote_ref, ZERO))

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
        self.assertIn('git push origin develop', result.stderr)

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
        self.assert_refused(self.line('refs/tags/v9.9.9', tag_object), reason='differs from the verified candidate')
        self.assert_passes(self.line('refs/tags/v9.9.9', ZERO))  # Deleting a remote tag publishes nothing.
        self.assert_passes(self.line('refs/tags/release-candidate', tag_object))

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
        self.assert_refused(self.line('refs/heads/develop'), script=script, reason='Receipt verification failed')

    def test_changed_settings_cannot_reuse_a_passing_receipt(self):
        self.opt_in()
        self.evidence()
        changed = {**self.environment, 'LC_ALL': 'C.UTF-8', 'TZ': 'Etc/GMT+3'}
        self.assert_refused(self.line('refs/heads/develop'), environment=changed, reason='locale, timezone or Python')

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
        shim = interpreter / 'python3'  # Exec keeps the runner's own (possibly virtual) environment.
        shim.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
        shim.chmod(0o755)
        # Real Git first: the fixture's fake git would intercept the push.
        self.environment = {**self.environment, 'PATH': str(interpreter) + os.pathsep +
                            self.environment['PATH'].split(os.pathsep, 1)[1]}
        self.remote = self.workspace / 'remote.git'
        subprocess.run([self.environment['RPI_REAL_GIT'], 'init', '-q', '--bare', str(self.remote)], check=True)
        scripts = self.project / '.rpi/scripts'
        scripts.mkdir()
        for name in ('rpi-prepush.py', 'rpi-candidate.py'):
            shutil.copyfile(test_policy.ROOT / 'templates/scripts' / name, scripts / name)
        hooks = Path(self.git('rev-parse', '--path-format=absolute', '--git-path', 'hooks'))  # As documented.
        hooks.mkdir(exist_ok=True)
        (hooks / 'pre-push').write_text(WRAPPER)
        (hooks / 'pre-push').chmod(0o755)
        self.opt_in()

    def push(self, *arguments, cwd=None):
        return subprocess.run([self.environment['RPI_REAL_GIT'], 'push', '--porcelain', str(self.remote), *arguments],
                              cwd=cwd or self.project, env=self.environment, capture_output=True, text=True)

    def remote_ref(self, ref):
        result = subprocess.run([self.environment['RPI_REAL_GIT'], '-C', str(self.remote), 'rev-parse', '--verify', '--quiet', ref],
                                capture_output=True, text=True)
        return result.stdout.strip() or None

    def test_real_pushes_are_gated_by_the_refs_git_reports(self):
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
        self.evidence()
        linked = self.workspace / 'linked'
        self.git('worktree', 'add', '-q', '-b', 'feature/linked', str(linked))
        result = self.push('HEAD:refs/heads/develop', cwd=linked)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('verification evidence is missing', result.stderr)
        self.assertEqual(self.push('feature/linked', cwd=linked).returncode, 0)


if __name__ == '__main__':
    unittest.main()
