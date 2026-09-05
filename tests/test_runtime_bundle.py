"""Package source closure must work without the maintainer checkout."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.spec_from_file_location('rpi_package', ROOT / 'templates/scripts/rpi-package.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class RuntimeBundleTests(unittest.TestCase):
    def test_explicit_closure_excludes_personal_and_generated_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'templates').mkdir()
            (root / 'skill').mkdir()
            (root / 'skill/SKILL.md').write_text('skill')
            (root / 'resource.md').write_text('resource')
            (root / 'secret').write_text('must not ship')
            manifest = {'runtime_sources': ['templates/distribution.json'], 'components': [
                {'kind': 'skill', 'source': 'skill', 'resources': [{'source': 'resource.md', 'destination': 'references/resource.md'}]}]}
            (root / 'templates/distribution.json').write_text(json.dumps(manifest))
            bundled = module().bundle_sources(root, manifest)
            self.assertEqual(set(bundled), {'templates/distribution.json', 'skill/SKILL.md', 'resource.md', 'skill/references/resource.md'})
            self.assertEqual(bundled['resource.md'], b'resource')

    def test_missing_and_escaping_runtime_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'root'
            root.mkdir()
            outside = Path(temporary) / 'sentinel'
            outside.write_text('private')
            (root / 'escape').symlink_to(outside)
            for relative in ('missing', '../sentinel', '/etc/passwd', 'escape'):
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    module().bundle_sources(root, {'runtime_sources': [relative], 'components': []})
            self.assertEqual(outside.read_text(), 'private')

    def test_alias_cannot_escape_or_replace_a_different_declared_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'skill').mkdir()
            (root / 'skill/SKILL.md').write_text('entrypoint')
            (root / 'resource').write_text('resource')
            for destination in ('../outside', 'SKILL.md'):
                with self.subTest(destination=destination), self.assertRaises(ValueError):
                    module().bundle_sources(root, {'runtime_sources': [], 'components': [
                        {'kind': 'skill', 'source': 'skill', 'resources': [
                            {'source': 'resource', 'destination': destination}]}]})

    def test_duplicate_declared_source_is_stored_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'shared').write_text('shared')
            tree = module().bundle_sources(root, {'runtime_sources': ['shared'], 'components': [
                {'kind': 'rule', 'source': 'shared'}, {'kind': 'instruction', 'source': 'shared'}]})
            self.assertEqual(tree, {'shared': b'shared'})


if __name__ == '__main__':
    unittest.main()
