"""Structured workflow handoffs reject incomplete work, not small teams."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'templates/scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assignment(identifier='parent', owner='parent', role='investigator', domains=None):
    return {'id': identifier, 'owner': owner, 'role': role, 'objective': 'Inspect the scoped source',
            'allowed_actions': ['read'], 'allowed_files': ['src/'],
            'evidence_contract': 'Source references and observed command results',
            'resource_constraints': 'One local command at a time, no remote compute',
            'completion_condition': 'Return the domain model and all scoped findings',
            'domains': domains or [], 'root_causes': [], 'concurrency_group': 'one'}


def result(item, candidate='tree-1'):
    return {'assignment_id': item['id'], 'status': 'complete', 'candidate': candidate,
            'evidence': ['src/main.py:1'], 'domains': item['domains'][:],
            'root_causes': item['root_causes'][:], 'actions': ['read'], 'changed_files': []}


def narrow():
    item = assignment()
    return {'schema_version': 1, 'objective': 'Describe current behavior', 'phase': 'research',
            'approved_phases': ['research'], 'candidate': 'tree-1', 'resource_limit': 1,
            'assignments': [item], 'results': [result(item)]}


class WorkflowContracts(unittest.TestCase):
    def setUp(self):
        self.dispatch = load('rpi-dispatch')
        self.findings = load('validate-findings')

    def errors(self, document, report=None, current_candidate=None):
        return self.dispatch.validate(document, report_text=report, current_candidate=current_candidate)

    def assertRejected(self, document, text, **kwargs):
        self.assertTrue(any(text in error for error in self.errors(document, **kwargs)),
                        self.errors(document, **kwargs))

    def audit(self):
        document = narrow()
        document['phase'] = 'pre-launch'
        document['approved_phases'] = ['pre-launch']
        document['audit'] = {'agent_surface': {'applicable': False, 'evidence': ['src/main.py:1: no tools exposed']}}
        document['assignments'][0]['domains'] = list(self.dispatch.CORE_DOMAINS)
        document['results'] = [result(document['assignments'][0])]
        return document

    def implementation(self):
        document = narrow()
        document['phase'] = 'implement'
        document['approved_phases'] = ['implement']
        implementer = assignment(role='implementer')
        reviewer = assignment('review', 'independent', 'reviewer')
        document['assignments'] = [implementer, reviewer]
        document['results'] = [result(item) for item in document['assignments']]
        return document

    def test_narrow_parent_only_research_has_no_fanout_requirement(self):
        self.assertEqual(self.errors(narrow()), [])

    def test_one_agent_can_complete_all_eight_core_domains_without_findings(self):
        self.assertEqual(self.errors(self.audit(), report='## Audit\nNo findings.\n'), [])

    def test_conditional_agent_surface_needs_detection_evidence_and_completed_result(self):
        document = self.audit()
        document['audit']['agent_surface']['applicable'] = True
        self.assertRejected(document, 'coverage gap: AS', report='No findings')
        document['assignments'][0]['domains'].append('AS')
        document['results'][0]['domains'].append('AS')
        self.assertEqual(self.errors(document, report=self.findings.VALID_FIXTURE), [])
        document['audit']['agent_surface']['evidence'] = []
        self.assertRejected(document, 'agent_surface.evidence', report='No findings')

    def test_failed_or_missing_result_is_a_coverage_gap_even_if_assignment_exists(self):
        for status in ['failed', 'missing']:
            document = self.audit()
            if status == 'missing':
                document['results'] = []
            else:
                document['results'][0]['status'] = status
            self.assertRejected(document, 'coverage gap: AR', report='No findings')
            self.assertRejected(document, 'required result', report='No findings')

    def test_assignment_cannot_claim_unassigned_domains_or_unknown_result(self):
        document = narrow()
        document['results'][0]['domains'] = ['SE']
        self.assertRejected(document, 'unassigned domains')
        document['results'][0]['assignment_id'] = 'phantom'
        self.assertRejected(document, 'unknown assignment')

    def test_stale_candidate_cannot_supply_coverage_or_independent_review(self):
        document = self.audit()
        document['results'][0]['candidate'] = 'old-tree'
        self.assertRejected(document, 'stale result', report='No findings')
        self.assertRejected(document, 'coverage gap', report='No findings')
        self.assertRejected(narrow(), 'resume candidate mismatch', current_candidate='new-tree')

    def test_implementation_requires_completed_independent_reviewer(self):
        document = self.implementation()
        self.assertEqual(self.errors(document), [])
        document['results'].pop()
        self.assertRejected(document, 'independent review')
        document = self.implementation()
        document['assignments'][1]['owner'] = 'parent'
        self.assertRejected(document, 'independent review')

    def test_resource_limit_counts_simultaneous_implementers_not_domain_count(self):
        document = self.implementation()
        for index in range(3):
            item = assignment(f'impl-{index}', f'worker-{index}', 'implementer')
            document['assignments'].append(item)
            document['results'].append(result(item))
        document['resource_limit'] = 3
        self.assertRejected(document, 'implementer limit')
        document['assignments'][-1]['concurrency_group'] = 'later'
        self.assertEqual(self.errors(document), [])
        document['resource_limit'] = 2
        self.assertRejected(document, 'implementer limit')
        document['resource_limit'] = 4
        self.assertRejected(document, 'resource_limit')

    def test_same_implementer_can_own_multiple_bounded_assignments(self):
        document = self.implementation()
        item = assignment('second-work-unit', 'parent', 'implementer')
        document['assignments'].append(item)
        document['results'].append(result(item))
        self.assertEqual(self.errors(document), [])
        item['owner'] = 'another-worker'
        self.assertRejected(document, 'implementer limit')

    def test_many_failing_tests_can_share_one_root_cause_assignment(self):
        document = self.implementation()
        document['assignments'][0]['root_causes'] = ['shared-fixture']
        document['results'][0]['root_causes'] = ['shared-fixture']
        document['results'][0]['evidence'] = [f'tests/test_api.py:{i}' for i in range(1, 21)]
        self.assertEqual(self.errors(document), [])
        document['results'][0]['root_causes'] = []
        self.assertRejected(document, 'root cause gap')

    def test_every_assignment_requires_bounded_contract_and_unique_identity(self):
        for field in ['objective', 'allowed_actions', 'allowed_files', 'evidence_contract',
                      'resource_constraints', 'completion_condition', 'owner', 'concurrency_group']:
            document = narrow()
            del document['assignments'][0][field]
            self.assertRejected(document, field)
        document = narrow()
        document['assignments'].append(copy.deepcopy(document['assignments'][0]))
        self.assertRejected(document, 'duplicate assignment')
        document = narrow()
        document['results'].append(copy.deepcopy(document['results'][0]))
        self.assertRejected(document, 'duplicate result')

    def test_result_actions_and_changed_files_cannot_exceed_assignment(self):
        document = narrow()
        document['results'][0]['actions'] = ['write']
        document['results'][0]['changed_files'] = ['outside/file.py']
        self.assertRejected(document, 'unpermitted actions')
        self.assertRejected(document, 'unpermitted changed file')
        document['assignments'][0]['allowed_actions'].append('write')
        document['results'][0]['changed_files'] = ['src/main.py']
        self.assertEqual(self.errors(document), [])
        document['results'][0]['changed_files'] = ['src/../secrets']
        self.assertRejected(document, 'unpermitted changed file')

    def test_research_and_phase_only_boundaries_reject_unapproved_next_phase(self):
        for phase in ['research', 'implement']:
            document = narrow() if phase == 'research' else self.implementation()
            document['next_phase'] = 'release'
            self.assertRejected(document, 'next_phase is not approved')
            document['approved_phases'].append('release')
            self.assertEqual(self.errors(document), [])

    def test_behavioral_change_requires_red_before_green_on_same_regression(self):
        document = self.implementation()
        document['behavioral_change'] = True
        self.assertRejected(document, 'TDD')
        document['tdd'] = {'regression': 'reject duplicate submit', 'red': {'sequence': 1, 'evidence': 'red.log'},
                           'green': {'sequence': 2, 'evidence': 'green.log', 'candidate': 'tree-1'}}
        self.assertEqual(self.errors(document), [])
        document['tdd']['red']['sequence'] = 2
        self.assertRejected(document, 'TDD')

    def test_complete_disposition_rejects_deferred_actionable_and_unreviewed_exception(self):
        document = self.implementation()
        document['findings'] = [{'id': 'BE-H1', 'disposition': 'resolved', 'evidence': ['tests/test_api.py:1']},
                                {'id': 'AS-H1', 'disposition': 'rejected', 'evidence': ['src/tool.py:2']}]
        self.assertEqual(self.errors(document, report=self.findings.VALID_FIXTURE), [])
        document['findings'][0]['disposition'] = 'deferred'
        self.assertRejected(document, 'unresolved finding', report=self.findings.VALID_FIXTURE)
        document['findings'][0]['disposition'] = 'architectural_exception'
        self.assertRejected(document, 'owner_review', report=self.findings.VALID_FIXTURE)
        document['findings'][0]['owner_review'] = 'Owner accepted local follow-up in decision-1'
        self.assertEqual(self.errors(document, report=self.findings.VALID_FIXTURE), [])
        document['findings'].pop()
        self.assertRejected(document, 'finding disposition gap', report=self.findings.VALID_FIXTURE)

    def test_simplify_parent_returns_invalidated_checks_standalone_reruns_them(self):
        document = narrow()
        document['phase'] = 'simplify'
        document['approved_phases'] = ['simplify']
        document['assignments'][0]['allowed_actions'].append('write')
        document['results'][0]['actions'].append('write')
        document['results'][0]['changed_files'] = ['src/main.py']
        document['simplify'] = {'mode': 'parent', 'changed_files': ['src/main.py'], 'invalidated_checks': ['unit'], 'checks': []}
        self.assertEqual(self.errors(document), [])
        document['simplify']['mode'] = 'standalone'
        self.assertRejected(document, 'invalidated check: unit')
        document['simplify']['checks'] = [{'id': 'unit', 'status': 'pass', 'candidate': 'tree-1', 'evidence': ['unit.log']}]
        self.assertEqual(self.errors(document), [])

    def test_simplify_changed_scope_must_match_successful_scoped_results(self):
        document = narrow()
        document['phase'] = 'simplify'
        document['approved_phases'] = ['simplify']
        document['simplify'] = {'mode': 'parent', 'changed_files': ['outside/secret.py'],
                                'invalidated_checks': [], 'checks': []}
        self.assertRejected(document, 'simplify changed scope')
        document['assignments'][0]['allowed_actions'].append('write')
        document['results'][0]['actions'].append('write')
        document['results'][0]['changed_files'] = ['src/main.py']
        document['simplify']['changed_files'] = []
        self.assertRejected(document, 'simplify changed scope')
        document['simplify']['changed_files'] = ['src/main.py']
        self.assertEqual(self.errors(document), [])
        document['results'][0]['status'] = 'failed'
        self.assertRejected(document, 'simplify changed scope')

    def test_supplied_version_and_authorized_docs_do_not_create_duplicate_decisions(self):
        document = narrow()
        document['context'] = {'supplied_version': '2.0.0', 'docs_authorized': True}
        document['decisions_requested'] = []
        self.assertEqual(self.errors(document), [])
        for decision in ['release_version', 'docs_authorization']:
            document['decisions_requested'] = [decision]
            self.assertRejected(document, 'already supplied')
        document['decisions_requested'] = ['production_authorization']
        self.assertEqual(self.errors(document), [])

    def test_report_ids_refs_fields_and_duplicate_ids_remain_strict(self):
        self.assertEqual(self.findings.validate_text(self.findings.VALID_FIXTURE), [])
        for report in [self.findings.INVALID_FIXTURE,
                       self.findings.VALID_FIXTURE.replace('src/orders/api.ts:42, src/orders/repo.ts:110-130', 'src/orders/api.ts'),
                       self.findings.VALID_FIXTURE + self.findings.VALID_FIXTURE,
                       self.findings.VALID_FIXTURE.replace('**Recommendation:** batch the lookups with a single join.', '**Recommendation:**')]:
            self.assertTrue(self.findings.validate_text(report))
        document = self.audit()
        self.assertRejected(document, 'AS findings without applicable coverage', report=self.findings.VALID_FIXTURE)

    def test_malformed_artifact_and_cli_failure_are_corrective_and_read_only(self):
        for malformed in [None, [], {'schema_version': True}, {'schema_version': 1, 'assignments': 'x'}]:
            self.assertTrue(self.errors(malformed))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'handoff.json'
            path.write_text(json.dumps(narrow()))
            before = path.read_bytes()
            command = [sys.executable, str(ROOT / 'templates/scripts/rpi-dispatch.py'), str(path)]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            failed = subprocess.run(command + ['--current-candidate', 'different'], capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1)
            self.assertIn('resume candidate mismatch', failed.stderr)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_malformed_nested_fields_never_become_success_or_traceback(self):
        for container, field in [('assignment', 'owner'), ('assignment', 'role'),
                                 ('assignment', 'domains'), ('assignment', 'allowed_files'),
                                 ('result', 'assignment_id'), ('result', 'domains'),
                                 ('result', 'evidence'), ('root', 'phase'), ('root', 'candidate'),
                                 ('root', 'resource_limit'), ('root', 'behavioral_change')]:
            for value in [None, {}, [], True]:
                document = self.implementation()
                for item in document['assignments'] + document['results']:
                    item['domains'] = ['BE']
                target = document['assignments'][1] if container == 'assignment' else document['results'][0] if container == 'result' else document
                target[field] = value
                with self.subTest(container=container, field=field, value=value):
                    self.assertTrue(self.errors(document))

    def test_result_cannot_omit_assigned_domain_outside_full_audit(self):
        document = narrow()
        document['assignments'][0]['domains'] = ['BE']
        self.assertRejected(document, 'domain gap')

    def test_read_only_audit_cannot_claim_source_mutation(self):
        document = self.audit()
        document['assignments'][0]['allowed_actions'].append('write')
        document['results'][0]['actions'].append('write')
        document['results'][0]['changed_files'] = ['src/main.py']
        self.assertRejected(document, 'audit assignments must be read-only', report='No findings')

    def test_extracted_report_validation_does_not_write_source_caches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['rpi-dispatch.py', 'validate-findings.py']:
                shutil.copyfile(ROOT / 'templates/scripts' / name, root / name)
            (root / 'handoff.json').write_text(json.dumps(self.audit()))
            (root / 'report.md').write_text('## Audit\nNo findings.\n')
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            completed = subprocess.run([sys.executable, str(root / 'rpi-dispatch.py'),
                                        str(root / 'handoff.json'), '--report', str(root / 'report.md')],
                                       capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual({path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}, before)
            self.assertEqual(set(path.name for path in root.iterdir()), set(before))


if __name__ == '__main__':
    unittest.main()
