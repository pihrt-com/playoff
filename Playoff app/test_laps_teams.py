import json
import os
import tempfile
import tkinter as tk
import unittest
from unittest import mock

import playoff


def make_laps_app(maximum=40):
    app = playoff.PlayoffApp.__new__(playoff.PlayoffApp)
    app.laps_max_teams = maximum
    app.laps_active_team_a = 1
    app.laps_teams = {}
    app.laps_a = []
    app.laps_b = []
    app.lap_id_a = 1
    app.lap_id_b = 1
    app.redraw = mock.Mock()
    app._load_laps_team_pair(1, store_current=False, redraw=False)
    return app


class LapsTeamHistoryTests(unittest.TestCase):
    def test_maximum_must_be_even_and_at_least_two(self):
        self.assertEqual(playoff.normalize_laps_max_teams(2), 2)
        self.assertEqual(playoff.normalize_laps_max_teams("40"), 40)
        self.assertEqual(playoff.normalize_laps_max_teams(39), 40)
        self.assertEqual(playoff.normalize_laps_max_teams(0), 40)

    def test_next_pair_is_empty_and_previous_pair_restores_results(self):
        app = make_laps_app(6)
        app.laps_a.append({"id": 1, "ride": 1, "ms": 12000})
        app.laps_b.append({"id": 2, "ride": 1, "ms": 13000})
        app.lap_id_a = 2
        app.lap_id_b = 2

        self.assertTrue(app.change_laps_team_pair(1))
        self.assertEqual(app.laps_active_team_a, 3)
        self.assertEqual(app.laps_a, [])
        self.assertEqual(app.laps_b, [])
        self.assertEqual((app.lap_id_a, app.lap_id_b), (1, 1))

        app.laps_a.append({"id": 3, "ride": 1, "ms": 14000})
        app.lap_id_a = 2
        self.assertTrue(app.change_laps_team_pair(-1))

        self.assertEqual(app.laps_active_team_a, 1)
        self.assertEqual(app.laps_a[0]["ms"], 12000)
        self.assertEqual(app.laps_b[0]["ms"], 13000)
        self.assertEqual((app.lap_id_a, app.lap_id_b), (2, 2))

        app.change_laps_team_pair(1)
        self.assertEqual(app.laps_a[0]["ms"], 14000)
        self.assertEqual(app.lap_id_a, 2)

    def test_pair_navigation_does_not_underflow_or_overflow(self):
        app = make_laps_app(4)

        self.assertFalse(app.change_laps_team_pair(-1))
        self.assertEqual(app.laps_active_team_a, 1)
        self.assertTrue(app.change_laps_team_pair(1))
        self.assertEqual(app.laps_active_team_a, 3)
        self.assertFalse(app.change_laps_team_pair(1))
        self.assertEqual(app.laps_active_team_a, 3)

    def test_saved_history_restores_active_pair_and_next_ride(self):
        app = make_laps_app(8)
        app.laps_a.append({
            "id": 1,
            "ride": 1,
            "date": "05.11.2026 20:00:00",
            "time": "00:12:000",
            "ms": 12000,
            "invalid": False,
        })
        app.lap_id_a = 2
        app.change_laps_team_pair(1)
        app.laps_b.append({
            "id": 4,
            "ride": 1,
            "date": "05.11.2026 20:01:00",
            "time": "00:13:000",
            "ms": 13000,
            "invalid": True,
        })
        app.lap_id_b = 2
        app._store_active_laps_pair()

        encoded = json.loads(json.dumps(app.laps_teams, ensure_ascii=False))
        restored = make_laps_app()
        restored._restore_laps_history(encoded, 8, 3)

        self.assertEqual(restored.laps_max_teams, 8)
        self.assertEqual(restored.laps_active_team_a, 3)
        self.assertEqual(restored.laps_b[0]["id"], 4)
        self.assertEqual(restored.laps_b[0]["ride"], 1)
        self.assertTrue(restored.laps_b[0]["invalid"])
        self.assertEqual(restored.lap_id_b, 2)

        restored.change_laps_team_pair(-1)
        self.assertEqual(restored.laps_a[0]["id"], 1)
        self.assertEqual(restored.lap_id_a, 2)

    def test_complete_laps_clear_removes_every_team_and_resets_pair(self):
        app = make_laps_app(6)
        app.laps_a.append({"id": 1, "ride": 1, "ms": 12000})
        app.change_laps_team_pair(1)
        app.laps_b.append({"id": 4, "ride": 1, "ms": 13000})

        with mock.patch.object(playoff.messagebox, "askyesno", return_value=True):
            self.assertTrue(app.clear_all_laps_history())

        self.assertEqual(app.laps_active_team_a, 1)
        self.assertEqual(app.laps_a, [])
        self.assertEqual(app.laps_b, [])
        self.assertEqual((app.lap_id_a, app.lap_id_b), (1, 1))
        self.assertEqual(set(app.laps_teams), {"1", "2"})


class LapsMenuAndSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def make_real_app(self, root, profile):
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
        return playoff.PlayoffApp(root)

    def test_laps_submenu_exists_in_real_tk_menu(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(self.root, profile)
            labels = {}
            for index in range(app.settings_menu.index("end") + 1):
                if app.settings_menu.type(index) == "separator":
                    continue
                labels[app.settings_menu.entrycget(index, "label")] = index
            self.assertIn("LAPS", labels)
            self.assertIn("Export do PDF PLAYOFF", labels)
            self.assertIn("Export do PDF LAPS", labels)
            menu_name = app.settings_menu.entrycget(labels["LAPS"], "menu")
            laps_menu = self.root.nametowidget(menu_name)
            self.assertEqual(laps_menu.entrycget(0, "label"), "LAPS max počet týmů")
            self.assertEqual(
                laps_menu.entrycget(1, "label"),
                "Vymazat tabulky A a B všech týmů",
            )

    def test_setup_file_contains_complete_laps_history(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(self.root, profile)
            app.laps_max_teams = 6
            app.laps_a.append({
                "id": 1,
                "ride": 1,
                "date": "05.11.2026 20:00:00",
                "time": "00:12:000",
                "ms": 12000,
                "invalid": False,
            })
            app.lap_id_a = 2
            app.change_laps_team_pair(1)
            app.laps_b.append({
                "id": 4,
                "ride": 1,
                "date": "05.11.2026 20:01:00",
                "time": "00:13:000",
                "ms": 13000,
                "invalid": False,
            })
            app.lap_id_b = 2
            setup_path = os.path.join(profile, "laps.setup")
            with mock.patch.object(playoff.filedialog, "asksaveasfilename", return_value=setup_path), mock.patch.object(playoff.messagebox, "showinfo"):
                app.save_setup()

            with open(setup_path, "r", encoding="utf-8") as saved_file:
                saved = json.load(saved_file)
            self.assertEqual(saved["laps_max_teams"], 6)
            self.assertEqual(saved["laps_active_team_a"], 3)
            self.assertEqual(saved["laps_teams"]["1"]["records"][0]["ms"], 12000)
            self.assertEqual(saved["laps_teams"]["4"]["next_ride"], 2)

            app.clear_all_laps_history(confirm=False)
            app.laps_max_teams = 40
            with mock.patch.object(playoff.filedialog, "askopenfilename", return_value=setup_path), mock.patch.object(playoff.messagebox, "showinfo"):
                app.load_setup()
            self.assertEqual(app.laps_max_teams, 6)
            self.assertEqual(app.laps_active_team_a, 3)
            self.assertEqual(app.laps_b[0]["id"], 4)
            self.assertEqual(app.lap_id_b, 2)
            app.change_laps_team_pair(-1)
            self.assertEqual(app.laps_a[0]["ms"], 12000)

    def test_laps_canvas_uses_blue_team_controls_and_matching_header_fonts(self):
        with tempfile.TemporaryDirectory() as profile:
            app = self.make_real_app(self.root, profile)
            app.view_mode = "laps"
            app.draw_laps()

            items = app.canvas.find_all()
            text_items = {
                app.canvas.itemcget(item, "text"): item
                for item in items
                if app.canvas.type(item) == "text"
            }
            self.assertIn("Team", text_items)
            self.assertIn("1-2", text_items)
            self.assertIn("Platnost", text_items)
            header_text = next(text for text in text_items if "Jízda" in text)
            self.assertEqual(
                app.canvas.itemcget(text_items["Platnost"], "font"),
                app.canvas.itemcget(text_items[header_text], "font"),
            )
            team_tags = app.canvas.find_withtag("laps_team_settings")
            team_rectangle = next(item for item in team_tags if app.canvas.type(item) == "rectangle")
            self.assertEqual(app.canvas.itemcget(team_rectangle, "fill"), "#0b6bd6")
            plus_item = text_items["+"]
            self.assertIn("15", app.canvas.itemcget(plus_item, "font"))

            app.change_laps_team_pair(1)
            pair_labels = [
                app.canvas.itemcget(item, "text")
                for item in app.canvas.find_withtag("laps_team_pair_label")
                if app.canvas.type(item) == "text"
            ]
            self.assertEqual(pair_labels, ["3-4"])

    def test_laps_pdf_contains_one_page_for_each_configured_team(self):
        app = make_laps_app(4)
        app._log = mock.Mock()
        app.laps_a.append({
            "id": 1,
            "ride": 1,
            "date": "05.11.2026 20:00:00",
            "time": "00:12:000",
            "ms": 12000,
            "invalid": False,
        })
        app.change_laps_team_pair(1)
        app.laps_b.append({
            "id": 4,
            "ride": 1,
            "date": "05.11.2026 20:01:00",
            "time": "00:09:000",
            "ms": 9000,
            "invalid": True,
        })

        with tempfile.TemporaryDirectory() as directory:
            pdf_path = os.path.join(directory, "laps.pdf")
            with mock.patch.object(playoff.filedialog, "asksaveasfilename", return_value=pdf_path), mock.patch.object(playoff.messagebox, "showinfo"), mock.patch.object(playoff.messagebox, "showerror") as showerror:
                result = app.export_laps_pdf()

            self.assertEqual(result, pdf_path)
            showerror.assert_not_called()
            with open(pdf_path, "rb") as pdf_file:
                pdf_data = pdf_file.read()
            self.assertTrue(pdf_data.startswith(b"%PDF"))
            self.assertEqual(
                pdf_data.count(b"/Type /Page") - pdf_data.count(b"/Type /Pages"),
                4,
            )


if __name__ == "__main__":
    unittest.main()
