"""Decision-path acceptance for policy; all remote executables are local sentinels."""
import json
import os
import shlex
import subprocess
import sys
import unittest

import test_policy


class PolicyDecisionTests(unittest.TestCase):
    # Reuse fixture operations without inheriting and rediscovering its tests.
    setUp = test_policy.PolicyTests.setUp
    git = test_policy.PolicyTests.git
    event = test_policy.PolicyTests.event
    invoke = test_policy.PolicyTests.invoke
    execute = test_policy.PolicyTests.execute
    expected_checks = test_policy.PolicyTests.expected_checks
    evidence = test_policy.PolicyTests.evidence

    def deny(self, command, reason, **kwargs):
        result = self.invoke(command, **kwargs)
        self.assertEqual(result.returncode, 2, command + '\n' + result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertIn('/ FIX:', result.stderr)
        self.assertFalse(self.sentinel.exists(), command)
        return result

    def allow(self, command, **kwargs):
        result = self.invoke(command, **kwargs)
        self.assertEqual(result.returncode, 0, command + '\n' + result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertFalse(self.sentinel.exists(), 'a hook structural pass cannot execute or approve')
        return result

    def commit(self):
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '--allow-empty', '-qm', 'Decision fixture')

    def policy(self, **changes):
        path = self.project / '.rpi/policy.json'
        value = json.loads(path.read_text())
        value.update(changes)
        path.write_text(json.dumps(value))
        return path

    def tag(self, name='v2.0.0'):
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'tag', '-a', name, '-m', 'Decision fixture')

    def release(self):
        self.tag()
        notes = self.project / '.rpi/local/notes.md'
        notes.parent.mkdir(parents=True, exist_ok=True)
        notes.write_text('Reviewed local notes.\n')
        return 'gh release create v2.0.0 --verify-tag --title v2.0.0 --notes-file .rpi/local/notes.md'

    def codex(self, version='codex-cli 0.153.4', decision='prompt', exit_code=0):
        path = self.fakebin / 'codex'
        path.write_text('#!/usr/bin/env python3\nimport json,sys\n'
                        f'print({version!r} if "--version" in sys.argv else json.dumps({{"decision": {decision!r}}}))\n'
                        f'sys.exit(0 if "--version" in sys.argv else {exit_code})\n')
        path.chmod(0o755)

    def native_rules(self):
        path = self.project / '.codex/rules/rpi.rules'
        path.parent.mkdir(parents=True)
        path.write_bytes((test_policy.ROOT / 'templates/adapters/codex-permissions.rules').read_bytes())
        self.commit()
        return path

    def test_topology_rejects_redirected_invalid_or_working_targets(self):
        path = self.project / '.rpi/policy.json'
        original = path.read_bytes()
        for update, reason in (({'schema_version': 2}, 'Invalid project topology schema'),
                               ({'unreviewed': True}, 'Invalid project topology schema'),
                               ({'integration_branch': 'feature/pretend'}, 'documented integration branch'),
                               ({'integration_branch': None}, 'documented integration branch'),
                               ({'remote': '../origin'}, 'publication remote must be one')):
            with self.subTest(update=update):
                path.write_bytes(original)
                self.policy(**update)
                self.deny('git push origin develop', reason)
        path.write_bytes(original)
        copied = self.workspace / 'policy.json'
        copied.write_bytes(original)
        path.unlink()
        path.symlink_to(copied)
        self.deny('git push origin develop', 'Project policy must be a regular file')
        self.assertEqual(copied.read_bytes(), original)

    def test_inferred_topology_never_substitutes_for_verification_declaration(self):
        (self.project / '.rpi/policy.json').unlink()
        self.deny('git push origin develop', 'must declare its complete local verification inventory')
        self.git('branch', '-m', 'other')
        self.deny('git push origin other', 'documented integration branch is required')

    def test_verification_declaration_rejects_malformed_command_and_checks(self):
        path = self.project / '.rpi/policy.json'
        original = path.read_bytes()
        updates = [({'verification_command': []}, 'verification command is missing or malformed'),
                   ({'verification_checks': []}, 'complete project verification inventory is missing'),
                   ({'verification_checks': [*self.expected_checks(), self.expected_checks()[0]]}, 'unique names and literal argv'),
                   ({'verification_checks': [{'name': 'test', 'argv': [None]}]}, 'unique names and literal argv'),
                   ({'verification_checks': [{'name': 'test', 'argv': ['true'], 'extra': True}]}, 'unique names and literal argv')]
        for update, reason in updates:
            with self.subTest(update=update):
                path.write_bytes(original)
                self.policy(**update)
                self.deny('git push origin develop', reason)

    def test_malformed_and_nonfinite_json_fail_closed(self):
        for data in ('{"tool_name":"Bash","tool_name":"Read"}', '{"tool_name": NaN}', '[]', '{}'):
            with self.subTest(data=data):
                result = subprocess.run([sys.executable, str(test_policy.POLICY), '--harness', 'claude'],
                                        input=data, text=True, capture_output=True,
                                        cwd=self.project, env=self.environment)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('BLOCKED / WHY:', result.stderr)
                self.assertFalse(self.sentinel.exists())

    def test_failed_git_state_and_unconfigured_remote_cannot_reach_transport(self):
        outside = self.workspace / 'outside'
        outside.mkdir()
        self.deny('git push origin develop', 'Git could not resolve',
                  event={**self.event('git push origin develop'), 'cwd': str(outside)})
        self.deny('git push other develop', 'not the documented configured publication remote')
        self.git('remote', 'remove', 'origin')
        self.deny('git push origin develop', 'not the documented configured publication remote')

    def test_push_option_source_and_commit_decisions(self):
        self.evidence()
        self.allow('git push --porcelain --dry-run -u origin develop')
        self.deny('git push --receive-pack=other origin develop', 'unsupported push option')
        self.deny('git push origin other:develop', 'push source differs')
        self.tag()
        self.commit()
        self.evidence()
        self.deny('git push origin v2.0.0', 'ref being published differs')
        self.git('checkout', '-qb', 'other')
        self.evidence()
        self.deny('git push origin develop', 'completed documented integration branch')

    def test_report_claims_cannot_replace_complete_exact_success(self):
        path = self.evidence()
        valid = json.loads(path.read_text())
        mutations = [dict(valid, passed=False), dict(valid, identity_after={}),
                     dict(valid, environment_unchanged=False), dict(valid, environment_after={}),
                     dict(valid, checks=[dict(item, exit_code=True) for item in valid['checks']]),
                     dict(valid, checks=[dict(item, exit_code=1) for item in valid['checks']]),
                     dict(valid, checks=[None, None])]
        for report in mutations:
            with self.subTest(report=report):
                path.write_text(json.dumps(report))
                self.deny('git push origin develop', 'does not attest this exact complete candidate')
        external = self.workspace / 'external-report.json'
        external.write_text(json.dumps(valid))
        path.unlink()
        path.symlink_to(external)
        self.deny('git push origin develop', 'verification evidence is missing')
        self.assertEqual(json.loads(external.read_text()), valid)

    def test_canonical_native_boundary_rejects_chains_wrappers_and_quoted_executable(self):
        self.evidence()
        for command in ('git status && git push origin develop', "'git' push origin develop",
                        'command git push origin develop'):
            with self.subTest(command=command):
                reason = 'canonical executable command' if command.startswith(('git status', "'git'")) else 'native permission shapes'
                self.deny(command, reason)

    def test_codex_missing_wrong_version_and_nonprompt_rules_are_distinct_denials(self):
        self.native_rules()
        # Restrict PATH so an actual installed Codex cannot satisfy the fixture.
        isolated = self.workspace / 'isolated'
        isolated.mkdir()
        for name, executable in (('git', self.fakebin / 'git'), ('python3', sys.executable)):
            (isolated / name).symlink_to(executable)
        environment = {**self.environment, 'PATH': str(isolated)}
        self.environment = environment
        self.evidence()
        self.deny('git push origin develop', 'native Codex rule evaluator is unavailable', harness='codex')
        self.environment = {**environment, 'PATH': str(self.fakebin) + os.pathsep + str(isolated)}
        for version, decision, code, reason in (
                ('codex-cli 0.0.0', 'prompt', 0, 'outside the verified'),
                ('codex-cli 0.153.4', 'allow', 0, 'Native rules do not require approval'),
                ('codex-cli 0.153.4', 'prompt', 1, 'Native rules do not require approval')):
            with self.subTest(version=version, decision=decision, code=code):
                self.codex(version, decision, code)
                self.evidence()  # Bind the receipt to each actual changed fake client.
                self.deny('git push origin develop', reason, harness='codex')
        self.codex()
        self.evidence()
        self.allow('git push origin develop', harness='codex')
        self.deny('git push origin develop', 'execution mode/command shape lacks', harness='codex',
                  event={**self.event('git push origin develop'), 'permission_mode': 'bypassPermissions'})

    def test_native_permission_file_symlink_never_claims_trust(self):
        rules = self.native_rules()
        outside = self.workspace / 'rules'
        outside.write_bytes(rules.read_bytes())
        rules.unlink()
        rules.symlink_to(outside)
        self.commit()
        self.evidence()
        self.deny('git push origin develop', 'permission rules are missing or redirected', harness='codex')

    def test_deployment_readonly_target_mutation_and_valid_production_paths(self):
        for command in ('vercel inspect fixture', 'vercel env ls', 'vc --version'):
            self.allow(command)
        for command, reason in (('vercel deploy --target', 'Missing Vercel target value'),
                                ('vercel promote deployment', 'promotion/rollback'),
                                ('vercel rollback deployment', 'promotion/rollback'),
                                ('vercel remove fixture --prod', 'Unsupported Vercel mutation shape')):
            self.deny(command, reason)
        self.evidence()
        for command in ('vercel deploy --target production', 'vercel --prod', 'vc deploy --prod'):
            self.allow(command)
        result = self.execute('vercel deploy --prod')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.sentinel.read_text(), 'vercel executed')

    def test_release_shapes_refuse_unbound_or_missing_option_values(self):
        for command, reason in (('gh release create', 'one literal named version tag'),
                                ('gh release create random', 'one literal named version tag'),
                                ('gh release create v2.0.0 --title', 'requires a literal value'),
                                ('gh release create v2.0.0 --title --verify-tag', 'requires a literal value'),
                                ('gh release upload v2.0.0 asset', 'release mutations require'),
                                ('gh release edit v2.0.0 --draft=false', 'release mutations require')):
            self.deny(command, reason)

    def test_release_requires_integration_annotated_tag_and_matching_commit(self):
        command = self.release()
        self.evidence()
        self.git('checkout', '-qb', 'other')
        self.deny(command, 'completed integration checkout')
        self.git('checkout', 'develop')
        self.git('tag', '-d', 'v2.0.0')
        self.deny(command, 'existing annotated version tag')
        self.tag()
        self.commit()
        self.evidence()
        self.deny(command, 'release tag differs from the verified candidate')

    def test_git_global_directory_and_pager_options_resolve_local_pull(self):
        self.allow('git')
        self.allow('git --no-pager status')
        self.allow('git --paginate status')
        self.allow('git -C. pull --rebase')
        self.assertEqual(self.execute('git -C. pull --rebase').returncode, 0)
        self.assertEqual(self.sentinel.read_text(), 'git executed')

    def test_wrappers_chained_cwd_and_literal_only_segments(self):
        nested = self.project / 'nested'
        nested.mkdir()
        for command in ('command -- git status', 'exec -- git status', 'TEST=git',
                        'true && git status', 'git status;\n', 'cd nested && git status',
                        "bash -lc 'git status'", 'env -i -- git status'):
            self.allow(command)
        for command, reason in (('cd missing && git push origin develop', 'working directory does not exist'),
                                ('wrapper git push origin develop', 'Unsupported executable wrapper'),
                                ('npm run vercel', 'Package scripts hide'),
                                ('npx git push origin develop', 'Unsupported package wrapper'),
                                ('(git push origin develop)', 'Unsupported compound shell grouping')):
            self.deny(command, reason)

    def test_shell_parse_failures_block_before_any_transport(self):
        for command in ('git push origin develop\\', 'git push "develop',
                        'echo `git push origin develop', 'echo $(git push origin develop',
                        "cat <<'EOF'\ngit push origin develop\n"):
            with self.subTest(command=command):
                self.deny(command, 'Malformed policy-sensitive shell syntax')
        self.evidence()
        self.allow('git \\\nstatus # git push origin feature/comment\n')
        for inner in ('echo "text \'nested\'"; git push origin feature/work',
                      'echo $(printf nested); git push origin feature/work',
                      r'echo escaped\); git push origin feature/work',
                      '(git push origin feature/work)'):
            self.deny('echo $(' + inner + ')', 'BLOCKED / WHY:')
        command = 'git status'
        for _ in range(7):
            command = 'bash -c ' + shlex.quote(command)
        self.deny(command, 'exceed the supported parser depth')

    def test_telemetry_symlink_is_skipped_without_changing_the_policy_result(self):
        directory = self.project / '.rpi/local'
        directory.mkdir()
        outside = self.workspace / 'telemetry.txt'
        outside.write_text('owner sentinel\n')
        (directory / 'contract-events.jsonl').symlink_to(outside)
        self.allow('git pull --rebase')
        self.assertEqual(outside.read_text(), 'owner sentinel\n')

    def test_missing_candidate_runtime_dependency_uses_native_block_exit(self):
        runtime = self.workspace / 'runtime'
        runtime.mkdir()
        policy = runtime / 'rpi-policy.py'
        policy.write_bytes(test_policy.POLICY.read_bytes())
        self.evidence()
        result = subprocess.run([sys.executable, str(policy), '--harness', 'claude'],
                                input=json.dumps(self.event('git push origin develop')),
                                text=True, capture_output=True, env=self.environment, cwd=self.project)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('policy dependency is missing', result.stderr)
        self.assertFalse(self.sentinel.exists())


if __name__ == '__main__':
    unittest.main()
