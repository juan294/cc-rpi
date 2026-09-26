"""Opt-in verification receipt gate; all remote executables are local sentinels."""
import json
import subprocess
import sys
import unittest

import test_policy


class PolicyReceiptTests(test_policy.PolicyFixture):
    def test_receipt_gate_is_off_by_default(self):
        (self.project / 'README.md').write_text('Dirty, unverified.\n')
        for command in ('git push origin develop', 'git push', 'vercel --prod',
                        'gh release create v9.9.9 --generate-notes'):
            with self.subTest(command=command):
                self.assert_allowed(command)

    def test_project_without_policy_file_is_never_gated(self):
        (self.project / '.rpi/policy.json').unlink()
        self.assert_allowed('git push origin develop')
        self.assert_blocked('git push -f origin develop', 'protected branch')
        self.assert_blocked('git push -f origin main', 'protected branch')

    def test_opted_in_integration_push_needs_current_complete_evidence(self):
        self.opt_in()
        for command in ('git push origin develop', 'git push', 'git push origin HEAD'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'verification evidence is missing')
        path = self.evidence()
        self.assert_allowed('git push origin develop')
        self.assert_allowed('git push')
        report = json.loads(path.read_text())
        for mutation in (dict(report, suite='custom'), dict(report, passed=False),
                         dict(report, checks=report['checks'][:1]),
                         dict(report, checks=list(reversed(report['checks']))),
                         dict(report, checks=[dict(item, exit_code=1) for item in report['checks']])):
            with self.subTest(mutation=mutation):
                path.write_text(json.dumps(mutation))
                self.assert_blocked('git push origin develop', 'does not attest')
        self.evidence()
        (self.project / 'README.md').write_text('Changed after verification.\n')
        self.assert_blocked('git push origin develop', 'clean')

    def test_opted_in_gate_ignores_working_branches(self):
        self.opt_in()
        self.git('checkout', '-qb', 'feature/work')
        (self.project / 'scratch.txt').write_text('in progress\n')
        self.assert_allowed('git push -u origin feature/work')
        self.assert_allowed('git push')

    def test_opted_in_tag_and_release_must_match_verified_commit(self):
        self.opt_in()
        self.tag()
        self.evidence()
        self.assert_allowed('git push origin v9.9.9')
        self.assert_allowed('gh release create v9.9.9 --verify-tag --title v9.9.9 --notes-file notes.md')
        self.commit()
        self.evidence()
        self.assert_blocked('git push origin v9.9.9', 'differs from the verified candidate')
        self.assert_blocked('gh release create v9.9.9 --notes x', 'differs from the verified candidate')
        self.assert_allowed('gh release create v0.0.1-unknown --notes x')

    def test_opted_in_bulk_tag_push_requires_named_tags_even_with_evidence(self):
        self.opt_in()
        self.tag('v1.2.3')
        self.git('checkout', '-qb', 'feature/work')
        self.evidence()
        for command in ('git push origin --tags', 'git push --follow-tags origin feature/work'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'git push origin vX.Y.Z')

    def test_opted_in_glob_refspecs_need_evidence(self):
        self.opt_in()
        self.assert_blocked("git push origin 'refs/heads/*'", 'verification evidence is missing')
        for command in ("git push origin 'refs/tags/*'", "git push origin 'refs/tags/*:refs/tags/*'"):
            with self.subTest(command=command):
                self.assert_blocked(command, 'git push origin vX.Y.Z')

    def test_opted_in_glob_push_with_a_receipt_never_crashes_the_evaluation(self):
        self.opt_in()
        self.evidence()
        self.assert_allowed("git push origin 'refs/heads/*'")
        for command in ("git push origin 'refs/tags/*'; git push -f origin develop",
                        "git push origin 'refs/heads/*' && gh repo delete o/r --yes"):
            with self.subTest(command=command):
                result = self.assert_blocked(command)
                self.assertNotIn('POLICY UNAVAILABLE', result.stderr)

    def test_opted_in_bulk_tag_publication_requires_named_tags(self):
        self.opt_in()
        self.tag('v1.0.0')
        self.commit('After the old tag')
        self.evidence()
        for command in ('git push --tags', "git push origin 'refs/tags/*'", 'git push --follow-tags origin develop'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'git push origin vX.Y.Z')

    def test_opted_in_glob_branch_push_checks_the_integration_commit(self):
        self.opt_in()
        self.evidence()
        self.commit('Unverified change')
        self.assert_blocked("git push origin 'refs/heads/*'", 'does not attest')

    def test_receipt_binds_the_resolved_interpreter(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('candidate_fixture', test_policy.ROOT / 'templates/scripts/rpi-candidate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        alias = self.workspace / 'python-alias'
        alias.symlink_to(sys.executable)
        original = sys.executable
        try:
            sys.executable = str(alias)
            aliased = module.environment(self.environment)['executable']
        finally:
            sys.executable = original
        self.assertEqual(aliased, module.environment(self.environment)['executable'])

    def test_ref_evidence_repair_is_a_runnable_command(self):
        self.opt_in()
        self.tag()
        self.commit('Moves HEAD past the tag')
        self.evidence()
        result = self.assert_blocked('git push origin v9.9.9', 'differs from the verified candidate')
        self.assertIn('git push origin develop', result.stderr)

    def test_invalid_policy_messages_name_the_cause(self):
        path = self.project / '.rpi/policy.json'
        path.write_text('not json')
        self.assert_blocked('git push origin develop', 'not valid JSON')
        path.write_text(json.dumps({'schema_version': 1, 'integration_branch': ['release']}))
        self.assert_blocked('git push -f origin release', 'integration_branch')

    def test_unreadable_policy_file_blocks_policy_dependent_commands(self):
        path = self.project / '.rpi/policy.json'
        path.unlink()
        path.mkdir()
        self.assert_blocked('git push origin develop', '.rpi/policy.json')
        self.assert_allowed('git status')

    def test_stale_receipt_repair_names_environment_changes(self):
        self.opt_in()
        self.evidence()
        result = self.invoke('git push origin develop', environment={**self.environment, 'LC_ALL': 'C.UTF-8', 'TZ': 'Etc/GMT+3'})
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('locale, timezone or Python', result.stderr)

    def test_opted_in_release_tag_is_found_after_option_values(self):
        self.opt_in()
        self.tag()
        self.commit()
        self.evidence()
        for command in ('gh release create --title "Release" v9.9.9', 'gh release create -t Rel v9.9.9',
                        'gh release create --repo owner/x v9.9.9', 'gh release create --draft v9.9.9 --notes x'):
            with self.subTest(command=command):
                self.assert_blocked(command, 'differs from the verified candidate')

    def test_opted_in_gate_errors_block_instead_of_failing_open(self):
        runtime = self.workspace / 'runtime'
        runtime.mkdir()
        policy = runtime / 'rpi-policy.py'
        policy.write_bytes(test_policy.POLICY.read_bytes())
        (runtime / 'rpi-candidate.py').write_text('def identity(root):\n    raise RuntimeError\n\ndef environment(*_):\n    return {}\n')
        self.opt_in()
        self.evidence()
        result = subprocess.run([sys.executable, str(policy), '--harness', 'claude'],
                                input=json.dumps(self.event('git push origin develop')),
                                text=True, capture_output=True, env=self.environment, cwd=self.project)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('Receipt verification failed', result.stderr)

    def test_invalid_policy_file_blocks_release_creation(self):
        (self.project / '.rpi/policy.json').write_text('not json')
        self.assert_blocked('gh release create v7.7.7 --notes x', '.rpi/policy.json')

    def test_opted_in_production_deploy_needs_evidence(self):
        self.opt_in()
        self.assert_blocked('vercel --prod', 'verification evidence is missing')
        self.evidence()
        self.assert_allowed('vercel deploy --prod')
        self.assert_allowed('vercel env ls')

    def test_opted_in_malformed_declaration_is_reported(self):
        path = self.project / '.rpi/policy.json'
        original = path.read_bytes()
        for update, reason in (({'verification_command': []}, 'verification command is missing or malformed'),
                               ({'verification_checks': []}, 'verification inventory is missing'),
                               ({'verification_checks': [{'name': 't', 'argv': [None]}]}, 'unique names and literal argv')):
            with self.subTest(update=update):
                path.write_bytes(original)
                self.policy(require_verification_receipt=True, **update)
                self.assert_blocked('git push origin develop', reason)
        path.write_text('{"schema_version": 1, "require_verification_receipt": "yes"}')
        self.assert_blocked('git push origin develop', 'require_verification_receipt must be true or false')

    def test_invalid_policy_file_blocks_only_policy_dependent_commands(self):
        path = self.project / '.rpi/policy.json'
        for data in ('not json', '[]', '{"schema_version": 2}', '{"schema_version": 1, "unknown": 1}'):
            with self.subTest(data=data):
                path.write_text(data)
                self.assert_blocked('git push origin develop', '.rpi/policy.json')
                self.assert_allowed('git status')
                self.assert_allowed('gh pr create --fill')
        copied = self.workspace / 'policy.json'
        copied.write_text('{"schema_version": 1}')
        path.unlink()
        path.symlink_to(copied)
        self.assert_blocked('git push origin develop', 'regular file')

    def test_changed_locale_cannot_reuse_passing_receipt(self):
        self.opt_in()
        self.environment['LC_ALL'] = 'C'
        self.evidence()
        self.assertEqual(self.invoke('git push origin develop').returncode, 0)
        changed = {**self.environment, 'LC_ALL': 'C.UTF-8'}
        result = self.invoke('git push origin develop', environment=changed)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_missing_candidate_helper_blocks_only_when_opted_in(self):
        runtime = self.workspace / 'runtime'
        runtime.mkdir()
        policy = runtime / 'rpi-policy.py'
        policy.write_bytes(test_policy.POLICY.read_bytes())
        def run():
            return subprocess.run([sys.executable, str(policy), '--harness', 'claude'],
                                  input=json.dumps(self.event('git push origin develop')),
                                  text=True, capture_output=True, env=self.environment, cwd=self.project)
        self.assertEqual(run().returncode, 0)
        self.opt_in()
        self.evidence()
        result = run()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('candidate identity helper is missing', result.stderr)


if __name__ == '__main__':
    unittest.main()
