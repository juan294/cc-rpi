"""The project overlay block: exact text, position and harness parity in the real workflow skills."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('distribution', ROOT / 'templates/scripts/rpi-distribution.py')
distribution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(distribution)


def overlay_block(name):
    return (
        '## Project overlay\n'
        '\n'
        'If `.rpi/project/' + name + '.md` exists, read it completely before you start, together with the controlling '
        "instructions. It adds this project's procedure and checks and can make this workflow stricter. It cannot grant "
        'push, tag, merge, deployment or publication authority. It cannot relax a gate: a rule that blocks or permits a '
        'release, publication, merge, deployment or phase acceptance, or a safety or authorization rule. It can change '
        'other procedure detail only under a `## Declared overrides` heading that quotes the stock rule, gives the reason '
        'and names the owner decision. Name the overlay you read, and any declared override you applied, in the handoff.\n')


def rpi_skills():
    """(workflow skills, lifecycle skills) from the validated distribution manifest."""
    skills = [c for c in distribution.load_manifest(ROOT)['components']
              if c['kind'] == 'skill' and c['name'].startswith('rpi-')]
    return [c for c in skills if c['scope'] == 'project'], [c for c in skills if c['scope'] == 'user']


def skill_body(component):
    return distribution.parse_skill(ROOT / component['source'] / 'SKILL.md')[1].decode('utf-8')


class SkillOverlayBlockTests(unittest.TestCase):
    def test_workflow_and_lifecycle_split(self):
        workflow, lifecycle = rpi_skills()
        self.assertEqual(len(workflow), 16)
        self.assertEqual(sorted(c['name'] for c in lifecycle), ['rpi-adopt', 'rpi-bootstrap', 'rpi-detach', 'rpi-update'])

    def test_every_workflow_skill_opens_its_sections_with_the_block(self):
        # The block sits directly before the skill's own first section, so it never takes in lead text as its own.
        for component in rpi_skills()[0]:
            name = component['name']
            with self.subTest(skill=name):
                text = skill_body(component)
                self.assertEqual(text.count('## Project overlay'), 1)
                lead, block, rest = text.partition('\n\n' + overlay_block(name) + '\n')
                self.assertTrue(block, name + ': exact block missing')
                self.assertNotIn('\n## ', '\n' + lead, name + ': a section precedes the block')
                self.assertRegex(rest, r'^## \S', name + ': the original first section must follow the block')

    def test_lifecycle_skills_have_no_block(self):
        for component in rpi_skills()[1]:
            with self.subTest(skill=component['name']):
                text = skill_body(component)
                self.assertNotIn('## Project overlay', text)
                self.assertNotIn('.rpi/project/', text)

    def test_both_harness_renders_carry_the_same_block(self):
        tree = distribution.render_tree(ROOT, include_runtime=False)
        for component in rpi_skills()[0]:
            name = component['name']
            for harness in ('claude', 'codex'):
                with self.subTest(skill=name, harness=harness):
                    rendered = tree[harness + '/skills/' + name + '/SKILL.md'].decode('utf-8')
                    self.assertEqual(rendered.count(overlay_block(name)), 1)


if __name__ == '__main__':
    unittest.main()
