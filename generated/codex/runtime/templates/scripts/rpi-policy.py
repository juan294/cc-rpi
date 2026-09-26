#!/usr/bin/env python3
"""Supplemental denylist for clearly destructive remote operations.

Shell text is parsed, never executed. Exit 0 emits no native decision: the
client's permission rules, mode and user decide everything else, including
ordinary pushes, pull requests and workflow dispatch. Exit 2 blocks only a
positively identified destructive operation or, when a project opts in with
require_verification_receipt, an integration publication without exact local
verification evidence. Shell text the parser cannot classify passes through;
this is not a shell security boundary.
"""
import sys

if sys.version_info < (3, 11):
    print('RPI POLICY SKIPPED: the policy adapter requires Python 3.11 or newer. FIX: uv python install 3.13; '
          'launch the client through uv run --python 3.13 so its hooks use the supported runtime.', file=sys.stderr)
    sys.exit(0)

# This runs before every shell command: modules only some paths need are
# imported where they are used.
import json  # noqa: E402
from pathlib import Path  # noqa: E402
import re  # noqa: E402

# Hook evaluation must not modify the verified candidate through sibling imports.
sys.dont_write_bytecode = True

POLICY_WORD = re.compile(r'\b(?:git|gh|vercel|vc)\b')
SHELL_KEYWORDS = {'{', '}', '!', 'if', 'then', 'else', 'elif', 'do', 'while', 'until'}
ASSIGNMENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*=.*')
REDIRECTION = re.compile(r'(?:\d*|&)(?:>>?|<)&?(.*)')
HEREDOC = re.compile(r"(?m)^[ \t]*(?:cat|tee)\b[^\n]*?<<-?(['\"])([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n")
# Wrapper -> its options that take a separate value.
WRAPPERS = {'env': {'-u', '--unset', '-C', '--chdir', '-S'}, 'command': set(), 'exec': {'-a'},
            'sudo': {'-u', '-g', '-C', '-h', '-p', '-U', '-r', '-t'}, 'time': set(), 'nohup': set(),
            'nice': {'-n'}, 'timeout': {'-k', '--kill-after', '-s', '--signal'}}
VERCEL_VALUE_OPTIONS = {'--token', '-t', '--scope', '-S', '--team', '-T', '--cwd', '-A', '--local-config',
                        '-Q', '--global-config', '--target', '-e', '--env', '-b', '--build-env', '-m', '--meta',
                        '--regions', '--archive'}
# gh release create options without a value; every other option takes one.
RELEASE_FLAGS = {'--draft', '-d', '--prerelease', '-p', '--latest', '--generate-notes', '--verify-tag',
                 '--fail-on-no-commits'}
LITERAL_TEXT = {'echo', 'printf', 'cat', 'rg', 'grep'}
PROTECTED = ('main', 'master', 'develop')
DYNAMIC = '__RPI_DYNAMIC__'
VERSION_TAG = re.compile(r'v?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?')
POLICY_KEYS = {'schema_version', 'integration_branch', 'production_branches', 'remote',
               'require_verification_receipt', 'verification_checks', 'verification_command'}
PUSH_VALUE_OPTIONS = {'-o', '--push-option', '--repo', '--receive-pack', '--exec'}
GIT_VALUE_OPTIONS = {'-c', '--git-dir', '--work-tree', '--namespace', '--config-env'}


class Blocked(ValueError):
    def __init__(self, reason, fix, rule):
        super().__init__(reason)
        self.fix, self.rule = fix, rule


class Unclassifiable(Exception):
    """Shell text the parser cannot read; it passes to native permissions."""


def fail(reason, fix, rule):
    raise Blocked(reason, fix, rule)


def fail_broad_push():
    fail('This push rewrites or deletes remote refs beyond the named branch.',
         'Push explicit refs instead: git push REMOTE BRANCH.', 'destructive-push')


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


def git(cwd, *arguments):
    """Return Git's stdout, or None when Git or the repository state is unavailable."""
    import subprocess
    try:
        result = subprocess.run(['git', '-C', str(cwd), *arguments], capture_output=True, text=True)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def repository(cwd):
    top = git(cwd, 'rev-parse', '--show-toplevel')
    return Path(top).resolve() if top else None


def tag_commit(root, tag):
    """Commit of an existing local version tag, or None."""
    return git(root, 'rev-parse', '--verify', '--quiet', 'refs/tags/' + tag + '^{commit}') if VERSION_TAG.fullmatch(tag) else None


def skip_options(args, takes_value):
    """Index of the first positional; an option for which takes_value holds consumes the next word."""
    index = 0
    while index < len(args) and args[index].startswith('-'):
        option = args[index]
        index += 1 + ('=' not in option and takes_value(option))
    return index


def project_policy(root):
    """Return the optional project policy; a present but invalid file is reported."""
    path = root / '.rpi/policy.json'
    if path.is_symlink():
        fail('Project policy .rpi/policy.json must be a regular file.',
             'Replace the .rpi/policy.json symlink with the reviewed regular file.', 'policy-file')
    if not path.exists():
        return {}
    try:
        value = read_json(path.read_text())
    except ValueError:
        value = None
    if not isinstance(value, dict) or value.get('schema_version') != 1 or set(value) - POLICY_KEYS:
        fail('Invalid project policy in .rpi/policy.json.',
             'Use schema_version 1 and only these keys: ' + ', '.join(sorted(POLICY_KEYS)) + '.', 'policy-file')
    if type(value.get('require_verification_receipt', False)) is not bool:
        fail('In .rpi/policy.json, require_verification_receipt must be true or false.',
             'Set "require_verification_receipt": true to gate integration publication, or remove the key.', 'policy-file')
    branches = value.get('production_branches', [])
    if not isinstance(branches, list) or any(not isinstance(item, str) or not item for item in branches):
        fail('In .rpi/policy.json, production_branches must be a list of branch names.',
             'Declare production_branches as ["name", ...] or remove the key.', 'policy-file')
    return value


def integration_branch(root, policy):
    declared = policy.get('integration_branch')
    if isinstance(declared, str) and declared:
        return declared
    return next((name for name in PROTECTED if git(root, 'rev-parse', '--verify', '--quiet', 'refs/heads/' + name)), None)


def verification_contract(policy):
    import shlex
    checks, command = policy.get('verification_checks'), policy.get('verification_command')
    if not isinstance(command, list) or not command or any(not isinstance(arg, str) or not arg for arg in command):
        fail('The project verification command is missing or malformed.',
             'Declare verification_command as the local runner argv in .rpi/policy.json.', 'verification-contract')
    if not isinstance(checks, list) or not checks:
        fail('The project verification inventory is missing.',
             'Declare every required local gate in .rpi/policy.json verification_checks.', 'verification-contract')
    names = set()
    for check in checks:
        if (not isinstance(check, dict) or set(check) != {'name', 'argv'} or not isinstance(check['name'], str) or
                not check['name'] or check['name'] in names or not isinstance(check['argv'], list) or not check['argv'] or
                any(not isinstance(arg, str) or not arg for arg in check['argv'])):
            fail('The project verification inventory must contain unique names and literal argv arrays.',
                 'Review .rpi/policy.json verification_checks against the complete local CI selection.', 'verification-contract')
        names.add(check['name'])
    return checks, shlex.join(command)


def verified_candidate(root, policy):
    """Exact local evidence for this clean candidate."""
    import importlib.util
    expected, runner = verification_contract(policy)
    if git(root, 'status', '--porcelain', '--untracked-files=normal'):
        fail('Publication requires a clean completed integration candidate.', 'Commit the completed integration, then run ' + runner, 'dirty-publication')
    path = root / '.rpi/local/verification.json'
    if path.is_symlink() or not path.is_file():
        fail('Exact-candidate local verification evidence is missing.', 'Run ' + runner + ' in the completed integration checkout.', 'missing-evidence')
    try:
        report = read_json(path.read_text())
    except ValueError:
        report = None
    helper = Path(__file__).with_name('rpi-candidate.py')
    if not helper.is_file():
        fail('The shared candidate identity helper is missing.', 'Reinstall the declared RPI policy resources (rpi-candidate.py).', 'missing-helper')
    spec = importlib.util.spec_from_file_location('rpi_policy_candidate', helper)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    actual, environment = candidate.identity(root), candidate.environment()
    checks = report.get('checks') if isinstance(report, dict) else None
    if (not isinstance(report, dict) or report.get('schema_version') != 1 or report.get('suite') != 'ci-equivalent' or
            report.get('passed') is not True or report.get('identity_unchanged') is not True or
            report.get('environment_unchanged') is not True or report.get('environment') != environment or
            report.get('environment_after') != environment or report.get('identity') != actual or
            report.get('identity_after') != actual or not isinstance(checks, list) or len(checks) != len(expected) or
            any(not isinstance(item, dict) or type(item.get('exit_code')) is not int or item['exit_code'] != 0 for item in checks) or
            [{key: item.get(key) for key in ('name', 'argv')} for item in checks] != expected):
        fail('Local verification does not attest this exact complete candidate.',
             'Run ' + runner + '; custom, stale, partial or failed reports do not attest the candidate.', 'stale-evidence')
    return actual


def require_receipt(root, policy, commit):
    """The opt-in receipt gate; commit, when given, must be the verified one."""
    if root is None or not policy.get('require_verification_receipt'):
        return None
    try:
        evidence = verified_candidate(root, policy)
    except Blocked:
        raise
    except Exception as error:  # The opted-in gate must not fail open.
        fail('Receipt verification failed (' + type(error).__name__ + ').',
             'Reinstall the declared RPI policy resources, then rerun the declared verification command.', 'receipt-error')
    if commit is not None and commit != evidence['commit']:
        fail('The published ref differs from the verified candidate commit.',
             'Verify the exact integration/tag commit before publication.', 'ref-evidence')
    return 'verified-publication'


def resolved_branch(ref, current):
    """Branch a push destination names, or None when it cannot be resolved."""
    if not ref or DYNAMIC in ref:
        return None
    if ref in ('HEAD', '@'):
        return current
    return ref.removeprefix('refs/heads/')


def push(args, cwd):
    force = delete = everything = tags = repo = False
    values, index = [], 0
    while index < len(args):
        arg = args[index]
        index += 1
        name = arg.split('=', 1)[0]
        if arg == '--':
            values.extend(args[index:])
            break
        if name in ('--mirror', '--prune'):
            fail_broad_push()
        if name in ('--force', '--force-with-lease'):
            force = True
        elif name == '--delete':
            delete = True
        elif name in ('--all', '--branches'):
            everything = True
        elif name in ('--tags', '--follow-tags'):
            tags = True
        elif name in PUSH_VALUE_OPTIONS:
            repo = repo or name == '--repo'
            index += '=' not in arg
        elif re.fullmatch(r'-[A-Za-z]+', arg):
            flags = arg[1:].split('o', 1)  # -o takes the rest, or the next word, as its value.
            force, delete = force or 'f' in flags[0], delete or 'd' in flags[0]
            index += len(flags) == 2 and not flags[1]
        elif not arg.startswith('-'):
            values.append(arg)
    if not repo:
        values = values[1:]  # The first positional names the remote.
    if everything and (force or delete):
        fail_broad_push()
    root = repository(cwd)
    policy = project_policy(root) if root else {}
    current = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD') if root else None
    targets = []
    for spec in values:
        forced = force or spec.startswith('+')
        spec = spec.lstrip('+')
        source, destination = spec.split(':', 1) if ':' in spec else (spec, spec)
        targets.append((source or None, destination, forced, delete or not source))
    if not values:
        targets.append((current, current, force, delete))
    rewritten = [resolved_branch(destination, current) for _, destination, forced, removed in targets if forced or removed]
    gated = root is not None and policy.get('require_verification_receipt')
    if not rewritten and not gated:
        return None
    integration = integration_branch(root, policy) if root else None
    protected = set(PROTECTED) | set(policy.get('production_branches', [])) | {integration}
    for branch in rewritten:
        if branch is None or branch in protected:
            fail('Force-pushing or deleting a protected branch (' + (branch or 'unresolved target') + ') rewrites shared history.',
                 'Push without force (git pull --rebase first) or use a working branch; if it is truly intended, the owner runs the exact command.',
                 'protected-branch')
    if not gated:
        return None
    decision = None
    for source, destination, _, _ in targets:
        if resolved_branch(destination, current) == integration:
            commit = git(root, 'rev-parse', '--verify', '--quiet', (source or 'HEAD') + '^{commit}')
            if commit is None:
                fail('The pushed integration ref cannot be resolved for receipt verification.',
                     'Push a literal ref: git push REMOTE ' + integration + '.', 'ref-evidence')
        else:
            commit = tag_commit(root, (destination or '').removeprefix('refs/tags/'))
            if commit is None:
                continue
        decision = require_receipt(root, policy, commit)
    if tags:
        decision = require_receipt(root, policy, None)  # Bulk tag publication: a clean, verified candidate.
    return decision


def git_command(args, cwd):
    args = list(args)
    while args and args[0].startswith('-'):
        option = args.pop(0)
        if option == '-C' and args:
            cwd = Path(cwd) / Path(args.pop(0)).expanduser()
        elif option.startswith('-C') and len(option) > 2:
            cwd = Path(cwd) / Path(option[2:]).expanduser()
        elif option in GIT_VALUE_OPTIONS and args:
            args.pop(0)
    if args[:1] == ['push']:
        return push(args[1:], cwd)
    return None


def deployment(args, cwd):
    if any(arg in ('--help', '-h', '--version', '-v') for arg in args):
        return None
    index = skip_options(args, VERCEL_VALUE_OPTIONS.__contains__)
    command = args[index] if index < len(args) else None
    if command is not None and command != 'deploy' and '/' not in command and command not in ('.', '..'):
        return None  # Other subcommands belong to native permissions.
    targets = [arg.split('=', 1)[1] if arg.startswith('--target=') else (args[position + 1] if position + 1 < len(args) else None)
               for position, arg in enumerate(args) if arg == '--target' or arg.startswith('--target=')]
    if not ('--prod' in args or targets) or any(target != 'production' for target in targets):
        fail('Vercel Preview deployments (including the bare default deploy) are disabled for this project.',
             'Build locally with vercel build, or deploy production explicitly with vercel deploy --prod.', 'preview')
    root = repository(cwd)
    return require_receipt(root, project_policy(root), None) if root else None


def github(args, cwd):
    if args[:2] == ['repo', 'delete']:
        fail('Deleting a repository is irreversible.',
             'The owner runs the exact gh repo delete command after confirming the target.', 'destructive-remote')
    if args[:2] == ['release', 'create']:
        root = repository(cwd)
        if root is None:
            return None
        policy = project_policy(root)
        index = 2 + skip_options(args[2:], lambda option: option not in RELEASE_FLAGS)
        commit = tag_commit(root, args[index]) if index < len(args) and policy.get('require_verification_receipt') else None
        if commit is not None:
            return require_receipt(root, policy, commit)
    return None


def strip_quoted_heredocs(command):
    while True:
        match = HEREDOC.search(command)
        if not match:
            return command
        end = re.search(r'(?m)^\t*' + re.escape(match[2]) + r'[ \t]*$', command[match.end():])
        if not end:
            raise Unclassifiable('unterminated quoted here-document')
        header = re.sub(r"<<-?(['\"])" + re.escape(match[2]) + r'\1', '', match[0])
        command = command[:match.start()] + header + command[match.end() + end.end():]


def substitution_end(command, start, opener):
    quote, depth, index = None, 1, start + len(opener)
    while index < len(command):
        char = command[index]
        if char == '\\' and quote != "'":
            index += 2
            continue
        if char in ('"', "'"):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            index += 1
            continue
        if quote != "'" and command.startswith('$(', index):
            index = substitution_end(command, index, '$(') + 1
            continue
        if quote is None:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if not depth:
                    return index
        index += 1
    raise Unclassifiable('unterminated shell substitution')


def backtick_end(command, start):
    index = start + 1
    while index < len(command) and command[index] != '`':
        index += 2 if command[index] == '\\' else 1
    if index >= len(command):
        raise Unclassifiable('unterminated backtick substitution')
    return index


def tokenize(command):
    """Retain operator identity; quoted semicolons/newlines stay literal words.

    Substitutions and parameter expansions become DYNAMIC in their word, and
    substitution bodies are returned separately for their own inspection.
    """
    command = strip_quoted_heredocs(command)
    tokens, embedded, word = [], [], []
    quote, started, index = None, False, 0
    def flush():
        nonlocal word, started
        if started:
            tokens.append(('word', ''.join(word)))
        word, started = [], False
    while index < len(command):
        char = command[index]
        if char == '\\' and quote != "'":
            if index + 1 == len(command):
                raise Unclassifiable('unterminated shell escape')
            if command[index + 1] != '\n':
                word.append(command[index + 1])
                started = True
            index += 2
            continue
        if char in ('"', "'"):
            if quote is None:
                quote, started = char, True
            elif quote == char:
                quote = None
            else:
                word.append(char)
            index += 1
            continue
        opener = next((value for value in ('$(', '<(', '>(') if command.startswith(value, index)), None)
        body = None
        if quote != "'" and opener and (opener == '$(' or quote is None):
            end = substitution_end(command, index, opener)
            body = command[index + len(opener):end]
        elif quote != "'" and char == '`':
            end = backtick_end(command, index)
            body = command[index + 1:end]
        if body is not None:
            embedded.append(body)
            word.append(DYNAMIC)
            started, index = True, end + 1
            continue
        if quote != "'" and char == '$':
            word.append(DYNAMIC)  # A parameter expansion cannot be resolved statically.
            started = True
        elif quote is None and char == '#' and not started:
            end = command.find('\n', index)
            index = len(command) if end < 0 else end
            continue
        elif quote is None and char == '&' and (command.startswith('&>', index) or (word and word[-1] in '<>')):
            started = True  # Redirections such as 2>&1 and &>file stay words.
            word.append(char)
        elif quote is None and char in ' \t\r':
            flush()
        elif quote is None and char in ';|&()\n':
            flush()
            operator = char
            if char in '|&' and command[index:index + 2] == char * 2:
                operator += char
                index += 1
            tokens.append(('operator', operator))
        else:
            started = True
            word.append(char)
        index += 1
    if quote is not None:
        raise Unclassifiable('unterminated quote')
    flush()
    return tokens, embedded


def without_redirections(words):
    """Drop 2>&1, >file, > file, &>file and similar words; they are not arguments."""
    output, index = [], 0
    while index < len(words):
        match = REDIRECTION.fullmatch(words[index])
        if not match:
            output.append(words[index])
        elif not match[1]:
            index += 1  # The target is the following word.
        index += 1
    return output


def unwrap(words):
    """Strip shell keywords, assignments and common executable wrappers."""
    while True:
        while words and (words[0] in SHELL_KEYWORDS or ASSIGNMENT.fullmatch(words[0])):
            words = words[1:]
        if not words or Path(words[0]).name not in WRAPPERS:
            return words
        wrapper, words = Path(words[0]).name, words[1:]
        if wrapper == 'command' and words[:1] in (['-v'], ['-V']):
            return []  # Shell lookup describes operands without executing them.
        words = words[skip_options(words, WRAPPERS[wrapper].__contains__):]
        if wrapper == 'timeout' and words:
            words = words[1:]  # The duration operand.


def inspect_command(command, cwd, depth=0):
    # Substitution bodies are part of the raw text, so no policy word anywhere
    # means nothing below can match.
    if depth > 5 or not POLICY_WORD.search(command):
        return []
    try:
        tokens, embedded = tokenize(command)
    except Unclassifiable:
        return []
    decisions = []
    for inner in embedded:
        decisions.extend(inspect_command(inner, cwd, depth + 1))
    segments, current = [], []
    for kind, token in tokens:
        if kind == 'operator':
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    for words in segments:
        words = unwrap(without_redirections(words))
        if not words:
            continue
        name, args = Path(words[0]).name, words[1:]
        if name in LITERAL_TEXT:
            continue
        if name in ('bash', 'sh', 'zsh') and len(args) >= 2 and args[0] in ('-c', '-lc'):
            decisions.extend(inspect_command(args[1], cwd, depth + 1))
            continue
        if name == 'eval':
            decisions.extend(inspect_command(' '.join(args), cwd, depth + 1))
            continue
        if name in ('npx', 'pnpm', 'npm', 'yarn', 'bunx'):
            while args and (args[0] in ('exec', 'dlx', '--') or args[0].startswith('-')):
                args = args[1:]
            package = Path(args[0]).name.split('@', 1)[0] if args else ''
            if package not in ('vercel', 'vc'):
                continue
            name, args = package, args[1:]
        if name == 'cd' and len(args) == 1 and DYNAMIC not in args[0]:
            target = (Path(cwd) / Path(args[0]).expanduser()).resolve()
            cwd = target if target.is_dir() else cwd
            continue
        if name == 'git':
            decision = git_command(args, cwd)
        elif name in ('vercel', 'vc'):
            decision = deployment(args, cwd)
        elif name == 'gh':
            decision = github(args, cwd)
        else:
            decision = None
        if decision:
            decisions.append(decision)
    return decisions


def evaluate(event):
    if not isinstance(event, dict) or not isinstance(event.get('tool_name'), str) or not event['tool_name']:
        fail('The native event does not identify its tool.', 'Reinstall the matching native PreToolUse adapter.', 'malformed-event')
    if event['tool_name'] != 'Bash':
        return []
    if event.get('hook_event_name') != 'PreToolUse' or not isinstance(event.get('tool_input'), dict):
        fail('Malformed guarded PreToolUse event.', 'Reinstall the matching native adapter and verify its stdin schema.', 'malformed-event')
    command, cwd = event['tool_input'].get('command'), event.get('cwd')
    if not isinstance(command, str) or not isinstance(cwd, str):
        fail('Guarded shell event requires command text and a cwd.', 'Verify the native adapter tool_input.command and cwd fields.', 'malformed-event')
    if not command.strip() or not Path(cwd).is_dir():
        return []  # A removed working directory must not block every shell command.
    return inspect_command(command, Path(cwd).resolve())


def telemetry(event, harness, decision, rule):
    from datetime import datetime, timezone
    try:
        root = Path(event.get('cwd', ''))
        directory = root / '.rpi/local'
        if not root.is_dir() or any(path.is_symlink() for path in (root, root / '.rpi', directory, directory / 'contract-events.jsonl')):
            return
        directory.mkdir(parents=True, exist_ok=True)
        value = {'ts': datetime.now(timezone.utc).isoformat(), 'session_id': event.get('session_id', ''),
                 'hook': 'rpi-policy-' + harness, 'decision': decision, 'rule': rule, 'file': ''}
        with (directory / 'contract-events.jsonl').open('a') as stream:
            stream.write(json.dumps(value) + '\n')
    except (OSError, TypeError):
        print('TELEMETRY UNAVAILABLE: policy evaluation still completed.', file=sys.stderr)


def main(argv):
    if len(argv) != 2 or argv[0] != '--harness' or argv[1] not in ('claude', 'codex'):
        print('BLOCKED / WHY: unsupported hook adapter arguments. / FIX: invoke rpi-policy.py --harness claude or --harness codex.', file=sys.stderr)
        return 2
    harness, event = argv[1], {}
    try:
        try:
            event = read_json(sys.stdin.read())
        except ValueError:
            fail('Native hook input must be one JSON object.', 'Reinstall the matching native PreToolUse adapter.', 'malformed-event')
        for rule in evaluate(event):
            telemetry(event, harness, 'allow', rule)
        return 0
    except Blocked as error:
        print('BLOCKED / WHY: ' + str(error) + ' / FIX: ' + error.fix, file=sys.stderr)
        if isinstance(event, dict) and isinstance(event.get('cwd'), str):
            telemetry(event, harness, 'block', error.rule)
        return 2
    except Exception as error:  # A denylist defect must not block ordinary work.
        print('POLICY UNAVAILABLE: evaluation failed (' + type(error).__name__ + '); the command passes to native permissions. '
              'Run python3 -m unittest discover -s tests -p "test_policy*.py" in cc-rpi to reproduce.', file=sys.stderr)
        return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
