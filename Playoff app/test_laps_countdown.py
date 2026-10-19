import tempfile
import unittest
from unittest import mock

import playoff


class FakeRoot:
    def __init__(self):
        self.callbacks = {}
        self.cancelled = []
        self.next_id = 1

    def after(self, delay, callback):
        after_id = f"after-{self.next_id}"
        self.next_id += 1
        self.callbacks[after_id] = (delay, callback)
        return after_id

    def after_cancel(self, after_id):
        self.cancelled.append(after_id)
        self.callbacks.pop(after_id, None)


class FakeLabel:
    def __init__(self):
        self.options = {
            "text": "05:00",
            "bg": "black",
            "fg": "white",
        }

    def config(self, **options):
        self.options.update(options)


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def make_app(timer_value="05:00"):
    app = playoff.PlayoffApp.__new__(playoff.PlayoffApp)
    app.root = FakeRoot()
    app.timer_label = FakeLabel()
    app.timer_value = timer_value
    app.enable_timer = True
    app.view_mode = "laps"
    app.laps_countdown_running = False
    app.laps_countdown_seconds = app.time_to_seconds(timer_value)
    app.laps_countdown_after_id = None
    app.laps_countdown_blink_after_id = None
    app.laps_countdown_blink_state = False
    app.timer_running = False
    app.timer_blink = False
    app.countdown_after_id = None
    app.blink_after_id = None
    app.redraw = lambda: None
    app.update_timer_visibility = lambda: None
    app.usb = None
    app.lap_running_a = False
    app.lap_running_b = False
    return app


class LapsCountdownTests(unittest.TestCase):
    def test_left_click_starts_countdown_from_configured_maximum(self):
        app = make_app("05:00")

        result = app.on_timer_left_click()

        self.assertEqual(result, "break")
        self.assertTrue(app.laps_countdown_running)
        self.assertEqual(app.laps_countdown_seconds, 300)
        self.assertEqual(app.timer_label.options["text"], "05:00")
        self.assertEqual(app.timer_label.options["bg"], "black")
        self.assertEqual(app.root.callbacks[app.laps_countdown_after_id][0], 1000)

    def test_left_click_does_not_change_playoff_countdown_behavior(self):
        app = make_app("00:02")
        app.view_mode = "playoff"

        result = app.on_timer_left_click()

        self.assertIsNone(result)
        self.assertFalse(app.laps_countdown_running)
        self.assertIsNone(app.laps_countdown_after_id)

        app.start_countdown()
        self.assertTrue(app.timer_running)
        self.assertEqual(app.current_seconds, 2)
        self.assertIsNotNone(app.countdown_after_id)

    def test_left_click_resets_running_countdown_and_stops_warning(self):
        app = make_app("05:00")
        app.start_laps_countdown()
        old_after_id = app.laps_countdown_after_id
        app.laps_countdown_seconds = 8
        app.laps_countdown_blink_after_id = app.root.after(
            playoff.LAPS_COUNTDOWN_BLINK_MS,
            app.laps_countdown_blink_step,
        )
        app.timer_label.config(bg="red")

        app.on_timer_left_click()

        self.assertIn(old_after_id, app.root.cancelled)
        self.assertEqual(app.laps_countdown_seconds, 300)
        self.assertEqual(app.timer_label.options["bg"], "black")
        self.assertEqual(app.timer_label.options["fg"], "white")

    def test_final_ten_seconds_blink_red_and_black_with_white_text(self):
        app = make_app("00:12")
        app.start_laps_countdown()
        app.laps_countdown_seconds = 11

        app.laps_countdown_tick()

        self.assertEqual(app.laps_countdown_seconds, 10)
        self.assertEqual(app.timer_label.options["text"], "00:10")
        self.assertEqual(app.timer_label.options["bg"], "red")
        self.assertEqual(app.timer_label.options["fg"], "white")
        blink_after_id = app.laps_countdown_blink_after_id
        self.assertEqual(app.root.callbacks[blink_after_id][0], 500)

        app.laps_countdown_blink_step()

        self.assertEqual(app.timer_label.options["bg"], "black")
        self.assertEqual(app.timer_label.options["fg"], "white")

    def test_expiry_restarts_next_cycle_automatically(self):
        app = make_app("00:03")
        app.start_laps_countdown()
        app.laps_countdown_seconds = 1
        app.laps_countdown_blink_after_id = app.root.after(
            playoff.LAPS_COUNTDOWN_BLINK_MS,
            app.laps_countdown_blink_step,
        )
        app.timer_label.config(bg="red")

        app.laps_countdown_tick()

        self.assertTrue(app.laps_countdown_running)
        self.assertEqual(app.laps_countdown_seconds, 3)
        self.assertEqual(app.timer_label.options["text"], "00:03")
        self.assertEqual(app.timer_label.options["bg"], "black")
        self.assertEqual(app.timer_label.options["fg"], "white")
        self.assertIsNotNone(app.laps_countdown_after_id)
        self.assertIsNone(app.laps_countdown_blink_after_id)

    def test_disabling_timer_stops_and_resets_laps_cycle(self):
        app = make_app("05:00")
        app.start_laps_countdown()
        active_after_id = app.laps_countdown_after_id
        app.laps_countdown_seconds = 123
        app.timer_menu_var = FakeVar(False)

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                playoff.os.path,
                "expanduser",
                return_value=temp_dir,
            ):
                app.on_toggle_timer()

        self.assertFalse(app.enable_timer)
        self.assertFalse(app.laps_countdown_running)
        self.assertEqual(app.laps_countdown_seconds, 300)
        self.assertIn(active_after_id, app.root.cancelled)

    def test_mode_change_stops_both_countdown_implementations(self):
        app = make_app("05:00")
        app.start_laps_countdown()
        laps_after_id = app.laps_countdown_after_id
        app.timer_running = True
        app.countdown_after_id = app.root.after(1000, lambda: None)
        playoff_after_id = app.countdown_after_id
        app.timer_blink = True
        app.blink_after_id = app.root.after(500, lambda: None)
        playoff_blink_id = app.blink_after_id

        app.stop_countdowns_for_mode_change()

        self.assertFalse(app.timer_running)
        self.assertFalse(app.laps_countdown_running)
        self.assertIsNone(app.countdown_after_id)
        self.assertIsNone(app.laps_countdown_after_id)
        self.assertCountEqual(
            app.root.cancelled,
            [laps_after_id, playoff_after_id, playoff_blink_id],
        )
        self.assertEqual(app.timer_label.options["bg"], "black")
        self.assertEqual(app.timer_label.options["fg"], "white")

    def test_alternative_mode_handler_also_stops_laps_cycle(self):
        app = make_app("05:00")
        app.start_laps_countdown()
        app.view_mode_var = FakeVar("playoff")
        app.update_view_mode_gui = lambda: None
        app._log = lambda *args: None

        with mock.patch.object(playoff.messagebox, "askyesno", return_value=True):
            app.on_view_mode_change()

        self.assertEqual(app.view_mode, "playoff")
        self.assertFalse(app.laps_countdown_running)
        self.assertIsNone(app.laps_countdown_after_id)
        self.assertEqual(app.timer_label.options["text"], "05:00")

    def test_zero_interval_is_rejected_without_scheduling_loop(self):
        app = make_app("00:00")

        with mock.patch.object(playoff.messagebox, "showerror") as showerror:
            result = app.start_laps_countdown()

        self.assertFalse(result)
        self.assertFalse(app.laps_countdown_running)
        self.assertIsNone(app.laps_countdown_after_id)
        showerror.assert_called_once()

    def test_laps_countdown_does_not_touch_lane_or_usb_state(self):
        app = make_app("00:12")
        sentinel_usb = object()
        app.usb = sentinel_usb
        app.lap_running_a = True
        app.lap_running_b = False

        app.start_laps_countdown()
        app.laps_countdown_tick()

        self.assertIs(app.usb, sentinel_usb)
        self.assertTrue(app.lap_running_a)
        self.assertFalse(app.lap_running_b)

    def test_laps_timer_position_is_bottom_center(self):
        x, y = playoff.laps_countdown_position(1200, 800, 144)

        self.assertEqual(x, 600)
        self.assertEqual(y, 708)


if __name__ == "__main__":
    unittest.main()
