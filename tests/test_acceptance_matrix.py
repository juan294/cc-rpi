"""Final-package acceptance across disposable adopter types and native layouts.

These are filesystem/CLI contracts, not native load/invoke/enforce evidence.
One extracted read-only package and one upstream variant serve all nine cells.
No native clients, hosted transports, scheduler jobs or actual adopters run.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = 'templates/skills/rpi-research/references/research-contract.md'
NATIVE_ROOTS = {'claude': '.claude/skills', 'codex': '.agents/skills'}


def files(root, *, local=True):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and '.git' not in p.relative_to(root).parts
            and (local or not p.relative_to(root).as_posix().startswith('.rpi/local/'))}


def write(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


class AcceptanceMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="rpi matrix Ü '&' ")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.workspace = Path(cls.temporary.name).resolve()
        cls.package = cls.workspace / 'extracted package'
        source = Path(os.environ.get('RPI_PACKAGE_TEST_SOURCE', ROOT / 'generated/codex'))
        shutil.copytree(source, cls.package)
        cls.source = cls.package / 'runtime'
        cls.upstream = cls.workspace / 'upstream runtime'
        shutil.copytree(cls.source, cls.upstream)
        contract = cls.upstream / RESOURCE
        original = contract.read_text()
        cls.original_heading = original.splitlines()[0]
        cls.upstream_heading = '# Revised upstream research evidence contract'
        contract.write_text(original.replace(cls.original_heading, cls.upstream_heading, 1))
        cls.engine = cls.source / 'templates/scripts/rpi-distribution.py'
        cls.manifest = json.loads((cls.source / 'templates/distribution.json').read_text())
        cls.package_before = files(cls.package)
        cls.upstream_before = files(cls.upstream)
        cls.remote_sentinel = cls.workspace / 'unexpected hosted action'
        cls.literal_sentinel = cls.workspace / 'literal-marker-must-not-execute'
        binary = cls.workspace / 'bin'
        binary.mkdir()
        real_git = shutil.which('git')
        if not real_git:
            raise RuntimeError('Git is required for the acceptance fixtures')
        shim = ('#!' + sys.executable + '\nimport os, pathlib, sys\n'
                'args = sys.argv[1:]\n'
                "if pathlib.Path(sys.argv[0]).name != 'git' or any(x in "
                "{'push','fetch','pull','clone','ls-remote','submodule'} for x in args):\n"
                f'    pathlib.Path({str(cls.remote_sentinel)!r}).write_text("unexpected hosted command")\n'
                '    raise SystemExit(97)\n'
                f'os.execv({real_git!r}, [{real_git!r}, *args])\n')
        for name in ('git', 'gh', 'vercel', 'claude', 'codex', 'launchctl', 'crontab'):
            path = write(binary, name, shim)
            path.chmod(0o755)
        literal = write(binary, 'literal-marker-must-not-execute',
                        '#!' + sys.executable + '\nfrom pathlib import Path\n'
                        + f'Path({str(cls.literal_sentinel)!r}).write_text("literal argument executed")\n')
        literal.chmod(0o755)
        cls.environment = {**os.environ, 'PATH': str(binary) + os.pathsep + os.environ.get('PATH', ''),
                           'PYTHONDONTWRITEBYTECODE': '1', 'GIT_CONFIG_NOSYSTEM': '1',
                           'GIT_CONFIG_GLOBAL': os.devnull}

    @classmethod
    def tearDownClass(cls):
        if files(cls.package) != cls.package_before or files(cls.upstream) != cls.upstream_before:
            raise AssertionError('acceptance mutated the shared package sources')
        if cls.remote_sentinel.exists() or cls.literal_sentinel.exists():
            raise AssertionError('a hosted/native/scheduler command or literal argument executed')

    def invoke(self, target, *arguments, expected=0):
        result = subprocess.run([sys.executable, str(self.engine), *map(str, arguments)],
                                cwd=target, env=self.environment, capture_output=True,
                                text=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def git(self, target, *arguments):
        result = subprocess.run(['git', '-C', str(target), *arguments], env=self.environment,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def fixture(self, kind, harness):
        # Literal shell metacharacters travel through subprocess argv only.
        target = self.workspace / (kind + ' ' + harness + " ' & $(literal-marker-must-not-execute)")
        target.mkdir()
        initial_branch = 'develop' if kind == 'application' else 'main'
        self.git(target, 'init', '-q', '-b', initial_branch)
        facts = '# Adopter\n\nPreserve the project-owned timezone and tenant rules.\n'
        write(target, 'AGENTS.md', facts)
        write(target, 'CLAUDE.md', '@AGENTS.md\n\nUse the existing synthetic fixture account.\n')
        write(target, 'README.md', '# Disposable adopter\n')
        write(target, 'docs/plans/owner-plan.md', '# Approved owner plan\nKeep the original acceptance decisions.\n')
        settings = {'env': {'SYNTHETIC_PRIVATE_TOKEN': 'DO_NOT_PUBLISH'},
                    'permissions': {'deny': ['Read(private-fixture/**)']},
                    'owner_extension': {'ordering': ['keep', 'exactly']}}
        if kind == 'customized-v1':
            settings['env']['CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS'] = '1'
            write(target, '.claude/cc-rpi-sync.json', '{"version":"1.29.0","commit":"unavailable-base"}\n')
            write(target, '.claude/commands/plan.md', '# Owner custom plan\nKeep this unproven legacy alias.\n')
            write(target, '.claude/commands/release.md', '# Owner release\nAll eight maneuvers must PASS; N/A is prohibited.\n')
            write(target, '.Codex/commands/plan.md', '# Partial import with owner notes\n')
            write(target, '.codex/skills/source-command-plan/SKILL.md',
                  '---\nname: source-command-plan\ndescription: Owner partial import.\n---\nPreserve this import.\n')
            write(target, 'docs/runbooks/release.md', '# Release charter\nAll eight maneuvers must PASS; N/A is prohibited.\n')
        elif kind == 'application':
            write(target, 'src/app.py', 'def greeting(name):\n    return "Hello " + name\n')
            write(target, 'tests/test_app.py', 'from src.app import greeting\n\ndef test_greeting():\n    assert greeting("fixture") == "Hello fixture"\n')
            write(target, '.github/workflows/local-fixture.yml',
                  'name: Synthetic deployment declarations\non:\n  push:\n    branches: [develop, main]\n'
                  'jobs:\n  fixture:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo synthetic-only\n')
            write(target, 'docs/deployment.md', '# Topology\nDevelop integrates; main production publication needs explicit authority.\nNo Vercel Previews.\n')
        write(target, '.claude/settings.json', json.dumps(settings, indent=2) + '\n')
        write(target, '.codex/config.toml', 'owner_private_setting = "SYNTHETIC_KEEP"\n')
        self.git(target, 'add', '.')
        self.git(target, '-c', 'user.name=RPI Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'Synthetic adopter baseline')
        if kind == 'application':
            self.git(target, 'branch', 'main')
        return target, settings, files(target), self.git(target, 'rev-parse', 'HEAD')

    def plan(self, target, harness, action='install', *, source=None, domains=('git-workflow',),
             capabilities=True, expected=0):
        self.counter += 1
        artifact = self.workspace / 'plans' / (target.name + '-' + str(self.counter) + '.json')
        artifact.parent.mkdir(exist_ok=True)
        args = ['plan', '--source', source or self.source, '--target', target, '--harness', harness,
                '--route', 'direct', '--action', action, '--output', artifact]
        for domain in domains:
            args.extend(['--domain', domain])
        if capabilities and action != 'detach':
            for component in (['config:claude-policy'] if harness == 'claude' else
                              ['config:codex-hooks', 'resource:codex-permissions'] if harness == 'codex' else
                              ['config:claude-policy', 'config:codex-hooks', 'resource:codex-permissions']):
                args.extend(['--allow-capabilities', component])
        self.invoke(target, *args, expected=expected)
        return json.loads(artifact.read_text()), artifact

    def apply(self, target, artifact, expected=0):
        return self.invoke(target, 'apply', '--plan', artifact, expected=expected)

    def assert_owner_preserved(self, target, original, settings, head):
        for name, data in original.items():
            if name in ('AGENTS.md', 'CLAUDE.md', '.claude/settings.json'):
                continue
            self.assertEqual((target / name).read_bytes(), data, name)
        for name in ('AGENTS.md', 'CLAUDE.md'):
            for line in original[name].decode().splitlines():
                if line.strip():
                    self.assertIn(line, (target / name).read_text(), name)
        current = json.loads((target / '.claude/settings.json').read_text())
        for key in ('env', 'owner_extension'):
            self.assertEqual(current[key], settings[key])
        self.assertIn('Read(private-fixture/**)', current['permissions']['deny'])
        self.assertEqual(self.git(target, 'rev-parse', 'HEAD'), head)
        self.assertFalse((target / 'scripts/agents').exists())
        self.assertFalse((target / 'Library/LaunchAgents').exists())
        self.assertFalse(self.remote_sentinel.exists())
        self.assertFalse(self.literal_sentinel.exists())

    def assert_layout(self, target, harness, *, webmcp=False):
        selected = set(NATIVE_ROOTS) if harness == 'both' else {harness}
        state = json.loads((target / '.rpi/manifest.json').read_text())
        self.assertEqual(set(state['installations']), selected)
        owned_paths = {entry['destination'] for entry in state['entries']}
        self.assertFalse(owned_paths & {'.claude/commands/plan.md', '.claude/commands/status.md'})
        for native, directory in NATIVE_ROOTS.items():
            skills = target / directory
            if native not in selected:
                self.assertFalse(skills.exists())
                continue
            self.assertTrue((skills / 'rpi-plan/SKILL.md').is_file())
            self.assertFalse((skills / 'plan/SKILL.md').exists())
            self.assertFalse((skills / 'status/SKILL.md').exists())
            self.assertEqual((skills / 'webmcp/SKILL.md').exists(), webmcp)
            for component in self.manifest['components']:
                if component['kind'] != 'skill' or component['scope'] != 'project':
                    continue
                if component.get('category') == 'domain' and component['name'] not in {'git-workflow', *(['webmcp'] if webmcp else [])}:
                    continue
                if native not in component['harnesses']:
                    continue
                self.assertTrue((skills / component['name'] / 'SKILL.md').is_file(), component['name'])
                for resource in component.get('resources', []):
                    source = (self.source / component['source'] / resource if isinstance(resource, str)
                              else self.source / resource['source'])
                    destination = resource if isinstance(resource, str) else resource['destination']
                    self.assertEqual((skills / component['name'] / destination).read_bytes(), source.read_bytes())
        self.assertIn(b'.rpi/rules/testing.md', (target / 'AGENTS.md').read_bytes())

    def exercise(self, kind, harness):
        self.counter = 0
        target, settings, original, head = self.fixture(kind, harness)
        selected = list(NATIVE_ROOTS) if harness == 'both' else [harness]
        # Unknown same-name native skills cannot become owned by filename.
        collision = write(target, NATIVE_ROOTS[selected[0]] + '/rpi-plan/SKILL.md', '# Owner collision\n')
        before = files(target)
        plan, artifact = self.plan(target, harness, expected=2)
        self.assertEqual(plan['status'], 'conflict')
        self.apply(target, artifact, expected=2)
        self.assertEqual(files(target), before)
        collision.unlink()
        collision.parent.rmdir()
        # Native settings changes require the explicit scoped setup choice.
        plan, artifact = self.plan(target, harness, capabilities=False, expected=2)
        self.assertEqual(plan['status'], 'conflict')
        self.apply(target, artifact, expected=2)
        self.assert_owner_preserved(target, original, settings, head)
        plan, artifact = self.plan(target, harness)
        self.assertEqual(plan['status'], 'ready')
        self.apply(target, artifact)
        self.assert_layout(target, harness)
        self.assert_owner_preserved(target, original, settings, head)
        if kind == 'customized-v1':
            self.assertTrue(any(item['destination'] == '.claude/commands/plan.md' for item in plan['retained']))
        # Read-only checks and same-source updates are genuinely no-op.
        before = files(target)
        self.invoke(target, 'check', '--source', self.source, '--target', target, '--harness', harness, '--route', 'direct')
        self.assertEqual(files(target), before)
        plan, artifact = self.plan(target, harness, 'update')
        self.assertEqual(plan['status'], 'noop')
        self.apply(target, artifact)
        self.assertEqual(files(target), before)
        # Select and then remove an actual optional module; keep other bytes/facts.
        plan, artifact = self.plan(target, harness, 'update', domains=('git-workflow', 'webmcp'))
        self.apply(target, artifact)
        self.assert_layout(target, harness, webmcp=True)
        plan, artifact = self.plan(target, harness, 'update')
        self.apply(target, artifact)
        self.assert_layout(target, harness)
        # Source-only update replaces the complete reachable resource.
        plan, artifact = self.plan(target, harness, 'update', source=self.upstream)
        self.apply(target, artifact)
        resource_paths = [target / NATIVE_ROOTS[n] / 'rpi-research/references/research-contract.md' for n in selected]
        for path in resource_paths:
            self.assertEqual(path.read_bytes(), (self.upstream / RESOURCE).read_bytes())
        # Competing edits of the same line must conflict before any write.
        changed = resource_paths[0]
        changed.write_text(changed.read_text().replace(self.upstream_heading, '# Local owner research contract', 1))
        before = files(target)
        plan, artifact = self.plan(target, harness, 'update', expected=2)
        self.assertTrue(any(item['destination'] == changed.relative_to(target).as_posix() for item in plan['conflicts']))
        self.apply(target, artifact, expected=2)
        self.assertEqual(files(target), before)
        # Local-only customization survives update and both detach calls.
        changed.write_bytes((self.upstream / RESOURCE).read_bytes() + b'\nOwner local extension must survive.\n')
        plan, artifact = self.plan(target, harness, 'update', source=self.upstream)
        self.apply(target, artifact)
        retained_resource = changed.read_bytes()
        self.assertIn(b'Owner local extension must survive.', retained_resource)
        self.assert_owner_preserved(target, original, settings, head)
        plan, artifact = self.plan(target, harness, 'detach', source=self.upstream)
        self.apply(target, artifact)
        self.assertEqual(changed.read_bytes(), retained_resource)
        self.assert_owner_preserved(target, original, settings, head)
        detached_settings = json.loads((target / '.claude/settings.json').read_text())
        # Entry ownership does not authorize deleting a mixed parent object;
        # empty native containers may remain after all managed entries are gone.
        if 'claude' in selected:
            self.assertEqual(detached_settings['permissions'].pop('ask', []), [])
            for events in detached_settings.pop('hooks', {}).values():
                self.assertEqual(events, [])
        self.assertEqual(detached_settings, settings)
        for native in selected:
            self.assertFalse((target / NATIVE_ROOTS[native] / 'rpi-research/SKILL.md').exists())
        before = files(target)
        plan, artifact = self.plan(target, harness, 'detach', source=self.upstream)
        self.assertEqual(plan['status'], 'noop')
        self.apply(target, artifact)
        self.assertEqual(files(target), before)

    def test_empty_main_claude(self):
        self.exercise('empty-main', 'claude')

    def test_empty_main_codex(self):
        self.exercise('empty-main', 'codex')

    def test_empty_main_both(self):
        self.exercise('empty-main', 'both')

    def test_customized_v1_claude(self):
        self.exercise('customized-v1', 'claude')

    def test_customized_v1_codex(self):
        self.exercise('customized-v1', 'codex')

    def test_customized_v1_both(self):
        self.exercise('customized-v1', 'both')

    def test_develop_main_claude(self):
        self.exercise('application', 'claude')

    def test_develop_main_codex(self):
        self.exercise('application', 'codex')

    def test_develop_main_both(self):
        self.exercise('application', 'both')


if __name__ == '__main__':
    unittest.main()
