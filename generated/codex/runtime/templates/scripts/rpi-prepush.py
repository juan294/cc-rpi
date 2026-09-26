#!/usr/bin/env python3
"""Opt-in Git pre-push gate binding integration and release refs to local evidence.

Git runs this with the remote name and URL as arguments and one stdin line per
ref it is about to update: "<local ref> <local sha> <remote ref> <remote sha>".
Git has already expanded --all, --tags, globs, remote.<name>.push, push.default
and aliases, so the gate sees the exact refs and commits being published.

A push is gated when the pushing checkout's .rpi/policy.json, or the one
committed in the pushed commit, sets "require_verification_receipt": true; the
stricter wins, so a worktree on a pre-opt-in branch cannot publish an opted-in
integration branch. Otherwise the hook exits 0. A gated update of
refs/heads/<integration_branch> or of a version tag requires a clean tree
(ignoring .rpi/local/) and a passing .rpi/local/verification.json for the pushed
commit; deleting the integration branch is refused. Any unexpected error in an
opted-in project fails closed. This validates local evidence, not user
authorization.
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
REPAIR = ('bash "$RPI_SOURCE/scripts/install.sh" --check --target "$(git rev-parse --show-toplevel)" '
          '(RPI_SOURCE is your verified cc-rpi checkout), then apply a reviewed update')


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


def git(root, *arguments, text=True):
    """Git's stdout, or None when Git or the repository state is unavailable."""
    try:
        result = subprocess.run(['git', '-C', str(root), *arguments], capture_output=True, text=text)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() if text else result.stdout


def project_policy(root):
    """The checkout's validated policy, or None when it does not opt in."""
    path = root / '.rpi/policy.json'
    if path.is_symlink():
        fail('Project policy .rpi/policy.json must be a regular file.',
             'Replace the .rpi/policy.json symlink with the reviewed regular file.')
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
    except OSError as error:
        fail('Project policy .rpi/policy.json cannot be read (' + type(error).__name__ + ').',
             'Make .rpi/policy.json a readable regular file, or remove it.')
    return validated_policy(data, '.rpi/policy.json')


def committed_policy(root, commit):
    """The validated policy committed in a pushed commit, or None when that commit does not opt in."""
    where = 'the .rpi/policy.json committed in ' + commit[:12]
    entry = git(root, 'ls-tree', commit, '--', '.rpi/policy.json')
    if not entry:
        return None
    if not entry.startswith('100'):
        fail('Project policy ' + where + ' must be a regular file.',
             'Commit .rpi/policy.json as the reviewed regular file, then push again.')
    data = git(root, 'cat-file', 'blob', commit + ':.rpi/policy.json', text=False)
    if data is None:
        fail('Project policy ' + where + ' cannot be read.', 'Push a commit whose objects are complete in this clone.')
    return validated_policy(data, where)


def validated_policy(data, where):
    """The opted-in policy with a bare integration branch name, or None when it does not opt in."""
    try:
        value = read_json(data.decode('utf-8'))
    except ValueError as error:
        fail('Project policy ' + where + ' is not valid JSON (' + str(error) + ').',
             'Fix the JSON syntax; save it as UTF-8 without a byte-order mark.')
    if not isinstance(value, dict) or value.get('schema_version') != 1 or set(value) - POLICY_KEYS:
        fail('Invalid project policy in ' + where + '.',
             'Use schema_version 1 and only these keys: ' + ', '.join(sorted(POLICY_KEYS)) + '.')
    if type(value.get('require_verification_receipt', False)) is not bool:
        fail('In ' + where + ', require_verification_receipt must be true or false.',
             'Set "require_verification_receipt": true to gate integration publication, or remove the key.')
    if not value.get('require_verification_receipt'):
        return None
    branch = value.get('integration_branch')
    branch = branch.removeprefix('refs/heads/') if isinstance(branch, str) else None  # As rpi-policy.py resolves it.
    if not branch:
        fail('The receipt gate needs one declared integration_branch in ' + where + '.',
             'Declare "integration_branch": "main" (or the actual branch).')
    if 'remote' in value and (not isinstance(value['remote'], str) or not value['remote']):
        fail('In ' + where + ', remote must be one remote name.', 'Declare "remote": "origin" (or the actual remote), or remove the key.')
    verification_contract(value)
    return dict(value, integration_branch=branch)


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


def settings(environ):
    """The locale, timezone and Python settings whose digest the runtime identity records."""
    return ', '.join(name + '=' + environ[name] for name in sorted(environ) if name.startswith('LC_') or name in (
        'LANG', 'LANGUAGE', 'TZ', 'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONCOERCECLOCALE', 'PYTHONHASHSEED')) or 'none set'


def changed_keys(recorded, current, prefix=''):
    keys = []
    for key in sorted(set(recorded) | set(current)):
        before, after = recorded.get(key), current.get(key)
        if before == after:
            continue
        if isinstance(before, dict) and isinstance(after, dict) and key in ('executables', 'packages'):
            keys += changed_keys(before, after, key + '.')
        else:
            keys.append(prefix + key)
    return keys


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
        if changed == {'execution_settings_sha256'}:
            fail('The verification receipt runtime differs only in its locale, timezone or Python settings; '
                 'this gate runs with ' + settings(hook_environment()) + '.',
                 'Run ' + runner + ' with the same LANG, LC_*, TZ and PYTHON* settings as git push, or push with the settings verification used.')
        fail('The verification receipt runtime differs in: ' + ', '.join(changed_keys(recorded, environment)) + '.',
             'Run ' + runner + ' in the environment that runs git push; changed tools, packages, platform, '
             'locale, timezone or Python settings require a fresh run.')
    fail('Local verification does not attest this exact complete candidate.',
         'Run ' + runner + '; custom, stale, partial or failed reports do not attest the candidate, and changed '
         'locale, timezone or Python settings require a fresh run.')


def verified_candidate(root, policy):
    """The commit that exact local evidence attests for this clean candidate."""
    import importlib.util
    expected, runner = verification_contract(policy)
    dirty = git(root, 'status', '--porcelain', '--untracked-files=normal', '--', '.', ':(exclude).rpi/local')
    if dirty is None or dirty:  # Local evidence is never part of the candidate (see rpi-candidate.py).
        listed = ', '.join(line[3:] for line in (dirty or '').splitlines()[:5]) or 'git status failed'
        fail('Publication requires a clean completed integration candidate (' + listed + ').',
             'Commit or remove those changes, then run ' + runner)
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


def gated_updates(root, checkout, lines):
    """(remote ref, pushed commit, policy) triples that need the receipt; deleting an integration branch is refused.

    Each update is gated by the checkout's policy or by the policy committed in
    the pushed (or, for a deletion, the replaced) commit, whichever opts in.
    """
    updates = []
    for line in lines:
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            fail('Unexpected pre-push input line: ' + line.strip()[:120], 'Run the hook only as Git\'s pre-push hook.')
        _, local_sha, remote_ref, remote_sha = fields
        deleted = ZERO.fullmatch(local_sha) is not None
        tag = remote_ref.startswith('refs/tags/') and VERSION_TAG.fullmatch(remote_ref[len('refs/tags/'):])
        if not (remote_ref.startswith('refs/heads/') or tag) or (deleted and tag):
            continue
        commit = git(root, 'rev-parse', '--verify', '--quiet', (remote_sha if deleted else local_sha) + '^{commit}')
        policies = [policy for policy in (checkout, committed_policy(root, commit) if commit else None) if policy]
        for policy in policies:
            if remote_ref == 'refs/heads/' + policy['integration_branch'] and deleted:
                fail('Deleting the integration branch (' + policy['integration_branch'] + ') removes the published history.',
                     'Delete only working branches; if it is truly intended, the owner runs the exact command without this hook.')
        gate = next((policy for policy in policies if tag or remote_ref == 'refs/heads/' + policy['integration_branch']), None)
        if deleted or gate is None:
            continue
        if commit is None:
            fail('The pushed object for ' + remote_ref + ' is not a local commit.', 'Push a ref that names a local commit.')
        updates.append((remote_ref, commit, gate))
    return updates


def evaluate(argv, lines, cwd):
    top = git(cwd, 'rev-parse', '--show-toplevel')
    if top is None:
        return  # A bare repository has no candidate or policy to gate.
    root = Path(top).resolve()
    checkout = project_policy(root)
    if checkout is not None and len(argv) != 2:
        fail('The pre-push gate expects the remote name and URL as its two arguments.', 'Install it as the repository pre-push hook.')
    updates = gated_updates(root, checkout, lines)
    if not updates:
        return
    if len(argv) != 2:
        fail('The pre-push gate expects the remote name and URL as its two arguments.', 'Install it as the repository pre-push hook.')
    # The receipt attests this checkout, so only an identical committed policy can pass with it.
    policy = checkout or updates[0][2]
    runner = verification_contract(policy)[1]
    try:
        verified = verified_candidate(root, policy)
    except Blocked:
        raise
    except Exception as error:  # The opted-in gate must not fail open.
        fail('Receipt verification failed (' + type(error).__name__ + ').',
             'Check the installation with ' + REPAIR + '; then run ' + runner + '.')
    for remote_ref, commit, gate in updates:
        if commit == verified:
            continue
        if remote_ref.startswith('refs/tags/'):
            name = remote_ref[len('refs/tags/'):]
            fix = ('Verify the tagged commit: git switch --detach ' + name + ', run ' + runner +
                   ', then push the tag: git push ' + argv[0] + ' ' + remote_ref + '.')
        else:
            fix = ('Push the verified commit: git push ' + argv[0] + ' ' + gate['integration_branch'] + ', or run ' +
                   runner + ' on the commit you are publishing.')
        fail('The pushed ' + remote_ref + ' (' + commit[:12] + ') differs from the verified candidate commit (' + str(verified)[:12] + ').', fix)


def main(argv):
    try:
        lines = [] if sys.stdin is None else sys.stdin.read().splitlines()
        evaluate(argv, lines, Path.cwd())
        return 0
    except Blocked as error:
        print('BLOCKED / WHY: ' + str(error) + ' / FIX: ' + error.fix, file=sys.stderr)
    except Exception as error:  # Only an opted-in project installs this hook: fail closed.
        print('BLOCKED / WHY: the pre-push gate failed (' + type(error).__name__ + ': ' + str(error)[:200] + '). / FIX: '
              'check the installation with ' + REPAIR + '.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
