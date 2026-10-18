import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import playoff


class FakeUSB:
    def __init__(self):
        self.messages = []

    def send_display_latest(self, display_id, text):
        self.messages.append((display_id, text))
        return True


class FakeVar:
    def __init__(self, value):
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


class ImmediateRoot:
    def after(self, delay, callback):
        callback()
        return "after-id"


def make_app():
    app = playoff.PlayoffApp.__new__(playoff.PlayoffApp)
    app.usb = FakeUSB()
    app.live_led_enabled = True
    app.live_led_refresh = 0.1
    app.live_led_next_send = {1: 10.0, 2: 10.0}
    app.lap_running_a = True
    app.lap_running_b = True
    app.lap_time_a = 1234
    app.lap_time_b = 61234
    return app


class LiveLEDTests(unittest.TestCase):
    def test_refresh_options_cover_tenth_to_one_second(self):
        self.assertEqual(
            playoff.LED_REFRESH_OPTIONS,
            (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
        )
        self.assertEqual(playoff.normalize_led_refresh("0.7"), 0.7)
        self.assertEqual(
            playoff.normalize_led_refresh("invalid"),
            playoff.DEFAULT_LED_REFRESH
        )
        self.assertEqual(
            playoff.normalize_led_refresh(1.1),
            playoff.DEFAULT_LED_REFRESH
        )

    def test_live_times_are_sent_only_when_due(self):
        app = make_app()

        app.send_live_led_times(now=9.99)
        self.assertEqual(app.usb.messages, [])

        app.send_live_led_times(now=10.0)
        self.assertEqual(
            app.usb.messages,
            [(1, "TXT:01.234"), (2, "TXT:01.01.2")]
        )

        app.send_live_led_times(now=10.05)
        self.assertEqual(len(app.usb.messages), 2)

        app.send_live_led_times(now=10.1)
        self.assertEqual(len(app.usb.messages), 4)

    def test_finished_lane_stops_while_other_lane_continues(self):
        app = make_app()
        app.lap_running_a = False

        app.send_live_led_times(now=10.0)

        self.assertEqual(app.usb.messages, [(2, "TXT:01.01.2")])

    def test_disabled_live_updates_send_nothing(self):
        app = make_app()
        app.live_led_enabled = False

        app.send_live_led_times(now=10.0)

        self.assertEqual(app.usb.messages, [])

    def test_reset_sends_zero_and_starts_new_interval(self):
        app = make_app()
        with mock.patch.object(playoff.time, "monotonic", return_value=20.0):
            app.reset_led_times(1, 2)

        self.assertEqual(
            app.usb.messages,
            [(1, "TXT:00.000"), (2, "TXT:00.000")]
        )
        self.assertEqual(app.live_led_next_send, {1: 20.1, 2: 20.1})

    def test_finish_event_sends_exact_final_time_immediately(self):
        app = make_app()
        app.root = ImmediateRoot()
        app._log = lambda *args: None
        app.lap_label_a = FakeWidget()

        app.on_usb_line("finish_a")

        self.assertFalse(app.lap_running_a)
        self.assertEqual(app.lap_label_a.options["fg"], "green")
        self.assertEqual(app.usb.messages, [(1, "TXT:01.234")])

    def test_refresh_selection_is_persisted(self):
        app = make_app()
        app.live_led_refresh_var = FakeVar("0.8")
        saved = {}
        app.persist_user_settings = lambda **values: saved.update(values)

        app.on_set_live_led_refresh()

        self.assertEqual(app.live_led_refresh, 0.8)
        self.assertEqual(app.live_led_refresh_var.get(), "0.8")
        self.assertEqual(saved["live_led_refresh"], 0.8)

    def test_user_settings_preserve_existing_usb_values(self):
        app = make_app()
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / ".playoff_settings.json"
            settings_path.write_text(
                json.dumps({"usb_port": "COM7"}),
                encoding="utf-8"
            )
            with mock.patch.object(
                playoff.os.path,
                "expanduser",
                return_value=temp_dir
            ):
                app.persist_user_settings(
                    live_led_enabled=True,
                    live_led_refresh=0.4
                )

            saved = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertEqual(saved["usb_port"], "COM7")
        self.assertTrue(saved["live_led_enabled"])
        self.assertEqual(saved["live_led_refresh"], 0.4)


if __name__ == "__main__":
    unittest.main()
