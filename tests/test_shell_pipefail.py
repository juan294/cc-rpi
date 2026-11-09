"""Shell scripts that run under pipefail must not feed an early-exit reader from a producer.

`printf '%s\n' "$LIST" | grep -qxF x` under `set -o pipefail` reports "absent" when grep -q exits on its first match while
printf is still writing a list larger than the pipe buffer: printf gets SIGPIPE and the pipeline fails. The scripts use a
shell-only `case` test instead, and these tests pin both the failure and the repair deterministically.

The static guard reads every logical command (a trailing backslash or pipe continues it), splits it into words with shell
quoting rules and looks at the command that follows each pipe, whatever its spelling: grep with -q, --quiet, --silent,
-m, --max-count or -l in any position, head, sed with a q command, read, awk with exit, an inline python or perl program
that does not read all of its input, cmp or diff reading standard input, and sort -c.
"""
from pathlib import Path
import re
import shlex
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ('templates/scripts/check-tree-drift.sh', 'templates/scripts/verify-version.sh')
# A list well beyond any pipe buffer whose FIRST line is the entry looked up.
BIG = 'first-entry\\n' + 'filler-line-padding-to-fill-the-pipe-buffer-000000\\n' * 2500

TERMINATORS = {'|', '||', '&&', ';', ';;', '&', ')', '|&', '(', '\n'}
WRAPPERS = {'{', '(', '!', 'env', 'command', 'builtin', 'exec', 'time', 'nohup'}
GREP_NAMES = {'grep', 'egrep', 'fgrep', 'rg', 'ugrep', 'ggrep'}
GREP_LONG = {'--quiet', '--silent', '--files-with-matches', '--max-count'}
GREP_SHORT = re.compile(r'^-[A-Za-z0-9]*[qlm][A-Za-z0-9]*$')
SED_QUIT = re.compile(r'(?:^|[;{}\s/$!0-9])[qQ][0-9]*\s*(?:$|[;}])')
READS_ALL = re.compile(r'sys\.stdin\.read\(\)|json\.loads?\(sys\.stdin|sys\.stdin\.readlines\(|for \w+ in sys\.stdin|\.read\(\)')


def run_bash(program):
    return subprocess.run(['bash', '-c', program], capture_output=True, text=True, timeout=120)


def logical_commands(text):
    """Yield (first physical line number, command text) with continuations joined and heredoc bodies skipped."""
    lines = text.splitlines()
    index, produced = 0, []
    while index < len(lines):
        number, command = index + 1, lines[index]
        index += 1
        if command.lstrip().startswith('#'):
            continue
        while index < len(lines):
            stripped = command.rstrip()
            following = lines[index].lstrip()
            if stripped.endswith('\\'):
                command = stripped[:-1] + ' ' + lines[index]
            elif (stripped.endswith('|') and not stripped.endswith('||')) or following.startswith('|') and not following.startswith('||'):
                command = stripped + ' ' + lines[index]
            else:
                try:
                    tokenize(command)
                    break
                except ValueError:  # An open quote: a multi-line awk or sed program continues on the next line.
                    command = command + '\n' + lines[index]
                    index += 1
                    continue
            index += 1
        produced.append((number, command))
        for tag in re.findall(r"<<-?\s*['\"]?([A-Za-z_]+)['\"]?", command):
            while index < len(lines) and lines[index].strip() != tag:
                index += 1
            index += 1
    return produced


def tokenize(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.commenters = ''
    lexer.whitespace_split = False
    return list(lexer)


def words(command):
    try:
        return tokenize(command)
    except ValueError:
        return command.split()


def early_exit_readers(command):
    """Names of the early-exit readers that sit after a pipe in this command."""
    tokens, found = words(command), []
    for position, token in enumerate(tokens):
        if token not in ('|', '|&'):
            continue
        stage = []
        for follower in tokens[position + 1:]:
            if follower in TERMINATORS:
                break
            stage.append(follower)
        while stage and (stage[0] in WRAPPERS or re.match(r'^[A-Za-z_]\w*=', stage[0])):
            stage = stage[1:]
        if stage and stage[0] == 'env':
            stage = [word for word in stage[1:] if not word.startswith('-') and '=' not in word]
        if not stage:
            continue
        name, arguments = Path(stage[0]).name, stage[1:]
        if name in ('head', 'read'):
            found.append(name)
        elif name in GREP_NAMES and any(a in GREP_LONG or a.startswith('--max-count=') or GREP_SHORT.match(a) for a in arguments):
            found.append(name + ' quiet/first-match option')
        elif name == 'sed' and any(SED_QUIT.search(a) for a in arguments if not a.startswith('-') or a.startswith('-e')):
            found.append('sed q')
        elif name in ('awk', 'gawk', 'mawk', 'nawk') and any(re.search(r'\bexit\b', re.sub(r'END\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', a)) for a in arguments):
            found.append('awk exit')
        elif re.match(r'^(python[0-9.]*|perl|ruby|node)$', name) and any(a in ('-c', '-e') for a in arguments) \
                and not READS_ALL.search(' '.join(arguments)):
            found.append(name + ' inline program that may stop reading')
        elif name == 'cmp' and '-' in arguments:
            found.append('cmp on standard input')
        elif name == 'diff' and '-' in arguments and any(a in ('-q', '--brief') for a in arguments):
            found.append('diff -q on standard input')
        elif name == 'sort' and any(a in ('-c', '-C', '--check') for a in arguments):
            found.append('sort -c')
    return found


class PipefailMembershipTests(unittest.TestCase):
    def helper(self, script):
        text = (ROOT / script).read_text()
        match = re.search(r'^list_has\(\) \{.*\}$', text, re.M)
        self.assertIsNotNone(match, script + ' must define the one-line list_has helper')
        return match.group(0)

    def test_the_old_pipeline_form_really_loses_a_present_entry(self):
        # Deterministic: 300 KB cannot sit in the pipe, so grep -q exits before printf has finished writing.
        program = ("set -euo pipefail; LIST=$(printf '" + BIG + "'); misses=0\n"
                   "for i in $(seq 1 50); do printf '%s\\n' \"$LIST\" | grep -qxF first-entry || misses=$((misses+1)); done\n"
                   "echo \"$misses\"")
        self.assertGreater(int(run_bash(program).stdout.strip()), 0, 'the pattern this suite forbids must demonstrably fail')

    def test_list_has_never_misses_a_present_entry_under_pipefail(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                program = ("set -euo pipefail\n" + self.helper(script) + "\nLIST=$(printf '" + BIG + "'); misses=0; false_hits=0\n"
                           "for i in $(seq 1 500); do list_has first-entry \"$LIST\" || misses=$((misses+1)); "
                           "list_has absent-entry \"$LIST\" && false_hits=$((false_hits+1)); done\n"
                           "echo \"$misses $false_hits\"")
                result = run_bash(program)
                self.assertEqual(result.stdout.strip(), '0 0', result.stderr)

    def test_list_has_matches_whole_lines_literally(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                program = ("set -euo pipefail\n" + self.helper(script) + "\nLIST=$(printf 'a.b\\nfoo/bar\\n-x\\n')\n"
                           "list_has 'a.b' \"$LIST\" && list_has 'foo/bar' \"$LIST\" && list_has -x \"$LIST\" "
                           "&& ! list_has 'a' \"$LIST\" && ! list_has 'a.' \"$LIST\" && ! list_has 'foo' \"$LIST\" && echo ok")
                self.assertEqual(run_bash(program).stdout.strip(), 'ok')

    def test_no_script_under_pipefail_feeds_an_early_exit_reader_from_a_producer(self):
        offenders = []
        for path in sorted(list((ROOT / 'templates').rglob('*.sh')) + list((ROOT / 'scripts').rglob('*.sh'))):
            if path.is_symlink() or 'pipefail' not in path.read_text():
                continue
            for number, command in logical_commands(path.read_text()):
                for reader in early_exit_readers(command):
                    offenders.append('%s:%d: %s [%s]' % (path.relative_to(ROOT), number, command.strip()[:100], reader))
        self.assertEqual(offenders, [], 'an early-exit reader after a pipe races its producer under pipefail; use a case test or a file argument')

    def test_the_guard_flags_every_spelling_that_really_fails_under_pipefail(self):
        spellings = {
            'grep -qxF': "printf '%s\\n' \"$L\" | grep -qxF x",
            'grep --quiet': "printf '%s\\n' \"$L\" | grep --quiet x",
            'grep --silent': "printf '%s\\n' \"$L\" | grep --silent x",
            'grep -e PAT -q': "printf '%s\\n' \"$L\" | grep -e x -q",
            'grep -F PAT -q': "printf '%s\\n' \"$L\" | grep -F x -q",
            'grep -m1': "printf '%s\\n' \"$L\" | grep -m1 x",
            'grep --max-count=1': "printf '%s\\n' \"$L\" | grep --max-count=1 x",
            'grep -l': "printf '%s\\n' \"$L\" | grep -l x",
            "sed '/x/q'": "printf '%s\\n' \"$L\" | sed '/x/q'",
            "sed 1q": "printf '%s\\n' \"$L\" | sed 1q",
            "sed -n '/x/{p;q}'": "printf '%s\\n' \"$L\" | sed -n '/x/{p;q}'",
            'sed -e q': "printf '%s\\n' \"$L\" | sed -e q",
            'read': "printf '%s\\n' \"$L\" | { read -r first; [ \"$first\" = x ]; }",
            'read bare': "printf '%s\\n' \"$L\" | read -r first",
            'head': "printf '%s\\n' \"$L\" | head -1",
            'python3 -c': "printf '%s\\n' \"$L\" | python3 -c 'import sys; sys.stdin.readline()'",
            'perl -e': "printf '%s\\n' \"$L\" | perl -e '<STDIN>; exit'",
            'cmp -s -': "printf '%s\\n' \"$L\" | cmp -s - file",
            'awk exit': "printf '%s\\n' \"$L\" | awk 'NR==1{print;exit}'",
            'awk exit before END': "printf '%s\\n' \"$L\" | awk 'NR==1{exit} END{print 1}'",
            'sort -c': "printf '%s\\n' \"$L\" | sort -c",
            'inside $()': 'x=$(cmd | tr a b | head -n 1)',
            'after env': "printf '%s\\n' \"$L\" | env LC_ALL=C grep -q x",
            'absolute path': "printf '%s\\n' \"$L\" | /usr/bin/grep -q x",
            'multi-line trailing pipe': "printf '%s\\n' \"$L\" |\n  head -1",
            'multi-line leading pipe': "printf '%s\\n' \"$L\"\n  | grep --quiet x",
            'multi-line backslash': "printf '%s\\n' \"$L\" \\\n  | grep -q x",
            'third stage': "cat f | tr a b | head -3",
        }
        for label, source in spellings.items():
            with self.subTest(label):
                flagged = [reader for _, command in logical_commands(source) for reader in early_exit_readers(command)]
                self.assertTrue(flagged, label + ' must be flagged')

    def test_the_guard_leaves_readers_that_consume_all_their_input_alone(self):
        harmless = [
            "printf '%s\\n' \"$L\" | sed -n '1p'",
            "printf '%s\\n' \"$L\" | sed 's/^ *//; s/ *$//'",
            "printf '%s\\n' \"$L\" | sed 's/ q$//'",
            "printf '%s\\n' \"$L\" | sed 's/a/q/'",
            "printf '%s\\n' \"$L\" | grep -c .",
            "printf '%s\\n' \"$L\" | grep -v x",
            "printf '%s\\n' \"$L\" | grep -oE '[0-9]+'",
            "printf '%s\\n' \"$L\" | grep -iE 'a|b'",
            "printf '%s\\n' \"$L\" | awk -F'|' '{print $2}'",
            "printf '%s\\n' \"$L\" | awk '{print $1}'",
            "printf '%s\\n' \"$L\" | awk '{ if ($1 == 2) bad = 1 } END { if (NR == 0 || bad) exit 1 }'",
            "printf '%s\\n' \"$L\" | sort -u | tr '+' '\\n'",
            "printf '%s\\n' \"$L\" | wc -l | tr -d ' '",
            "python3 -c 'print(1)' | wc -l",
            "printf '%s\\n' \"$L\" | python3 -c 'import sys; print(sys.stdin.read())'",
            "grep -q x file",
            "[[ $a == b || $c == d ]]",
            "x=$(cmd) || true",
            "cat <<'TXT'\nfoo | head -1\nTXT",
        ]
        for source in harmless:
            with self.subTest(source):
                flagged = [reader for _, command in logical_commands(source) for reader in early_exit_readers(command)]
                self.assertEqual(flagged, [])

    def test_the_forms_the_guard_forbids_really_do_fail_ten_out_of_ten_with_a_large_producer(self):
        # The reproduction behind the guard: each of these loses a present entry under pipefail with a 150 KB producer.
        forms = ["grep --quiet first-entry", "grep -F first-entry -q", "grep -e first-entry -q",
                 "sed '/first-entry/q' | grep -q first-entry", "{ read -r first; [ \"$first\" = first-entry ]; }"]
        for form in forms:
            with self.subTest(form):
                program = ("set -o pipefail; BIG=$(printf 'first-entry\\n'; for i in $(seq 1 3000); do echo "
                           "filler-line-padding-to-fill-the-pipe-buffer-000000; done); misses=0\n"
                           "for i in 1 2 3 4 5 6 7 8 9 10; do printf '%s\\n' \"$BIG\" | " + form + " >/dev/null 2>&1 || misses=$((misses+1)); done\n"
                           "echo $misses")
                self.assertGreater(int(run_bash(program).stdout.strip()), 0, form)

    def test_the_documented_enable_command_has_no_producer_into_grep_q(self):
        lifecycle = (ROOT / 'templates/scripts/rpi-lifecycle.py').read_text()
        block = lifecycle[lifecycle.index("PRE_PUSH_ENABLE = r'''"):lifecycle.index("'''", lifecycle.index("PRE_PUSH_ENABLE = r'''") + 25)]
        self.assertNotRegex(block, r'\|\s*grep\b[^\n]*\s-[A-Za-z]*q')


if __name__ == '__main__':
    unittest.main()
