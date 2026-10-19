import json
import unittest
from pathlib import Path

import playoff


class UpdateManifestTests(unittest.TestCase):
    def test_manifest_matches_release_version(self):
        app_dir = Path(__file__).resolve().parent
        manifest = json.loads(
            (app_dir / "version.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["version"], "1.0.14")
        self.assertEqual(playoff.APP_current, manifest["version"])
        self.assertIn("/releases/download/1.0.14/", manifest["url"])
        self.assertTrue(manifest["url"].endswith("PlayoffSetup_1.0.14.exe"))
        self.assertEqual(len(manifest["sha256"]), 64)
        self.assertTrue(all(char in "0123456789abcdef" for char in manifest["sha256"]))
        self.assertGreater(manifest["size"], 0)

        installer = (app_dir / "installer_playoff.iss").read_text(
            encoding="utf-8"
        )
        self.assertIn("AppVersion=1.0.14", installer)
        self.assertIn("OutputBaseFilename=PlayoffSetup_1.0.14", installer)

    def test_updater_command_contains_manifest_integrity_data(self):
        info = {
            "version": "1.0.13",
            "url": "https://example.test/PlayoffSetup_1.0.13.exe",
            "sha256": "a" * 64,
            "size": 12345,
        }

        command = playoff.build_updater_command("updater.exe", "playoff.exe", info)

        self.assertEqual(command[:3], ["updater.exe", "playoff.exe", info["url"]])
        self.assertEqual(command[3:], [
            "--version", "1.0.13",
            "--sha256", "a" * 64,
            "--size", "12345",
        ])

    def test_updater_command_rejects_invalid_sha256(self):
        with self.assertRaises(ValueError):
            playoff.build_updater_command(
                "updater.exe",
                "playoff.exe",
                {"url": "https://example.test/setup.exe", "sha256": "invalid"},
            )


if __name__ == "__main__":
    unittest.main()
