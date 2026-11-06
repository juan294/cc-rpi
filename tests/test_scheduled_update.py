"""Opted-in scheduled updates bind source/target without launching a real model."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScheduledUpdateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rpi schedule ' & ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source $(touch NEVER_EXECUTED)"
        self.project = self.root / 'project'
        self.project.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        with (self.project / '.git/info/exclude').open('a') as exclude:
            exclude.write('\n.rpi/local/\n')
        engine = self.source / 'templates/scripts/rpi-distribution.py'
        engine.parent.mkdir(parents=True)
        engine.write_text('import json, os, sys\n'
            'with open(os.environ["FAKE_ENGINE_LOG"],"a") as log: log.write(json.dumps(sys.argv[1:])+"\\n")\n'
            'raise SystemExit(int(json.loads(os.environ.get("FAKE_ENGINE_CODES","{}")).get(sys.argv[1],0)))\n')
        for relative in ['templates/distribution.json', '.claude-plugin/plugin.json',
                         'generated/claude/skills/rpi-update/SKILL.md',
                         'generated/claude/skills/rpi-update/references/lifecycle-contract.md']:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}\n')
        self.cli = self.root / 'fake-claude'
        self.cli.write_text(f'#!{sys.executable}\n' +
            'import json, os, sys\n'
            'with open(os.environ["FAKE_CLI_LOG"],"a") as log: log.write(json.dumps({"argv":sys.argv[1:],"cwd":os.getcwd(),"home":os.environ.get("HOME")})+"\\n")\n'
            'probe = "Reply READY only" in " ".join(sys.argv)\n'
            'hold = os.environ.get("FAKE_CLI_HOLD")\n'
            'events = os.environ.get("FAKE_CLI_EVENTS")\n'
            'if events:\n'
            '    import time\n'
            '    with open(events, "a") as log: log.write("enter " + os.environ.get("FAKE_RUN_ID", "?") + "\\n")\n'
            '    time.sleep(float(os.environ.get("FAKE_CLI_PAUSE", "0.05")))\n'
            '    with open(events, "a") as log: log.write("exit " + os.environ.get("FAKE_RUN_ID", "?") + "\\n")\n'
            'if hold and probe:\n'
            '    import time\n'
            '    open(hold + ".pid", "w").write(str(os.getpid()))\n'
            '    open(hold + ".ready", "w").close()\n'
            '    deadline = time.time() + 20\n'
            '    while not os.path.exists(hold + ".release") and time.time() < deadline: time.sleep(0.05)\n'
            'print(os.environ.get("FAKE_CLI_PROBE_BODY", "READY") if probe else "Fake update result")\n'
            'raise SystemExit(int(os.environ.get("FAKE_CLI_PROBE_CODE" if probe else "FAKE_CLI_CODE", "0")))\n')
        self.cli.chmod(0o700)
        self.codex = self.root / 'fake-codex'
        self.codex.write_text(f'#!{sys.executable}\n' +
            'import json, os, sys\n'
            'with open(os.environ["FAKE_CODEX_LOG"],"a") as log: log.write(json.dumps({"argv":sys.argv[1:],"cwd":os.getcwd(),"prompt":sys.stdin.read(),"openai_api_key":os.environ.get("OPENAI_API_KEY"),"codex_api_key":os.environ.get("CODEX_API_KEY")})+"\\n")\n'
            'args = sys.argv[1:]\n'
            'open(args[args.index("--output-last-message") + 1], "w").write("" if os.environ.get("FAKE_CODEX_EMPTY") else "Fake Codex update result\\n")\n'
            'raise SystemExit(int(os.environ.get("FAKE_CODEX_CODE", "0")))\n')
        self.codex.chmod(0o700)
        self.env = {**os.environ, 'RPI_UPDATE_ENABLED': '1', 'CC_RPI_PATH': str(self.source),
                    'PATH': str(Path(sys.executable).parent) + os.pathsep + os.environ['PATH'],
                    'RPI_ROUTE': 'plugin', 'RPI_HARNESS': 'both',
                    'RPI_PROJECT_ROOT': str(self.project), 'CLAUDE_BIN': str(self.cli),
                    'CODEX_BIN': str(self.codex),
                    'FAKE_CLI_LOG': str(self.root / 'cli.jsonl'),
                    'FAKE_CODEX_LOG': str(self.root / 'codex.jsonl'),
                    'FAKE_ENGINE_LOG': str(self.root / 'engine.jsonl')}

    def run_launcher(self):
        return subprocess.run(['bash', str(ROOT / 'templates/scripts/cc-rpi-update-agent.sh')],
                              env=self.env, capture_output=True, text=True, timeout=10)

    def start_held_run(self, name='first', env=None):
        """A launcher run that parks inside its provider probe until the test releases it."""
        hold = self.root / ('hold-' + name)
        process = subprocess.Popen(['bash', str(ROOT / 'templates/scripts/cc-rpi-update-agent.sh')],
                                   env={**self.env, **(env or {}), 'FAKE_CLI_HOLD': str(hold)},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (process.kill() if process.poll() is None else None, process.communicate()))
        deadline = time.time() + 15
        while not Path(str(hold) + '.ready').exists():
            if process.poll() is not None:
                self.fail('held run exited early: ' + str(process.communicate()))
            self.assertLess(time.time(), deadline, 'held run never reached its provider probe')
            time.sleep(0.05)
        child = int(Path(str(hold) + '.pid').read_text())
        self.addCleanup(lambda: os.kill(child, signal.SIGKILL) if self.alive(child) else None)
        return process, hold, child

    @staticmethod
    def alive(pid):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def release(self, process, hold):
        Path(str(hold) + '.release').touch()
        out, err = process.communicate(timeout=20)
        return process.returncode, out, err

    @property
    def lock_file(self):
        return self.project / '.rpi/local/update-runs/launcher.lock'

    def probe_calls(self):
        return sum('Reply READY only' in ' '.join(call['argv']) for call in self.calls('cli'))

    def calls(self, kind):
        path = self.root / f'{kind}.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def enable_codex_skill(self):
        skill = self.source / 'generated/codex/skills/rpi-update'
        self.env['RPI_UPDATE_CODEX_SKILL_DIR'] = str(skill)
        for relative in ['SKILL.md', 'references/lifecycle-contract.md']:
            path = skill / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{}\n')
        return skill

    def test_requires_explicit_opt_in_before_any_cli_or_engine_work(self):
        self.env.pop('RPI_UPDATE_ENABLED')
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('RPI_UPDATE_ENABLED=1', result.stdout + result.stderr)
        self.assertEqual(self.calls('cli'), [])
        self.assertEqual(self.calls('engine'), [])

    def test_resolves_actual_plugin_workflow_and_preserves_native_permissions_and_home(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls('cli')
        self.assertEqual(len(calls), 2, 'one read-only quota probe then one native invocation')
        self.assertEqual(calls[0]['argv'][calls[0]['argv'].index('--tools') + 1], '')
        self.assertIn('--strict-mcp-config', calls[0]['argv'])
        argv = calls[1]['argv']
        self.assertEqual(argv[argv.index('--plugin-dir') + 1], str(self.source.resolve()))
        self.assertTrue(argv[argv.index('-p') + 1].startswith('/cc-rpi:rpi-update'))
        self.assertIn(str(self.project.resolve()), argv[argv.index('-p') + 1])
        self.assertEqual(argv[argv.index('--permission-mode') + 1], 'dontAsk')
        self.assertEqual(argv[argv.index('--permission-prompts') + 1], 'none')
        self.assertNotIn('bypassPermissions', argv)
        self.assertNotIn('--allowedTools', argv)
        self.assertEqual(calls[1]['home'], os.environ.get('HOME'))
        self.assertEqual(calls[1]['cwd'], str(self.project.resolve()))
        self.assertFalse((self.project / 'NEVER_EXECUTED').exists())
        self.assertEqual([call[0] for call in self.calls('engine')], ['validate','check-generated','check'])
        check = self.calls('engine')[-1]
        self.assertEqual(check[check.index('--target') + 1], str(self.project.resolve()))

    def test_missing_bundled_contract_blocks_before_native_invocation(self):
        (self.source / 'generated/claude/skills/rpi-update/references/lifecycle-contract.md').unlink()
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls('cli'), [])

    def test_direct_invocation_uses_existing_skill_without_loading_duplicate_plugin(self):
        self.env['RPI_ROUTE'] = 'direct'
        self.env['RPI_UPDATE_SKILL_DIR'] = str(self.source / 'generated/claude/skills/rpi-update')
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        argv = self.calls('cli')[1]['argv']
        self.assertNotIn('--plugin-dir', argv)
        self.assertTrue(argv[argv.index('-p') + 1].startswith('/rpi-update'))

    def test_invalid_source_preflight_preserves_failure_without_native_invocation(self):
        self.env['FAKE_ENGINE_CODES'] = json.dumps({'check-generated': 9})
        result = self.run_launcher()
        self.assertEqual(result.returncode, 9)
        self.assertEqual(self.calls('cli'), [])

    def test_native_failure_is_not_hidden_by_passing_engine_check(self):
        self.env['FAKE_CLI_CODE'] = '7'
        result = self.run_launcher()
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(self.calls('cli')), 2)
        self.assertEqual(self.calls('engine')[-1][0], 'check')
        self.assertIn('native_exit=7', result.stdout)

    def test_native_success_does_not_hide_remaining_installation_drift(self):
        self.env['FAKE_ENGINE_CODES'] = json.dumps({'check': 2})
        result = self.run_launcher()
        self.assertEqual(result.returncode, 2)
        self.assertIn('check_exit=2', result.stdout)

    def test_target_must_be_explicit_git_root_and_reports_cannot_escape(self):
        self.env['RPI_PROJECT_ROOT'] = str(self.project / 'nested')
        (self.project / 'nested').mkdir()
        self.assertNotEqual(self.run_launcher().returncode, 0)
        self.assertEqual(self.calls('cli'), [])
        self.env['RPI_PROJECT_ROOT'] = str(self.project)
        (self.project / '.rpi').symlink_to(self.root, target_is_directory=True)
        self.assertNotEqual(self.run_launcher().returncode, 0)
        self.assertEqual(self.calls('cli'), [])
        self.assertFalse((self.root / 'local/update-runs').exists())

    def test_private_outputs_must_be_ignored_before_native_run_without_editing_ignore_rules(self):
        exclude = self.project / '.git/info/exclude'
        exclude.write_text('# Existing owner exclusions\nowner-local.txt\n')
        gitignore = self.project / '.gitignore'
        for rules in ['# Keep project ignores\n',
                      '.rpi/local/update-runs/run.*/report.md\n.rpi/local/update-runs/run.*/check.json\n',
                      '.rpi/local/update-runs/run.*/*\n!.rpi/local/update-runs/run.*/report.md\n']:
            gitignore.write_text(rules)
            before = {path.relative_to(self.project): path.read_bytes() for path in self.project.rglob('*') if path.is_file()}
            completed = self.run_launcher()
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn('ignored', completed.stdout + completed.stderr)
            self.assertEqual(self.calls('cli'), [])
            after = {path.relative_to(self.project): path.read_bytes() for path in self.project.rglob('*') if path.is_file()}
            self.assertEqual(after, before)
            self.assertFalse((self.project / '.rpi').exists())

    def test_quota_preflight_switches_to_codex_without_running_claude_update(self):
        self.env['FAKE_CLI_PROBE_BODY'] = "You've hit your weekly limit"
        self.env['FAKE_CLI_PROBE_CODE'] = '1'
        self.env['OPENAI_API_KEY'] = 'wrong-billing'
        self.env['CODEX_API_KEY'] = 'wrong-billing'
        skill = self.enable_codex_skill()
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls('cli')), 1)
        codex = self.calls('codex')
        self.assertEqual(len(codex), 1)
        self.assertEqual(codex[0]['openai_api_key'], None)
        self.assertEqual(codex[0]['codex_api_key'], None)
        args = codex[0]['argv']
        self.assertEqual(args[:2], ['exec', '--ephemeral'])
        self.assertIn('sandbox_workspace_write.network_access=true', args)
        self.assertIn(str(self.project.resolve()), args)
        self.assertIn(str(skill / 'SKILL.md'), codex[0]['prompt'])
        self.assertEqual([call[0] for call in self.calls('engine')], ['validate', 'check-generated', 'check'])

    def test_zero_exit_quota_message_also_uses_codex(self):
        self.env['FAKE_CLI_PROBE_BODY'] = "You've hit your weekly limit"
        self.enable_codex_skill()
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(self.calls('cli')), 1)
        self.assertEqual(len(self.calls('codex')), 1)

    def test_codex_failure_is_not_hidden_by_passing_installation_check(self):
        self.env['FAKE_CLI_PROBE_BODY'] = 'rate_limit_error'
        self.env['FAKE_CLI_PROBE_CODE'] = '1'
        self.env['FAKE_CODEX_CODE'] = '7'
        self.enable_codex_skill()
        result = self.run_launcher()
        self.assertEqual(result.returncode, 7)
        self.assertEqual(len(self.calls('codex')), 1)
        self.assertEqual(self.calls('engine')[-1][0], 'check')

    def test_empty_codex_final_report_fails(self):
        self.env['FAKE_CLI_PROBE_BODY'] = 'rate_limit_error'
        self.env['FAKE_CLI_PROBE_CODE'] = '1'
        self.env['FAKE_CODEX_EMPTY'] = '1'
        self.enable_codex_skill()
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('native_exit=1', result.stdout)

    def test_changed_installed_codex_skill_blocks_before_fallback(self):
        self.env['FAKE_CLI_PROBE_BODY'] = 'rate_limit_error'
        self.env['FAKE_CLI_PROBE_CODE'] = '1'
        source_skill = self.enable_codex_skill()
        installed = self.root / 'installed-codex-skill'
        shutil.copytree(source_skill, installed)
        (installed / 'SKILL.md').write_text('changed owner skill\n')
        self.env['RPI_UPDATE_CODEX_SKILL_DIR'] = str(installed)
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('differ from selected source', result.stdout + result.stderr)
        self.assertEqual(self.calls('codex'), [])

    def test_nonquota_probe_failure_blocks_without_mutating_update_or_fallback(self):
        self.env['FAKE_CLI_PROBE_BODY'] = 'permission denied'
        self.env['FAKE_CLI_PROBE_CODE'] = '1'
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls('cli')), 1)
        self.assertEqual(self.calls('codex'), [])

    def test_a_second_run_during_a_held_lock_is_blocked_before_any_provider_call(self):
        first, hold, _ = self.start_held_run()
        for _ in range(2):
            second = self.run_launcher()
            self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
            message = second.stderr.strip()
            self.assertTrue(message.startswith('BLOCKED / WHY: another update run for this project is active'), message)
            self.assertIn(str(self.lock_file), message)
            self.assertIn('/ FIX: wait for it to finish', message)
            self.assertIn('lsof', message)
        self.assertEqual(self.probe_calls(), 1, 'only the holder reached a provider')
        self.assertEqual(self.calls('codex'), [])
        self.assertEqual(len(list((self.project / '.rpi/local/update-runs').glob('run.*'))), 1,
                         'refused runs create no report directory')
        code, out, err = self.release(first, hold)
        self.assertEqual(code, 0, out + err)
        again = self.run_launcher()  # The kernel released the lock when the holder exited.
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)

    def test_ten_concurrent_runs_repeated_admit_one_provider_session_at_a_time(self):
        script = str(ROOT / 'templates/scripts/cc-rpi-update-agent.sh')
        for attempt in range(20):
            events = self.root / ('events-%d.log' % attempt)
            processes = [subprocess.Popen(['bash', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                          env={**self.env, 'FAKE_CLI_EVENTS': str(events), 'FAKE_RUN_ID': 'run%d' % number,
                                               'FAKE_CLI_PAUSE': '0.15'}) for number in range(10)]
            codes = []
            for process in processes:
                process.communicate(timeout=60)
                codes.append(process.returncode)
            self.assertEqual(set(codes) - {0, 1}, set(), codes)
            tokens = events.read_text().split()
            log = list(zip(tokens[0::2], tokens[1::2]))
            spans = {}
            for position, (kind, run) in enumerate(log):
                spans.setdefault(run, [position, position])[1] = position
            ordered = sorted(spans.values())
            for earlier, later in zip(ordered, ordered[1:]):
                self.assertLess(earlier[1], later[0], 'provider sessions overlapped: %s' % log)
            self.assertEqual(len(spans), codes.count(0), (attempt, codes, log))
            for run in spans:  # An admitted run made both provider calls (probe and update).
                self.assertEqual([kind for kind, other in log if other == run], ['enter', 'exit'] * 2)
            self.assertTrue(codes.count(0) >= 1)

    def test_killing_the_launcher_keeps_the_lock_until_its_provider_child_exits(self):
        first, hold, child = self.start_held_run()
        first.kill()
        first.communicate(timeout=10)
        self.assertTrue(self.alive(child))
        blocked = self.run_launcher()
        self.assertEqual(blocked.returncode, 1, blocked.stdout + blocked.stderr)
        self.assertIn('another update run for this project is active', blocked.stderr)
        Path(str(hold) + '.release').touch()
        deadline = time.time() + 15
        while self.alive(child):
            self.assertLess(time.time(), deadline, 'the provider child never exited')
            time.sleep(0.05)
        proceed = self.run_launcher()
        self.assertEqual(proceed.returncode, 0, proceed.stdout + proceed.stderr)

    def test_killing_the_launcher_and_its_child_frees_the_lock_at_once(self):
        first, hold, child = self.start_held_run()
        os.kill(child, signal.SIGKILL)
        first.kill()
        first.communicate(timeout=10)
        deadline = time.time() + 15
        while self.alive(child):
            self.assertLess(time.time(), deadline)
            time.sleep(0.05)
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sequential_runs_after_normal_exit_and_failures_proceed_immediately(self):
        for env in ({}, {'FAKE_CLI_CODE': '7'}, {'FAKE_ENGINE_CODES': json.dumps({'check': 2})}):
            self.env.update(env)
            first = self.run_launcher()
            self.assertIn(first.returncode, (0, 7, 2), first.stdout + first.stderr)
            self.assertNotIn('another update run', first.stderr)
            for key in env:
                del self.env[key]
        self.env['FAKE_CLI_PROBE_BODY'] = 'rate_limit_error'
        self.env['FAKE_CLI_PROBE_CODE'] = '1'
        self.env['CODEX_BIN'] = str(self.root / 'missing-codex')
        blocked = self.run_launcher()
        self.assertIn('Codex is unavailable', blocked.stderr)
        for key in ('FAKE_CLI_PROBE_BODY', 'FAKE_CLI_PROBE_CODE'):
            del self.env[key]
        self.env['CODEX_BIN'] = str(self.codex)
        self.assertEqual(self.run_launcher().returncode, 0)

    def test_time_zone_differences_do_not_matter(self):
        first, hold, _ = self.start_held_run(env={'TZ': 'UTC'})
        self.env['TZ'] = 'America/Los_Angeles'
        second = self.run_launcher()
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
        self.assertIn('another update run for this project is active', second.stderr)
        self.assertEqual(self.probe_calls(), 1)

    def test_a_path_without_ps_changes_nothing(self):
        tools = self.root / 'tools-without-ps'
        tools.mkdir()
        git = Path(shutil.which('git'))
        for directory in (Path('/bin'), Path('/usr/bin'), git.parent):
            for entry in directory.iterdir():
                if entry.name == 'ps' or (directory == git.parent and entry.name != 'git') or (tools / entry.name).exists():
                    continue
                (tools / entry.name).symlink_to(entry)
        self.assertIsNone(shutil.which('ps', path=str(tools)))
        self.env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + str(tools)
        first, hold, _ = self.start_held_run()
        second = self.run_launcher()
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
        self.assertIn('another update run for this project is active', second.stderr)
        self.release(first, hold)
        self.assertEqual(self.run_launcher().returncode, 0)

    def test_an_inherited_held_marker_is_not_trusted(self):
        # A copied environment from some other process must neither skip the lock nor loop.
        first, hold, _ = self.start_held_run()
        self.env.update({'RPI_UPDATE_LOCK_OWNER': str(first.pid), 'RPI_UPDATE_LOCK_FD': '9'})
        second = self.run_launcher()
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
        self.assertIn('another update run for this project is active', second.stderr)
        self.assertEqual(self.probe_calls(), 1)

    def test_lock_file_that_cannot_be_opened_fails_fast_with_the_os_error(self):
        runs = self.project / '.rpi/local/update-runs'
        runs.mkdir(parents=True)
        if os.geteuid() != 0:
            runs.chmod(0o555)
            self.addCleanup(runs.chmod, 0o755)
            result = self.run_launcher()
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertTrue(result.stderr.startswith('BLOCKED / WHY: cannot open the launcher lock'), result.stderr)
            self.assertIn('Permission denied', result.stderr)
            self.assertEqual(self.calls('cli'), [])
            runs.chmod(0o755)
        self.lock_file.mkdir()
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('cannot open the launcher lock', result.stderr)
        self.assertIn('Is a directory', result.stderr)
        self.lock_file.rmdir()
        self.lock_file.symlink_to(self.root / 'elsewhere')
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('cannot open the launcher lock', result.stderr)
        self.assertFalse((self.root / 'elsewhere').exists(), 'a link is never followed')
        self.assertEqual(self.calls('cli'), [])

    def test_lock_area_must_be_ignored_before_any_provider_call(self):
        (self.project / '.git/info/exclude').write_text('')
        (self.project / '.gitignore').write_text('.rpi/local/update-runs/run.*/*\n')
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('launcher.lock', result.stderr)
        self.assertEqual(self.calls('cli'), [])
        self.assertFalse((self.project / '.rpi').exists())


if __name__ == '__main__':
    unittest.main()
