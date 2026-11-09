"""check-tree-drift.sh must block every kind of drift between templates/ and .claude/ and never report a false green.

Each case runs the real script against a throwaway copy of the repository (templates/, .claude/, generated/ and the
manifest) after one deliberate change. Names with a line break, a leading dash, glob characters or quotes, and a manifest
with CRLF line ends, are inputs the script once misread: a name with a line break was cut in two and skipped (rc 0 with
an unrecorded shared file), a name starting with a dash made readlink print its usage text (rc 1), and a CRLF manifest was
reported as listing no files.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = 'templates/scripts/check-tree-drift.sh'


class DriftScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Path(tempfile.mkdtemp(prefix='rpi-drift-')).resolve()
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

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.fixture, ignore_errors=True)

    def setUp(self):
        subprocess.run(['git', 'checkout', '-q', '--', '.'], cwd=self.fixture, check=True)
        subprocess.run(['git', 'clean', '-fdxq'], cwd=self.fixture, check=True)

    def run_script(self):
        env = {**os.environ, 'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'], 'PYTHONDONTWRITEBYTECODE': '1'}
        return subprocess.run(['/bin/bash', SCRIPT], cwd=self.fixture, env=env, capture_output=True, text=True, timeout=300)

    def expect(self, code, *fragments):
        result = self.run_script()
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, code, output[-1500:])
        for fragment in fragments:
            self.assertIn(fragment, output)
        return output

    def share(self, name, *, symlink=True):
        """A file present in templates/scripts and .claude/scripts under the same name."""
        (self.fixture / 'templates/scripts' / name).write_text('x\n')
        link = self.fixture / '.claude/scripts' / name
        if symlink:
            link.symlink_to('../../templates/scripts/' + name)
        else:
            link.write_text('x\n')

    def list_in_manifest(self, *rows, table='Linked'):
        path = self.fixture / '.claude/DIVERGENCE.md'
        text = path.read_text()
        anchor = '| `scripts/verify-counts.sh` |'
        self.assertIn(anchor, text)
        path.write_text(text.replace(anchor, anchor + ''.join('\n| `scripts/%s` |' % row for row in rows), 1))

    def test_a_clean_tree_passes(self):
        self.expect(0, 'PASS')

    def test_an_unrecorded_shared_file_is_blocked(self):
        self.share('wb2-x.sh', symlink=False)
        self.expect(2, 'wb2-x.sh exists in both templates/ and .claude/')

    def test_an_unrecorded_shared_hook_is_blocked(self):
        (self.fixture / 'templates/hooks/wb2-y.sh').write_text('x\n')
        (self.fixture / '.claude/hooks/wb2-y.sh').write_text('x\n')
        self.expect(2, 'hooks/wb2-y.sh exists in both')

    def test_a_linked_file_replaced_by_a_copy_is_blocked(self):
        link = self.fixture / '.claude/scripts/verify-counts.sh'
        link.unlink()
        shutil.copy2(self.fixture / 'templates/scripts/verify-counts.sh', link)
        self.expect(2, 'is listed as linked but is a real file')

    def test_a_linked_file_pointing_elsewhere_is_blocked(self):
        link = self.fixture / '.claude/scripts/verify-counts.sh'
        link.unlink()
        link.symlink_to('../../templates/scripts/verify-skills.sh')
        self.expect(2, "points at '../../templates/scripts/verify-skills.sh'")

    def test_a_removed_manifest_row_leaves_the_file_unrecorded(self):
        path = self.fixture / '.claude/DIVERGENCE.md'
        path.write_text(''.join(line for line in path.read_text().splitlines(True) if '`scripts/verify-counts.sh`' not in line))
        self.expect(2, 'scripts/verify-counts.sh exists in both')

    def test_a_missing_manifest_is_blocked(self):
        (self.fixture / '.claude/DIVERGENCE.md').unlink()
        self.expect(2, 'is missing')

    def test_a_name_that_only_starts_like_a_listed_one_is_unrecorded(self):
        self.share('wb2-x.sh')
        self.share('wb2-x.sh.bak')
        self.list_in_manifest('wb2-x.sh')
        self.expect(2, 'wb2-x.sh.bak exists in both')

    def test_a_listed_name_with_a_dot_does_not_cover_a_name_that_matches_it_as_a_pattern(self):
        self.share('wb2-a.b.sh')
        self.share('wb2-aXb.sh')
        self.list_in_manifest('wb2-a.b.sh')
        self.expect(2, 'wb2-aXb.sh exists in both')

    def test_names_with_spaces_globs_quotes_and_dollars_are_compared_literally(self):
        names = ['wb2-dash-.sh', 'wb2 sp ace.sh', 'wb2-[gl]ob*.sh', 'wb2-$dollar.sh', 'wb2-"q".sh', "wb2-'s'.sh"]
        for name in names:
            self.share(name)
        self.list_in_manifest(*names)
        self.expect(0, 'PASS')
        self.share('wb2-unlisted-*.sh')
        self.expect(2, 'wb2-unlisted-*.sh exists in both')

    def test_a_name_that_starts_with_a_dash_is_read_not_taken_for_an_option(self):
        # `readlink -dash.sh` printed its usage text and the script exited 1 instead of judging the link.
        self.share('-dash.sh')
        self.list_in_manifest('-dash.sh')
        self.expect(0, 'PASS')
        link = self.fixture / '.claude/scripts/-dash.sh'
        link.unlink()
        link.symlink_to('../../templates/scripts/verify-skills.sh')
        self.expect(2, "points at '../../templates/scripts/verify-skills.sh'")

    def test_an_unlisted_name_that_starts_with_a_dash_is_blocked(self):
        self.share('-dash.sh')
        self.expect(2, '-dash.sh exists in both')

    def test_an_unrecorded_shared_file_whose_name_contains_a_line_break_is_blocked_not_skipped(self):
        # The names were read one per line, so this one was cut in two, both halves were skipped as "not in templates/",
        # and the script exited 0 with an unrecorded shared file.
        self.share('wb2-nl\nfoo.sh')
        output = self.expect(2, 'BLOCKED: A shared file name contains a line break')
        self.assertIn('FIX:', output)

    def test_a_name_with_a_line_break_in_a_listed_row_cannot_hide_other_drift(self):
        self.share('wb2-nl\nfoo.sh')
        self.share('wb2-other.sh', symlink=False)
        self.expect(2, 'line break')

    def test_a_trailing_space_in_a_manifest_row_does_not_match_the_file(self):
        self.share('wb2-t.sh')
        self.list_in_manifest('wb2-t.sh ')
        self.expect(2, 'wb2-t.sh exists in both')

    def test_a_manifest_with_windows_line_ends_is_still_read(self):
        path = self.fixture / '.claude/DIVERGENCE.md'
        path.write_bytes(path.read_text().replace('\n', '\r\n').encode())
        self.expect(0, 'PASS')

    def test_a_manifest_with_windows_line_ends_does_not_hide_drift(self):
        path = self.fixture / '.claude/DIVERGENCE.md'
        path.write_bytes(path.read_text().replace('\n', '\r\n').encode())
        self.share('wb2-x.sh', symlink=False)
        self.expect(2, 'wb2-x.sh exists in both')

    def test_a_stale_divergent_row_is_blocked(self):
        # A row in the Divergent table whose file is byte-identical to its template is stale (the shipped manifest has no
        # divergent file today, so the table is added here).
        path = self.fixture / '.claude/DIVERGENCE.md'
        (self.fixture / '.claude/scripts/wb2-d.sh').write_text('x\n')
        (self.fixture / 'templates/scripts/wb2-d.sh').write_text('x\n')
        path.write_text(path.read_text() + '\n## Divergent\n\n| File | Why |\n| --- | --- |\n| `scripts/wb2-d.sh` | stale row |\n')
        self.expect(2, 'is listed as divergent but is now byte-identical')

    def test_a_divergent_row_that_really_differs_passes(self):
        path = self.fixture / '.claude/DIVERGENCE.md'
        (self.fixture / '.claude/scripts/wb2-d.sh').write_text('local\n')
        (self.fixture / 'templates/scripts/wb2-d.sh').write_text('shipped\n')
        path.write_text(path.read_text() + '\n## Divergent\n\n| File | Why |\n| --- | --- |\n| `scripts/wb2-d.sh` | repository specific |\n')
        self.expect(0, '1 divergent files')


if __name__ == '__main__':
    unittest.main()
