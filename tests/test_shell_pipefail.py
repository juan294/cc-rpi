"""Shell scripts that run under pipefail must not feed an early-exit reader from a producer.

`printf '%s\n' "$LIST" | grep -qxF x` under `set -o pipefail` reports "absent" when grep -q exits on its first match while
printf is still writing a list larger than the pipe buffer: printf gets SIGPIPE and the pipeline fails. The scripts use a
here-string instead, and these tests pin both the failure and the repair deterministically.
"""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ('templates/scripts/check-tree-drift.sh', 'templates/scripts/verify-version.sh')
# A list well beyond any pipe buffer whose FIRST line is the entry looked up.
BIG = 'first-entry\\n' + 'filler-line-padding-to-fill-the-pipe-buffer-000000\\n' * 2500


def run_bash(program):
    return subprocess.run(['bash', '-c', program], capture_output=True, text=True, timeout=120)


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
        reader = re.compile(r'(?<!\|)\|(?!\|)\s*(?:grep\s+(?:-[A-Za-z]+\s+)*(?:-[A-Za-z]*q[A-Za-z]*|-m\d*)(?=\s)|head\b|'
                            r'sed\s+(?:-n\s+)?[\'"]?\d*q|awk\b[^|\n]*\bexit\b)')
        for path in sorted(list((ROOT / 'templates').rglob('*.sh')) + list((ROOT / 'scripts').rglob('*.sh'))):
            if path.is_symlink() or 'pipefail' not in path.read_text():
                continue
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if reader.search(line) and not line.lstrip().startswith('#'):
                    offenders.append('%s:%d: %s' % (path.relative_to(ROOT), number, line.strip()[:110]))
        self.assertEqual(offenders, [], 'an early-exit reader after a pipe races its producer under pipefail; use a here-string or a file argument')

    def test_the_documented_enable_command_has_no_producer_into_grep_q(self):
        lifecycle = (ROOT / 'templates/scripts/rpi-lifecycle.py').read_text()
        block = lifecycle[lifecycle.index("PRE_PUSH_ENABLE = r'''"):lifecycle.index("'''", lifecycle.index("PRE_PUSH_ENABLE = r'''") + 25)]
        self.assertNotRegex(block, r'\|\s*grep\b[^\n]*\s-[A-Za-z]*q')


if __name__ == '__main__':
    unittest.main()
