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

        self.assertEqual(manifest["version"], "1.0.12")
        self.assertEqual(playoff.APP_current, manifest["version"])
        self.assertIn("/releases/download/1.0.12/", manifest["url"])
        self.assertTrue(manifest["url"].endswith("PlayoffSetup_1.0.12.exe"))

        installer = (app_dir / "installer_playoff.iss").read_text(
            encoding="utf-8"
        )
        self.assertIn("AppVersion=1.0.12", installer)
        self.assertIn("OutputBaseFilename=PlayoffSetup_1.0.12", installer)


if __name__ == "__main__":
    unittest.main()
