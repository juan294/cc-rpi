#!/usr/bin/env python3
"""Supplemental denylist for clearly destructive remote operations.

Shell text is parsed, never executed. Exit 0 emits no native decision: the
client's permission rules, mode and user decide everything else, including
ordinary pushes, pull requests and workflow dispatch. Exit 2 blocks a
positively identified destructive operation, and also a command that names git,
gh or vercel and cannot be evaluated (an unexpected error or the time budget):
that failure is closed. Shell text that never reaches a policy word, and forms
the parser cannot classify (see docs/native-policy.md), pass through; this is
not a shell security boundary. The opt-in verification receipt gate is a Git
pre-push hook (rpi-prepush.py), because only Git knows exactly which refs a
push publishes.
"""
import sys

if sys.version_info < (3, 11):
    print('RPI POLICY SKIPPED: the policy adapter requires Python 3.11 or newer. FIX: uv python install 3.13; '
          'launch the client through uv run --python 3.13 so its hooks use the supported runtime.', file=sys.stderr)
    sys.exit(0)

# This runs before every shell command: modules only some paths need are
# imported where they are used.
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402
import re  # noqa: E402
import shlex  # noqa: E402
import time  # noqa: E402

POLICY_WORD = re.compile(r'\b(?:git|gh|vercel|vc)\b')
# Quote, escape and expansion characters can split a command name the shell still resolves (g\it, gi"t", g\<newline>it).
SPLITTING = re.compile(r'[\\\'"$\n]')
# Unquoted brace characters are kept apart from quoted ones until brace expansion has run.
OPEN_BRACE, COMMA, CLOSE_BRACE = '', '', ''
MAX_BRACE_WORDS = 1024
MAX_SPELLED_WORD = 512
MAX_SEQUENCE_DIGITS = 18
# Wall-clock bound for one hook invocation; a command that needs more is blocked, not passed.
DEFAULT_BUDGET_SECONDS = 10.0
# The Codex hook timeout is 30 s (templates/adapters/codex-hooks.json): the budget, the hard timer and the report must all fit inside it.
MAX_BUDGET_SECONDS = 20.0
BUDGET_SECONDS = DEFAULT_BUDGET_SECONDS
_DEADLINE = None
_FINAL_DEADLINE = None
_TICKS = 0
# git push long options (git push --git-completion-helper, git 2.56); the hook never runs git push to ask.
PUSH_LONG_OPTIONS = {'--verbose', '--quiet', '--repo', '--all', '--branches', '--mirror', '--delete', '--tags', '--dry-run',
                     '--porcelain', '--force', '--force-with-lease', '--force-if-includes', '--recurse-submodules',
                     '--receive-pack', '--exec', '--set-upstream', '--progress', '--prune', '--no-verify', '--follow-tags',
                     '--signed', '--atomic', '--push-option', '--ipv4', '--ipv6', '--verify'}
PUSH_LONG_OPTIONS |= {'--no-' + name[2:] for name in set(PUSH_LONG_OPTIONS) if not name.startswith('--no-')}
CODE_CONSUMERS = {'bash', 'sh', 'zsh', 'dash', 'ksh', 'fish', 'csh', 'tcsh', 'eval', 'source', '.', 'xargs', 'gxargs', 'parallel'}
# Words that start a command list (or modify the next command) without being the command: `- cmd` and `coproc cmd`
# are zsh and bash forms, `repeat N` is a wrapper below.
SHELL_KEYWORDS = {'{', '}', '!', 'if', 'then', 'else', 'elif', 'do', 'while', 'until', '-', 'coproc'}
ASSIGNMENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*=.*')
# A redirection word: an optional descriptor (2, &, or a bash {fd} variable), the operator, an optional glued target.
REDIRECTION = re.compile(r'(?:\d*|&|\{[A-Za-z_][A-Za-z0-9_]*\})(?:>>?|<)&?(.*)')


class Wrapper:
    """Options of an executable that runs another command, read with getopt rules: options end at the first operand.

    `short` are the short options that take a value (attached or the next word), `values` and `flags` the long ones
    (abbreviations resolve like getopt_long), `exact` single-dash words that are whole options, and `operands` the
    positional words before the command (timeout's duration), none of them when an option in `operands_unless` was given."""

    def __init__(self, short='', values=(), flags=(), exact=(), operands=0, operands_unless=''):
        self.short, self.values, self.flags, self.exact = short, frozenset(values), frozenset(flags), frozenset(exact)
        self.operands, self.operands_unless = operands, frozenset(operands_unless)


WRAPPERS = {
    'env': Wrapper('uCSaP', ('--unset', '--chdir', '--split-string', '--argv0'),
                   ('--ignore-environment', '--null', '--debug', '--default-signal', '--ignore-signal', '--block-signal',
                    '--list-signal-handling', '--help', '--version')),
    'command': Wrapper(), 'builtin': Wrapper(), 'noglob': Wrapper(), 'nocorrect': Wrapper(), 'nohup': Wrapper(),
    'busybox': Wrapper(), 'setsid': Wrapper(), 'unbuffer': Wrapper(),
    'exec': Wrapper('a'),
    'repeat': Wrapper(operands=1),
    'doas': Wrapper('Cua'),
    'sudo': Wrapper('CDghpRrTtUu', ('--chdir', '--close-from', '--group', '--host', '--prompt', '--chroot', '--role',
                                    '--command-timeout', '--type', '--other-user', '--user'),
                    ('--askpass', '--background', '--bell', '--edit', '--set-home', '--help', '--login', '--remove-timestamp',
                     '--reset-timestamp', '--list', '--non-interactive', '--preserve-groups', '--preserve-env', '--stdin',
                     '--shell', '--validate', '--version', '--stop-at-first-operand')),
    'time': Wrapper('fo', ('--format', '--output'), ('--append', '--portability', '--verbose', '--quiet', '--help', '--version')),
    'nice': Wrapper('n', ('--adjustment',), ('--help', '--version')),
    'timeout': Wrapper('ks', ('--kill-after', '--signal'), ('--foreground', '--preserve-status', '--verbose', '--help', '--version'),
                       operands=1),
    'stdbuf': Wrapper('ioe', ('--input', '--output', '--error'), ('--help', '--version')),
    'caffeinate': Wrapper('tw'),
    'ionice': Wrapper('cnpPu', ('--class', '--classdata', '--pid', '--pgid', '--uid'), ('--ignore', '--help', '--version')),
    'chrt': Wrapper('TPD', ('--sched-runtime', '--sched-period', '--sched-deadline'),
                    ('--batch', '--deadline', '--fifo', '--idle', '--other', '--rr', '--reset-on-fork', '--verbose',
                     '--all-tasks', '--max', '--help', '--version'), operands=1),
    'taskset': Wrapper('c', ('--cpu-list',), ('--all-tasks', '--pid', '--help', '--version'), operands=1, operands_unless=('c', '--cpu-list')),
    'arch': Wrapper('ed', exact=('-arch',)),
    'watch': Wrapper('nq', ('--interval', '--equexit'), ('--differences', '--no-title', '--beep', '--errexit', '--color', '--no-color',
                                                         '--chgexit', '--exec', '--precise', '--no-wrap', '--help', '--version')),
    'xcrun': Wrapper(exact=('-sdk', '--sdk', '-toolchain', '--toolchain')),
    'xargs': Wrapper('adEILnPsJRS', ('--arg-file', '--delimiter', '--eof', '--max-args', '--max-lines', '--max-chars',
                                     '--max-procs', '--process-slot-var'),
                     ('--null', '--exit', '--interactive', '--no-run-if-empty', '--open-tty', '--verbose', '--show-limits',
                      '--replace', '--help', '--version')),
}
# Wrappers that also take a -c command string of their own, so they are read in inspect_segment, not stripped by unwrap.
FLOCK = Wrapper('wE', ('--timeout', '--wait', '--conflict-exit-code'), ('--shared', '--exclusive', '--unlock', '--nonblock', '--no-fork',
                                                                      '--close', '--help', '--version'), operands=1)
RUNUSER = Wrapper('ugGsw', ('--user', '--group', '--supp-group', '--shell', '--whitelist-environment'),
                  ('--login', '--preserve-environment', '--pty', '--help', '--version'))
PARALLEL = Wrapper('jnNSaIsLlPTRCu', ('--jobs', '--max-args', '--max-replace-args', '--sshlogin', '--arg-file', '--max-lines', '--max-chars',
                                      '--delimiter', '--colsep', '--results', '--tmux', '--timeout', '--retries', '--load'),
                   ('--dry-run', '--keep-order', '--group', '--ungroup', '--halt', '--bar', '--progress', '--eta', '--verbose', '--null',
                    '--help', '--version'))
# Homebrew's coreutils and findutils install their tools with a g prefix (gtimeout, gnice, genv, gstdbuf, gnohup, gxargs).
for _name in ('env', 'nice', 'nohup', 'stdbuf', 'timeout', 'xargs', 'time'):
    WRAPPERS['g' + _name] = WRAPPERS[_name]
SHELLS = ('bash', 'sh', 'zsh', 'dash', 'ksh', 'fish', 'csh', 'tcsh')
# su and runuser run their -c string in the target user's shell.
SHELL_RUNNERS = ('su', 'runuser', 'flock')
NPX_VALUE_OPTIONS = {'-p', '--package', '-c', '--call', '--filter', '-C', '--dir'}
# Vercel CLI subcommands; any other first word is a path to deploy.
VERCEL_SUBCOMMANDS = {'alias', 'aliases', 'api', 'bisect', 'blob', 'build', 'buy', 'cache', 'certs', 'cert', 'deploy',
                      'dev', 'dns', 'domains', 'domain', 'env', 'flags', 'git', 'guidance', 'help', 'httpstat', 'init',
                      'inspect', 'install', 'i', 'integration', 'integration-resource', 'link', 'list', 'ls', 'login',
                      'logout', 'logs', 'mcp', 'microfrontends', 'open', 'project', 'projects', 'promote', 'pull',
                      'redeploy', 'remove', 'rm', 'rollback', 'rolling-release', 'switch', 'target', 'targets',
                      'teams', 'team', 'telemetry', 'upgrade', 'whoami'}
VERCEL_VALUE_OPTIONS = {'--token', '-t', '--scope', '-S', '--team', '-T', '--cwd', '-A', '--local-config',
                        '-Q', '--global-config', '--target', '-e', '--env', '-b', '--build-env', '-m', '--meta',
                        '--regions', '--archive'}
LITERAL_TEXT = {'echo', 'printf', 'cat', 'rg', 'grep'}
PROTECTED = ('main', 'master', 'develop')
DYNAMIC = '__RPI_DYNAMIC__'
POLICY_KEYS = {'schema_version', 'integration_branch', 'production_branches', 'remote',
               'require_verification_receipt', 'verification_checks', 'verification_command'}
# A version tag, as the receipt gate (rpi-prepush.py) defines it; a test keeps the two patterns identical. Three shapes: v1, v1.0,
# V3.0.0-rc.1 (a v and numbers); 2.0, 1.2.3 (numbers with at least one dot); release-v1, release-1.0.0 (a word and one of those).
# A bare number or word-number (1, issue-42, fix-123, feature-2, release-1) is a branch name, not a version. Every quantifier is
# possessive and the suffix cannot start with a digit or a dot, so matching is linear: nothing backtracks.
VERSION_TAG = re.compile(r'(?:[A-Za-z][A-Za-z0-9]*+[-_])?(?:[vV]\d++(?:\.\d++)*+|\d++(?:\.\d++)++)(?:[-+_A-Za-z][-+._0-9A-Za-z]*+)?')
# Names a tag glob is tried against: a pattern that can match one of them may rewrite a version tag.
VERSION_TAG_SAMPLES = ('v1', 'v1.0', 'v1.0.0', '1.0.0', 'V1.0', 'release-1.0', 'release-v1')
PUSH_VALUE_OPTIONS = {'-o', '--push-option', '--repo', '--receive-pack', '--exec'}
# Shell options whose next word is a value. Every other long option (--norc, --posix, --login ...) is a flag.
SHELL_VALUE_OPTIONS = {'-o', '+o', '-O', '+O', '--rcfile', '--init-file'}
# Git ignores an alias that has the name of a builtin; these are the builtins when `git --list-cmds=builtins` is unavailable.
GIT_BUILTINS = {'add', 'am', 'apply', 'archive', 'bisect', 'blame', 'branch', 'bundle', 'checkout', 'cherry', 'cherry-pick',
                'clean', 'clone', 'commit', 'config', 'describe', 'diff', 'fetch', 'format-patch', 'gc', 'grep', 'init', 'log',
                'ls-files', 'ls-remote', 'ls-tree', 'merge', 'mv', 'notes', 'pull', 'push', 'range-diff', 'rebase', 'reflog',
                'remote', 'reset', 'restore', 'revert', 'rm', 'shortlog', 'show', 'stash', 'status', 'submodule', 'switch',
                'tag', 'worktree'}
# The options git itself takes before the command (git.c handle_options, git 2.56). Those in GIT_VALUE_OPTIONS take the
# next word (the long ones also --name=value); --exec-path and --list-cmds take a value only as --name=value. Any other
# word that starts with a dash is an error to git. A test runs the installed git against both tables.
GIT_VALUE_OPTIONS = {'-C', '-c', '--git-dir', '--work-tree', '--namespace', '--super-prefix', '--config-env', '--attr-source'}
GIT_FLAG_OPTIONS = {'--version', '--help', '--exec-path', '--html-path', '--man-path', '--info-path', '-p', '--paginate', '-P',
                    '--no-pager', '--no-replace-objects', '--no-lazy-fetch', '--no-optional-locks', '--no-advice', '--bare',
                    '--literal-pathspecs', '--no-literal-pathspecs', '--glob-pathspecs', '--noglob-pathspecs',
                    '--icase-pathspecs', '--list-cmds'}
# Configuration variables whose value Git runs as a command; a destructive command in one is evaluated like shell text.
CODE_CONFIG = {'sshcommand', 'fsmonitor', 'pager', 'editor', 'askpass', 'program', 'external', 'textconv', 'clean', 'smudge',
               'process', 'driver', 'cmd', 'gitproxy', 'packobjectshook', 'helper', 'extcmd', 'command'}
# git filter-branch options whose value is shell text.
FILTER_BRANCH_CODE = ('--env-filter', '--tree-filter', '--index-filter', '--parent-filter', '--msg-filter', '--commit-filter',
                      '--tag-name-filter', '--setup')
AUTOCORRECT_OFF = {'', '0', 'never', 'false', 'no', 'off', 'show'}
AUTOCORRECT_FLOOR = 7  # git's SIMILARITY_FLOOR: a typed command nearer than this to a command is corrected to it.


class Blocked(ValueError):
    def __init__(self, reason, fix, rule):
        super().__init__(reason)
        self.fix, self.rule = fix, rule


class Unclassifiable(Exception):
    """Shell text the parser cannot read; it passes to native permissions."""


class BudgetExceeded(BaseException):
    """The evaluation outgrew its time budget. Not an Exception: no handler in the parser may swallow it.

    `cause` is 'size' (the command took too long to read) or 'git' (a git lookup did not answer in time)."""

    def __init__(self, cause='size'):
        super().__init__(cause)
        self.cause = cause


def fail(reason, fix, rule):
    raise Blocked(reason, fix, rule)


def fail_broad_push():
    fail('This push rewrites or deletes remote refs beyond the named branch.',
         'Push explicit refs instead: git push REMOTE BRANCH.', 'destructive-push')


def fail_tag_rewrite(name):
    fail('Deleting or force-moving a version tag (' + name + ') changes a published release.',
         'Publish a new version tag instead of changing a published one; if it is truly intended, the owner runs the exact command.',
         'protected-tag')


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


def budget_seconds():
    """(seconds, warning): RPI_POLICY_BUDGET_SECONDS when it is a finite number in (0, 20], else the default."""
    raw = os.environ.get('RPI_POLICY_BUDGET_SECONDS')
    if raw is None:
        return DEFAULT_BUDGET_SECONDS, None
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if math.isfinite(value) and 0 < value <= MAX_BUDGET_SECONDS:
        return value, None
    return DEFAULT_BUDGET_SECONDS, ('RPI_POLICY_BUDGET_SECONDS=' + repr(raw[:40]) + ' is not a number of seconds above 0 and at most ' +
                                    str(int(MAX_BUDGET_SECONDS)) + '; the default of ' + str(int(DEFAULT_BUDGET_SECONDS)) + ' seconds applies.')


def check_budget():
    if _DEADLINE is not None and time.monotonic() > _DEADLINE:
        raise BudgetExceeded()


def tick():
    """Called from every loop whose cost grows with the input: the time bound is enforced where the time is spent."""
    global _TICKS
    _TICKS += 1
    if not _TICKS & 255:
        check_budget()


_GIT_CACHE = {}


def git(cwd, *arguments):
    """Return Git's stdout, or None when Git or the repository state is unavailable.

    Answers are cached for this hook invocation: nothing is executed while the command is judged, so the
    repository cannot change between two lookups, and a long command pays for each distinct lookup once."""
    key = (str(cwd), arguments)
    if key not in _GIT_CACHE:
        import subprocess
        check_budget()
        remaining = None if _DEADLINE is None else max(_DEADLINE - time.monotonic(), 0.05)
        try:
            # Its own process group, so the whole group can be ended when the budget runs out (a helper holding the pipe
            # open would otherwise keep this call waiting).
            process = subprocess.Popen(['git', '-C', str(cwd), *arguments], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='surrogateescape',
                                       start_new_session=os.name == 'posix')
        except OSError:
            _GIT_CACHE[key] = None
            return None
        try:
            output, _ = process.communicate(timeout=remaining)
        except BaseException as error:  # The budget, the timer or an interrupt: leave no git behind.
            try:
                os.killpg(process.pid, 9) if os.name == 'posix' else process.kill()
            except OSError:
                pass
            try:
                process.communicate(timeout=1)
            except (subprocess.TimeoutExpired, OSError):
                pass
            if isinstance(error, (subprocess.TimeoutExpired, BudgetExceeded)):
                raise BudgetExceeded('git') from None
            raise
        _GIT_CACHE[key] = output.strip() if process.returncode == 0 else None
    return _GIT_CACHE[key]


def repository(cwd):
    if cwd is None:
        return None
    top = git(cwd, 'rev-parse', '--show-toplevel')
    return Path(top).resolve() if top else None


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
        value = read_json(path.read_text(encoding='utf-8'))
    except OSError as error:
        fail('Project policy .rpi/policy.json cannot be read (' + type(error).__name__ + ').',
             'Make .rpi/policy.json a readable regular file, or remove it.', 'policy-file')
    except ValueError as error:
        fail('Project policy .rpi/policy.json is not valid JSON (' + str(error) + ').',
             'Fix the JSON syntax; save it as UTF-8 without a byte-order mark.', 'policy-file')
    if not isinstance(value, dict) or value.get('schema_version') != 1 or set(value) - POLICY_KEYS:
        fail('Invalid project policy in .rpi/policy.json.',
             'Use schema_version 1 and only these keys: ' + ', '.join(sorted(POLICY_KEYS)) + '.', 'policy-file')
    if 'integration_branch' in value and (not isinstance(value['integration_branch'], str) or not value['integration_branch']):
        fail('In .rpi/policy.json, integration_branch must be one branch name.',
             'Declare "integration_branch": "main" (or the actual branch), or remove the key.', 'policy-file')
    branches = value.get('production_branches', [])
    if not isinstance(branches, list) or any(not isinstance(item, str) or not item for item in branches):
        fail('In .rpi/policy.json, production_branches must be a list of branch names.',
             'Declare production_branches as ["name", ...] or remove the key.', 'policy-file')
    return value


def branch_name(name):
    """A declared branch as a bare name: refs/heads/NAME and NAME are the same branch."""
    name = name.removeprefix('refs/')  # refs/heads/NAME, heads/NAME and NAME all name the branch (git's short-ref rules).
    return name.removeprefix('heads/')


def production_branches(policy):
    return {branch_name(name) for name in policy.get('production_branches', [])}


def integration_branch(root, policy):
    declared = policy.get('integration_branch')
    if isinstance(declared, str) and declared:
        return branch_name(declared)
    return next((name for name in PROTECTED if git(root, 'rev-parse', '--verify', '--quiet', 'refs/heads/' + name)), None)


def protected_branches(root, policy):
    return set(PROTECTED) | production_branches(policy) | {integration_branch(root, policy) if root else None}


def ref_kind(ref):
    """('tag', NAME) for refs/tags/NAME and tags/NAME, else ('branch', NAME) for a branch spelling of any form."""
    name = ref.removeprefix('refs/')
    if name.startswith('tags/'):
        return 'tag', name[len('tags/'):]
    return 'branch', name.removeprefix('heads/')


def parse_refspec(spec, force, delete):
    """(source, destination, forced, removed) for one push refspec."""
    forced = force or spec.startswith('+')
    spec = spec.lstrip('+')
    if spec == ':':
        return None, '*', forced, False  # The matching push: every branch present on both sides.
    source, destination = spec.split(':', 1) if ':' in spec else (spec, spec)
    return source or None, destination, forced, delete or not source


def config_key(key):
    """Git config key with a case-insensitive section and variable and a case-sensitive subsection."""
    parts = key.split('.')
    return '.'.join([parts[0].lower(), *parts[1:-1], parts[-1].lower()]) if len(parts) > 1 else key


def config_value(root, overrides, key, default=None):
    """The last value of a setting: this command line's git -c setting, else the repository's configuration."""
    key = config_key(key)
    if key in overrides:
        return overrides[key][-1]
    return (git(root, 'config', '--get', key) if root is not None else None) or default


def config_true(value):
    return str(value).strip().lower() in ('true', 'yes', 'on', '1')


def push_remote(root, remote, current, overrides):
    """The remote a push without a remote operand uses: branch.<b>.pushRemote, remote.pushDefault, branch.<b>.remote, origin."""
    if remote:
        return remote
    branch = [config_value(root, overrides, 'branch.' + current + '.pushRemote')] if current else []
    return next((name for name in branch + [config_value(root, overrides, 'remote.pushDefault'),
                                            config_value(root, overrides, 'branch.' + current + '.remote') if current else None] if name), 'origin')


def configured_targets(root, remote, current, force, delete, overrides=None):
    """Destinations Git derives from configuration when a push names no refspec.

    `overrides` are the git -c settings of this command line: they append to a multi-valued
    remote.<name>.push and replace a single-valued setting."""
    overrides = overrides or {}
    if root is None:
        return [(current, current, force, delete)]  # The configuration is unknown: the current branch cannot be resolved either.
    key = config_key('remote.' + push_remote(root, remote, current, overrides) + '.push')
    specs = (git(root, 'config', '--get-all', key) or '').splitlines() + overrides.get(key, [])
    if specs:
        return [parse_refspec(spec, force, delete) for spec in specs]
    mode = config_value(root, overrides, 'push.default', 'simple')
    if mode == 'matching':
        return [(None, '*', force, False)]
    if current is None or mode == 'nothing':
        return []  # Git refuses: a detached HEAD has no branch to push, and push.default=nothing pushes nothing unnamed.
    if mode in ('upstream', 'tracking'):
        merge = config_value(root, overrides, 'branch.' + current + '.merge')
        if merge:
            return [(current, merge, force, delete)]
    return [(current, current, force, delete)]


def push_option_names(name):
    """The long options a (possibly abbreviated) --name can mean. git accepts any unambiguous prefix; an
    ambiguous one is rejected by git, and every reading is applied here so none of them can hide a rewrite."""
    if name in PUSH_LONG_OPTIONS or not name.startswith('--') or len(name) < 3:
        return {name}
    return {option for option in PUSH_LONG_OPTIONS if option.startswith(name)} or {name}


def glob_matches(pattern, names):
    """Could a ref glob (the * of a refspec) match any of `names`? Compared without case, as a case-insensitive remote would."""
    import fnmatch
    return any(fnmatch.fnmatchcase(name.lower(), pattern.lower()) for name in names)


def check_ref(kind, pattern, protected):
    """Block when a rewrite of the ref `pattern` (a branch or a tag name; * stands for any text) can hit a protected branch or
    a version tag. A name with a wildcard is compared as a glob, without case, as a case-insensitive remote would."""
    wildcard = '*' in pattern
    label = 'unresolved target' if pattern.replace('*', '') == '' else pattern
    if kind == 'tag':
        if glob_matches(pattern, VERSION_TAG_SAMPLES) if wildcard else VERSION_TAG.fullmatch(pattern):
            fail_tag_rewrite(label)
    elif glob_matches(pattern, [item for item in protected if item]) if wildcard else pattern.lower() in {item.lower() for item in protected if item}:
        fail('Force-pushing or deleting a protected branch (' + label + ') rewrites shared history.', PROTECTED_FIX, 'protected-branch')


def check_destination(destination, root, current, protected):
    """Block when a forced or deleting push to `destination` would rewrite a protected branch or a version tag.

    A destination that spells a version tag is a tag rewrite whatever its source is: git matches the destination against the
    remote's refs first, so a branch can move a tag (`feat:v1.0`). Only a qualified refs/heads/ or heads/ name is a branch
    for sure. A destination that cannot be resolved (a variable, a substitution) is a wildcard: it is blocked when any
    protected branch or version tag could be meant, which is every unresolved name and not "feature-$N"."""
    if destination in ('HEAD', '@'):
        destination = current
    if not destination:
        destination = DYNAMIC
    kind, name = ref_kind(destination)
    pattern = name.replace(DYNAMIC, '*')
    kinds = [kind]
    if kind == 'branch' and not destination.startswith(('refs/', 'heads/')):
        if '*' in pattern:
            kinds = ['branch', 'tag']  # An unqualified name that may be anything may be a tag.
        elif VERSION_TAG.fullmatch(pattern):
            kinds = ['tag']
    for each in kinds:
        check_ref(each, pattern, protected)


PROTECTED_FIX = ('Push without force (git pull --rebase first) or use a working branch; if it is truly intended, '
                 'the owner runs the exact command.')


def push(args, cwd, overrides=None):
    force = delete = everything = broad = dry_run = tags = False
    remote, values, index = None, [], 0
    while index < len(args):
        arg = args[index]
        index += 1
        names = push_option_names(arg.split('=', 1)[0])
        if arg == '--':
            values.extend(args[index:])
            break
        if names & {'--mirror', '--prune'}:
            broad = True
        if names & {'--force', '--force-with-lease'}:
            force = True
        if names & {'--delete'}:
            delete = True
        if names & {'--all', '--branches'}:
            everything = True
        if names & {'--tags'}:
            tags = True
        if names & {'--dry-run'}:
            dry_run = True
        if names & PUSH_VALUE_OPTIONS:
            value = arg.split('=', 1)[1] if '=' in arg else (args[index] if index < len(args) else None)
            remote = value if names & {'--repo'} else remote
            index += '=' not in arg
        elif names & {'--mirror', '--prune', '--force', '--force-with-lease', '--delete', '--all', '--branches', '--dry-run', '--tags'}:
            pass
        elif re.fullmatch(r'-[A-Za-z0-9]+', arg):
            flags = arg[1:].split('o', 1)  # -o takes the rest, or the next word, as its value; -4 and -6 are flags.
            force, delete = force or 'f' in flags[0], delete or 'd' in flags[0]
            dry_run = dry_run or 'n' in flags[0]
            index += len(flags) == 2 and not flags[1]
        elif not arg.startswith('-'):
            values.append(arg)
    if dry_run:
        return  # A dry run changes nothing remotely.
    if remote is None and values:
        remote, values = values[0], values[1:]  # The first positional names the remote.
    if broad or everything and (force or delete):
        fail_broad_push()
    if tags and force:
        fail_tag_rewrite('all tags')  # --force --tags may move any published tag.
    root = repository(cwd)
    current = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD') if root else None
    if (not values and not tags and not everything and root and
            config_true(config_value(root, overrides or {}, 'remote.' + push_remote(root, remote, current, overrides or {}) + '.mirror'))):
        fail_broad_push()  # remote.<name>.mirror makes a plain push a mirror push.
    if values:
        targets = [parse_refspec(spec, force, delete) for spec in values]
    elif tags or everything:
        targets = []  # --tags pushes tags only and --all every branch without force (a forced --all was refused above).
    else:
        targets = configured_targets(root, remote, current, force, delete, overrides)
    rewriting = [destination for _, destination, forced, removed in targets if forced or removed]
    if not rewriting:
        return
    policy = project_policy(root) if root else {}
    protected = protected_branches(root, policy)
    for destination in rewriting:
        check_destination(destination, root, current, protected)


def send_pack(args, cwd):
    """git send-pack / http-push: [options] REMOTE [REF...]; without refs every matching branch is sent."""
    force = delete = everything = broad = False
    values, index = [], 0
    while index < len(args):
        arg = args[index]
        index += 1
        names = {arg.split('=', 1)[0]}
        if arg == '--':
            values.extend(args[index:])
            break
        broad = broad or bool(names & {'--mirror', '--prune'})
        force = force or bool(names & {'--force', '-f', '--force-with-lease'}) or arg.startswith('--force-with-lease=')
        delete = delete or bool(names & {'--delete', '-d'})
        everything = everything or '--all' in names
        if names & {'--receive-pack', '--exec', '--push-option', '-o', '--repo'} and '=' not in arg:
            index += 1
        elif not arg.startswith('-'):
            values.append(arg)
    if broad or everything and (force or delete):
        fail_broad_push()
    values = values[1:]  # The first positional is the remote.
    root = repository(cwd)
    current = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD') if root else None
    targets = [parse_refspec(spec, force, delete) for spec in values] if values else ([] if everything else [(None, '*', force, False)])
    rewriting = [destination for _, destination, forced, removed in targets if forced or removed]
    if rewriting:
        protected = protected_branches(root, project_policy(root) if root else {})
        for destination in rewriting:
            check_destination(destination, root, current, protected)


def environment_config(assigned):
    """(key, value) pairs Git reads from inline GIT_CONFIG_COUNT/KEY_n/VALUE_n and GIT_CONFIG_PARAMETERS."""
    pairs = []
    for item in shlex.split(assigned.get('GIT_CONFIG_PARAMETERS', '')):
        name, _, value = item.partition('=')
        pairs.append((name, value))
    count = assigned.get('GIT_CONFIG_COUNT', '')
    for number in range(int(count) if count.isdigit() and int(count) <= 100 else 0):
        key = assigned.get('GIT_CONFIG_KEY_%d' % number)
        if key is not None and ('GIT_CONFIG_VALUE_%d' % number) in assigned:
            pairs.append((key, assigned['GIT_CONFIG_VALUE_%d' % number]))
    return pairs


# Alias expansions and nested shells followed before the command is left to native permissions.
MAX_NESTING = 100
_BUILTINS = None


def git_builtins(cwd):
    """The builtin command names, listed by git once per process (a static list is the fallback)."""
    global _BUILTINS
    if _BUILTINS is None:
        listed = git(cwd or '.', '--list-cmds=builtins')
        _BUILTINS = set(listed.split()) if listed else set()
    return _BUILTINS


def shell_text(words):
    """Words that a shell receives as a command line: the first is script text, the rest are quoted arguments."""
    return (words[0] + ' ' + ' '.join(shlex.quote(word) for word in words[1:])) if words else ''


def autocorrect_distance(typed, command):
    """git's weighted edit distance (swap 0, substitution 2, addition 1, deletion 3) between a typed and a real command."""
    swap, substitute, add, delete = 0, 2, 1, 3
    previous2, previous = None, [number * add for number in range(len(command) + 1)]
    for i, one in enumerate(typed):
        row = [previous[0] + delete]
        for j, two in enumerate(command):
            cell = previous[j] + substitute * (one != two)
            if i and j and typed[i - 1] == two and one == command[j - 1] and previous2 is not None:
                cell = min(cell, previous2[j - 1] + swap)
            cell = min(cell, previous[j + 1] + delete, row[j] + add)
            row.append(cell)
        previous2, previous = previous, row
    return previous[-1]


def git_command(args, cwd, depth=0, assigned=None, inherited=None):
    """A git invocation: -C, -c, --config-env and inline GIT_CONFIG_* are applied, a command-line alias is
    expanded, and push is evaluated. Variables exported by an earlier command are not known."""
    args, assigned = list(args), assigned or {}
    # A shell alias runs a child git that inherits this command line's -c settings, as git passes them on.
    overrides = {key: list(values) for key, values in inherited[0].items()} if inherited else {}
    seen = set(inherited[1]) if inherited else set()
    code = []  # Values of configuration variables that Git runs as commands, set on this command line.
    try:
        for name, value in environment_config(assigned):
            overrides.setdefault(config_key(name), []).append(value)
            code.append((config_key(name), value))
    except ValueError:
        pass  # Unreadable GIT_CONFIG_PARAMETERS pass to native permissions.

    def global_options(args, cwd):
        """Consume leading global options (-C, -c, --config-env, -p, --no-pager ...) of `args` in place."""
        while args and args[0].startswith('-'):
            option = args.pop(0)
            name, equals, inline = option.partition('=')
            if option == '-C' and args or option.startswith('-C') and len(option) > 2:
                cwd = directory(cwd, args.pop(0) if option == '-C' else option[2:])
            elif option == '-c' and args:
                key, _, value = args.pop(0).partition('=')
                overrides.setdefault(config_key(key), []).append(value)
                code.append((config_key(key), value))
            elif name == '--config-env' and (equals or args):
                key, _, variable = (inline if equals else args.pop(0)).partition('=')
                if variable in assigned:  # Only a variable assigned in this very command is known.
                    overrides.setdefault(config_key(key), []).append(assigned[variable])
            elif name in GIT_VALUE_OPTIONS and name.startswith('--') and not equals and args:
                args.pop(0)
        return cwd

    cwd = global_options(args, cwd)
    for key, value in code:
        if key.rsplit('.', 1)[-1] in CODE_CONFIG and POLICY_WORD.search(value):
            inspect_command(value.removeprefix('!'), cwd, depth + 1, (overrides, frozenset(seen)))
    for _ in range(MAX_NESTING + 1):  # MAX_NESTING expansions are followed; the next lookup finds the command itself.
        name = args[0] if args else None
        if name is None or name in GIT_BUILTINS or name in git_builtins(cwd):
            break  # No command, or one named like a builtin: Git ignores an alias of that name.
        alias = config_value(cwd, overrides, 'alias.' + name)
        if alias is None:
            break
        if name in seen:
            return  # An alias loop: Git rejects it, and it is not a push.
        seen.add(name)
        if alias.startswith('!'):
            inspect_command(shell_text([alias[1:], *args[1:]]), cwd, depth + 1, (overrides, frozenset(seen)))
            return
        try:
            args = shlex.split(alias) + args[1:]
        except ValueError:
            return
        cwd = global_options(args, cwd)  # An alias may begin with global options such as -c or -p.
    else:
        return  # More than MAX_NESTING expansions: unclassifiable, so it passes to native permissions.
    name = args[0] if args else None
    if name is not None and name not in GIT_BUILTINS and name not in git_builtins(cwd):
        # An unknown command word: with help.autocorrect enabled Git runs the nearest command, which may be push.
        value = str(config_value(cwd, overrides, 'help.autocorrect', '')).strip().lower()
        if (value not in AUTOCORRECT_OFF and not name.startswith('-') and
                autocorrect_distance(name, 'push') < AUTOCORRECT_FLOOR):
            name = 'push'
    rest = args[1:]
    if name == 'push':
        push(rest, cwd, overrides)
    elif name in ('send-pack', 'http-push'):
        send_pack(rest, cwd)
    elif name == 'submodule' and 'foreach' in rest:
        script = [word for word in rest[rest.index('foreach') + 1:] if word not in ('--recursive', '-q', '--quiet', '--')]
        if script:
            inspect_command(shell_text(script), None, depth + 1, (overrides, frozenset(seen)))  # It runs in each submodule.
    elif name == 'rebase':
        for position, word in enumerate(rest):
            exec_option = re.fullmatch(r'--ex(?:e(?:c)?)?(?:=(.*))?|-(?!-)[A-Za-z]*?x(.*)', word)
            if exec_option:
                script = exec_option[1] if exec_option[1] is not None else exec_option[2]
                script = script or (rest[position + 1] if position + 1 < len(rest) else '')
                inspect_command(script, cwd, depth + 1, (overrides, frozenset(seen)))
    elif name == 'bisect' and rest[:1] == ['run'] and len(rest) > 1:
        inspect_command(shell_text(rest[1:]) if len(rest) > 2 else rest[1], cwd, depth + 1, (overrides, frozenset(seen)))
    elif name == 'filter-branch':
        for position, word in enumerate(rest):
            option, equals, inline = word.partition('=')
            if option in FILTER_BRANCH_CODE:
                script = inline if equals else (rest[position + 1] if position + 1 < len(rest) else '')
                inspect_command(script, cwd, depth + 1, (overrides, frozenset(seen)))
    elif name in ('difftool', 'mergetool'):
        for position, word in enumerate(rest):
            command = re.fullmatch(r'--extcmd=(.*)|-x(.*)', word)
            if command or word == '--extcmd':
                script = (command[1] if command[1] is not None else command[2]) if command else None
                script = script or (rest[position + 1] if position + 1 < len(rest) else '')
                inspect_command(script, cwd, depth + 1, (overrides, frozenset(seen)))
    elif name == 'for-each-repo':
        words = [word for word in rest if not word.startswith('--config=') and not word.startswith('--keep-going')]
        if words:
            git_command(words, None, depth + 1, None, (overrides, frozenset(seen)))


def change_directory(name, args, state):
    """Apply a literal cd, pushd or popd to the shell state (cwd, previous directory, directory stack)."""
    cwd = state['cwd']
    if name == 'popd':
        state['cwd'] = state['stack'].pop() if state['stack'] and not args else None
        return
    operands, options = [], True
    for word in args:
        if options and word == '--':
            options = False
        elif not (options and len(word) > 1 and word[0] == '-' and set(word[1:]) <= set('LPe@')):
            operands.append(word)
    if len(operands) > 1 or (name == 'pushd' and not operands):
        state['cwd'] = None
    elif not operands:
        state['cwd'] = directory(cwd, '~')
    elif operands[0] == '-':
        state['cwd'] = state['previous']
    else:
        state['cwd'] = directory(cwd, operands[0])
    if name == 'pushd':
        state['stack'].append(cwd)
    state['previous'] = cwd


def directory(cwd, target):
    """The literal directory a cd or git -C names, or None when it cannot be known."""
    if DYNAMIC in target:
        return None
    try:
        path = Path(target).expanduser()
        if not path.is_absolute():
            if cwd is None:
                return None
            path = Path(cwd) / path
        path = path.resolve()
        return path if path.is_dir() else cwd
    except (OSError, RuntimeError, ValueError):
        return None


def deployment(args):
    if any(arg in ('--help', '-h', '--version', '-v') for arg in args):
        return
    index = skip_options(args, VERCEL_VALUE_OPTIONS.__contains__)
    command = args[index] if index < len(args) else None
    if command is not None and command != 'deploy' and command in VERCEL_SUBCOMMANDS:
        return  # Other subcommands belong to native permissions.
    targets = [arg.split('=', 1)[1] if arg.startswith('--target=') else (args[position + 1] if position + 1 < len(args) else None)
               for position, arg in enumerate(args) if arg == '--target' or arg.startswith('--target=')]
    if not ('--prod' in args or targets) or any(target != 'production' for target in targets):
        fail('Vercel Preview deployments (including the bare default deploy) are disabled for this project.',
             'Build locally with vercel build, or deploy production explicitly with vercel deploy --prod.', 'preview')


def gh_aliases(environment=None):
    """The aliases of the gh configuration file (config.yml), read without a YAML parser: name -> expansion."""
    environment = os.environ if environment is None else environment
    aliases, inside = {}, False
    try:
        base = environment.get('GH_CONFIG_DIR') or (
            environment['XDG_CONFIG_HOME'] + '/gh' if environment.get('XDG_CONFIG_HOME') else str(Path.home()) + '/.config/gh')
        lines = (Path(base) / 'config.yml').read_text(encoding='utf-8', errors='replace').splitlines()
    except (OSError, RuntimeError):
        return aliases
    for line in lines[:2000]:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if line[0] not in ' \t':
            inside = line.split('#', 1)[0].strip() == 'aliases:'
        elif inside and (match := re.match(r'\s+([^\s:#][^:]*?):\s*(.*?)\s*$', line)):
            value = match[2]
            if len(value) > 1 and value[0] == value[-1] and value[0] in '\'"':
                value = value[1:-1]
            aliases[match[1].strip('\'"')] = value
    return aliases


def github_alias(expansion, rest, cwd, depth):
    """Evaluate a gh alias expansion as the gh command (or, with a leading !, the shell text) it stands for."""
    if expansion.startswith('!'):
        inspect_command(shell_text([expansion[1:], *rest]), cwd, depth + 1)
        return
    try:
        words = shlex.split(expansion)
    except ValueError:
        words = expansion.split()
    github(words + rest, cwd, depth + 1)


def github(args, cwd, depth=0):
    if args[:2] == ['repo', 'delete']:
        if any(arg in ('--help', '-h') for arg in args):
            return
        fail('Deleting a repository is irreversible.',
             'The owner runs the exact gh repo delete command after confirming the target.', 'destructive-remote')
    if args[:1] == ['api']:
        api_destruction(args[1:], cwd)
    if args[:2] == ['release', 'delete'] and any(arg == '--cleanup-tag' or arg.startswith('--cleanup-tag=') for arg in args):
        fail_tag_rewrite('the release tag')
    if args[:2] == ['alias', 'set'] and len(args) > 3:
        rest = [arg for arg in args[2:] if arg not in ('--shell', '-s', '--clobber')]
        if len(rest) >= 2:
            github_alias(('!' if '--shell' in args or '-s' in args else '') + rest[1], [], cwd, depth)
    elif depth < MAX_NESTING and args and not args[0].startswith('-') and args[0] in (aliases := gh_aliases()):
        github_alias(aliases[args[0]], args[1:], cwd, depth)


def shell_script(args):
    """The -c script of a shell invocation such as bash -ec 'CMD', sh -e -c 'CMD' or bash -c -e 'CMD'.

    A shell takes options (before and after -c) until its first non-option word, and with -c
    that word is the script. -o and -O take an option name."""
    index, command = 0, False
    while index < len(args):
        word = args[index]
        if word == '--':
            index += 1
            break
        if word[:1] not in ('-', '+') or word in ('-', '+'):
            break
        if word.startswith('--command='):
            return word.split('=', 1)[1]  # fish
        if word == '--command' and index + 1 < len(args):
            return args[index + 1]
        command = command or bool(re.fullmatch(r'-[A-Za-z]*c[A-Za-z]*', word))
        index += 2 if word in SHELL_VALUE_OPTIONS else 1  # -o and -O take an option name, --rcfile and --init-file a file.
    return args[index] if command and index < len(args) else None


def runner_script(args):
    """The -c command of su / runuser: -c CMD, -cCMD, --command CMD, --command=CMD, also inside a cluster such as -lc."""
    for position, word in enumerate(args):
        if word.startswith('--command='):
            return word.split('=', 1)[1]
        if word == '--command' or re.fullmatch(r'-[A-Za-z]*c', word):
            return args[position + 1] if position + 1 < len(args) else None
        if re.fullmatch(r'-c.+', word):
            return word[2:]
    return None


def api_methods(args):
    """HTTP methods gh api is given: -X VALUE, -XVALUE, -iX VALUE (X inside a flag cluster), -X=VALUE, --method[=]VALUE."""
    methods = []
    for index, arg in enumerate(args):
        cluster = re.fullmatch(r'-i*X=?(.*)', arg)  # -i is gh api's only boolean short flag.
        if cluster:
            methods.append(cluster[1] or (args[index + 1] if index + 1 < len(args) else ''))
        elif arg == '--method':
            methods.append(args[index + 1] if index + 1 < len(args) else '')
        elif arg.startswith('--method='):
            methods.append(arg.split('=', 1)[1])
    return methods


def api_fields(args):
    """(name, value) of every -f/-F/--field/--raw-field argument of gh api, in the spellings cobra accepts."""
    fields = []
    for index, arg in enumerate(args):
        text = None
        if arg in ('-f', '-F', '--field', '--raw-field'):
            text = args[index + 1] if index + 1 < len(args) else ''
        elif re.fullmatch(r'-[fF].+', arg):
            text = arg[2:].removeprefix('=')
        elif arg.startswith(('--field=', '--raw-field=')):
            text = arg.split('=', 1)[1]
        if text is not None:
            name, _, value = text.partition('=')
            fields.append((name, value))
    return fields


def api_path(arg):
    """The endpoint path of a gh api operand, normalised: query and fragment removed, percent-decoded,
    repeated slashes collapsed and . and .. segments resolved. A host prefix is peeled off first."""
    import posixpath
    from urllib.parse import unquote
    path = unquote(re.split(r'[?#]', arg, maxsplit=1)[0])
    host = re.match(r'https?://[^/]+', path)
    path = path[host.end():] if host else path
    return posixpath.normpath(re.sub(r'/+', '/', path)) if path else path


def api_path_raw(arg):
    """The decoded operand before normalisation, for recognising a ref path that normalisation resolved away."""
    from urllib.parse import unquote
    return unquote(re.split(r'[?#]', arg, maxsplit=1)[0])


GRAPHQL_DESTRUCTION = re.compile(r'\b(deleteRepository|deleteRef)\b')
GRAPHQL_FORCE_UPDATE = re.compile(r'\bupdateRef\b[\s\S]*?\bforce\s*:\s*(?:true\b|\$)')


def graphql_text(args, cwd):
    """(query text, opaque) of a gh api graphql call. The text is its -f/-F fields and the files they read with @FILE or
    --input FILE; the call is opaque when the query itself is not known statically: a query field built from a variable
    or substitution, a file whose path is dynamic, or standard input."""
    texts = [(name, value) for name, value in api_fields(args)]
    for index, arg in enumerate(args):
        if arg == '--input' and index + 1 < len(args):
            texts.append(('input', '@' + args[index + 1]))
        elif arg.startswith('--input='):
            texts.append(('input', '@' + arg.split('=', 1)[1]))
    output, opaque = [], False
    for name, text in texts:
        query = name in ('query', 'input')
        if text.startswith('@') and len(text) > 1:
            if text == '@-' or DYNAMIC in text:
                opaque = opaque or query
                continue
            try:
                path = Path(text[1:]).expanduser()
                path = path if path.is_absolute() or cwd is None else Path(cwd) / path
                with path.open(encoding='utf-8', errors='replace') as stream:
                    text = stream.read(65536)
            except (OSError, RuntimeError):
                continue  # A file that is not there: gh itself stops.
        elif query and DYNAMIC in text:
            opaque = True
        output.append(text)
    return '\n'.join(output), opaque


def api_destruction(args, cwd):
    """Block API deletion of a repository, a protected branch or a version tag, a forced update of one, and the
    GraphQL mutations that do the same."""
    methods = {method.upper() for method in api_methods(args)}
    paths = [api_path(arg) for arg in args if not arg.startswith('-')]
    forced = any(name == 'force' and (value.strip().lower() in ('true', '1', 't', 'yes') or DYNAMIC in value)
                 for name, value in api_fields(args))
    if 'graphql' in paths:
        query, opaque = graphql_text(args, cwd)
        match = GRAPHQL_DESTRUCTION.search(query)
        mutation = match[1] if match else ('updateRef' if GRAPHQL_FORCE_UPDATE.search(query) else None)
        if mutation:
            fail('This GraphQL mutation (' + mutation + ') deletes a repository or rewrites or deletes refs, and its target cannot be read from the query.',
                 'Use the REST endpoint for a working branch (gh api -X DELETE repos/OWNER/REPO/git/refs/heads/BRANCH); the owner runs the exact mutation otherwise.',
                 'destructive-remote' if mutation == 'deleteRepository' else 'protected-branch')
        if opaque and not mutation:
            fail('The query of this gh api graphql call comes from a variable, a substitution or standard input, so a deleteRepository or deleteRef '
                 'mutation cannot be ruled out.', 'Write the query out with -f query=\'...\' or read it from a file in the project with -F query=@FILE; '
                 'the owner runs a query that cannot be written out.', 'destructive-remote')
    if not methods & {'DELETE', 'PATCH'}:
        return
    prefix = r'/?(?:api/v3/)?repos/[^/]+/[^/]+'
    # A PATCH of a ref is destructive only when it forces the update; a body read from a file or standard input is unknown.
    destructive = 'DELETE' in methods or forced or any(arg == '--input' or arg.startswith('--input=') for arg in args)
    for arg in args:
        if arg.startswith('-'):
            continue
        path = api_path(arg)
        if 'DELETE' in methods and '..' in path.split('/') and 'refs/heads' in api_path_raw(arg):
            fail('This API path climbs out of its endpoint, so a protected branch deletion cannot be ruled out.',
                 'Use the plain endpoint, for example repos/OWNER/REPO/git/refs/heads/BRANCH, and delete only working branches.',
                 'protected-branch')
        if 'DELETE' in methods and re.fullmatch(prefix + r'/?', path):
            fail('Deleting a repository is irreversible.',
                 'The owner runs the exact deletion after confirming the target.', 'destructive-remote')
        match = re.fullmatch(prefix + r'/git/refs/(heads|tags|' + re.escape(DYNAMIC) + r'[^/]*)/(.+?)/*', path)
        if not match or not destructive:
            continue
        kind, pattern = match[1], match[2].replace(DYNAMIC, '*')
        root = repository(cwd)
        protected = protected_branches(root, project_policy(root) if root else {})
        for each in (['branch', 'tag'] if DYNAMIC in kind else ['tag' if kind == 'tags' else 'branch']):
            check_ref(each, pattern, protected)


ANSI_ESCAPES = {'a': '\a', 'b': '\b', 'e': '\x1b', 'E': '\x1b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t', 'v': '\v',
                '\\': '\\', "'": "'", '"': '"', '?': '?'}


def ansi_c_quoted(command, start):
    """Decode the $'...' word starting at command[start]; returns (text, index after the closing quote)."""
    index, output = start + 2, []
    while index < len(command):
        tick()
        char = command[index]
        if char == "'":
            return ''.join(output), index + 1
        if char == '\\' and index + 1 < len(command):
            following = command[index + 1]
            digits = re.match(r'[0-7]{1,3}', command[index + 1:]) if following in '01234567' else None
            hexadecimal = re.match(r'x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}', command[index + 1:])
            if following in ANSI_ESCAPES:
                output.append(ANSI_ESCAPES[following])
                index += 2
            elif digits:
                output.append(chr(int(digits[0], 8) & 0xFF))
                index += 1 + len(digits[0])
            elif hexadecimal:
                try:
                    output.append(chr(int(hexadecimal[0][1:], 16)))
                except (ValueError, OverflowError):
                    output.append('?')
                index += 1 + len(hexadecimal[0])
            elif following == 'c' and index + 2 < len(command):
                output.append(chr(ord(command[index + 2]) & 0x1f))
                index += 3
            else:
                output.append(char + following)
                index += 2
            continue
        output.append(char)
        index += 1
    raise Unclassifiable('unterminated ANSI-C quote')


SEQUENCE = re.compile(r'(-?\d+)\.\.(-?\d+)(?:\.\.(-?\d+))?|([A-Za-z])\.\.([A-Za-z])(?:\.\.(-?\d+))?')


def brace_sequence(inner):
    """The words of a {x..y} or {x..y..step} sequence (integers or single letters), None when `inner` is not one.

    A numeric sequence of more than MAX_BRACE_WORDS words is one unresolved word: digits alone cannot spell a command."""
    match = SEQUENCE.fullmatch(inner)
    if not match:
        return None
    numeric = match[1] is not None
    if numeric and max(len(match[1]), len(match[2]), len(match[3] or '')) > MAX_SEQUENCE_DIGITS:
        return [DYNAMIC]  # Too long to count with: one unresolved word (int() itself refuses past 4300 digits).
    first, last = (int(match[1]), int(match[2])) if numeric else (ord(match[4]), ord(match[5]))
    step = abs(int(match[3] or match[6] or 0)) or 1
    count = abs(last - first) // step + 1
    if count > MAX_BRACE_WORDS:
        return [DYNAMIC]
    width = max(len(match[1].lstrip('-')), len(match[2].lstrip('-'))) if numeric and (
        match[1].lstrip('-')[:1] == '0' and len(match[1].lstrip('-')) > 1 or
        match[2].lstrip('-')[:1] == '0' and len(match[2].lstrip('-')) > 1) else 0
    direction = 1 if last >= first else -1
    values = [first + direction * step * number for number in range(count)]
    return [str(value).zfill(width) for value in values] if numeric else [chr(value) for value in values]


def expand_first_group(text):
    """The alternatives of the leftmost brace group of `text` (a list or a sequence), or None when it has none."""
    groups, stack = {}, []
    for index, char in enumerate(text):
        if char == OPEN_BRACE:
            stack.append([index, []])
        elif char == COMMA and stack:
            stack[-1][1].append(index)
        elif char == CLOSE_BRACE and stack:
            start, commas = stack.pop()
            groups[start] = (commas, index)
        tick()
    for start in sorted(groups):
        commas, close = groups[start]
        if commas:
            bounds = [start] + commas + [close]
            return [text[:start] + text[bounds[number] + 1:bounds[number + 1]] + text[close + 1:] for number in range(len(bounds) - 1)]
        words = brace_sequence(text[start + 1:close])
        if words is not None:
            return [text[:start] + word + text[close + 1:] for word in words]
    return None


def brace_expand(text):
    """Expand unquoted {a,b} lists (nested and repeated) and {x..y} sequences; more than MAX_BRACE_WORDS words fails closed."""
    pending, done = [text], []
    while pending:
        current = pending.pop()
        alternatives = expand_first_group(current)
        if alternatives is None:
            done.append(current)
        else:
            pending.extend(reversed(alternatives))
        if len(done) + len(pending) > MAX_BRACE_WORDS:
            fail('A brace expansion in this command produces more than ' + str(MAX_BRACE_WORDS) + ' words, which cannot be inspected.',
                 'Write the arguments out, or split the command.', 'policy-budget')
    return done


def body_expansions(body):
    """Command and backtick substitutions in an unquoted here-document body; the shell runs them."""
    found, index = [], 0
    while index < len(body):
        tick()
        if body[index] == '\\':
            index += 2
            continue
        try:
            if body.startswith('$(', index):
                end = substitution_end(body, index, '$(')
                found.append(body[index + 2:end])
                index = end + 1
                continue
            if body[index] == '`':
                end = backtick_end(body, index)
                found.append(body[index + 1:end])
                index = end + 1
                continue
        except Unclassifiable:
            break
        index += 1
    return found


def substitution_end(command, start, opener):
    """Index of the parenthesis that closes the substitution opened at `start`; nesting is followed without recursion."""
    saved, quote, depth, index = [], None, 1, start + len(opener)
    while index < len(command):
        tick()
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
            saved.append((quote, depth))
            quote, depth, index = None, 1, index + 2
            continue
        if quote is None:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if not depth:
                    if not saved:
                        return index
                    quote, depth = saved.pop()
        index += 1
    raise Unclassifiable('unterminated shell substitution')


def backtick_end(command, start):
    index = start + 1
    while index < len(command) and command[index] != '`':
        tick()
        index += 2 if command[index] == '\\' else 1
    if index >= len(command):
        raise Unclassifiable('unterminated backtick substitution')
    return index


def brace_pairs(command):
    """Index of each '{' -> index of the '}' that closes it, over the whole text."""
    pairs, stack = {}, []
    for index, char in enumerate(command):
        if char == '{':
            stack.append(index)
        elif char == '}' and stack:
            pairs[stack.pop()] = index
        tick()
    return pairs


def tokenize(command):
    """Retain operator identity; quoted semicolons/newlines stay literal words.

    Substitutions and parameter expansions become DYNAMIC in their word, $'...' words are decoded, unquoted
    brace lists are expanded, and substitution bodies are returned separately for their own inspection.
    A real here-document operator (not one inside a comment, quote or string) becomes a ('heredoc', ref)
    token and its body is read from the following lines instead of being parsed as commands.
    """
    tokens, embedded, word, pending = [], [], [], []
    quote, started, index, pairs = None, False, 0, None

    def flush():
        nonlocal word, started
        if started:
            text = ''.join(word)
            for item in brace_expand(text) if OPEN_BRACE in text else [text]:
                tokens.append(('word', item.replace(OPEN_BRACE, '{').replace(COMMA, ',').replace(CLOSE_BRACE, '}')))
        word, started = [], False
    while index < len(command):
        tick()
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
        if quote is None and command.startswith('$"', index):
            index += 1  # A locale string $"..." is an ordinary double-quoted string.
            continue
        if quote is None and command.startswith("$'", index):
            text, index = ansi_c_quoted(command, index)
            word.append(text)
            started = True
            continue
        if quote is None and command.startswith('<<', index) and not command.startswith('<<<', index):
            cursor = index + 2
            strip_tabs = command.startswith('-', cursor)
            cursor += strip_tabs
            while cursor < len(command) and command[cursor] in ' \t':
                cursor += 1
            marker, quoted = [], False
            while cursor < len(command):
                letter = command[cursor]
                if letter in '"\'':
                    end = command.find(letter, cursor + 1)
                    if end < 0:
                        raise Unclassifiable('unterminated here-document delimiter')
                    marker.append(command[cursor + 1:end])
                    quoted, cursor = True, end + 1
                elif letter == '\\' and cursor + 1 < len(command):
                    marker.append(command[cursor + 1])
                    quoted, cursor = True, cursor + 2
                elif letter in ' \t\n;|&()<>':
                    break
                else:
                    marker.append(letter)
                    cursor += 1
            if marker:
                if word and ''.join(word).isdigit():
                    word, started = [], False  # A file descriptor number before the operator.
                flush()
                reference = {'quoted': quoted, 'marker': ''.join(marker), 'strip_tabs': strip_tabs, 'body': ''}
                tokens.append(('heredoc', reference))
                pending.append(reference)
                index = cursor
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
            embedded.append((len(tokens), body))
            word.append(DYNAMIC)
            started, index = True, end + 1
            continue
        if quote != "'" and char == '$' and command.startswith('${', index):
            if pairs is None:
                pairs = brace_pairs(command)
            word.append(DYNAMIC)  # A parameter expansion, braces and all, cannot be resolved statically.
            started, index = True, pairs[index + 1] + 1 if index + 1 in pairs else index + 1
            continue
        if quote != "'" and char == '$':
            word.append(DYNAMIC)  # A parameter expansion cannot be resolved statically.
            started = True
            name = PARAMETER_NAME.match(command, index + 1)
            if name:
                index = name.end()  # $BRANCH is one dynamic word, not a dynamic word followed by the letters BRANCH.
                continue
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
            if char == '\n' and pending:
                position = index + 1
                for reference in pending:
                    lines = []
                    while position < len(command):
                        tick()
                        end = command.find('\n', position)
                        end = len(command) if end < 0 else end
                        line, position = command[position:end], min(end + 1, len(command))
                        if (line.lstrip('\t') if reference['strip_tabs'] else line).rstrip(' \t') == reference['marker']:
                            break
                        lines.append(line)
                    reference['body'] = '\n'.join(lines)
                pending = []
                index = position - 1
        elif quote is None and char in '{,}':
            started = True
            word.append({'{': OPEN_BRACE, ',': COMMA, '}': CLOSE_BRACE}[char])
        else:
            started = True
            word.append(char)
        index += 1
    if quote is not None:
        raise Unclassifiable('unterminated quote')
    flush()
    return tokens, embedded


def without_redirections(words):
    """Drop 2>&1, >file, > file, &>file, {fd}>file and similar words; they are not arguments."""
    output, index = [], 0
    while index < len(words):
        word = words[index]
        match = REDIRECTION.fullmatch(word)
        if not match:
            glued = re.search(r'[<>]', word)  # main>/dev/null is the argument main with a redirection.
            if glued and glued.start() > 0:
                output.append(word[:glued.start()])
                match = REDIRECTION.fullmatch(word[glued.start():])
            else:
                output.append(word)
        if match and not match[1]:
            index += 1  # The target is the following word.
        index += 1
    return output


def env_split_string(text):
    """The words env -S makes of its string: blanks separate, quotes group, backslash escapes are env's, ${NAME} is dynamic.

    An escape env does not define is an error to env, so it is one here (ValueError)."""
    words, current, started, quote, index = [], [], False, None, 0
    controls = {'n': '\n', 't': '\t', 'r': '\r', 'f': '\f', 'v': '\v', 'a': '\a'}
    while index < len(text):
        char = text[index]
        index += 1
        if quote == "'":
            if char == "'":
                quote = None
            elif char == '\\' and text[index:index + 1] in ("'", '\\'):
                current.append(text[index])
                index += 1
            else:
                current.append(char)
            continue
        if char == '\\':
            following = text[index:index + 1]
            index += 1
            if following == 'c':
                break  # \c ends the string.
            if following == '_' and quote is None:
                words.append(''.join(current)) if started else None
                current, started = [], False
            elif following == '_':
                current.append(' ')
            elif following in controls:
                current.append(controls[following])
                started = True
            elif following and following in '#$"\'\\' or following == ' ':
                current.append(following)
                started = True
            else:
                raise ValueError('invalid backslash sequence in an env -S string')
            continue
        if char == '$':
            if text[index:index + 1] != '{' or '}' not in text[index:]:
                raise ValueError('only ${NAME} is expanded in an env -S string')
            index = text.index('}', index) + 1
            current.append(DYNAMIC)
            started = True
        elif quote == '"':
            if char == '"':
                quote = None
            else:
                current.append(char)
        elif char in '"\'':
            quote, started = char, True
        elif char in ' \t\n\v\f\r':
            if started:
                words.append(''.join(current))
            current, started = [], False
        elif char == '#' and not started:
            break
        else:
            current.append(char)
            started = True
    if quote:
        raise ValueError('no terminating quote in an env -S string')
    if started:
        words.append(''.join(current))
    return words


def env_split(words):
    """Replace each env -S/--split-string option by the words of its string, where env puts them, until none is left."""
    index = 0
    while index < len(words):
        word = words[index]
        if word == '--' or len(word) < 2 or word[0] != '-':
            break
        text, rest, skip = None, None, 1
        if word.startswith('--'):
            name, equals, value = word.partition('=')
            if len(name) >= 3 and '--split-string'.startswith(name):
                text, skip = (value, 1) if equals else (words[index + 1] if index + 1 < len(words) else '', 2)
            elif not equals and name in ('--unset', '--chdir', '--argv0'):
                skip = 2
        else:
            for position in range(1, len(word)):
                letter = word[position]
                if letter in 'SuCaP':
                    attached = word[position + 1:]
                    if letter == 'S':
                        text, skip = (attached, 1) if attached else (words[index + 1] if index + 1 < len(words) else '', 2)
                        rest = word[:position] if position > 1 else None
                    else:
                        skip = 1 if attached else 2
                    break
        if text is not None:
            try:
                split = env_split_string(text)
            except ValueError:
                if POLICY_WORD.search(text) or policy_word_possible(text):
                    fail('This env -S string cannot be read, so the command it runs cannot be inspected.',
                         'Write the command out as separate words after env, without -S.', 'policy-error')
                split = []
            words = words[:index] + ([rest] if rest else []) + split + words[index + skip:]
            continue
        index += skip
    return words


def wrapper_rest(wrapper, words):
    """The words after a wrapper's own options and operands: the command it runs."""
    index, seen = 0, set()
    while index < len(words):
        tick()
        word = words[index]
        if word == '--':
            index += 1
            break
        if len(word) < 2 or word[0] != '-':
            break
        index += 1
        if word in wrapper.exact:
            index += 1
        elif word.startswith('--'):
            name, equals, _ = word.partition('=')
            known = wrapper.values | wrapper.flags
            options = {name} if name in known else {option for option in known if option.startswith(name)}
            if options and options <= wrapper.values and not equals:
                index += 1
            seen |= options
        else:
            for position in range(1, len(word)):
                seen.add(word[position])
                if word[position] in wrapper.short:
                    index += position + 1 == len(word)  # Nothing attached: the value is the next word.
                    break
    operands = 0 if seen & wrapper.operands_unless else wrapper.operands
    return words[min(index + operands, len(words)):]


def unwrap(words, assigned=None):
    """Strip shell keywords, assignments and common executable wrappers.

    Inline assignments (`VAR=value cmd`, `env VAR=value cmd`) are recorded in `assigned`."""
    while True:
        while words and (words[0] in SHELL_KEYWORDS or ASSIGNMENT.fullmatch(words[0]) or words[0] == 'function' or
                         len(words[0]) > 1 and words[0][0] == '='):
            if assigned is not None and ASSIGNMENT.fullmatch(words[0]):
                name, _, value = words[0].partition('=')
                assigned[name] = value
            if words[0] == 'function':
                words = words[2:]  # function NAME { ... } defines, then runs its body here.
            elif words[0][0] == '=' and words[0] != '=':
                words = [words[0][1:], *words[1:]]  # zsh: =git is the path of git.
                break
            else:
                words = words[1:]
        if not words or Path(words[0]).name not in WRAPPERS:
            return words
        wrapper, words = Path(words[0]).name, words[1:]
        if wrapper == 'command' and words[:1] in (['-v'], ['-V']):
            return []  # Shell lookup describes operands without executing them.
        if WRAPPERS[wrapper] is WRAPPERS['env']:  # env and genv
            words = env_split(words)
        words = wrapper_rest(WRAPPERS[wrapper], words)


PARAMETER_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-]')
ANSI_WORD = re.compile(r"\$'(?:[^'\\]|\\.)*'", re.S)


def policy_word_possible(command):
    """Could the shell turn this text into a command name the hook inspects? Deliberately generous: it only
    decides whether the tokenizer runs, so quote, escape and expansion characters are removed and $'...'
    words decoded before the search."""
    if POLICY_WORD.search(command):
        return True
    if "$'" in command:
        def decode(match):
            try:
                return ansi_c_quoted(match[0], 0)[0]
            except Unclassifiable:
                return match[0]
        command = ANSI_WORD.sub(decode, command)
    if POLICY_WORD.search(SPLITTING.sub('', command)):
        return True
    if '{' not in command:
        return False
    # A brace list or sequence can spell a command name (g{i,}t, g{i..i}t): try the expansions of each word, quoting ignored.
    for word in re.split(r'[\s;|&()<>]+', command):
        if '{' not in word or len(word) > MAX_SPELLED_WORD:
            continue  # A command name is short; a long brace word is data (minified JSON, a regular expression).
        try:
            variants = brace_expand(word.replace('{', OPEN_BRACE).replace(',', COMMA).replace('}', CLOSE_BRACE))
        except Blocked:
            return True  # Too many expansions to try: the tokenizer decides.
        if any(POLICY_WORD.search(SPLITTING.sub('', re.sub('[\ue000-\ue002]', '', variant))) for variant in variants):
            return True
    return False


def command_name(words):
    unwrapped = unwrap(without_redirections(words))
    return os.path.basename(unwrapped[0]) if unwrapped else ''


def heredoc_is_code(segments, position):
    """A here-document body is script text when its consumer, or a later stage of its pipeline, is a shell,
    eval, source, . or xargs; for every other consumer (cat, tee, git commit -F -, gh, ruby ...) it is text."""
    segment = segments[position]
    if command_name(segment['words']) in CODE_CONSUMERS or (segment['words'] and os.path.basename(segment['words'][0]) in CODE_CONSUMERS):
        return True
    while segment['op'] == '|' and position + 1 < len(segments):
        position += 1
        segment = segments[position]
        if command_name(segment['words']) in CODE_CONSUMERS:
            return True
    return False


def function_body_end(segments, header):
    """Index of the last segment of the function body that follows the header at `header`, or None when it cannot be found.

    The header is `NAME ( )` (the parentheses are their own segments), `function NAME` or `function NAME ( )`; the body
    is a `{ ... }` group or a `( ... )` subshell."""
    words, start, depth = segments[header]['words'], header + 1, 0
    inline = words[:1] == ['function'] and words[2:3] == ['{']  # The group opens in the header segment itself.
    if inline:
        depth = 1
    else:
        if segments[header]['op'] == '(' and start < len(segments) and not segments[start]['words'] and segments[start]['op'] == ')':
            start += 1
        if start >= len(segments):
            return None
    opening = segments[start]['words'][:1] == ['{'] if not inline else True
    subshell = not inline and not segments[start]['words'] and segments[start]['op'] == '('
    if not opening and not subshell:
        return None
    for position in range(start, len(segments)):
        segment = segments[position]
        if subshell:
            depth += (segment['op'] == '(') - (segment['op'] == ')')
            if not depth:
                return position
        else:
            depth += segment['words'][:1] == ['{']
            if segment['words'][:1] == ['}']:
                depth -= 1
                if not depth:
                    return position
    return None


def function_name(segments, position):
    """The name a segment defines as a function (`NAME ( )` or `function NAME`), or None."""
    words = segments[position]['words']
    if words[:1] == ['function'] and len(words) >= 2:
        return words[1]
    if (len(words) == 1 and segments[position]['op'] == '(' and position + 1 < len(segments) and
            not segments[position + 1]['words'] and segments[position + 1]['op'] == ')'):
        return words[0]
    return None


def dynamic_call(segments, skipped):
    """Could the command call a function by a name it does not spell? A command word that is a substitution or an expansion,
    or text a code consumer (eval, a shell, xargs ...) is given from one, outside the segments in `skipped`."""
    for index, segment in enumerate(segments):
        if index in skipped or not segment['words']:
            continue
        words = unwrap(without_redirections(segment['words']))
        if words and (DYNAMIC in words[0] or Path(words[0]).name in CODE_CONSUMERS | {'command', 'builtin'} and
                      any(DYNAMIC in word for word in words[1:])):
            return True
    return False


def inspect_command(command, cwd, depth=0, inherited=None):
    # Substitution bodies are part of the raw text, so no policy word anywhere
    # means nothing below can match. Quote, escape and expansion characters can split
    # a command name the shell still resolves, so the search runs on the text without them too.
    if not policy_word_possible(command):
        return
    if depth > MAX_NESTING:
        fail('This command nests shells, eval or substitutions more than ' + str(MAX_NESTING) + ' levels deep and names git, gh or vercel, '
             'so it cannot be inspected.', 'Write the command without the nesting, or split it into separate commands.', 'policy-error')
    check_budget()
    try:
        tokens, embedded = tokenize(command)
    except Unclassifiable:
        return
    segments, current, held, owner = [], [], [], {}
    for index, (kind, token) in enumerate(tokens):
        if kind == 'operator':
            if current or held or token in ('(', ')'):  # Parentheses are kept even when empty: they scope a cd.
                segments.append({'words': current, 'heredocs': held, 'op': token})
            current, held = [], []
        elif kind == 'heredoc':
            held.append(token)
        else:
            current.append(token)
            owner[index] = len(segments)
    if current or held:
        segments.append({'words': current, 'heredocs': held, 'op': ''})
    # A substitution runs where its word is: after the cd that precedes it, not at the start of the command.
    substitutions = {}
    for index, body in embedded:
        substitutions.setdefault(min(owner.get(index, len(segments) - 1), max(len(segments) - 1, 0)), []).append(body)
    state = {'cwd': cwd, 'previous': None, 'stack': []}
    scopes = []  # The shell state saved at each open parenthesis, restored at its close.
    position = 0
    while position < len(segments):
        check_budget()
        segment = segments[position]
        defined = function_name(segments, position)
        if defined is not None:
            # A function body runs when the function is called: a definition that nothing names again is inert, but only
            # when no command word of the command is dynamic (${X:-f}, $(echo f)) and the name is not spelled indirectly.
            spelled = re.compile(r'(?<![\w.-])' + re.escape(defined) + r'(?![\w.-])')
            names = max(len(spelled.findall(command)),
                        sum(len(spelled.findall(word)) for each in segments for word in each['words']) +
                        sum(len(spelled.findall(body)) for _, body in embedded))
            end = function_body_end(segments, position) if names <= 1 else None
            if end is not None and not dynamic_call(segments, set(range(position, end + 1))):
                position = end + 1
                continue
        for body in substitutions.get(position, ()):
            inspect_command(body, state['cwd'], depth + 1, inherited)
        inspect_segment(segments, position, state, depth, inherited)
        if segment['op'] == '(':
            scopes.append(dict(state, stack=list(state['stack'])))
        elif segment['op'] == ')' and scopes:
            state = scopes.pop()
        position += 1


def inspect_segment(segments, position, state, depth, inherited):
    segment, cwd = segments[position], state['cwd']
    previous = segments[position - 1]['op'] if position else ''
    for reference in segment['heredocs']:
        if heredoc_is_code(segments, position):
            inspect_command(reference['body'], cwd, depth + 1, inherited)
        elif not reference['quoted']:
            for inner in body_expansions(reference['body']):
                inspect_command(inner, cwd, depth + 1, inherited)
    assigned = {}
    words = unwrap(without_redirections(segment['words']), assigned)
    if not words:
        return
    name, args = Path(words[0]).name, words[1:]
    if name in LITERAL_TEXT:
        return
    if name in SHELLS or name in SHELL_RUNNERS:
        script = shell_script(args) if name in SHELLS else runner_script(args)
        if script is not None:
            inspect_command(script, cwd, depth + 1, inherited)
        elif name == 'flock' or name == 'runuser' and any(arg in ('-u', '--user') or arg.startswith('--user=') for arg in args):
            # flock [OPTIONS] FILE CMD and runuser -u USER [--] CMD run a command, not a string.
            inspect_command(shell_text(wrapper_rest(FLOCK if name == 'flock' else RUNUSER, args)), cwd, depth + 1, inherited)
        return
    if name == 'trap':
        operands = [arg for arg in args if arg != '--']
        if len(operands) >= 2 and operands[0] not in ('-l', '-p'):
            inspect_command(operands[0], cwd, depth + 1, inherited)  # trap 'CODE' SIGNAL ...: the shell runs CODE later
        return
    if name == 'parallel':
        command = []
        for word in wrapper_rest(PARALLEL, args):
            if word.startswith(':::'):
                break
            command.append(word)
        # parallel joins its words into one shell command line; {}, {.}, {1} ... stand for its input, which is not known here.
        inspect_command(re.sub(r'\{[^{}\s]*\}', '"$PARALLEL_INPUT"', ' '.join(command)), cwd, depth + 1, inherited)
        return
    if name == 'eval':
        inspect_command(' '.join(args), cwd, depth + 1, inherited)
        return
    if name in ('npx', 'pnpm', 'npm', 'yarn', 'bunx'):
        args = args[skip_options(args, NPX_VALUE_OPTIONS.__contains__):]
        if args[:1] in (['exec'], ['dlx']):
            args = args[1:]
            args = args[skip_options(args, NPX_VALUE_OPTIONS.__contains__):]
        package = Path(args[0]).name.split('@', 1)[0] if args else ''
        if package not in ('vercel', 'vc'):
            return
        name, args = package, args[1:]
    if name in ('cd', 'pushd', 'popd'):
        if previous in ('|', '|&') or segment['op'] in ('|', '|&', '&'):
            return  # A pipeline stage and a background job run in a subshell: the directory change is not kept.
        change_directory(name, args, state)
    elif name == 'git':
        git_command(args, cwd, depth, assigned, inherited)
    elif name in ('vercel', 'vc'):
        deployment(args)
    elif name == 'gh':
        github(args, cwd, depth)


def evaluate(event):
    if not isinstance(event, dict) or not isinstance(event.get('tool_name'), str) or not event['tool_name']:
        fail('The native event does not identify its tool.', 'Reinstall the matching native PreToolUse adapter.', 'malformed-event')
    if event['tool_name'] != 'Bash':
        return
    if event.get('hook_event_name') != 'PreToolUse' or not isinstance(event.get('tool_input'), dict):
        fail('Malformed guarded PreToolUse event.', 'Reinstall the matching native adapter and verify its stdin schema.', 'malformed-event')
    command, cwd = event['tool_input'].get('command'), event.get('cwd')
    if not isinstance(command, str) or not isinstance(cwd, str):
        fail('Guarded shell event requires command text and a cwd.', 'Verify the native adapter tool_input.command and cwd fields.', 'malformed-event')
    if not command.strip():
        return
    # A working directory that is gone leaves the repository unknown; the default protected names still apply.
    try:
        root = Path(cwd).resolve() if Path(cwd).is_dir() else None
    except (OSError, RuntimeError, ValueError):
        root = None
    global _DEADLINE, _FINAL_DEADLINE, BUDGET_SECONDS, _BUILTINS, _TICKS
    BUDGET_SECONDS, warning = budget_seconds()
    if warning:
        print('POLICY NOTE: ' + warning, file=sys.stderr)
    # One invocation owns its caches: a second call in the same process (a test, an embedding) starts clean.
    _GIT_CACHE.clear()
    _BUILTINS, _TICKS = None, 0
    started = time.monotonic()
    # The report of a block (and its telemetry) must fit inside the budget too, so the judging stops a little earlier.
    _FINAL_DEADLINE = started + BUDGET_SECONDS
    _DEADLINE = _FINAL_DEADLINE - min(1.0, BUDGET_SECONDS / 4)
    restore = arm_timer(BUDGET_SECONDS + 0.1)  # A backstop just behind the loop checks, not a second deadline.
    try:
        inspect_command(command, root)
    finally:
        if restore:
            restore()
        _GIT_CACHE.clear()


def arm_timer(seconds):
    """A hard wall-clock bound for work the loops cannot check (a long regular-expression match, a slow subprocess).

    Returns a function that puts back the SIGALRM handler and the timer that were there before, or None when this platform
    or thread has no SIGALRM (the loop checks still apply)."""
    try:
        import signal

        def expired(signum, frame):
            raise BudgetExceeded()
        before = signal.signal(signal.SIGALRM, expired)
        armed = time.monotonic()
        previous = signal.setitimer(signal.ITIMER_REAL, seconds)

        def restore():
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, before if before is not None else signal.SIG_DFL)
            if previous[0] > 0:  # A timer of the embedding process keeps running for what was left of it.
                signal.setitimer(signal.ITIMER_REAL, max(previous[0] - (time.monotonic() - armed), 0.001), previous[1])
        return restore
    except (ImportError, AttributeError, ValueError, OSError):
        return None


def telemetry(event, harness, decision, rule):
    from datetime import datetime, timezone
    try:
        cwd = event.get('cwd', '')
        root = repository(cwd) if Path(cwd).is_dir() else None
        if root is None:
            return  # Outside a repository there is no ignored evidence directory to write.
        if not (root / '.rpi').is_dir():
            return  # No installed state directory: do not create one.
        directory = root / '.rpi/local'
        if any(path.is_symlink() for path in (root, root / '.rpi', directory, directory / 'contract-events.jsonl')):
            return
        directory.mkdir(parents=True, exist_ok=True)
        value = {'ts': datetime.now(timezone.utc).isoformat(), 'session_id': event.get('session_id', ''),
                 'hook': 'rpi-policy-' + harness, 'decision': decision, 'rule': rule, 'file': ''}
        with (directory / 'contract-events.jsonl').open('a') as stream:
            stream.write(json.dumps(value) + '\n')
    except (OSError, TypeError, ValueError):
        print('TELEMETRY UNAVAILABLE: policy evaluation still completed.', file=sys.stderr)


def names_a_policy_word(event):
    """Does the command of a Bash event name git, gh or vercel in any spelling the shell resolves to one?"""
    try:
        command = event['tool_input']['command']
        return event['tool_name'] == 'Bash' and policy_word_possible(command)
    except Exception:
        return True


def budget_block(event, harness, error):
    if error.cause == 'git':
        return blocked(event, harness, 'git did not answer within the hook time budget of ' + str(BUDGET_SECONDS).rstrip('0').rstrip('.') +
                       ' seconds, so the repository state could not be read and the command cannot be shown to avoid a protected-branch rewrite.',
                       'Check that git responds here (git rev-parse --show-toplevel; a hung network file system or a stuck git process is the usual cause), '
                       'then run the command again.', 'policy-budget')
    return blocked(event, harness, 'This command is too large to inspect within the hook time budget of ' +
                   str(BUDGET_SECONDS).rstrip('0').rstrip('.') + ' seconds, so it cannot be shown to avoid a protected-branch rewrite.',
                   'Split it into smaller commands.', 'policy-budget')


def main(argv):
    for stream in (sys.stderr, sys.stdout):
        try:
            stream.reconfigure(errors='backslashreplace')  # A non-ASCII command or branch name must not break the message.
        except (AttributeError, ValueError):
            pass
    if len(argv) != 2 or argv[0] != '--harness' or argv[1] not in ('claude', 'codex'):
        print('BLOCKED / WHY: unsupported hook adapter arguments. / FIX: invoke rpi-policy.py --harness claude or --harness codex.', file=sys.stderr)
        return 2
    harness, event = argv[1], {}
    try:
        try:
            event = read_json(sys.stdin.buffer.read().decode('utf-8', 'surrogateescape'))
        except (ValueError, OSError, AttributeError):
            fail('Native hook input must be one JSON object.', 'Reinstall the matching native PreToolUse adapter.', 'malformed-event')
        evaluate(event)
        return 0
    except Blocked as error:
        return blocked(event, harness, str(error), error.fix, error.rule)
    except BudgetExceeded as error:
        return budget_block(event, harness, error)
    except Exception as error:
        return failed(event, harness, error)


def failed(event, harness, error):
    """An unexpected error: a command that names git, gh or vercel is blocked, any other passes. Every way out of here is closed."""
    global _DEADLINE
    _DEADLINE = time.monotonic() + 2.0  # Deciding whether the command names git must not be cut short by the spent budget.
    try:
        named = names_a_policy_word(event)
    except BudgetExceeded:
        named = True  # Could not even tell: it cannot be shown to be harmless.
    if not named:
        print('POLICY UNAVAILABLE: evaluation failed (' + type(error).__name__ + '); the command passes to native permissions.', file=sys.stderr)
        return 0
    # The command names git, gh or vercel and could not be read: it cannot be shown to be harmless, so it is not passed.
    return blocked(event, harness, 'The policy could not evaluate this command (' + type(error).__name__ +
                   ') and it names git, gh or vercel, so it cannot be shown to avoid a protected-branch rewrite.',
                   'Split the command into smaller commands, or have the owner run the exact command; then report the command '
                   'shape to cc-rpi and run python3 .rpi/scripts/rpi-distribution.py check --target . to rule out a damaged installation.',
                   'policy-error')


def blocked(event, harness, reason, fix, rule):
    global _DEADLINE
    print('BLOCKED / WHY: ' + reason + ' / FIX: ' + fix, file=sys.stderr, flush=True)
    # Recording the block asks git for the repository root: it gets what is left of the budget, never more.
    left = (_FINAL_DEADLINE - time.monotonic()) if _FINAL_DEADLINE is not None else 1.0
    if isinstance(event, dict) and isinstance(event.get('cwd'), str):
        try:
            if left < 0.05:
                raise BudgetExceeded('size')
            _DEADLINE = time.monotonic() + left
            telemetry(event, harness, 'block', rule)
        except BudgetExceeded:
            print('TELEMETRY UNAVAILABLE: the block was reported but not recorded.', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
