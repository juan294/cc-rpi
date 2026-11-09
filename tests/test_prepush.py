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
INSTALL = r'''hooks_common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
top=$(git rev-parse --show-toplevel 2>/dev/null)
hooks=$(git config --type=path --get core.hooksPath || echo "$hooks_common/hooks")
case $hooks in /*) ;; *) hooks="$top/$hooks" ;; esac
gate_line='/^[[:space:]]*#|^[[:space:]]*(echo|printf|:)[[:space:]]/'
if [ -z "$hooks_common" ]; then
  echo "BLOCKED / WHY: the current directory is not inside a Git repository, so there is no hooks directory to write. / FIX: cd to the repository root of the integration checkout, then run this command again." >&2
  false
elif [ -z "$top" ]; then
  echo "BLOCKED / WHY: this is a bare repository or the inside of a .git directory: it has no working tree, so there is no integration checkout whose receipt the gate could read, and a relative core.hooksPath has no root to resolve against. / FIX: cd to the repository root of the integration checkout, then run this command again." >&2
  false
elif [ -e "$hooks" ] && [ ! -d "$hooks" ]; then
  echo "BLOCKED / WHY: the hooks path $hooks (core.hooksPath, or the clone's hooks directory) exists and is not a directory. / FIX: point core.hooksPath at a directory (git config core.hooksPath PATH) or move that file away, then run this command again." >&2
  false
elif [ -L "$hooks/pre-push" ]; then
  if [ -f "$hooks/pre-push" ] && awk "$gate_line { next } /^[[:space:]]*exit([[:space:]]|;|\$)/ { stopped = 1 } /rpi-prepush\\.py/ && !stopped { found = 1 } END { exit !found }" "$hooks/pre-push"; then
    echo "$hooks/pre-push is a symbolic link to a hook that runs rpi-prepush.py; left unchanged. WARNING: if an earlier line can end the hook, or the hook drops the gate's exit status, the gate cannot refuse; check one refusal."
  else
    echo "BLOCKED / WHY: $hooks/pre-push is a symbolic link, and this command never writes through a link. / FIX: add this line to the hook the link points to, or replace the link with a regular file that contains it, before any command that reads standard input (replace python3.13 with any Python 3.11 or newer on PATH), then push again: python3.13 \"\$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py\" \"\$@\" || exit 1" >&2
    false
  fi
elif [ -e "$hooks/pre-push" ] && ! grep -q 'cc-rpi receipt gate wrapper' "$hooks/pre-push"; then
  if awk "$gate_line { next } /^[[:space:]]*exit([[:space:]]|;|\$)/ { stopped = 1 } /rpi-prepush\\.py/ && !stopped { found = 1 } END { exit !found }" "$hooks/pre-push"; then
    echo "$hooks/pre-push runs rpi-prepush.py; left unchanged. WARNING: if an earlier line can end the hook, or the hook drops the gate's exit status, the gate cannot refuse; check one refusal."
  else
    echo "BLOCKED / WHY: $hooks/pre-push already exists and does not run rpi-prepush.py (a comment, an echo or a line after an exit does not count), and this command never overwrites an existing hook. / FIX: add this line near the top of that hook, before any exit and before any command that reads standard input (replace python3.13 with any Python 3.11 or newer on PATH), then push again: python3.13 \"\$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py\" \"\$@\" || exit 1" >&2
    false
  fi
else
  find "$hooks" -maxdepth 1 -type f -name '.pre-push.[0-9]*' -exec sh -c 'for stale; do kill -0 "${stale##*.}" 2>/dev/null || rm -f "$stale"; done' sh {} + 2>/dev/null
  tmp="$hooks/.pre-push.$$"
  if mkdir -p "$hooks" 2>/dev/null && cat 2>/dev/null > "$tmp" <<'EOF'
#!/bin/sh
# cc-rpi receipt gate wrapper: written by the documented enable command; run it again to update.
top=$(git rev-parse --show-toplevel 2>/dev/null)
gate="$top/.rpi/scripts/rpi-prepush.py"
case $0 in /*) hook=$0 ;; *) hook=$PWD/$0 ;; esac
if [ -z "$top" ]; then
  echo "BLOCKED / WHY: this push runs in a repository without a working tree (a bare repository), so there is no .rpi/scripts/rpi-prepush.py receipt gate to run and no checkout to attest the pushed commit. / FIX: push from a working checkout of the integration branch; or, for this repository only, the owner pushes with git push --no-verify, or removes this hook: rm \"$hook\"" >&2
  exit 1
fi
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
  then
    chmod +x "$tmp" 2>/dev/null && mv -f "$tmp" "$hooks/pre-push" 2>/dev/null || { rm -f "$tmp"; echo "BLOCKED / WHY: cannot write the receipt gate wrapper into $hooks. / FIX: make that directory writable by this user (ls -ld \"$hooks\"), then run this command again; an existing hook there was not changed." >&2; false; }
  else
    rm -f "$tmp" 2>/dev/null
    echo "BLOCKED / WHY: cannot write the receipt gate wrapper into $hooks. / FIX: make that directory writable by this user (ls -ld \"$hooks\"), then run this command again; an existing hook there was not changed." >&2
    false
  fi
fi
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
        # CI runners have no ambient Git identity, so the fixture names its own.
        other = self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                         'commit-tree', '-m', 'Unverified', self.git('rev-parse', 'HEAD^{tree}'))
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
        self.assertTrue(fix.startswith('Publish the verified HEAD: git push origin HEAD:refs/heads/develop (if Git rejects'), fix)
        self.assertIn('git pull --rebase origin develop', fix)  # The non-fast-forward exit is printed too.
        self.assertNotIn('--no-verify', fix)  # Only an opt-out push names the owner bypass.
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
        result = self.assert_refused(self.line('refs/heads/develop', remote_sha=published), reason='verification evidence is missing')
        self.assertIn('"require_verification_receipt": false', result.stderr)
        self.assert_passes(self.line('refs/heads/develop', remote_sha='1' * 40))  # An unfetched remote object cannot be read.
        self.evidence()
        self.assert_passes(self.line('refs/heads/develop', remote_sha=published))  # One verified push turns it off.
        (self.project / '.rpi/local/verification.json').unlink()
        (self.project / '.rpi/policy.json').unlink()
        self.commit('Remove the policy')
        result = self.assert_refused(self.line('refs/heads/develop', remote_sha=published), reason='verification evidence is missing')
        # The verifier cannot run without the policy file, so the refusal must print the ways out.
        fix = result.stderr.split('/ FIX:')[1]
        self.assertIn('keep .rpi/policy.json with "require_verification_receipt": false', fix)
        self.assertIn('git push --no-verify', fix)

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


class InstalledHookFixture(PrePushFixture):
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

    def hook(self):
        return self.project / '.git/hooks/pre-push'

    def enable(self):
        return subprocess.run(['bash', '-c', INSTALL], cwd=self.project, env=self.environment,
                              capture_output=True, text=True)

    def push(self, *arguments, cwd=None):
        return subprocess.run([self.environment['RPI_REAL_GIT'], 'push', '--porcelain', str(self.remote), *arguments],
                              cwd=cwd or self.project, env=self.environment, capture_output=True, text=True)

    def remote_ref(self, ref):
        result = subprocess.run([self.environment['RPI_REAL_GIT'], '-C', str(self.remote), 'rev-parse', '--verify', '--quiet', ref],
                                capture_output=True, text=True)
        return result.stdout.strip() or None


class InstalledHookTests(InstalledHookFixture):






    def test_existing_owner_hook_is_refused_untouched_with_the_line_to_add(self):
        self.hook().parent.mkdir(parents=True, exist_ok=True)
        owner = '#!/bin/sh\necho "owner hook ran" >&2\n'
        self.hook().write_text(owner)
        self.hook().chmod(0o755)
        result = self.enable()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.hook().read_text(), owner, 'the owner hook is never overwritten')
        self.assertTrue(result.stderr.startswith('BLOCKED / WHY: '), result.stderr)
        why, fix = result.stderr.strip().split(' / FIX: ', 1)
        self.assertIn('already exists', why)
        self.assertIn('rpi-prepush.py', why)
        line = fix.rsplit('then push again: ', 1)[1]
        self.assertIn('/.rpi/scripts/rpi-prepush.py', line)
        # Following the FIX verbatim yields a hook that runs the owner's step and then the gate.
        self.hook().write_text(owner + line + '\n')
        self.git('branch', 'feature/work')
        self.assertEqual(self.push('feature/work').returncode, 0)
        refused = self.push('develop')
        self.assertNotEqual(refused.returncode, 0, refused.stdout + refused.stderr)
        self.assertIn('owner hook ran', refused.stderr)
        self.assertIn('verification evidence is missing', refused.stderr)

    def test_fresh_install_and_rerun_are_idempotent(self):
        self.assertFalse(self.hook().exists())
        first = self.enable()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        installed = self.hook().read_text()
        self.assertIn('rpi-prepush.py', installed)
        self.assertTrue(os.access(self.hook(), os.X_OK))
        second = self.enable()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.hook().read_text(), installed)

    def test_a_comment_that_mentions_the_gate_does_not_count_as_installing_it(self):
        self.hook().parent.mkdir(parents=True, exist_ok=True)
        owner = '#!/bin/sh\n# TODO rpi-prepush.py\nexit 0\n'
        self.hook().write_text(owner)
        result = self.enable()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stderr.startswith('BLOCKED / WHY: '), result.stderr)
        self.assertEqual(self.hook().read_text(), owner)
        # An indented comment and a here-string comment do not count either; a real command does.
        self.hook().write_text('#!/bin/sh\n   # run rpi-prepush.py later\n')
        self.assertNotEqual(self.enable().returncode, 0)
        self.hook().write_text('#!/bin/sh\npython3 .rpi/scripts/rpi-prepush.py "$@" # gate\n')
        self.assertEqual(self.enable().returncode, 0)

    def test_a_symlinked_hook_is_never_written_through(self):
        self.hook().parent.mkdir(parents=True, exist_ok=True)
        dangling = self.workspace / 'dangling-target'
        self.hook().symlink_to(dangling)
        result = self.enable()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stderr.startswith('BLOCKED / WHY: '), result.stderr)
        self.assertIn('symbolic link', result.stderr)
        self.assertFalse(dangling.exists(), 'the link target is not created')
        self.assertTrue(self.hook().is_symlink())
        self.hook().unlink()
        owner = self.workspace / 'owner-hook.sh'
        owner.write_text('#!/bin/sh\necho owner\n')
        self.hook().symlink_to(owner)
        result = self.enable()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(owner.read_text(), '#!/bin/sh\necho owner\n')
        self.assertTrue(self.hook().is_symlink())
        owner.write_text('#!/bin/sh\npython3 "$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py" "$@"\n')
        result = self.enable()  # A link to a hook that already runs the gate is a working setup.
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.hook().is_symlink())

    def test_a_stale_read_only_wrapper_is_replaced_not_left_behind(self):
        self.hook().parent.mkdir(parents=True, exist_ok=True)
        self.hook().write_text('#!/bin/sh\n# cc-rpi receipt gate wrapper: OLD VERSION\nexit 0\n')
        self.hook().chmod(0o555)
        result = self.enable()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        installed = self.hook().read_text()
        self.assertNotIn('OLD VERSION', installed)
        self.assertIn('rpi-prepush.py', installed)
        self.assertTrue(os.access(self.hook(), os.X_OK))
        again = self.enable()
        self.assertEqual(again.returncode, 0)
        self.assertEqual(self.hook().read_text(), installed)
        self.assertEqual(sorted(path.name for path in self.hook().parent.iterdir() if path.name.startswith('.pre-push')), [])

    def test_every_write_failure_ends_with_blocked_why_fix_and_nonzero(self):
        if os.geteuid() == 0:
            self.skipTest('root ignores directory permissions')
        hooks = self.hook().parent
        hooks.mkdir(parents=True, exist_ok=True)
        self.addCleanup(hooks.chmod, 0o755)
        for existing in (None, '#!/bin/sh\n# cc-rpi receipt gate wrapper: OLD VERSION\nexit 0\n'):
            with self.subTest(existing=bool(existing)):
                hooks.chmod(0o755)
                self.hook().unlink(missing_ok=True)
                if existing:
                    self.hook().write_text(existing)
                hooks.chmod(0o555)
                result = self.enable()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(result.stderr.startswith('BLOCKED / WHY: cannot write'), result.stderr)
                self.assertIn('/ FIX: ', result.stderr)
                self.assertNotIn('Permission denied', result.stderr)
                self.assertNotIn('chmod:', result.stderr)
                if existing:
                    self.assertEqual(self.hook().read_text(), existing, 'the existing hook is untouched')
                self.assertEqual(sorted(path.name for path in hooks.iterdir() if path.name.startswith('.pre-push')), [])

    def test_outside_a_repository_and_with_a_file_for_hooks_nothing_is_written(self):
        outside = self.workspace / 'not-a-repo'
        outside.mkdir()
        environment = {**self.environment, 'HOME': str(outside), 'GIT_CEILING_DIRECTORIES': str(self.workspace)}
        result = subprocess.run(['bash', '-c', INSTALL], cwd=outside, env=environment, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stderr.startswith('BLOCKED / WHY: the current directory is not inside a Git repository'), result.stderr)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(Path('/hooks').exists())
        blocker = self.workspace / 'hooks-is-a-file'
        blocker.write_text('not a directory\n')
        self.git('config', 'core.hooksPath', str(blocker))
        result = self.enable()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stderr.startswith('BLOCKED / WHY: the hooks path'), result.stderr)
        self.assertIn('is not a directory', result.stderr)
        self.assertEqual(blocker.read_text(), 'not a directory\n')

    def test_hook_that_already_invokes_the_gate_is_left_alone(self):
        self.hook().parent.mkdir(parents=True, exist_ok=True)
        custom = '#!/bin/sh\necho before\npython3 "$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py" "$@" || exit 1\n'
        self.hook().write_text(custom)
        result = self.enable()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.hook().read_text(), custom)

    def test_dry_run_push_is_still_evaluated_by_the_gate(self):
        # Git runs pre-push for --dry-run and does not tell the hook, so the gate cannot exempt it.
        self.install()
        self.git('branch', 'feature/work')
        result = self.push('--dry-run', 'develop')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('verification evidence is missing', result.stderr)
        self.assertEqual(self.push('--dry-run', 'feature/work').returncode, 0)
        self.assertIsNone(self.remote_ref('refs/heads/develop'))
        self.evidence()
        self.assertEqual(self.push('--dry-run', 'develop').returncode, 0)
        self.assertIsNone(self.remote_ref('refs/heads/develop'), 'a dry run publishes nothing')

    def test_documented_command_is_the_tested_command(self):
        self.assertIn('```bash\n' + INSTALL + '```', DOCS.read_text())



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



class GateFindingTests(InstalledHookFixture):
    """Wave B round 2: WB2-P-14 (bare repository), P-15 (foreign hooks), P-16 (subdirectory), P-17 (stale temporary file),
    P-18 (hidden changes) and P-19 (case)."""

    def refuse(self, *arguments, reason):
        result = self.push(*arguments)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(reason, result.stderr)
        return result

    def test_a_bare_repository_cannot_attest_a_gated_push(self):
        bare = self.workspace / 'bare.git'
        self.install()
        subprocess.run([self.environment['RPI_REAL_GIT'], 'clone', '-q', '--bare', str(self.project), str(bare)], check=True, capture_output=True)
        develop = self.git('rev-parse', 'HEAD')
        for lines, code in (((self.line('refs/heads/develop', develop),), 1), ((self.line('refs/tags/v1.0.0', develop),), 1),
                            ((self.line('refs/heads/feature/x', develop),), 0), ((), 0)):
            result = subprocess.run([sys.executable, str(PREPUSH), 'origin', 'url'], input=''.join(line + '\n' for line in lines),
                                    capture_output=True, text=True, cwd=bare, env=self.environment)
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
            if code:
                self.assertIn('bare repository', result.stderr)
                self.assertIn('/ FIX: Push from a working checkout', result.stderr)
                self.assertIn('git push --no-verify', result.stderr)
        # Outside any repository there is nothing to gate.
        outside = self.workspace / 'nowhere'
        outside.mkdir()
        result = subprocess.run([sys.executable, str(PREPUSH), 'origin', 'url'], input=self.line('refs/heads/develop', develop) + '\n',
                                capture_output=True, text=True, cwd=outside,
                                env={**self.environment, 'GIT_CEILING_DIRECTORIES': str(self.workspace)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_installed_wrapper_in_a_bare_repository_prints_a_runnable_fix(self):
        bare = self.workspace / 'bare.git'
        self.install()
        subprocess.run([self.environment['RPI_REAL_GIT'], 'clone', '-q', '--bare', str(self.project), str(bare)], check=True, capture_output=True)
        wrapper = self.hook()
        result = subprocess.run([str(wrapper), 'origin', 'url'], input='', capture_output=True, text=True, cwd=bare, env=self.environment)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('bare repository', result.stderr)
        self.assertNotIn('--target ""', result.stderr)
        self.assertNotIn('"/.rpi', result.stderr)
        self.assertIn('rm "%s"' % wrapper, result.stderr)
        self.assertIn('git push --no-verify', result.stderr)
        enable = subprocess.run(['bash', '-c', INSTALL], cwd=bare, env=self.environment, capture_output=True, text=True)
        self.assertNotEqual(enable.returncode, 0)
        self.assertTrue(enable.stderr.startswith('BLOCKED / WHY: this is a bare repository'), enable.stderr)
        self.assertIn('/ FIX: cd to the repository root', enable.stderr)

    def foreign(self, text, link=False):
        hooks = self.hook().parent
        hooks.mkdir(parents=True, exist_ok=True)
        self.hook().unlink(missing_ok=True)
        if link:
            target = self.workspace / 'managed-pre-push'
            target.write_text(text)
            self.hook().symlink_to(target)
        else:
            self.hook().write_text(text)
        return self.enable()

    def test_a_foreign_hook_counts_only_when_it_really_reaches_the_gate(self):
        gate = '"$(git rev-parse --show-toplevel)/.rpi/scripts/rpi-prepush.py" "$@" || exit 1\n'
        for link in (False, True):
            for text in ('#!/bin/sh\necho rpi-prepush.py\nexit 0\n', '#!/bin/sh\nexit 0\npython3 ' + gate,
                         '#!/bin/sh\n# python3 ' + gate, '#!/bin/sh\nprintf "%s\\n" rpi-prepush.py\n', '#!/bin/sh\n: rpi-prepush.py\n',
                         '#!/bin/sh\nexit\npython3 ' + gate, '#!/bin/sh\nexit 0; python3 ' + gate):
                with self.subTest(link=link, text=text):
                    result = self.foreign(text, link)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertTrue(result.stderr.startswith('BLOCKED / WHY:'), result.stderr)
                    self.assertIn('does not run rpi-prepush.py', result.stderr + 'does not run rpi-prepush.py' * link)
                    self.assertEqual(self.hook().read_text(), text)
        for link in (False, True):
            for text in ('#!/bin/sh\npython3 ' + gate, '#!/bin/sh\necho before\nexec python3 ' + gate.replace(' || exit 1', ''),
                         '#!/bin/sh\nset -e\nif true; then\n  python3 ' + gate + 'fi\n', '#!/bin/sh\nsh -c "echo x"\n[ -x z ] && exit 0\npython3 ' + gate):
                with self.subTest(link=link, text=text):
                    result = self.foreign(text, link)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('runs rpi-prepush.py; left unchanged', result.stdout)
                    self.assertIn('WARNING', result.stdout)

    def test_a_hook_line_that_starts_with_the_bare_gate_name_counts(self):
        """WB2-S-4: the detection must not need a character before the script name (the old pipeline matched these)."""
        for link in (False, True):
            for text in ('rpi-prepush.py', 'rpi-prepush.py "$@"\n', '\trpi-prepush.py "$@" || exit 1\n',
                         '#!/bin/sh\n  rpi-prepush.py "$@"\n', '#!/bin/sh\n./rpi-prepush.py "$@"\n'):
                with self.subTest(link=link, text=text):
                    result = self.foreign(text, link)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('runs rpi-prepush.py; left unchanged', result.stdout)
                    self.assertEqual(self.hook().read_text(), text)

    def test_the_refusal_for_a_foreign_hook_says_where_to_add_the_line(self):
        result = self.foreign('#!/bin/sh\nexit 0\n')
        self.assertIn('near the top of that hook, before any exit', result.stderr)

    def test_a_relative_hooks_path_resolves_against_the_checkout_root_from_any_directory(self):
        self.git('config', 'core.hooksPath', '.githooks')
        nested = self.project / 'deep' / 'er'
        nested.mkdir(parents=True)
        result = subprocess.run(['bash', '-c', INSTALL], cwd=nested, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.project / '.githooks/pre-push').is_file())
        self.assertFalse((nested / '.githooks').exists())
        self.assertEqual(self.enable().returncode, 0)
        self.git('config', 'core.hooksPath', 'tools/hooks')
        result = subprocess.run(['bash', '-c', INSTALL], cwd=nested, env=self.environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.project / 'tools/hooks/pre-push').is_file())
        # Git itself runs that wrapper for a push from the nested directory.
        self.git('config', 'core.hooksPath', '.githooks')
        self.commit('Wrapper')
        result = self.push('develop', cwd=nested)
        self.assertIn('verification evidence is missing', result.stderr)

    def test_a_killed_enable_leaves_nothing_that_the_next_run_keeps(self):
        self.install()
        hooks = self.hook().parent
        dead = hooks / '.pre-push.2147483646'
        alive = hooks / ('.pre-push.%d' % os.getpid())
        other = hooks / '.pre-push.notapid'
        for path in (dead, alive, other):
            path.write_text('partial\n')
        result = self.enable()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(dead.exists(), 'the temporary file of a process that is gone is removed')
        self.assertTrue(alive.exists(), 'a file of a running process is not touched')
        self.assertTrue(other.exists(), 'only .pre-push.PID files are ours')
        self.assertIn('cc-rpi receipt gate wrapper', self.hook().read_text())
        self.assertEqual(sorted(path.name for path in hooks.iterdir() if path.name.startswith('.pre-push.') and path not in (alive, other)), [])

    def test_changes_hidden_from_git_status_are_not_attested_by_a_receipt(self):
        (self.project / 'data.txt').write_text('committed\n')
        self.commit('Add data')
        for flag in ('--skip-worktree', '--assume-unchanged'):
            with self.subTest(flag=flag):
                self.git('update-index', flag, 'data.txt')
                (self.project / 'data.txt').write_text('LOCAL ONLY\n')
                self.assertEqual(self.git('status', '--porcelain'), '', 'git status cannot see the change')
                self.evidence()
                result = self.assert_refused(self.line('refs/heads/develop'), reason='skip-worktree or assume-unchanged')
                self.assertIn('data.txt', result.stderr)
                fix = result.stderr.split('/ FIX: ', 1)[1]
                self.assertIn('git update-index --no-skip-worktree -- data.txt && git update-index --no-assume-unchanged -- data.txt', fix)
                subprocess.run(['bash', '-c', fix.split(': ', 1)[1].split('; git status')[0]], cwd=self.project, env=self.environment, check=True)
                self.assertIn('data.txt', self.git('status', '--porcelain'))
                self.git('checkout', '--', 'data.txt')
                self.evidence()
                self.assert_passes(self.line('refs/heads/develop'))

    def test_a_flagged_path_that_matches_the_commit_or_is_absent_is_fine(self):
        (self.project / 'big.bin').write_text('committed\n')
        (self.project / 'link').symlink_to('big.bin')
        self.commit('Add files')
        self.git('update-index', '--skip-worktree', 'big.bin', 'link')
        self.evidence()
        self.assert_passes(self.line('refs/heads/develop'))
        (self.project / 'big.bin').unlink()  # A sparse checkout leaves flagged files out.
        self.evidence()
        self.assert_passes(self.line('refs/heads/develop'))
        (self.project / 'big.bin').write_text('committed\n')
        (self.project / 'link').unlink()
        (self.project / 'link').symlink_to('elsewhere')
        self.evidence()
        self.assert_refused(self.line('refs/heads/develop'), reason='link')

    def test_many_hidden_paths_print_a_command_that_lists_them(self):
        for number in range(25):
            (self.project / ('f%02d.txt' % number)).write_text('x\n')
        self.commit('Many files')
        self.git('update-index', '--skip-worktree', *['f%02d.txt' % number for number in range(25)])
        for number in range(25):
            (self.project / ('f%02d.txt' % number)).write_text('y\n')
        self.evidence()
        result = self.assert_refused(self.line('refs/heads/develop'), reason='25 paths differ')
        self.assertIn('and 5 more', result.stderr)
        self.assertIn("git ls-files -v | grep '^[a-zS]'", result.stderr)

    def test_the_integration_branch_is_recognised_without_case(self):
        for ref in ('refs/heads/Develop', 'refs/heads/DEVELOP'):
            with self.subTest(ref=ref):
                self.assert_refused(self.line(ref), reason='verification evidence is missing')
                self.assert_refused(self.line(ref, ZERO), reason='Deleting the integration branch')
        self.evidence()
        self.assert_passes(self.line('refs/heads/Develop'), self.line('refs/heads/developer'))
        self.assert_passes(self.line('refs/heads/feature/Develop'))


if __name__ == '__main__':
    unittest.main()
