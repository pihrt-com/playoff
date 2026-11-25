import tempfile
import tkinter as tk
import unittest
import os
import json
import time
from pathlib import Path
from unittest import mock

from pypdf import PdfReader

import playoff
import playoff_sounds as sounds


SAMPLE_PAYLOAD = {
    "api_version": "v1",
    "competition": {"year": 2026, "date": "2026-11-12"},
    "generated_at": "2026-11-18T07:53:12+00:00",
    "best_time_includes_penalties": True,
    "teams": [
        {"team_number": rank + 100, "rank": rank}
        for rank in range(1, 25)
    ],
}


def make_app():
    app = playoff.PlayoffApp.__new__(playoff.PlayoffApp)
    app.pre_round_enabled = True
    app.bracket = playoff.Bracket([""] * 16, [""] * 16, use_pre_round=True)
    app.robo_import_links = {}
    app.redraw = mock.Mock()
    return app


class RoboImportTests(unittest.TestCase):
    def test_tls_configuration_uses_existing_ca_file(self):
        with tempfile.NamedTemporaryFile() as certificate:
            with mock.patch.dict(os.environ, {"SSL_CERT_FILE": "missing.pem"}):
                selected = playoff.configure_tls_certificates(certificate.name)

                self.assertEqual(selected, certificate.name)
                self.assertEqual(os.environ["SSL_CERT_FILE"], certificate.name)

    def test_dialog_icon_is_applied_to_the_specific_window(self):
        class IconWindow:
            def __init__(self):
                self.paths = []

            def iconbitmap(self, path):
                self.paths.append(path)

        window = IconWindow()
        app = playoff.PlayoffApp.__new__(playoff.PlayoffApp)

        app.set_playoff_icon(window)

        self.assertEqual(len(window.paths), 1)
        self.assertTrue(window.paths[0].endswith("playoff.ico"))

    def test_default_key_places_direct_seeds_and_leaves_pre_round_targets_empty(self):
        plan = playoff.robo_import_plan(SAMPLE_PAYLOAD, playoff.robo_import_default_rules())

        self.assertEqual(
            plan["pre_round"],
            ["109", "124", "110", "123", "111", "122", "112", "121", "113", "120", "114", "119", "115", "118", "116", "117"],
        )
        self.assertEqual(
            plan["round_1"],
            ["101", "", "108", "", "105", "", "104", "", "", "103", "", "106", "107", "", "", "102"],
        )
        self.assertEqual(plan["links"][0], {"match": 1, "side": "b"})
        self.assertEqual(plan["links"][7], {"match": 0, "side": "b"})

    def test_import_populates_only_direct_slots_and_pre_round_winner_reaches_its_keyed_destination(self):
        app = make_app()
        plan = playoff.robo_import_plan(SAMPLE_PAYLOAD, playoff.robo_import_default_rules())

        app.apply_robo_import_plan(plan)

        self.assertEqual(
            [(match.a.text, match.b.text) for match in app.bracket.pre_rounds[0]],
            [("109", "124"), ("110", "123"), ("111", "122"), ("112", "121"), ("113", "120"), ("114", "119"), ("115", "118"), ("116", "117")],
        )
        self.assertEqual(app.bracket.rounds[0][0].a.text, "101")
        self.assertEqual(app.bracket.rounds[0][0].b.text, "")
        self.assertEqual(app.bracket.rounds[0][1].a.text, "108")
        self.assertEqual(app.bracket.rounds[0][1].b.text, "")

        app.promote_pre_round(0, "b")

        self.assertEqual(app.bracket.rounds[0][1].b.text, "124")
        self.assertEqual(app.bracket.rounds[0][1].a.text, "108")

    def test_import_is_rejected_when_pre_round_is_disabled(self):
        app = make_app()
        app.pre_round_enabled = False
        plan = playoff.robo_import_plan(SAMPLE_PAYLOAD, playoff.robo_import_default_rules())

        with self.assertRaisesRegex(ValueError, "vypnutém předkole"):
            app.apply_robo_import_plan(plan)

    def test_missing_or_duplicate_robo_rank_is_rejected(self):
        missing = dict(SAMPLE_PAYLOAD, teams=SAMPLE_PAYLOAD["teams"][:-1])
        with self.assertRaisesRegex(ValueError, "24"):
            playoff.robo_import_plan(missing, playoff.robo_import_default_rules())

        duplicate = dict(SAMPLE_PAYLOAD, teams=SAMPLE_PAYLOAD["teams"] + [{"team_number": 999, "rank": 1}])
        with self.assertRaisesRegex(ValueError, "vícekrát"):
            playoff.robo_import_plan(duplicate, playoff.robo_import_default_rules())

    def test_key_is_added_as_query_parameter_and_requires_https(self):
        self.assertEqual(
            playoff.robo_import_url("https://pihrt.com/robo/api/v1?mode=test", "tajny klic"),
            "https://pihrt.com/robo/api/v1?mode=test&key=tajny+klic",
        )
        with self.assertRaisesRegex(ValueError, "https"):
            playoff.robo_import_url("http://pihrt.com/robo/api/v1", "key")

    def test_robo_timestamp_is_human_readable(self):
        formatted = playoff.format_robo_generated_at("2026-11-18T08:44:55+00:00")
        self.assertIn("18. 11. 2026", formatted)
        self.assertNotIn("T08", formatted)

    def test_saved_links_ignore_invalid_legacy_or_manual_values(self):
        self.assertEqual(
            playoff.normalize_robo_import_links({"0": {"match": "1", "side": "b"}, "bad": {"match": 2, "side": "a"}, "2": {"match": 9, "side": "a"}}),
            {0: {"match": 1, "side": "b"}},
        )


class RoboImportMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as error:
            raise unittest.SkipTest(f"Tkinter není v tomto prostředí dostupný: {error}")
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def make_real_app(self, profile):
        patches = (
            mock.patch.object(playoff, "USB_AVAILABLE", False),
            mock.patch.object(playoff.PlayoffApp, "check_for_update"),
            mock.patch.object(playoff.PlayoffApp, "auto_check_usb"),
            mock.patch.object(playoff.PlayoffApp, "auto_check_displays"),
            mock.patch.object(playoff.os.path, "expanduser", return_value=profile),
        )
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        return playoff.PlayoffApp(self.root)

    def test_robo_menu_stays_configurable_but_disables_download_without_pre_round(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(profile)
            labels = {
                app.settings_menu.entrycget(index, "label"): index
                for index in range(app.settings_menu.index("end") + 1)
                if app.settings_menu.type(index) != "separator"
            }
            self.assertIn("Import online z ROBO", labels)
            menu = self.root.nametowidget(app.settings_menu.entrycget(labels["Import online z ROBO"], "menu"))
            self.assertEqual(menu.entrycget(0, "label"), "Nastavení importu…")
            self.assertEqual(menu.entrycget(2, "state"), "normal")

            app.pre_round_var.set(False)
            app.toggle_pre_round()

            self.assertEqual(menu.entrycget(0, "state"), "normal")
            self.assertEqual(menu.entrycget(2, "state"), "disabled")

    def test_frequent_settings_actions_have_retained_menu_icons(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(profile)
            entries = {
                app.settings_menu.entrycget(index, "label"): index
                for index in range(app.settings_menu.index("end") + 1)
                if app.settings_menu.type(index) != "separator"
            }
            labels = (
                "Počet týmů",
                "Pojmenování týmů",
                "Import online z ROBO",
                "Načíst pozadí",
                "Velikost písma",
                "Barva pozadí",
                "Tloušťka čar",
                "Zamknout editaci týmů",
                "Načíst ze souboru",
                "Uložit do souboru (pouze nastavení)",
                "Uložit do složky (ZIP)",
                "USB nastavení – brána a panely",
                "Zvuky",
                "Export do PDF PLAYOFF",
                "Export do PDF LAPS",
                "Celá obrazovka",
                "Nápověda",
                "Debug",
                "Kontrola aktualizace",
            )
            for label in labels:
                self.assertIn(label, entries)
                self.assertTrue(app.settings_menu.entrycget(entries[label], "image"))
            self.assertEqual(entries["Zvuky"], entries["USB nastavení – brána a panely"] + 1)
            self.assertEqual(app.settings_menu.type(entries["Zvuky"] + 1), "separator")

    def test_sounds_dialog_and_zip_restore_through_menu(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(profile)
            self.addCleanup(app.media_executor.shutdown)
            self.addCleanup(app.sound_player.close)
            entries = {
                app.settings_menu.entrycget(index, "label"): index
                for index in range(app.settings_menu.index("end") + 1)
                if app.settings_menu.type(index) != "separator"
            }
            app.settings_menu.invoke(entries["Zvuky"])
            dialog = next(widget for widget in self.root.winfo_children()
                          if isinstance(widget, tk.Toplevel) and widget.title() == "Zvuky")
            tabs = next(widget for widget in dialog.winfo_children()
                        if isinstance(widget, playoff.ttk.Notebook))
            self.assertEqual([tabs.tab(tab, "text") for tab in tabs.tabs()],
                             ["Události", "USB", "Knihovna zvuků"])
            dialog.destroy()

            def finish_io():
                until = time.monotonic() + 5
                while app.media_job is not None and time.monotonic() < until:
                    self.root.update()
                    time.sleep(0.01)
                self.assertIsNone(app.media_job)

            folder = Path(profile)
            filename = str(folder / "test.zip")
            file_dialog = playoff.filedialog
            with mock.patch.object(sounds, "media_root", return_value=folder / "source"):
                sound = sounds.add_sound(sounds.sound_path("short"))
                app.sound_settings["start"] = {"sound": sound, "enabled": False, "volume": 41}
                app.laps_sound_warning_seconds = 8
                app.bg_image = playoff.Image.new("RGB", (3, 2), "blue")
                with mock.patch.object(file_dialog, "asksaveasfilename", return_value=filename), \
                     mock.patch.object(playoff.messagebox, "showinfo"), \
                     mock.patch.object(playoff.messagebox, "showerror") as error:
                    app.settings_menu.invoke(entries["Uložit do složky (ZIP)"])
                    finish_io()
                    error.assert_not_called()

            app.load_sound_settings({})
            app.bg_image = None
            with mock.patch.object(sounds, "media_root", return_value=folder / "target"), \
                 mock.patch.object(file_dialog, "askopenfilename", return_value=filename), \
                 mock.patch.object(playoff.messagebox, "showinfo"), \
                 mock.patch.object(playoff.messagebox, "showerror") as error:
                app.settings_menu.invoke(entries["Načíst ze souboru"])
                finish_io()
                error.assert_not_called()
                self.assertTrue(sounds.sound_path(sound).is_file())
            self.assertEqual(app.bg_image.getpixel((0, 0)), (0, 0, 255, 255))
            saved = json.loads((folder / ".playoff_settings.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["sounds"]["start"], {"sound": sound, "enabled": False, "volume": 41})
            self.assertEqual(saved["laps_sound_warning_seconds"], 8)

    def test_debug_menu_is_between_help_and_update(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(profile)
            labels = [
                app.settings_menu.entrycget(index, "label")
                for index in range(app.settings_menu.index("end") + 1)
                if app.settings_menu.type(index) != "separator"
            ]
            self.assertLess(labels.index("Nápověda"), labels.index("Debug"))
            self.assertLess(labels.index("Debug"), labels.index("Kontrola aktualizace"))

    def test_usb_defaults_use_115200_for_gate_and_displays(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(profile)
            self.assertEqual(app.usb_baud, 115200)
            self.assertEqual(app.display_baud_a, 115200)
            self.assertEqual(app.display_baud_b, 115200)

    def test_imported_bracket_draws_eight_pre_round_links(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(profile)
            app.generate_bracket_with_empty(16)
            app.apply_robo_import_plan(
                playoff.robo_import_plan(SAMPLE_PAYLOAD, playoff.robo_import_default_rules())
            )
            link_ids = app.canvas.find_withtag("robo_import_link")
            self.assertEqual(len(link_ids), 8)
            for link_id in link_ids:
                self.assertEqual(app.canvas.itemcget(link_id, "dash"), "")

    def test_pdf_export_contains_pre_round_and_robo_connections(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(profile)
            app.generate_bracket_with_empty(16)
            app.apply_robo_import_plan(
                playoff.robo_import_plan(SAMPLE_PAYLOAD, playoff.robo_import_default_rules())
            )
            self.assertEqual(app.line_width, playoff.DEFAULT_LINE_WIDTH)
            pdf_path = f"{profile}\\robo-playoff.pdf"
            with mock.patch.object(playoff.filedialog, "asksaveasfilename", return_value=pdf_path), mock.patch.object(playoff.messagebox, "showinfo"), mock.patch.object(playoff.messagebox, "showerror") as showerror:
                app.export_pdf()
            self.assertFalse(showerror.called)
            with open(pdf_path, "rb") as exported:
                self.assertTrue(exported.read(5).startswith(b"%PDF"))
            self.assertIn("Předkolo", PdfReader(pdf_path).pages[0].extract_text())


if __name__ == "__main__":
    unittest.main()
