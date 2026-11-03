import json
import os
import tempfile
import unittest
from unittest import mock

import playoff


class FakeUSB:
    def __init__(self, available=(1, 2)):
        self.available = set(available)
        self.messages = []
        self.latest_messages = []

    def send_display(self, display_id, text):
        self.messages.append((display_id, text))
        return display_id in self.available

    def send_display_latest(self, display_id, text):
        self.latest_messages.append((display_id, text))
        return display_id in self.available


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeWidget:
    def __init__(self):
        self.options = {}

    def config(self, **options):
        self.options.update(options)


class FakeRoot:
    def __init__(self):
        self.callbacks = {}
        self.cancelled = []

    def cget(self, key):
        if key == "bg":
            return "system-bg"
        raise KeyError(key)

    def after(self, delay, callback):
        after_id = f"after-{len(self.callbacks) + 1}"
        self.callbacks[after_id] = (delay, callback)
        return after_id

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)
        self.callbacks.pop(after_id, None)


def make_app():
    app = playoff.PlayoffApp.__new__(playoff.PlayoffApp)
    app.root = FakeRoot()
    app.usb = FakeUSB()
    app.display_port_a = "COM5"
    app.display_port_b = "COM6"
    app.promo_text = "ROBO2026"
    app.promo_mode = playoff.DEFAULT_PROMO_MODE
    app.promo_scroll_ms = playoff.DEFAULT_PROMO_SCROLL_MS
    app.promo_active = False
    app.promo_scroll_position = 0
    app.promo_after_id = None
    app.race_active = False
    app.timer_running = False
    app.laps_countdown_running = False
    app.lap_running_a = False
    app.lap_running_b = False
    app.promo_btn = FakeWidget()
    app.status_var = FakeVar()
    app.status_label = FakeWidget()
    return app


class PromoTests(unittest.TestCase):
    def test_promo_text_accepts_ascii_and_rejects_unsupported_input(self):
        self.assertEqual(
            playoff.validate_promo_text(" ROBO2026 "),
            (True, " ROBO2026 ", ""),
        )
        self.assertEqual(playoff.validate_promo_text("   "), (True, "", ""))
        valid, _text, error = playoff.validate_promo_text("Příliš žluťoučký")
        self.assertFalse(valid)
        self.assertIn("bez diakritiky", error)
        valid, _text, error = playoff.validate_promo_text("X" * 80)
        self.assertFalse(valid)
        self.assertIn("79", error)

    def test_continuous_promo_sends_circular_windows_to_all_displays(self):
        app = make_app()

        self.assertTrue(app.start_promo())

        self.assertEqual(
            app.usb.messages,
            [(1, "TXT:ROBO202"), (2, "TXT:ROBO202")],
        )
        self.assertTrue(app.promo_active)
        self.assertEqual(app.status_var.get(), "PROMO: ROBO2026")
        self.assertEqual(app.promo_btn.options["relief"], "sunken")

        _delay, callback = app.root.callbacks[app.promo_after_id]
        self.assertEqual(_delay, playoff.DEFAULT_PROMO_SCROLL_MS)
        callback()
        self.assertEqual(
            app.usb.latest_messages,
            [(1, "TXT:OBO2026"), (2, "TXT:OBO2026")],
        )

    def test_firmware_mode_uses_native_scroll_command(self):
        app = make_app()
        app.promo_mode = "firmware"

        self.assertTrue(app.start_promo())

        self.assertEqual(
            app.usb.messages,
            [
                (1, "SPD:250"),
                (1, "SCR:ROBO2026"),
                (2, "SPD:250"),
                (2, "SCR:ROBO2026"),
            ],
        )
        self.assertIsNone(app.promo_after_id)

    def test_static_mode_uses_first_seven_characters(self):
        app = make_app()
        app.promo_mode = "static"

        self.assertTrue(app.start_promo())

        self.assertEqual(
            app.usb.messages,
            [(1, "TXT:ROBO202"), (2, "TXT:ROBO202")],
        )
        self.assertIsNone(app.promo_after_id)

    def test_circular_window_preserves_spaces_without_restart_gap(self):
        self.assertEqual(
            playoff.promo_display_window("AB C", 3),
            "CAB CAB",
        )
        self.assertEqual(playoff.normalize_promo_mode("invalid"), "continuous")

    def test_promo_scroll_interval_is_normalized_and_used(self):
        self.assertEqual(playoff.normalize_promo_scroll_ms("invalid"), 250)
        self.assertEqual(playoff.normalize_promo_scroll_ms(10), 50)
        self.assertEqual(playoff.normalize_promo_scroll_ms(5000), 1000)
        self.assertEqual(playoff.normalize_promo_scroll_ms(274), 250)
        self.assertEqual(playoff.normalize_promo_scroll_ms(276), 300)

        app = make_app()
        app.promo_scroll_ms = 600
        self.assertTrue(app.start_promo())
        delay, _callback = app.root.callbacks[app.promo_after_id]
        self.assertEqual(delay, 600)

    def test_mode_and_scroll_speed_are_persisted_to_user_json(self):
        app = make_app()
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(playoff.os.path, "expanduser", return_value=temp_dir):
                app.persist_user_settings(
                    promo_mode="firmware",
                    promo_scroll_ms=600,
                )
            with open(
                os.path.join(temp_dir, ".playoff_settings.json"),
                "r",
                encoding="utf-8",
            ) as settings_file:
                settings = json.load(settings_file)

        self.assertEqual(settings["promo_mode"], "firmware")
        self.assertEqual(settings["promo_scroll_ms"], 600)

    def test_stopping_promo_clears_all_configured_displays(self):
        app = make_app()
        app.promo_active = True
        app.promo_after_id = app.root.after(250, lambda: None)
        app.status_var.set("PROMO: ROBO2026")

        self.assertTrue(app.stop_promo())

        self.assertEqual(
            app.usb.latest_messages,
            [(1, "CLS"), (2, "CLS")],
        )
        self.assertFalse(app.promo_active)
        self.assertEqual(app.status_var.get(), "")
        self.assertIsNone(app.promo_after_id)
        self.assertTrue(app.root.cancelled)

    def test_promo_is_blocked_while_any_timing_is_active(self):
        for active_name in (
            "race_active",
            "timer_running",
            "laps_countdown_running",
            "lap_running_a",
            "lap_running_b",
        ):
            with self.subTest(active_name=active_name):
                app = make_app()
                setattr(app, active_name, True)
                with mock.patch.object(playoff.messagebox, "showwarning") as warning:
                    self.assertFalse(app.start_promo())
                warning.assert_called_once()
                self.assertEqual(app.usb.messages, [])

    def test_promo_button_requires_text_display_and_idle_state(self):
        app = make_app()
        app.update_promo_button_state()
        self.assertEqual(app.promo_btn.options["state"], "normal")

        app.timer_running = True
        app.update_promo_button_state()
        self.assertEqual(app.promo_btn.options["state"], "disabled")

        app.timer_running = False
        app.promo_text = ""
        app.update_promo_button_state()
        self.assertEqual(app.promo_btn.options["state"], "disabled")

    def test_only_configured_display_receives_promo(self):
        app = make_app()
        app.display_port_b = ""

        self.assertTrue(app.start_promo())
        self.assertEqual(app.usb.messages, [(1, "TXT:ROBO202")])

    def test_starting_countdown_clears_active_promo(self):
        app = make_app()
        app.promo_active = True
        app.status_var.set("PROMO: ROBO2026")
        app.timer_value = "00:05"
        app.timer_label = FakeWidget()
        app.countdown_after_id = None
        app.stop_blinking = lambda: None

        app.start_countdown()

        self.assertEqual(
            app.usb.latest_messages,
            [(1, "CLS"), (2, "CLS")],
        )
        self.assertFalse(app.promo_active)
        self.assertTrue(app.timer_running)
        self.assertEqual(app.promo_btn.options["state"], "disabled")


if __name__ == "__main__":
    unittest.main()
