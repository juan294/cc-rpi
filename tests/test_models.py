"""Native model requests remain distinct from fresh session observations."""
import importlib.util
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'templates/scripts/rpi-models.py'


def module():
    spec = importlib.util.spec_from_file_location('rpi_models_test', SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.models = module()
        self.observation = {
            'source': 'codex.turn_context', 'client_version': '0.153.4',
            'session_id': 'session-one', 'observed_at': '2026-09-05T12:00:00Z',
            'data': {'type': 'turn_context', 'payload': {'model': 'gpt-6-astra', 'effort': 'high'}}}

    def report(self, observation=None, **kwargs):
        return self.models.diagnose('codex', 'research', '0.153.4',
            observation=self.observation if observation is None else observation,
            session_id='session-one', now='2026-09-05T12:01:00Z', **kwargs)

    def test_default_inheritance_emits_no_native_overrides(self):
        for harness in ('claude', 'codex'):
            selected = self.models.select_profile(harness, 'implementation')
            self.assertEqual(selected['fields'], {})
            self.assertEqual(selected['source'], 'session inheritance')

    def test_economy_requires_explicit_mechanical_scope_and_supported_role(self):
        for role, mechanical in [('locator', False), ('research', True), ('validation', True), ('diagnosis', True)]:
            with self.subTest(role=role), self.assertRaises(ValueError):
                self.models.select_profile('codex', role, policy='economy', mechanical=mechanical)
        self.assertEqual(self.models.select_profile('codex', 'locator', policy='economy',
                         mechanical=True)['fields'],
                         {'model': 'gpt-5.6-sol', 'model_reasoning_effort': 'medium'})

    def test_haiku_economy_does_not_invent_effort(self):
        selected = self.models.select_profile('claude', 'formatting', policy='economy', mechanical=True)
        self.assertEqual(selected['fields'], {'model': 'haiku'})
        self.assertEqual(selected['application'], 'separate explicit session/profile')

    def test_explicit_selection_wins_over_economy_even_for_substantive_work(self):
        selected = self.models.select_profile('codex', 'research', policy='economy',
            explicit={'model': 'gpt-6-astra', 'effort': 'high', 'source': 'owner CLI selection'})
        self.assertEqual(selected['fields'], {'model': 'gpt-6-astra', 'model_reasoning_effort': 'high'})
        self.assertEqual(selected['source'], 'owner CLI selection')
        only_model = self.models.select_profile('codex', 'locator', policy='economy',
            explicit={'model': 'gpt-6-astra'})
        self.assertEqual(only_model['fields'], {'model': 'gpt-6-astra'})

    def test_offline_catalog_preserves_explicit_unknown_request(self):
        selected = self.models.select_profile('codex', 'research', catalog={},
            explicit={'model': 'owner-custom-model', 'effort': 'high'})
        self.assertEqual(selected['fields'], {'model': 'owner-custom-model', 'model_reasoning_effort': 'high'})
        self.assertEqual(selected['capability_status'], 'unverified')
        with self.assertRaises(ValueError):
            self.models.select_profile('codex', 'locator', policy='economy', mechanical=True, catalog={})

    def test_known_unsupported_effort_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'effort'):
            self.models.select_profile('claude', 'locator', explicit={'model': 'haiku', 'effort': 'low'})
        with self.assertRaisesRegex(ValueError, 'effort'):
            self.models.select_profile('codex', 'research', explicit={'model': 'gpt-6-astra', 'effort': 'inherit'})

    def test_partial_claude_request_rejects_codex_only_effort(self):
        with self.assertRaisesRegex(ValueError, 'effort'):
            self.models.select_profile('claude', 'research', explicit={'effort': 'ultra'})

    def test_malformed_descriptor_and_unrelated_native_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'catalog.json'
            for malformed in [[], {'schema_version': 1, 'default_policy': 'inherit', 'clients': []},
                              {'schema_version': 1, 'default_policy': 'inherit', 'clients': {'codex': []}}]:
                path.write_text(json.dumps(malformed))
                with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                    self.models.load_catalog(path)
        catalog = self.models.load_catalog()
        catalog['clients']['codex']['economy']['approval_policy'] = 'never'
        with self.assertRaises(ValueError):
            self.models.select_profile('codex', 'locator', policy='economy', mechanical=True, catalog=catalog)

    def test_unverified_client_cannot_silently_receive_economy_defaults(self):
        with self.assertRaisesRegex(ValueError, 'client'):
            self.models.select_profile('codex', 'locator', policy='economy', mechanical=True,
                                       client_version='0.1.0')

    def test_four_diagnostic_fields_and_session_bound_observation(self):
        report = self.report()
        self.assertEqual(set(report), {'requested_role', 'requested_model_effort_source',
                                      'resolved_model_effort', 'evidence_source_client_version'})
        self.assertEqual(report['resolved_model_effort']['model'], 'gpt-6-astra')
        self.assertEqual(report['resolved_model_effort']['effort'], 'high')
        self.assertEqual(report['evidence_source_client_version']['client_version'], '0.153.4')

    def test_requested_identity_does_not_fill_missing_observation(self):
        selection = self.models.select_profile('codex', 'research',
            explicit={'model': 'gpt-6-astra', 'effort': 'high'})
        report = self.models.diagnose('codex', 'research', '0.153.4', selection=selection)
        self.assertIsNone(report['resolved_model_effort']['model'])
        self.assertIsNone(report['resolved_model_effort']['effort'])

    def test_stale_future_mismatched_and_unknown_evidence_unavailable(self):
        for change in [{'observed_at': '2026-09-05T11:00:00Z'},
                       {'observed_at': '2026-09-05T12:02:00Z'}, {'session_id': 'other-pane'},
                       {'client_version': '0.1.0'}, {'source': 'assistant prose'},
                       {'observed_at': 'yesterday'}, {'data': {'model': 'invented'}}]:
            with self.subTest(change=change):
                report = self.report({**self.observation, **change})
                self.assertIsNone(report['resolved_model_effort']['model'])
                self.assertIsNone(report['resolved_model_effort']['effort'])
                self.assertEqual(report['resolved_model_effort']['status'], 'unavailable')

    def test_missing_session_binding_is_unavailable(self):
        report = self.models.diagnose('codex', 'research', '0.153.4', observation=self.observation,
                                     now='2026-09-05T12:01:00Z')
        self.assertEqual(report['resolved_model_effort']['status'], 'unavailable')

    def test_claude_native_init_reports_model_but_not_guessed_effort(self):
        evidence = {**self.observation, 'source': 'claude.system.init', 'client_version': '2.1.261',
                    'data': {'type': 'system', 'subtype': 'init', 'session_id': 'session-one',
                             'model': 'claude-fable-5-1'}}
        report = self.models.diagnose('claude', 'implementation', '2.1.261', observation=evidence,
                                     session_id='session-one', now='2026-09-05T12:01:00Z')
        self.assertEqual(report['resolved_model_effort']['model'], 'claude-fable-5-1')
        self.assertIsNone(report['resolved_model_effort']['effort'])
        evidence['data']['session_id'] = 'wrong-inner-session'
        mismatched = self.models.diagnose('claude', 'implementation', '2.1.261', observation=evidence,
                                         session_id='session-one', now='2026-09-05T12:01:00Z')
        self.assertEqual(mismatched['resolved_model_effort']['status'], 'unavailable')

    def test_effort_environment_cannot_supply_model_identity(self):
        evidence = {**self.observation, 'source': 'claude.CLAUDE_EFFORT', 'client_version': '2.1.261',
                    'data': {'CLAUDE_EFFORT': 'low', 'model': 'fabricated-model'}}
        report = self.models.diagnose('claude', 'locator', '2.1.261', observation=evidence,
                                     session_id='session-one', now='2026-09-05T12:01:00Z')
        self.assertIsNone(report['resolved_model_effort']['model'])
        self.assertEqual(report['resolved_model_effort']['effort'], 'low')
        self.assertNotIn('fabricated', json.dumps(report))

    def test_separate_profiles_never_mutate_parent_selection_or_input(self):
        parent = {'model': 'gpt-6-astra', 'effort': 'high', 'source': 'owner selection'}
        copy = dict(parent)
        self.models.select_profile('codex', 'locator', policy='economy', mechanical=True)
        self.assertEqual(parent, copy)
        self.assertEqual(self.models.select_profile('codex', 'implementation')['fields'], {})

    def test_invalid_requests_and_timestamp_clock_are_actionable(self):
        for harness, role, extra in [('other', 'research', {}), ('codex', '', {}),
                                     ('codex', 'research', {'explicit': {'model': 'bad\nmodel'}})]:
            with self.subTest(harness=harness, role=role), self.assertRaises(ValueError):
                self.models.select_profile(harness, role, **extra)
        with self.assertRaises(ValueError):
            self.models.diagnose('codex', 'research', '0.153.4', max_age=0)
        with self.assertRaises(ValueError):
            self.models.timestamp('2026-09-05T12:00:00')
        for data in [None, [], {'type': 'wrong'}]:
            self.assertEqual(self.report({**self.observation, 'data': data})[
                'resolved_model_effort']['status'], 'unavailable')

    def test_thread_metadata_and_claude_response_require_native_inner_binding(self):
        codex = {**self.observation, 'source': 'codex.thread.start',
                 'data': {'thread': {'id': 'session-one'}, 'model': 'gpt-6-astra', 'reasoningEffort': 'high'}}
        self.assertEqual(self.report(codex)['resolved_model_effort']['effort'], 'high')
        codex['data']['thread']['id'] = 'wrong-inner-session'
        self.assertEqual(self.report(codex)['resolved_model_effort']['status'], 'unavailable')
        evidence = {**self.observation, 'source': 'claude.assistant', 'client_version': '2.1.261',
                    'data': {'type': 'assistant', 'session_id': 'session-one',
                             'message': {'model': 'claude-fable-5-1'}}}
        report = self.models.diagnose('claude', 'research', '2.1.261', observation=evidence,
                                     session_id='session-one', now='2026-09-05T12:01:00Z')
        self.assertEqual(report['resolved_model_effort']['model'], 'claude-fable-5-1')
        evidence['data']['session_id'] = 'wrong-inner-session'
        self.assertEqual(self.models.diagnose('claude', 'research', '2.1.261', observation=evidence,
            session_id='session-one', now='2026-09-05T12:01:00Z')['resolved_model_effort']['status'], 'unavailable')

    def test_cli_offline_request_and_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = str(Path(temporary) / 'absent.json')
            cases = [(['--catalog', missing, '--model', 'owner-model', '--effort', 'high'], 0),
                     (['--observation', missing], 1), (['--effort', 'inherit'], 1),
                     (['--policy', 'economy', '--mechanical', '--role', 'locator'], 0)]
            for extra, expected in cases:
                output, error = io.StringIO(), io.StringIO()
                with self.subTest(extra=extra), patch.object(sys, 'argv', [str(SCRIPT),
                    '--harness', 'codex', '--role', 'research', '--client-version', '0.153.4', *extra]), \
                        redirect_stdout(output), redirect_stderr(error):
                    result = self.models.main()
                self.assertEqual(result, expected, error.getvalue())
                if expected:
                    self.assertIn('BLOCKED / WHY', error.getvalue())
                else:
                    self.assertIsNone(json.loads(output.getvalue())['resolved_model_effort']['model'])

    def test_cli_is_read_only_and_filters_unrelated_observation_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary) / 'evidence.json'
            evidence.write_text(json.dumps({**self.observation, 'secret': 'SYNTHETIC_NOT_FOR_OUTPUT'}))
            before = evidence.read_bytes()
            result = subprocess.run([sys.executable, str(SCRIPT), '--harness', 'codex', '--role', 'research',
                '--client-version', '0.153.4', '--session-id', 'session-one', '--observation', str(evidence),
                '--now', '2026-09-05T12:01:00Z'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('SYNTHETIC', result.stdout)
            self.assertEqual(evidence.read_bytes(), before)
            self.assertEqual(list(Path(temporary).iterdir()), [evidence])


if __name__ == '__main__':
    unittest.main()
