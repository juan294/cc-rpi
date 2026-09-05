"""Exercise only extracted package entrypoints, including optional OS isolation.

Normal CI needs Python alone. Required release isolation additionally runs:
RPI_PACKAGE_TEST_IMAGE=cc-rpi-codex-native:0.153.4 python3 -m unittest discover \
    -s tests -p test_package_runtime.py -v
The named image must already exist; tests never pull or build one.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExtractedPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rpi package Ü ' & ")
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Path(self.temporary.name)
        self.package = self.fixture / 'package'
        self.target = self.fixture / 'target'
        self.target.mkdir()
        source = Path(os.environ.get('RPI_PACKAGE_TEST_SOURCE', ROOT / 'generated/codex'))
        shutil.copytree(source, self.package)
        self.runtime = self.package / 'runtime'
        self.engine = self.runtime / 'templates/scripts/rpi-distribution.py'
        self.image = os.environ.get('RPI_PACKAGE_TEST_IMAGE')

    def invoke(self, *args, expected=0):
        arguments = [str(arg) for arg in args]
        if self.image:
            arguments = [arg.replace(str(self.fixture), '/fixture') for arg in arguments]
            argv = ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none',
                    '--mount', f'type=bind,src={self.fixture},dst=/fixture',
                    '--mount', f'type=bind,src={self.package},dst=/fixture/package,readonly',
                    '--workdir', '/fixture/target', '--env', 'PYTHONDONTWRITEBYTECODE=1',
                    self.image, 'python3', *arguments]
        else:
            argv = [os.sys.executable, *arguments]
        result = subprocess.run(argv, cwd=self.target, capture_output=True, text=True,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, timeout=90)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_runtime_has_exact_declared_source_closure(self):
        manifest = json.loads((self.runtime / 'templates/distribution.json').read_text())
        expected = set(manifest['runtime_sources'])
        for component in manifest['components']:
            source = component['source']
            if component['kind'] == 'skill':
                expected.add(source + '/SKILL.md')
                for resource in component.get('resources', []):
                    if isinstance(resource, str):
                        expected.add(source + '/' + resource)
                    else:
                        expected.add(resource['source'])
                        alias = source + '/' + resource['destination']
                        expected.add(alias)
                        self.assertEqual((self.runtime / alias).read_bytes(),
                                         (self.runtime / resource['source']).read_bytes())
            else:
                expected.add(source)
        actual = {p.relative_to(self.runtime).as_posix() for p in self.runtime.rglob('*')
                  if p.is_file()}
        self.assertEqual(actual, expected)
        self.assertFalse(any(p.is_symlink() for p in self.package.rglob('*')))
        self.assertFalse(any('runtime' in Path(name).parts for name in actual))
        self.assertFalse(self.package.is_relative_to(ROOT))
        if self.image:
            # The host checkout is not mounted, even read-only, in this process.
            self.invoke('-c', 'from pathlib import Path; '
                        f'assert not Path({str(ROOT)!r}).exists()')

    def test_extracted_default_source_validates_and_renders_identical_package(self):
        self.invoke(self.engine, 'validate')
        output = self.fixture / 'rendered'
        self.invoke(self.engine, 'render', '--harness', 'codex', '--output', output)
        regenerated = output / 'codex'
        expected = {p.relative_to(self.package): p.read_bytes()
                    for p in self.package.rglob('*') if p.is_file()}
        actual = {p.relative_to(regenerated): p.read_bytes()
                  for p in regenerated.rglob('*') if p.is_file()}
        self.assertEqual(actual, expected)

    def test_missing_bundled_contract_blocks_before_render(self):
        contract = self.runtime / 'templates/skills/rpi-research/references/research-contract.md'
        self.assertTrue(contract.is_file())
        contract.unlink()
        output = self.fixture / 'rejected-render'
        result = self.invoke(self.engine, 'render', '--output', output, expected=1)
        self.assertIn('BLOCKED', result.stderr)
        self.assertFalse(output.exists())

    def test_altered_resource_alias_is_rejected(self):
        alias = self.runtime / 'templates/skills/rpi-plan/references/pseudocode-notation.md'
        source = self.runtime / 'methodology/pseudocode-notation.md'
        self.assertEqual(alias.read_bytes(), source.read_bytes())
        alias.write_bytes(alias.read_bytes() + b'\nUnexpected conflicting alias bytes.\n')
        result = self.invoke(self.engine, 'validate', expected=1)
        self.assertIn('BLOCKED', result.stderr)

    def test_extracted_lifecycle_preserves_project_knowledge_and_resources(self):
        agents = self.target / 'AGENTS.md'
        agents.write_text('# Fixture\n\nKeep the orchard rotation policy.\n')
        artifact = self.target / 'docs/research/orchard.md'
        artifact.parent.mkdir(parents=True)
        artifact.write_text('Existing project research.\n')
        plan = self.target / '.rpi/local/install-plan.json'
        self.invoke(self.engine, 'plan', '--target', self.target, '--harness', 'both',
                    '--route', 'direct', '--action', 'install', '--output', plan)
        self.invoke(self.engine, 'apply', '--plan', plan)
        for directory in ['.claude/skills', '.agents/skills']:
            skill = self.target / directory / 'rpi-research'
            self.assertTrue((skill / 'SKILL.md').is_file())
            self.assertIn('Research Evidence',
                          (skill / 'references/research-contract.md').read_text())
        before_check = {p.relative_to(self.target): p.read_bytes()
                        for p in self.target.rglob('*') if p.is_file()}
        self.invoke(self.engine, 'check', '--target', self.target, '--harness', 'both',
                    '--route', 'direct')
        after_check = {p.relative_to(self.target): p.read_bytes()
                       for p in self.target.rglob('*') if p.is_file()}
        self.assertEqual(after_check, before_check)
        detach = self.target / '.rpi/local/detach-plan.json'
        self.invoke(self.engine, 'plan', '--target', self.target, '--harness', 'both',
                    '--route', 'direct', '--action', 'detach', '--output', detach)
        self.invoke(self.engine, 'apply', '--plan', detach)
        self.assertIn('Keep the orchard rotation policy.', agents.read_text())
        self.assertEqual(artifact.read_text(), 'Existing project research.\n')
        self.assertFalse((self.target / '.agents/skills/rpi-research/SKILL.md').exists())
        self.assertFalse((self.target / '.claude/skills/rpi-research/SKILL.md').exists())


if __name__ == '__main__':
    unittest.main()
