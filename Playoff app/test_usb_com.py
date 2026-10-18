import threading
import unittest
from types import SimpleNamespace

from usb_module import USBManager


class FakeSerial:
    def __init__(self):
        self.is_open = True
        self.in_waiting = 4
        self.read_sizes = []
        self.writes = []
        self.flushed = False
        self.closed = False

    def read(self, size):
        self.read_sizes.append(size)
        self.in_waiting = 0
        return b"OK\r\n"

    def write(self, payload):
        self.writes.append(payload)

    def flush(self):
        self.flushed = True

    def close(self):
        self.closed = True
        self.is_open = False


def make_manager():
    app = SimpleNamespace(
        display_port_a="",
        display_port_b="",
        display_baud_a=115200,
        display_baud_b=115200,
    )
    return USBManager(app=app, verbose=False)


class USBDisplayTests(unittest.TestCase):
    def test_send_display_writes_command_and_drains_previous_reply(self):
        manager = make_manager()
        serial_port = FakeSerial()
        manager.display_a = serial_port

        self.assertTrue(manager.send_display(1, "TXT:12.345"))

        self.assertEqual(serial_port.read_sizes, [4])
        self.assertEqual(serial_port.writes, [b"TXT:12.345\r\n"])
        self.assertTrue(serial_port.flushed)

    def test_latest_queue_coalesces_slow_updates(self):
        manager = make_manager()
        first_started = threading.Event()
        release_first = threading.Event()
        sent = []

        def slow_send(display_id, text):
            sent.append((display_id, text))
            if len(sent) == 1:
                first_started.set()
                release_first.wait(timeout=2)
            return True

        manager.send_display = slow_send

        self.assertTrue(manager.send_display_latest(1, "TXT:00.100"))
        self.assertTrue(first_started.wait(timeout=1))
        manager.send_display_latest(1, "TXT:00.200")
        manager.send_display_latest(1, "TXT:00.300")
        manager.send_display_latest(1, "TXT:00.400")
        release_first.set()

        worker = manager.display_workers[1]
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(
            sent,
            [(1, "TXT:00.100"), (1, "TXT:00.400")]
        )
        self.assertIsNone(manager.display_pending[1])

    def test_latest_queues_are_independent_for_both_displays(self):
        manager = make_manager()
        sent = []
        manager.send_display = lambda display_id, text: sent.append(
            (display_id, text)
        ) or True

        manager.send_display_latest(1, "TXT:01.000")
        manager.send_display_latest(2, "TXT:02.000")

        for display_id in (1, 2):
            worker = manager.display_workers[display_id]
            if worker is not None:
                worker.join(timeout=1)

        self.assertCountEqual(
            sent,
            [(1, "TXT:01.000"), (2, "TXT:02.000")]
        )

    def test_invalid_display_id_is_rejected(self):
        manager = make_manager()
        self.assertFalse(manager.send_display_latest(3, "TXT:00.000"))

    def test_missing_second_display_does_not_disconnect_first_display(self):
        manager = make_manager()
        first_display = FakeSerial()
        manager.display_a = first_display

        self.assertFalse(manager.send_display(2, "TXT:00.000"))

        self.assertIs(manager.display_a, first_display)
        self.assertTrue(first_display.is_open)
        self.assertFalse(first_display.closed)


if __name__ == "__main__":
    unittest.main()
