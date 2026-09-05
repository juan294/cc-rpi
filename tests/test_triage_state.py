"""A completed triage must never hide late arrivals or failed earlier reports."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'templates/scripts/rpi-triage-state.py'


class TriageStateTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('triage_state', SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temporary = tempfile.TemporaryDirectory(prefix='rpi triage é & ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.reports = self.root / 'docs/agents'
        self.reports.mkdir(parents=True)
        self.complete = {name: 'complete' for name in self.module.INVENTORIES}

    def report(self, name, text='report', stamp=10):
        path = self.reports / name
        path.write_text(text)
        os.utime(path, ns=(stamp, stamp))
        return path

    def finish(self, scan, outcomes=None, **kwargs):
        return self.module.checkpoint(self.root, scan,
            outcomes if outcomes is not None else {name: 'processed' for name in scan['selected']},
            kwargs.pop('inventories', self.complete), reported=kwargs.pop('reported', True), **kwargs)

    def test_late_arrival_and_modified_report_survive_scan_start_checkpoint(self):
        original = self.report('first-report.md')
        scan = self.module.scan(self.root, now_ns=100)
        self.report('late-report.md', stamp=110)
        original.write_text('changed during processing')
        os.utime(original, ns=(110, 110))
        result = self.finish(scan)
        self.assertTrue(result['checkpoint_advanced'])
        self.assertEqual((self.reports / '.last-triage').stat().st_mtime_ns, 100)
        following = self.module.scan(self.root, now_ns=120)
        self.assertEqual(set(following['selected']), {'first-report.md', 'late-report.md'})

    def test_failed_old_and_unknown_backdated_reports_are_never_skipped(self):
        self.report('failed-report.md')
        self.report('done-report.md')
        scan = self.module.scan(self.root, now_ns=100)
        self.finish(scan, {'failed-report.md': 'failed', 'done-report.md': 'processed'})
        self.report('backdated-report.md', stamp=1)
        following = self.module.scan(self.root, now_ns=120)
        self.assertEqual(set(following['selected']), {'failed-report.md', 'backdated-report.md'})

    def test_failed_query_or_incomplete_reporting_never_advances_marker(self):
        self.report('first-report.md')
        self.finish(self.module.scan(self.root, now_ns=100))
        for values in ({'inventories': {**self.complete, 'code_scanning': 'failed'}}, {'reported': False}):
            with self.subTest(values=values):
                scan = self.module.scan(self.root, now_ns=200)
                result = self.finish(scan, **values)
                self.assertFalse(result['checkpoint_advanced'])
                self.assertEqual((self.reports / '.last-triage').stat().st_mtime_ns, 100)

    def test_partial_scope_keeps_global_marker_and_unprocessed_inventory(self):
        self.report('one-report.md')
        self.report('two-report.md')
        scan = self.module.scan(self.root, only=['one-report.md'], now_ns=100)
        self.finish(scan)
        self.assertFalse((self.reports / '.last-triage').exists())
        following = self.module.scan(self.root, now_ns=200)
        self.assertEqual(following['selected'], ['two-report.md'])

    def test_missing_failed_report_is_an_explicit_discovery_gap(self):
        path = self.report('failed-report.md')
        self.finish(self.module.scan(self.root, now_ns=100), {'failed-report.md': 'failed'})
        path.unlink()
        scan = self.module.scan(self.root, now_ns=200)
        self.assertEqual(scan['missing_retry'], ['failed-report.md'])
        result = self.finish(scan)
        self.assertFalse(result['checkpoint_advanced'])

    def test_stale_scan_cannot_overwrite_newer_checkpoint(self):
        self.report('report-report.md')
        first = self.module.scan(self.root, now_ns=100)
        stale = self.module.scan(self.root, now_ns=110)
        self.finish(first)
        path = self.root / '.rpi/local/triage-state.json'
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.finish(stale)
        self.assertEqual(path.read_bytes(), before)

    def test_report_and_state_symlinks_preserve_outside_data(self):
        outside = self.root / 'outside.txt'
        outside.write_text('private sentinel')
        (self.reports / 'linked-report.md').symlink_to(outside)
        scan = self.module.scan(self.root, now_ns=100)
        self.assertTrue(scan['issues'])
        result = self.finish(scan)
        self.assertFalse(result['checkpoint_advanced'])
        state = self.root / '.rpi/local/triage-state.json'
        state.unlink()
        state.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.module.scan(self.root)
        self.assertEqual(outside.read_text(), 'private sentinel')

    def test_invalid_outcome_or_binding_rejects_before_state_write(self):
        self.report('report-report.md')
        scan = self.module.scan(self.root, now_ns=100)
        for invalid in ({'../outside': 'processed'}, {'report-report.md': 'ignored'}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.finish(scan, invalid)
        scan['root'] = str(self.root.parent)
        with self.assertRaises(ValueError):
            self.finish(scan)
        self.assertFalse((self.root / '.rpi/local/triage-state.json').exists())

    def test_full_scan_tracks_previously_explicit_nonstandard_report_names(self):
        report = self.report('audit.md')
        self.finish(self.module.scan(self.root, only=['audit.md'], now_ns=100))
        report.write_text('changed audit')
        scan = self.module.scan(self.root, now_ns=200)
        self.assertEqual(scan['selected'], ['audit.md'])
        self.finish(scan, {'audit.md': 'failed'})
        retry = self.module.scan(self.root, now_ns=300)
        self.assertEqual(retry['selected'], ['audit.md'])
        self.assertEqual(retry['missing_retry'], [])

    def test_unreadable_directory_cannot_become_an_empty_successful_scan(self):
        with patch('os.scandir', side_effect=PermissionError('fixture denied')):
            scan = self.module.scan(self.root, now_ns=100)
        self.assertTrue(scan['issues'])
        self.assertFalse(self.finish(scan)['checkpoint_advanced'])

    def test_report_fifo_is_a_gap_without_blocking_discovery(self):
        os.mkfifo(self.reports / 'fifo-report.md')
        scan = self.module.scan(self.root, now_ns=100)
        self.assertTrue(scan['issues'])
        self.assertFalse(self.finish(scan)['checkpoint_advanced'])

    def test_metadata_never_contains_report_contents_and_state_is_ignored(self):
        self.report('report-report.md', 'PRIVATE_REPORT_CONTENT')
        scan = self.module.scan(self.root, now_ns=100)
        self.assertNotIn('PRIVATE_REPORT_CONTENT', json.dumps(scan))
        self.finish(scan)
        self.assertIn('*', (self.root / '.rpi/local/.gitignore').read_text().splitlines())
        self.assertNotIn('PRIVATE_REPORT_CONTENT', (self.root / '.rpi/local/triage-state.json').read_text())


if __name__ == '__main__':
    unittest.main()
