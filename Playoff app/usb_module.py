from __future__ import annotations

#!/usr/bin/env python
# usb_module.py
# test: python usb_module.py
# -*- coding: utf-8 -*-
__author__ = 'Martin Pihrt'

import threading
import time
import sys
from datetime import datetime

try:
    import serial
    import serial.tools.list_ports as list_ports
    PY_SERIAL_AVAILABLE = True
except Exception:
    serial = None
    list_ports = None
    PY_SERIAL_AVAILABLE = False


DEFAULT_SERIAL_PORT = ""
DEFAULT_SERIAL_BAUD = 115200
DEFAULT_SERIAL_TIMEOUT = 5.0


def _now():
    return time.strftime("%H:%M:%S")


def _dbg(msg: str):
    print(f"[usb_module {_now()}] {msg}", file=sys.stderr)


class SerialHandler:
    def __init__(self, verbose: bool = False, prevent_reset: bool = True, event_sink=None):
        self.ser = None
        self.port = DEFAULT_SERIAL_PORT
        self.baud = DEFAULT_SERIAL_BAUD
        self.timeout = DEFAULT_SERIAL_TIMEOUT
        self.verbose = verbose
        self.prevent_reset = prevent_reset
        self.rx_thread = None
        self.rx_running = False
        self.rx_stop_event = None
        self.rx_callback = None
        self.write_lock = threading.Lock()
        self.open_lock = threading.Lock()
        self.event_sink = event_sink

    def _log(self, msg: str):
        try:
            if self.event_sink is not None:
                self.event_sink(f"USB {msg}")
        except Exception:
            pass
        if self.verbose:
            _dbg(msg)

    def list_ports(self):
        if not PY_SERIAL_AVAILABLE:
            return []

        try:
            return [p.device for p in list_ports.comports()]
        except Exception:
            return []

    def is_open(self):
        try:
            return self.ser is not None and self.ser.is_open
        except Exception:
            return False

    def open(
        self,
        port=None,
        baud=None,
        timeout=None,
        retries: int = 3,
        retry_delay: float = 0.5
    ):

        if not PY_SERIAL_AVAILABLE:
            raise RuntimeError("pyserial není nainstalován")

        with self.open_lock:
            if self.is_open():
                return

            if port:
                self.port = port

            if baud:
                self.baud = int(baud)

            if timeout is not None:
                self.timeout = float(timeout)

            last_exc = None

            for attempt in range(1, retries + 1):
                try:

                    self._log(f"GATE open {self.port} {self.baud} attempt {attempt}")

                    ser = serial.Serial(
                        port=None,
                        baudrate=self.baud,
                        timeout=self.timeout,
                        write_timeout=1
                    )

                    ser.port = self.port

                    if self.prevent_reset:
                        try:
                            ser.dtr = False
                            ser.rts = False
                        except Exception:
                            pass

                    ser.open()

                    try:
                        ser.reset_input_buffer()
                        ser.reset_output_buffer()
                    except Exception:
                        pass

                    time.sleep(2)

                    self.ser = ser
                    self._log(f"GATE opened {self.port}")

                    return

                except Exception as e:
                    last_exc = e
                    self._log(f"open failed {e}")

                    try:
                        ser.close()
                    except Exception:
                        pass

                    self.ser = None
                    time.sleep(retry_delay)

            raise last_exc

    def close(self):
        self.stop_reader()

        try:
            if self.ser:
                self.ser.close()

        except Exception:
            pass

        self.ser = None
        time.sleep(0.2)

    def send(self, payload: bytes):
        if not self.is_open():
            self._log("PORT CLOSED -> OPEN")
            self.open()

        self._log(f"GATE {self.port} TX {payload.decode(errors='replace').strip()}")
        with self.write_lock:
            self.ser.write(payload)
            try:
                self.ser.flush()
            except Exception:
                pass

    def send_start(self):
        self.send(b"start\n")

    def send_finish(self):
        self.send(b"finish\n")

    def start_reader(self, callback):
        self.stop_reader()
        self.rx_callback = callback
        self.rx_running = True
        stop_event = threading.Event()
        self.rx_stop_event = stop_event
        serial_connection = self.ser

        def worker():
            buffer = b""
            while not stop_event.is_set():
                try:
                    if serial_connection is None or not getattr(serial_connection, "is_open", False):
                        self._log("GATE reader stopped because its connection closed")
                        break
                    if self.ser is not serial_connection:
                        self._log("GATE reader stopped because a newer connection replaced it")
                        break
                    if not self.is_open():
                        time.sleep(0.05)
                        continue

                    waiting = 0

                    try:
                        waiting = serial_connection.in_waiting
                    except Exception:
                        pass

                    if waiting <= 0:
                        time.sleep(0.01)
                        continue

                    chunk = serial_connection.read(waiting)

                    if not chunk:
                        time.sleep(0.01)
                        continue

                    buffer += chunk

                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)

                        try:
                            text = line.decode(
                                errors="ignore"
                            ).strip()
                        except Exception:
                            text = ""

                        if not text:
                            continue

                        self._log(f"RX {text}")

                        try:
                            if self.rx_callback and not stop_event.is_set():
                                self.rx_callback(text)

                        except Exception as e:
                            self._log(
                                f"callback error {e}"
                            )

                except Exception as e:
                    self._log(f"reader error {e}")
                    time.sleep(0.05)

        self.rx_thread = threading.Thread(
            target=worker,
            daemon=True
        )

        self.rx_thread.start()

    def stop_reader(self):
        self.rx_running = False
        if self.rx_stop_event is not None:
            self.rx_stop_event.set()
        try:
            if self.rx_thread and self.rx_thread.is_alive():
                self.rx_thread.join(timeout=1.0)

        except Exception:
            pass

        self.rx_thread = None
        self.rx_stop_event = None


class USBManager:
    def __init__(
        self,
        app=None,
        verbose: bool = True,
        prevent_reset: bool = True
    ):

        self.app = app

        self.verbose = verbose
        self.prevent_reset = prevent_reset

        self.handler = SerialHandler(
            verbose=verbose,
            prevent_reset=prevent_reset,
            event_sink=getattr(app, "record_debug_event", None),
        )

        self.port = DEFAULT_SERIAL_PORT
        self.baud = DEFAULT_SERIAL_BAUD
        self.timeout = DEFAULT_SERIAL_TIMEOUT
        self.display_a = None
        self.display_b = None
        self.matrix_a = None
        self.matrix_b = None
        self.display_lock = threading.Lock()
        self.display_connect_lock = threading.Lock()
        self.display_connect_locks = {display_id: threading.Lock() for display_id in range(1, 5)}
        self.display_locks = {display_id: threading.Lock() for display_id in range(1, 5)}
        self.display_pending_lock = threading.Lock()
        self.display_pending = {display_id: None for display_id in range(1, 5)}
        self.display_workers = {display_id: None for display_id in range(1, 5)}
        self.display_errors = {display_id: "" for display_id in range(1, 5)}

    def _log(self, msg: str):
        try:
            if self.app is not None and hasattr(self.app, "record_debug_event"):
                self.app.record_debug_event(f"USB {msg}")
        except Exception:
            pass
        if self.verbose:
            _dbg(msg)

    def diagnostic_snapshot(self):
        """Return only read-only state for the in-application debug window."""
        panels = {}
        for display_id in range(1, 5):
            settings = self._display_settings(display_id)
            port, baud, connection_name = settings or ("", "", "")
            connection = getattr(self, connection_name, None) if connection_name else None
            panels[display_id] = {
                "port": port,
                "baud": baud,
                "open": bool(connection and getattr(connection, "is_open", False)),
                "error": self.display_error(display_id),
                "pending": self.display_pending.get(display_id) is not None,
                "worker": bool(self.display_workers.get(display_id) and self.display_workers[display_id].is_alive()),
            }
        return {
            "at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "available_ports": self.list_port_details(),
            "gate": {
                "port": self.port,
                "baud": self.baud,
                "timeout": self.timeout,
                "open": self.handler.is_open(),
                "reader": bool(self.handler.rx_thread and self.handler.rx_thread.is_alive()),
            },
            "panels": panels,
        }

    def list_ports(self):
        return self.handler.list_ports()

    def list_port_details(self):
        if not PY_SERIAL_AVAILABLE:
            return []

        try:
            return [
                {
                    "device": port.device,
                    "description": port.description or "",
                    "hwid": port.hwid or "",
                    "vid": port.vid,
                    "pid": port.pid,
                    "serial_number": port.serial_number or "",
                }
                for port in list_ports.comports()
            ]
        except Exception:
            return []

    def validate_and_set(
        self,
        port: str,
        baud: int,
        timeout: float
    ):

        self.port = (port or "").strip()

        try:
            self.baud = int(baud)
        except Exception:
            self.baud = DEFAULT_SERIAL_BAUD

        try:
            self.timeout = float(timeout)
        except Exception:
            self.timeout = DEFAULT_SERIAL_TIMEOUT

        self.handler.port = self.port
        self.handler.baud = self.baud
        self.handler.timeout = self.timeout

    def connect(self):
        self.handler.open(
            self.port,
            self.baud,
            self.timeout
        )
        return self.handler.is_open()

    def disconnect(self):
        self.handler.close()

    def start_reader(self, callback):
        if self.handler.rx_running:
            return
        self.connect()
        self.handler.start_reader(callback)

    def stop_reader(self):
        self.handler.stop_reader()

    def reconnect(self, callback=None):
        """Apply the current gate settings even when a reader is already running."""
        self.disconnect()
        if not self.port:
            return False
        if not self.connect():
            return False
        if callback is not None:
            self.handler.start_reader(callback)
        return self.handler.is_open()

    def reset_gate(self):
        """Release only the gate COM handle; the caller starts its normal resync."""
        self._log("GATE manual reset requested")
        self.disconnect()
        return True

    def _display_settings(self, display_id, port_override=None, baud_override=None):
        """Return the app settings and connection attribute for one of four panels."""
        settings = {
            1: ("display_port_a", "display_baud_a", "display_a"),
            2: ("display_port_b", "display_baud_b", "display_b"),
            3: ("matrix_port_a", "matrix_baud_a", "matrix_a"),
            4: ("matrix_port_b", "matrix_baud_b", "matrix_b"),
        }.get(display_id)
        if settings is None:
            return None
        port_name, baud_name, connection_name = settings
        port = str(
            port_override if port_override is not None
            else getattr(self.app, port_name, "") or ""
        ).strip()
        baud = (
            baud_override if baud_override is not None
            else getattr(self.app, baud_name, DEFAULT_SERIAL_BAUD)
        )
        return port, baud, connection_name

    def _display_timeout(self, display_id, timeout_override=None):
        if timeout_override is not None:
            value = timeout_override
        else:
            timeout_name = {
                1: "display_timeout_a",
                2: "display_timeout_b",
                3: "matrix_timeout_a",
                4: "matrix_timeout_b",
            }.get(display_id)
            value = getattr(self.app, timeout_name, 1.0) if timeout_name else 1.0
        try:
            return min(30.0, max(0.05, float(value)))
        except (TypeError, ValueError):
            return 1.0

    def _connect_display(self, display_id, port_override=None, baud_override=None, timeout_override=None):
        lock = self.display_connect_locks.get(display_id)
        if lock is None:
            return False
        with lock:
            return self._connect_display_locked(display_id, port_override, baud_override, timeout_override)

    def _connect_display_locked(self, display_id, port_override=None, baud_override=None, timeout_override=None):
        settings = self._display_settings(display_id, port_override, baud_override)
        if settings is None:
            return False
        port, baud, connection_name = settings
        current = getattr(self, connection_name)

        if not port:
            self.display_errors[display_id] = "Pro displej není zvolený COM port."
            if current is not None:
                self.disconnect_display(display_id)
            return False

        try:
            baud = int(baud)
        except (TypeError, ValueError):
            baud = DEFAULT_SERIAL_BAUD
        timeout = self._display_timeout(display_id, timeout_override)

        if current is not None and current.is_open:
            if current.port == port and current.baudrate == baud:
                return True
            self.disconnect_display(display_id)
        elif current is not None:
            self.disconnect_display(display_id)

        if not PY_SERIAL_AVAILABLE:
            error = "pyserial není nainstalován."
            self.display_errors[display_id] = error
            self._log(f"Display connect skipped: {error}")
            return False

        display = None
        try:
            display = serial.Serial(
                port=None,
                baudrate=baud,
                timeout=timeout,
                write_timeout=timeout
            )
            display.port = port
            if self.prevent_reset:
                try:
                    display.dtr = False
                    display.rts = False
                except Exception:
                    pass
            display.open()
            time.sleep(1)
            display.reset_input_buffer()
            display.reset_output_buffer()
        except Exception as e:
            self.display_errors[display_id] = str(e)
            self._log(f"Display {display_id} connect error {e}")
            try:
                if display is not None:
                    display.close()
            except Exception:
                pass
            return False

        setattr(self, connection_name, display)
        self.display_errors[display_id] = ""
        return True

    def connect_displays(self):
        with self.display_connect_lock:
            return {
                display_id: self._connect_display(display_id)
                for display_id in range(1, 5)
            }


    def send_display(self, id, text):
        with self.display_locks[id]:
            self._connect_display(id)
            settings = self._display_settings(id)
            if settings is None:
                return False
            _port, _baud, connection_name = settings
            ser = getattr(self, connection_name)
            if ser is None or not ser.is_open:
                self.disconnect_display(id)
                self._connect_display(id)
                ser = getattr(self, connection_name)
            if ser is None:
                return False
            msg = (str(text) + "\r\n").encode()
            self._log(f"ID-{id} {_port} TX {msg.decode(errors='replace').strip()}")
            try:
                try:
                    waiting = ser.in_waiting
                    if waiting:
                        reply = ser.read(waiting)
                        self._log(f"ID-{id} {_port} RX {reply.decode(errors='replace').strip()}")
                except Exception:
                    pass
                ser.write(msg)
                ser.flush()
                self.display_errors[id] = ""
                return True
            except Exception as e:
                self.display_errors[id] = str(e)
                self._log(f"Display {id} error {e}")
                self.disconnect_display(id)
                return False

    def send_display_to_port(self, id, text, port, baud, timeout=None):
        """Send a test command using the current values shown in the dialog."""
        if not self._connect_display(id, port_override=port, baud_override=baud, timeout_override=timeout):
            return False

        settings = self._display_settings(id, port, baud)
        if settings is None:
            return False
        _selected_port, _selected_baud, connection_name = settings
        ser = getattr(self, connection_name)

        try:
            msg = (str(text) + "\r\n").encode()
            self._log(f"Display test msg: {msg}")
            with self.display_lock:
                try:
                    waiting = ser.in_waiting
                    if waiting:
                        ser.read(waiting)
                except Exception:
                    pass
                ser.write(msg)
                ser.flush()
            self.display_errors[id] = ""
            return True
        except Exception as e:
            self.display_errors[id] = str(e)
            self._log(f"Display test error {e}")
            self.disconnect_display(id)
            return False

    def display_error(self, id):
        return self.display_errors.get(id, "")

    def probe_display(self, id):
        """Send the firmware's harmless PING request and record its reply."""
        if id not in self.display_locks:
            return False, "Neplatné ID panelu."
        with self.display_locks[id]:
            if not self._connect_display(id):
                return False, self.display_error(id) or "Panel nelze otevřít."
            settings = self._display_settings(id)
            _port, _baud, connection_name = settings
            ser = getattr(self, connection_name)
            try:
                try:
                    waiting = ser.in_waiting
                    if waiting:
                        ser.read(waiting)
                except Exception:
                    pass
                self._log(f"ID-{id} {_port} TX PING")
                ser.write(b"PING\r\n")
                ser.flush()
                deadline = time.monotonic() + self._display_timeout(id)
                reply_bytes = b""
                while time.monotonic() < deadline:
                    waiting = getattr(ser, "in_waiting", 0)
                    if waiting:
                        reply_bytes += ser.read(waiting)
                        break
                    time.sleep(0.02)
                if not reply_bytes:
                    # One final bounded read also supports serial adapters
                    # whose in_waiting counter is updated just after PING.
                    reply_bytes = ser.read(1)
                reply = reply_bytes.decode(errors="replace").strip()
                self._log(f"ID-{id} {_port} RX {reply or '(bez odpovědi)'}")
                # CLS, SPD and TXT each acknowledge with OK. A USB read can
                # contain those earlier acknowledgements together with the
                # PONG for this probe, so inspect complete response lines.
                reply_lines = [line.strip().upper() for line in reply.splitlines()]
                success = "PONG" in reply_lines
                if not success:
                    self.display_errors[id] = reply or "Bez odpovědi na PING."
                    # A USB-CDC handle may remain marked open after a cable was
                    # removed. Drop it here so the next independent retry opens
                    # a fresh connection instead of writing to a stale handle.
                    self.disconnect_display(id)
                return success, reply or "Bez odpovědi na PING."
            except Exception as error:
                self.display_errors[id] = str(error)
                self._log(f"ID-{id} {_port} PING error {error}")
                self.disconnect_display(id)
                return False, str(error)

    def send_display_latest(self, id, text):
        """Queue at most the newest pending message for one display."""
        if id not in self.display_pending:
            return False

        with self.display_pending_lock:
            self.display_pending[id] = text
            worker = self.display_workers[id]
            if worker is not None and worker.is_alive():
                return True

            worker = threading.Thread(
                target=self._display_latest_worker,
                args=(id,),
                daemon=True
            )
            self.display_workers[id] = worker
            worker.start()
        return True

    def _display_latest_worker(self, id):
        while True:
            with self.display_pending_lock:
                text = self.display_pending[id]
                if text is None:
                    self.display_workers[id] = None
                    return
                self.display_pending[id] = None

            self.send_display(id, text)

    def disconnect_display(self, id):
        settings = self._display_settings(id)
        if settings is None:
            return
        _port, _baud, connection_name = settings
        display = getattr(self, connection_name)

        was_open = False
        try:
            if display:
                was_open = bool(display.is_open)
                display.close()
        except Exception:
            pass

        if was_open:
            # Give Windows and common USB-serial drivers time to release the handle.
            time.sleep(0.2)

        setattr(self, connection_name, None)

    def reset_display(self, id):
        """Release exactly one panel port so the app can reopen and restore it."""
        if id not in self.display_locks:
            return False
        with self.display_locks[id]:
            self._log(f"Display {id} manual reset requested")
            self.disconnect_display(id)
            self.display_errors[id] = ""
        return True


    def disconnect_displays(self):
        with self.display_pending_lock:
            for display_id in self.display_pending:
                self.display_pending[display_id] = None

        for display_id in range(1, 5):
            self.disconnect_display(display_id)


    def send_start_async(self, on_result):
        def worker():
            try:
                self.connect()
                self.handler.send_start()
                on_result(True, "sent")

            except Exception as e:
                on_result(False, str(e))

        t = threading.Thread(
            target=worker,
            daemon=True
        )

        t.start()
        return t


    def send_finish_async(self, on_result):
        def worker():
            try:
                self.connect()
                self.handler.send_finish()
                on_result(True, "sent")

            except Exception as e:
                on_result(False, str(e))

        t = threading.Thread(
            target=worker,
            daemon=True
        )

        t.start()
        return t


if __name__ == "__main__":
    print("usb_module selftest")
    um = USBManager(
        verbose=True,
        prevent_reset=True
    )

    ports = um.list_ports()
    print("ports", ports)

    if not ports:
        sys.exit(0)

    um.validate_and_set(
        ports[0],
        9600,
        2.0
    )

    def rx(line):
        print("RX:", line)

    um.start_reader(rx)

    while True:
        cmd = input(
            "s=start f=finish q=quit > "
        ).strip().lower()

        if cmd == "q":
            break

        if cmd == "s":
            um.send_start_async(
                lambda ok, reason:
                print("START", ok, reason)
            )

        elif cmd == "f":
            um.send_finish_async(
                lambda ok, reason:
                print("FINISH", ok, reason)
            )

    um.disconnect()
