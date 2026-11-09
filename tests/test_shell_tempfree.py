"""The invariant scripts must not depend on a writable temporary directory.

bash 3.2 (the macOS /bin/bash) writes every here-string and here-document to a temporary file. Where no temporary
directory is writable the redirection fails with "cannot create temp file for here document"; in a `while ... done <<<`
loop, a `list_has` test or a `read <<<` that failure used to be swallowed, so a check was skipped and the script still
printed PASS or raised a false BLOCKED. These tests pin the repair twice: statically (no such construct is left in the
scripts) and at run time (on macOS, inside a sandbox where nothing can be written, the scripts still reach the right
verdict).
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INVARIANT = ('templates/scripts/check-tree-drift.sh', 'templates/scripts/verify-version.sh',
             'templates/scripts/verify-counts.sh')
TEMP_FREE = INVARIANT + ('templates/scripts/cc-rpi-update-agent.sh', 'templates/scripts/morning-triage.sh',
                         'templates/scripts/verify-skills.sh', 'templates/hooks/guard-bash.sh',
                         'templates/hooks/verify-edit.sh')
# A here-document (<<WORD, <<'WORD', <<-WORD) or a here-string (<<<); never the arithmetic shift.
TEMP_FILE_REDIRECTION = re.compile(r'<<<|<<-?\s*[\\\'"A-Za-z_]')
SANDBOX = shutil.which('sandbox-exec')


class NoTemporaryFileTests(unittest.TestCase):
    def test_no_script_feeds_a_loop_or_command_through_a_here_string_or_here_document(self):
        offenders = []
        for relative in TEMP_FREE:
            for number, line in enumerate((ROOT / relative).read_text().splitlines(), 1):
                if not line.lstrip().startswith('#') and TEMP_FILE_REDIRECTION.search(line):
                    offenders.append('%s:%d: %s' % (relative, number, line.strip()[:100]))
        self.assertEqual(offenders, [], 'bash 3.2 writes these to a temporary file, which may not be writable')

    def test_no_script_asks_the_system_for_a_temporary_file(self):
        offenders = [relative for relative in TEMP_FREE if re.search(r'\bmktemp\b|\$\{?TMPDIR', re.sub(r'(?m)^\s*#.*$', '', (ROOT / relative).read_text()))]
        self.assertEqual(offenders, [], 'keep intermediate output in variables or in an owned run directory')

    def test_a_missing_or_read_only_temp_directory_changes_no_verdict(self):
        # bash 3.2 falls back to /tmp when TMPDIR is unusable, so this alone cannot reproduce the failure
        # (the sandboxed tests below do); it guards the common misconfiguration.
        with tempfile.TemporaryDirectory(prefix='rpi-readonly-tmp-') as directory:
            readonly = Path(directory) / 'ro'
            readonly.mkdir()
            readonly.chmod(0o555)
            try:
                for tmpdir in (str(readonly), str(Path(directory) / 'does-not-exist')):
                    for relative in INVARIANT:
                        with self.subTest(script=relative, tmpdir=tmpdir):
                            result = subprocess.run(['bash', str(ROOT / relative)], cwd=ROOT, capture_output=True, text=True, timeout=300,
                                                    env={**os.environ, 'TMPDIR': tmpdir, 'PATH': self.path()})
                            self.assertEqual(result.returncode, 0, result.stdout[-400:] + result.stderr)
                            self.assertNotIn('temp file', result.stderr)
            finally:
                readonly.chmod(0o755)

    @staticmethod
    def path():
        return str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH']


@unittest.skipUnless(SANDBOX and sys.platform == 'darwin', 'sandbox-exec (macOS) is needed to make every temporary location unwritable')
class UnwritableTemporaryLocationTests(unittest.TestCase):
    """Run the scripts where bash 3.2 cannot create any temporary file, against a throwaway copy of the repository."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = Path(tempfile.mkdtemp(prefix='rpi-tempfree-')).resolve()
        listing = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout
        for raw in filter(None, listing.split(b'\0')):
            name = Path(os.fsdecode(raw))
            source, target = ROOT / name, cls.fixture / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                target.symlink_to(os.readlink(source))
            elif source.is_file():
                shutil.copy2(source, target)
        subprocess.run(['git', 'init', '-q'], cwd=cls.fixture, check=True)
        subprocess.run(['git', 'add', '-A'], cwd=cls.fixture, check=True)
        cls.profile = cls.fixture.parent / (cls.fixture.name + '.sb')
        denied = ''.join('(subpath "%s")' % path for path in
                         ('/private/tmp', '/private/var/tmp', '/private/var/folders', str(cls.fixture), str(cls.fixture.parent)))
        cls.profile.write_text('(version 1)\n(allow default)\n(deny file-write* %s)\n' % denied)
        canary = cls.sandboxed(['/bin/bash', '-c', 'cat <<< canary'], cwd=cls.fixture)
        cls.canary_denied = canary.returncode != 0 and 'cannot create temp file' in canary.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.fixture, ignore_errors=True)
        cls.profile.unlink(missing_ok=True)

    @classmethod
    def sandboxed(cls, command, cwd):
        return subprocess.run(['sandbox-exec', '-f', str(cls.profile)] + command, cwd=cwd, capture_output=True, text=True, timeout=300,
                              env={**os.environ, 'PATH': NoTemporaryFileTests.path(), 'PYTHONDONTWRITEBYTECODE': '1'})

    def setUp(self):
        if not self.canary_denied:
            self.skipTest('the sandbox did not stop bash 3.2 from creating a here-document file, so it cannot prove anything here')
        # The fixture is this suite's own throwaway repository: restore the staged tree before every case.
        subprocess.run(['git', 'checkout', '-q', '--', '.'], cwd=self.fixture, check=True)
        subprocess.run(['git', 'clean', '-fdxq'], cwd=self.fixture, check=True)

    def edit(self, relative, new):
        path = self.fixture / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new)

    def run_script(self, name):
        return self.sandboxed(['/bin/bash', 'templates/scripts/%s.sh' % name], cwd=self.fixture)

    def test_a_clean_tree_passes_without_a_single_complaint_about_temp_files(self):
        for name in ('check-tree-drift', 'verify-version', 'verify-counts'):
            with self.subTest(script=name):
                result = self.run_script(name)
                self.assertEqual(result.returncode, 0, result.stdout[-500:] + result.stderr)
                self.assertNotIn('temp file', result.stdout + result.stderr)
                self.assertIn('PASS', result.stdout)

    def test_verify_version_still_blocks_two_unreleased_ledger_versions(self):
        # The old loop `done <<< "$LEDGER_VERSIONS"` failed to start, PENDING stayed empty and the script printed PASS.
        ledger = self.fixture / '.claude/rules/contributing.md'
        text = ledger.read_text()
        self.assertIn('### Retirement Ledger', text)
        injected = text.replace('### Retirement Ledger', '### Retirement Ledger\n\n| 901 | v9.8.7 | Merged | wb2 fixture |\n| 902 | v9.8.8 | Merged | wb2 fixture |', 1)
        self.edit('.claude/rules/contributing.md', injected)
        result = self.run_script('verify-version')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('more than one unreleased version', result.stdout)
        self.assertNotIn('temp file', result.stderr)

    def test_verify_version_names_the_one_pending_version_in_its_note(self):
        ledger = self.fixture / '.claude/rules/contributing.md'
        text = ledger.read_text()
        injected = text.replace('### Retirement Ledger', '### Retirement Ledger\n\n| 901 | v9.8.7 | Merged | wb2 fixture |', 1)
        self.edit('.claude/rules/contributing.md', injected)
        result = self.run_script('verify-version')
        self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)
        self.assertNotIn('temp file', result.stderr)
        self.assertTrue('9.8.7' in result.stdout, result.stdout)

    def test_check_tree_drift_still_blocks_each_kind_of_drift(self):
        self.edit('templates/scripts/wb2-unrecorded.sh', '#!/bin/sh\n')
        self.edit('.claude/scripts/wb2-unrecorded.sh', '#!/bin/sh\n')
        result = self.run_script('check-tree-drift')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('wb2-unrecorded.sh exists in both templates/ and .claude/', result.stdout)
        self.assertNotIn('temp file', result.stderr)

    def test_check_tree_drift_blocks_a_linked_file_replaced_by_a_copy(self):
        link = self.fixture / '.claude/scripts/verify-counts.sh'
        link.unlink()
        shutil.copy2(self.fixture / 'templates/scripts/verify-counts.sh', link)
        result = self.run_script('check-tree-drift')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('is listed as linked but is a real file', result.stdout)

    def test_verify_counts_still_blocks_a_stale_count(self):
        guide = self.fixture / 'GUIDE.md'
        text = guide.read_text()
        match = re.search(r'(\d+) documented errors', text)
        self.assertIsNotNone(match)
        self.edit('GUIDE.md', text.replace(match.group(0), '%d documented errors' % (int(match.group(1)) + 5), 1))
        result = self.run_script('verify-counts')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Error count (Where to Go Deeper)', result.stdout)


if __name__ == '__main__':
    unittest.main()
