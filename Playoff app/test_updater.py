import json
import unittest
from pathlib import Path

import playoff


class UpdateManifestTests(unittest.TestCase):
    def test_only_newer_versions_are_offered(self):
        self.assertTrue(playoff.is_newer_version("1.0.17", "1.0.16"))
        self.assertTrue(playoff.is_newer_version("1.1", "1.0.16"))
        self.assertFalse(playoff.is_newer_version("1.0.16", "1.0.16"))
        self.assertFalse(playoff.is_newer_version("1.0.15", "1.0.16"))
        self.assertFalse(playoff.is_newer_version("invalid", "1.0.16"))

    def test_update_notes_are_shown_or_fall_back_to_a_message(self):
        self.assertEqual(
            playoff.update_notes_text({"notes": "Opravené ukládání a nové ikony."}),
            "Opravené ukládání a nové ikony.",
        )
        self.assertEqual(
            playoff.update_notes_text({}),
            "Popis změn této verze není k dispozici.",
        )

    def test_manifest_matches_release_version(self):
        app_dir = Path(__file__).resolve().parent
        manifest = json.loads(
            (app_dir / "version.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["version"], "1.0.36")
        self.assertEqual(playoff.APP_current, manifest["version"])
        self.assertIn("/releases/download/1.0.36/", manifest["url"])
        self.assertTrue(manifest["url"].endswith("PlayoffSetup_1.0.36.exe"))
        self.assertEqual(len(manifest["sha256"]), 64)
        self.assertTrue(all(char in "0123456789abcdef" for char in manifest["sha256"]))
        self.assertGreater(manifest["size"], 0)

        installer = (app_dir / "installer_playoff.iss").read_text(
            encoding="utf-8"
        )
        self.assertIn("AppVersion=1.0.36", installer)
        self.assertIn("OutputBaseFilename=PlayoffSetup_1.0.36", installer)

    def test_installer_preserves_existing_desktop_shortcut_during_update(self):
        installer = (Path(__file__).resolve().parent / "installer_playoff.iss").read_text(
            encoding="utf-8"
        )

        self.assertIn("Check: ShouldCreateDesktopShortcut", installer)
        self.assertIn("Flags: uninsneveruninstall", installer)
        self.assertIn("Type: files; Name: \"{userdesktop}\\Playoff.lnk\"", installer)
        self.assertIn("Result := not FileExists(ExpandConstant('{userdesktop}\\Playoff.lnk'));", installer)

    def test_installer_offers_to_launch_playoff_after_interactive_setup(self):
        installer = (Path(__file__).resolve().parent / "installer_playoff.iss").read_text(
            encoding="utf-8"
        )

        self.assertIn('Description: "Spustit Playoff"', installer)
        self.assertIn("Flags: nowait postinstall skipifsilent", installer)

    def test_build_specs_keep_playoff_icon(self):
        app_dir = Path(__file__).resolve().parent
        portable_spec = (app_dir / "playoff.spec").read_text(encoding="utf-8")
        updater_spec = (app_dir / "updater.spec").read_text(encoding="utf-8")

        self.assertIn("icon='playoff.ico'", portable_spec)
        self.assertIn("('playoff.ico', '.')", portable_spec)
        self.assertIn("datas=[('playoff.ico', '.')]", updater_spec)

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
