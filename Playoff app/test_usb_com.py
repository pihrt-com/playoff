import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import usb_module
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


class OpeningSerial(FakeSerial):
    def __init__(self, port=None, baudrate=115200, timeout=1, write_timeout=1):
        super().__init__()
        self.is_open = False
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.dtr = None
        self.rts = None
        self.input_reset = False
        self.output_reset = False

    def open(self):
        if self.port == "COM1":
            raise OSError(f"Cannot open {self.port}")
        self.is_open = True

    def reset_input_buffer(self):
        self.input_reset = True

    def reset_output_buffer(self):
        self.output_reset = True


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
        manager.app.display_port_a = "COM3"
        serial_port = OpeningSerial(port="COM3", baudrate=115200)
        serial_port.open()
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

    def test_failed_first_display_does_not_prevent_second_display_initialization(self):
        manager = make_manager()
        manager.app.display_port_a = "COM1"
        manager.app.display_port_b = "COM2"
        created = []

        def make_serial(**kwargs):
            serial_port = OpeningSerial(**kwargs)
            created.append(serial_port)
            return serial_port

        with mock.patch.object(usb_module, "PY_SERIAL_AVAILABLE", True), \
             mock.patch.object(usb_module, "serial", SimpleNamespace(Serial=make_serial)), \
             mock.patch.object(usb_module.time, "sleep"):
            connected = manager.connect_displays()

        self.assertFalse(connected[1])
        self.assertTrue(connected[2])
        self.assertIsNone(manager.display_a)
        self.assertIs(manager.display_b, created[1])
        self.assertTrue(manager.display_b.is_open)
        self.assertFalse(created[0].dtr)
        self.assertFalse(created[0].rts)

    def test_reconnect_replaces_a_running_gate_reader(self):
        manager = make_manager()
        manager.port = "COM8"
        manager.handler.rx_running = True
        manager.disconnect = mock.Mock()
        manager.connect = mock.Mock()
        manager.handler.start_reader = mock.Mock()
        callback = mock.Mock()

        self.assertTrue(manager.reconnect(callback))

        manager.disconnect.assert_called_once_with()
        manager.connect.assert_called_once_with()
        manager.handler.start_reader.assert_called_once_with(callback)

    def test_dialog_test_uses_selected_display_port_without_gate(self):
        manager = make_manager()
        created = []

        def make_serial(**kwargs):
            serial_port = OpeningSerial(**kwargs)
            created.append(serial_port)
            return serial_port

        with mock.patch.object(usb_module, "PY_SERIAL_AVAILABLE", True), \
             mock.patch.object(usb_module, "serial", SimpleNamespace(Serial=make_serial)), \
             mock.patch.object(usb_module.time, "sleep"):
            sent = manager.send_display_to_port(1, "TXT:ID-1", "COM3", 115200)

        self.assertTrue(sent)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].port, "COM3")
        self.assertEqual(created[0].writes, [b"TXT:ID-1\r\n"])
        self.assertFalse(manager.handler.is_open())

    def test_dialog_test_reports_open_error(self):
        manager = make_manager()

        def make_serial(**kwargs):
            return OpeningSerial(**kwargs)

        with mock.patch.object(usb_module, "PY_SERIAL_AVAILABLE", True), \
             mock.patch.object(usb_module, "serial", SimpleNamespace(Serial=make_serial)), \
             mock.patch.object(usb_module.time, "sleep"):
            sent = manager.send_display_to_port(1, "TXT:ID-1", "COM1", 115200)

        self.assertFalse(sent)
        self.assertIn("Cannot open COM1", manager.display_error(1))

    def test_reapplying_same_display_settings_keeps_open_connection(self):
        manager = make_manager()
        manager.app.display_port_a = "COM3"
        current = OpeningSerial(port="COM3", baudrate=115200)
        current.open()
        manager.display_a = current

        with mock.patch.object(usb_module, "serial") as serial_module:
            connected = manager._connect_display(1)

        self.assertTrue(connected)
        self.assertIs(manager.display_a, current)
        self.assertFalse(current.closed)
        serial_module.Serial.assert_not_called()

    def test_disabling_display_closes_existing_connection(self):
        manager = make_manager()
        current = OpeningSerial(port="COM3", baudrate=115200)
        current.open()
        manager.display_a = current

        with mock.patch.object(usb_module.time, "sleep"):
            connected = manager._connect_display(1)

        self.assertFalse(connected)
        self.assertTrue(current.closed)
        self.assertIsNone(manager.display_a)


if __name__ == "__main__":
    unittest.main()
