import unittest
from pathlib import Path


class ReadmeBadgeTests(unittest.TestCase):
    def test_readme_contains_live_release_download_test_and_license_badges(self):
        repo_root = Path(__file__).resolve().parents[1]
        readme = (repo_root / "README.md").read_text(encoding="utf-8")

        expected = (
            "img.shields.io/github/v/release/pihrt-com/playoff",
            "img.shields.io/github/downloads/pihrt-com/playoff/total",
            "img.shields.io/github/actions/workflow/status/pihrt-com/playoff/tests.yml",
            "img.shields.io/github/license/pihrt-com/playoff",
        )
        for badge in expected:
            with self.subTest(badge=badge):
                self.assertIn(badge, readme)

    def test_tests_badge_points_to_existing_workflow(self):
        repo_root = Path(__file__).resolve().parents[1]
        self.assertTrue((repo_root / ".github" / "workflows" / "tests.yml").is_file())


if __name__ == "__main__":
    unittest.main()
