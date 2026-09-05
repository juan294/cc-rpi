"""Link checks must describe the publishable candidate, not incidental files."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-links.py"


class LinkTests(unittest.TestCase):
    def check(self, files, ignored=(), candidates=()):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            (root / ".gitignore").write_text("\n".join(ignored))
            args = [sys.executable, str(SCRIPT), "--root", str(root)]
            for candidate in candidates:
                args.extend(["--candidate", candidate])
            return subprocess.run(args, capture_output=True, text=True)

    def test_relative_paths_fragments_images_and_fences(self):
        result = self.check({
            "README.md": "[guide](docs/guide.md#hello-world)\n![image](image.svg)\n"
                         "```md\n[not a link](missing.md)\n```\n"
                         "~~~\n[also ignored](absent.md)\n~~~\n",
            "docs/guide.md": "# Hello, World!\n[back](../README.md)\n",
            "image.svg": "<svg/>"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_anchor_and_missing_image_fail(self):
        for link in ("[bad](#missing)", "![bad](missing.svg)"):
            with self.subTest(link=link):
                self.assertNotEqual(self.check({"README.md": link}).returncode, 0)

    def test_image_link_also_checks_outer_destination(self):
        self.assertNotEqual(self.check({"README.md": "[![badge](badge.svg)](missing.md)",
                                       "badge.svg": "<svg/>"}).returncode, 0)

    def test_paths_outside_candidate_fail(self):
        for target in ("/definitely-missing-cc-rpi.md", "../../local.md"):
            with self.subTest(target=target):
                self.assertNotEqual(self.check({"README.md": f"[bad]({target})"}).returncode, 0)

    def test_ignored_workspace_target_is_not_published(self):
        files = {"README.md": "[local](notes.md)", "notes.md": "# Evidence"}
        self.assertNotEqual(self.check(files, ignored=("notes.md",)).returncode, 0)
        self.assertEqual(self.check(files, ignored=("notes.md",),
                                    candidates=("notes.md",)).returncode, 0)

    def test_reference_links_duplicate_anchors_and_spaces(self):
        result = self.check({"README.md": "# Heading\n# Heading\n"
            "[second](#heading-1) [space](<a file.md#target>)\n"
            "[reference][guide]\n[guide]: a%20file.md#target\n",
            "a file.md": "Target\n======\n"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_reference_link_fails(self):
        self.assertNotEqual(self.check({"README.md": "[read][guide]\n"
                                       "[guide]: absent.md"}).returncode, 0)

    def test_empty_inventory_fails(self):
        self.assertNotEqual(self.check({}).returncode, 0)

    def test_source_symlink_cannot_import_ignored_workspace_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("local.md\n")
            (root / "local.md").write_text("# only local\n")
            (root / "README.md").symlink_to("local.md")
            result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stderr)


if __name__ == "__main__":
    unittest.main()
