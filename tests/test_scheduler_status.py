"""Read-only scheduler reporting uses a fake native seam and no owner writes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SchedulerStatusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='rpi scheduler status ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        scripts = self.root / 'project/scripts/agents'
        scripts.mkdir(parents=True)
        self.script = scripts / 'install-agents.sh'
        shutil.copyfile(ROOT / 'templates/scripts/agents/install-agents.sh', self.script)
        (scripts / 'daily-agent.sh').write_text('#!/bin/bash\n# SCHEDULE: daily 03:00\n')
        self.calls = self.root / 'calls.jsonl'
        self.state = self.root / 'query.json'
        self.state.write_text(json.dumps({'exit': 0, 'stdout': 'PID\tStatus\tLabel\n'}))
        binary = self.root / 'bin'
        binary.mkdir()
        seam = ('#!' + sys.executable + '\nimport json, pathlib, sys\n'
                f'calls = pathlib.Path({str(self.calls)!r})\n'
                'with calls.open("a") as handle:\n'
                '    handle.write(json.dumps(sys.argv) + "\\n")\n'
                'if pathlib.Path(sys.argv[0]).name != "launchctl":\n'
                '    raise SystemExit(98)\n'
                f'value = json.loads(pathlib.Path({str(self.state)!r}).read_text())\n'
                'print(value.get("stdout", ""), end="")\n'
                'print(value.get("stderr", ""), end="", file=sys.stderr)\n'
                'raise SystemExit(value["exit"])\n')
        for name in ('launchctl', 'mkdir', 'rm'):
            executable = binary / name
            executable.write_text(seam)
            executable.chmod(0o755)
        self.environment = {**os.environ, 'PATH': str(binary) + os.pathsep + os.environ.get('PATH', '')}

    def invoke(self, *args, without_home=False):
        environment = dict(self.environment)
        if without_home:
            environment.pop('HOME', None)
        return subprocess.run(['bash', str(self.script), *args], env=environment,
                              capture_output=True, text=True, timeout=10)

    def assert_query_once(self):
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual([call[1:] for call in calls], [['list']])
        self.assertEqual(Path(calls[0][0]).name, 'launchctl')

    def test_help_and_discovery_need_no_home_or_scheduler(self):
        for option in ('--help', '--list'):
            with self.subTest(option=option):
                result = self.invoke(option, without_home=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Usage:' if option == '--help' else 'daily-agent', result.stdout)
                self.assertFalse(self.calls.exists())

    def test_failed_query_is_unknown_and_preserves_native_diagnostic(self):
        self.state.write_text(json.dumps({'exit': 77, 'stderr': 'scheduler connection unavailable\n'}))
        result = self.invoke('--status')
        self.assertEqual(result.returncode, 77, result.stdout + result.stderr)
        self.assertIn('UNKNOWN', result.stdout + result.stderr)
        self.assertIn('scheduler connection unavailable', result.stderr)
        self.assertNotIn('NOT LOADED', result.stdout)
        self.assert_query_once()

    def test_successful_inventory_confirms_absence_without_home(self):
        result = self.invoke('--status', without_home=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('NOT LOADED', result.stdout)
        self.assert_query_once()

    def test_loaded_status_uses_one_snapshot_and_preserves_signal_exit(self):
        self.state.write_text(json.dumps({'exit': 0, 'stdout':
            'PID\tStatus\tLabel\n-\t-15\tcom.project.daily-agent\n123\t0\tcom.unrelated.job\n'}))
        result = self.invoke('--status')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('LOADED (last exit: -15)', result.stdout)
        self.assert_query_once()

    def test_all_agents_share_one_inventory_snapshot(self):
        (self.script.parent / 'weekly-agent.sh').write_text('#!/bin/bash\n# SCHEDULE: weekly monday 06:30\n')
        self.state.write_text(json.dumps({'exit': 0, 'stdout':
            'PID\tStatus\tLabel\n-\t0\tcom.project.daily-agent\n'}))
        result = self.invoke('--status')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('LOADED (last exit: 0)', result.stdout)
        self.assertIn('NOT LOADED', result.stdout)
        self.assertIn('weekly-agent', result.stdout)
        self.assert_query_once()

    def test_mutation_without_home_fails_before_scheduler_or_directory_writes(self):
        for arguments in ((), ('--unload',)):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments, without_home=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('requires an absolute HOME', result.stderr)
                self.assertFalse(self.calls.exists())

    def test_malformed_successful_query_cannot_claim_absence(self):
        self.state.write_text(json.dumps({'exit': 0, 'stdout': 'unexpected native response\n'}))
        result = self.invoke('--status')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('UNKNOWN', result.stdout + result.stderr)
        self.assertNotIn('NOT LOADED', result.stdout)
        self.assert_query_once()

    def test_unknown_or_trailing_arguments_never_reach_mutation(self):
        for arguments in (('--state-root', str(self.root / 'ignored')), ('--bogus',),
                          ('--status', '--state-root', str(self.root)), ('--help', 'extra')):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('Usage:', result.stderr)
                self.assertFalse(self.calls.exists(), 'invalid input reached a scheduler/filesystem command')

    def test_printed_uninstall_command_survives_copy_from_a_hostile_path(self):
        # A real install needs real mkdir/rm, so only launchctl is faked here, and
        # HOME is redirected so no owner scheduler location is ever written.
        home = self.root / 'home'
        (home / 'Library/LaunchAgents').mkdir(parents=True)
        binary = self.root / 'bin-scheduler-only'
        binary.mkdir()
        shutil.copyfile(self.root / 'bin/launchctl', binary / 'launchctl')
        (binary / 'launchctl').chmod(0o755)
        scripts = self.root / "parent path ' & literal/project/scripts/agents"
        scripts.mkdir(parents=True)
        script = scripts / 'install-agents.sh'
        shutil.copyfile(ROOT / 'templates/scripts/agents/install-agents.sh', script)
        (scripts / 'daily-agent.sh').write_text('#!/bin/bash\n# SCHEDULE: daily 03:00\n')
        environment = {**os.environ, 'HOME': str(home),
                       'PATH': str(binary) + os.pathsep + os.environ.get('PATH', '')}
        installed = subprocess.run(['bash', str(script)], env=environment,
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertTrue(list((home / 'Library/LaunchAgents').glob('*.plist')))
        printed = [line.strip() for line in installed.stdout.splitlines()
                   if 'install-agents.sh' in line and '--unload' in line]
        self.assertEqual(len(printed), 1, installed.stdout)
        # Naming the script is not enough -- the printed line must survive copy/paste.
        copied = subprocess.run(['bash', '-c', printed[0]], env=environment,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(copied.returncode, 0, copied.stdout + copied.stderr)
        self.assertIn('Unloading', copied.stdout)
        self.assertFalse(list((home / 'Library/LaunchAgents').glob('*.plist')))


if __name__ == '__main__':
    unittest.main()
