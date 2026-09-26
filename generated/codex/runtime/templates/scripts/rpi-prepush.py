#!/usr/bin/env python3
"""Opt-in Git pre-push gate binding integration and release refs to local evidence.

Git runs this with the remote name and URL as arguments and one stdin line per
ref it is about to update: "<local ref> <local sha> <remote ref> <remote sha>".
Git has already expanded --all, --tags, globs, remote.<name>.push, push.default
and aliases, so the gate sees the exact refs and commits being published.

Only a project whose .rpi/policy.json sets "require_verification_receipt": true
is gated; every other project exits 0 at once. When opted in, an update of
refs/heads/<integration_branch> or of a version tag requires a clean tree and a
passing .rpi/local/verification.json for the pushed commit; deleting the
integration branch is refused. Any unexpected error in an opted-in project
fails closed. This validates local evidence, not user authorization.
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

# Evaluation must not modify the verified candidate through sibling imports.
sys.dont_write_bytecode = True

ZERO = re.compile(r'0+')
VERSION_TAG = re.compile(r'v?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?')
POLICY_KEYS = {'schema_version', 'integration_branch', 'production_branches', 'remote',
               'require_verification_receipt', 'verification_checks', 'verification_command'}
INTERPRETER = ('python', 'implementation', 'executable', 'packages')  # Packages belong to the interpreter.


class Blocked(ValueError):
    def __init__(self, reason, fix):
        super().__init__(reason)
        self.fix = fix


def fail(reason, fix):
    raise Blocked(reason, fix)


def unique_object(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError('duplicate JSON field: ' + key)
        output[key] = value
    return output


def read_json(data):
    def invalid(value):
        raise ValueError('nonfinite JSON value: ' + value)
    return json.loads(data, object_pairs_hook=unique_object, parse_constant=invalid)


def git(root, *arguments):
    """Git's stdout, or None when Git or the repository state is unavailable."""
    try:
        result = subprocess.run(['git', '-C', str(root), *arguments], capture_output=True, text=True)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def project_policy(root):
    """The validated policy, or None when the project does not opt in."""
    path = root / '.rpi/policy.json'
    if path.is_symlink():
        fail('Project policy .rpi/policy.json must be a regular file.',
             'Replace the .rpi/policy.json symlink with the reviewed regular file.')
    if not path.exists():
        return None
    try:
        value = read_json(path.read_text(encoding='utf-8'))
    except OSError as error:
        fail('Project policy .rpi/policy.json cannot be read (' + type(error).__name__ + ').',
             'Make .rpi/policy.json a readable regular file, or remove it.')
    except ValueError as error:
        fail('Project policy .rpi/policy.json is not valid JSON (' + str(error) + ').',
             'Fix the JSON syntax; save it as UTF-8 without a byte-order mark.')
    if not isinstance(value, dict) or value.get('schema_version') != 1 or set(value) - POLICY_KEYS:
        fail('Invalid project policy in .rpi/policy.json.',
             'Use schema_version 1 and only these keys: ' + ', '.join(sorted(POLICY_KEYS)) + '.')
    if type(value.get('require_verification_receipt', False)) is not bool:
        fail('In .rpi/policy.json, require_verification_receipt must be true or false.',
             'Set "require_verification_receipt": true to gate integration publication, or remove the key.')
    if not value.get('require_verification_receipt'):
        return None
    if not isinstance(value.get('integration_branch'), str) or not value['integration_branch']:
        fail('The receipt gate needs one declared integration_branch in .rpi/policy.json.',
             'Declare "integration_branch": "main" (or the actual branch).')
    if 'remote' in value and (not isinstance(value['remote'], str) or not value['remote']):
        fail('In .rpi/policy.json, remote must be one remote name.', 'Declare "remote": "origin" (or the actual remote), or remove the key.')
    verification_contract(value)
    return value


def verification_contract(policy):
    checks, command = policy.get('verification_checks'), policy.get('verification_command')
    if not isinstance(command, list) or not command or any(not isinstance(arg, str) or not arg for arg in command):
        fail('The project verification command is missing or malformed.',
             'Declare verification_command as the local runner argv in .rpi/policy.json.')
    if not isinstance(checks, list) or not checks:
        fail('The project verification inventory is missing.',
             'Declare every required local gate in .rpi/policy.json verification_checks.')
    names = set()
    for check in checks:
        if (not isinstance(check, dict) or set(check) != {'name', 'argv'} or not isinstance(check['name'], str) or
                not check['name'] or check['name'] in names or not isinstance(check['argv'], list) or not check['argv'] or
                any(not isinstance(arg, str) or not arg for arg in check['argv'])):
            fail('The project verification inventory must contain unique names and literal argv arrays.',
                 'Review .rpi/policy.json verification_checks against the complete local CI selection.')
        names.add(check['name'])
    return checks, shlex.join(command)


def hook_environment():
    """The caller's environment without the exec-path entry Git prepends to PATH for hooks."""
    environ, prefix = dict(os.environ), os.environ.get('GIT_EXEC_PATH')
    entries = environ.get('PATH', '').split(os.pathsep)
    if prefix and entries and entries[0] and os.path.realpath(entries[0]) == os.path.realpath(prefix):
        environ['PATH'] = os.pathsep.join(entries[1:])
    return environ


def interpreter(runtime):
    return str(runtime.get('executable')) + ' (Python ' + str(runtime.get('python')) + ')'


def stale(report, environment, runner):
    recorded = report.get('environment') if isinstance(report, dict) else None
    if isinstance(recorded, dict) and recorded != environment:
        changed = {key for key in set(recorded) | set(environment) if recorded.get(key) != environment.get(key)}
        if changed & {'python', 'executable'}:
            scope = 'differs only in its Python interpreter' if changed <= set(INTERPRETER) else 'differs, including its Python interpreter'
            fail('The verification receipt runtime ' + scope + ': verified with ' + interpreter(recorded) +
                 ', this gate runs ' + interpreter(environment) + '.',
                 'Run ' + runner + ' with the interpreter the hook uses (' + environment['executable'] +
                 ' first on PATH), or put the verified interpreter first on PATH for git push.')
    fail('Local verification does not attest this exact complete candidate.',
         'Run ' + runner + '; custom, stale, partial or failed reports do not attest the candidate, and changed '
         'locale, timezone or Python settings require a fresh run.')


def verified_candidate(root, policy):
    """The commit that exact local evidence attests for this clean candidate."""
    import importlib.util
    expected, runner = verification_contract(policy)
    if git(root, 'status', '--porcelain', '--untracked-files=normal'):
        fail('Publication requires a clean completed integration candidate.', 'Commit the completed integration, then run ' + runner)
    path = root / '.rpi/local/verification.json'
    if path.is_symlink() or not path.is_file():
        fail('Exact-candidate local verification evidence is missing.', 'Run ' + runner + ' in the completed integration checkout.')
    try:
        report = read_json(path.read_text())
    except ValueError:
        report = None
    helper = Path(__file__).resolve().with_name('rpi-candidate.py')
    if not helper.is_file():
        fail('The shared candidate identity helper is missing.', 'Reinstall the declared RPI policy resources (rpi-candidate.py).')
    spec = importlib.util.spec_from_file_location('rpi_prepush_candidate', helper)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    actual, environment = candidate.identity(root), candidate.environment(hook_environment())
    checks = report.get('checks') if isinstance(report, dict) else None
    if (not isinstance(report, dict) or report.get('schema_version') != 1 or report.get('suite') != 'ci-equivalent' or
            report.get('passed') is not True or report.get('identity_unchanged') is not True or
            report.get('environment_unchanged') is not True or report.get('identity') != actual or
            report.get('identity_after') != actual or not isinstance(checks, list) or len(checks) != len(expected) or
            any(not isinstance(item, dict) or type(item.get('exit_code')) is not int or item['exit_code'] != 0 for item in checks) or
            [{key: item.get(key) for key in ('name', 'argv')} for item in checks] != expected):
        stale(None, environment, runner)
    if report.get('environment') != environment or report.get('environment_after') != environment:
        stale(report, environment, runner)
    return actual['commit']


def gated_updates(root, policy, lines):
    """(remote ref, pushed commit) pairs that need the receipt; deletions of the integration branch are refused."""
    integration = 'refs/heads/' + policy['integration_branch']
    updates = []
    for line in lines:
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            fail('Unexpected pre-push input line: ' + line.strip()[:120], 'Run the hook only as Git\'s pre-push hook.')
        _, local_sha, remote_ref, _ = fields
        deleted = ZERO.fullmatch(local_sha) is not None
        if remote_ref == integration and deleted:
            fail('Deleting the integration branch (' + policy['integration_branch'] + ') removes the published history.',
                 'Delete only working branches; if it is truly intended, the owner runs the exact command without this hook.')
        tag = remote_ref.startswith('refs/tags/') and VERSION_TAG.fullmatch(remote_ref[len('refs/tags/'):])
        if deleted or not (remote_ref == integration or tag):
            continue
        commit = git(root, 'rev-parse', '--verify', '--quiet', local_sha + '^{commit}')
        if commit is None:
            fail('The pushed object for ' + remote_ref + ' is not a local commit.', 'Push a ref that names a local commit.')
        updates.append((remote_ref, commit))
    return updates


def evaluate(argv, lines, cwd):
    top = git(cwd, 'rev-parse', '--show-toplevel')
    if top is None:
        return  # A bare repository has no candidate or policy to gate.
    root = Path(top).resolve()
    policy = project_policy(root)
    if policy is None:
        return
    if len(argv) != 2:
        fail('The pre-push gate expects the remote name and URL as its two arguments.', 'Install it as the repository pre-push hook.')
    updates = gated_updates(root, policy, lines)
    if not updates:
        return
    try:
        verified = verified_candidate(root, policy)
    except Blocked:
        raise
    except Exception as error:  # The opted-in gate must not fail open.
        fail('Receipt verification failed (' + type(error).__name__ + ').',
             'Reinstall the declared RPI policy resources, then run ' + verification_contract(policy)[1] + '.')
    for remote_ref, commit in updates:
        if commit != verified:
            fail('The pushed ' + remote_ref + ' (' + commit[:12] + ') differs from the verified candidate commit (' + str(verified)[:12] + ').',
                 'Push the verified commit: git push ' + argv[0] + ' ' + policy['integration_branch'] + ', or run ' +
                 verification_contract(policy)[1] + ' on the commit you are publishing.')


def main(argv):
    try:
        lines = [] if sys.stdin is None else sys.stdin.read().splitlines()
        evaluate(argv, lines, Path.cwd())
        return 0
    except Blocked as error:
        print('BLOCKED / WHY: ' + str(error) + ' / FIX: ' + error.fix, file=sys.stderr)
    except Exception as error:  # Only an opted-in project installs this hook: fail closed.
        print('BLOCKED / WHY: the pre-push gate failed (' + type(error).__name__ + ': ' + str(error)[:200] + '). / FIX: '
              'run python3 .rpi/scripts/rpi-distribution.py check --target . and repair the installation.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
