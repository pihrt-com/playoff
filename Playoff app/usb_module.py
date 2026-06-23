from __future__ import annotations

#!/usr/bin/env python
# usb_module.py
# test: python usb_module.py
# -*- coding: utf-8 -*-
__author__ = 'Martin Pihrt'

import threading
import time
import sys

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
    def __init__(self, verbose: bool = False, prevent_reset: bool = True):
        self.ser = None
        self.port = DEFAULT_SERIAL_PORT
        self.baud = DEFAULT_SERIAL_BAUD
        self.timeout = DEFAULT_SERIAL_TIMEOUT
        self.verbose = verbose
        self.prevent_reset = prevent_reset
        self.rx_thread = None
        self.rx_running = False
        self.rx_callback = None
        self.write_lock = threading.Lock()
        self.open_lock = threading.Lock()

    def _log(self, msg: str):
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

                    self._log(
                        f"open {self.port} {self.baud} attempt {attempt}"
                    )

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
                    self._log("opened")

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

        self._log(f"TX {payload!r}")
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

        if self.rx_running:
            return

        self.rx_callback = callback
        self.rx_running = True

        def worker():
            buffer = b""
            while self.rx_running:
                try:
                    if not self.is_open():
                        time.sleep(0.05)
                        continue

                    waiting = 0

                    try:
                        waiting = self.ser.in_waiting
                    except Exception:
                        pass

                    if waiting <= 0:
                        time.sleep(0.01)
                        continue

                    chunk = self.ser.read(waiting)

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
                            if self.rx_callback:
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
        try:
            if self.rx_thread and self.rx_thread.is_alive():
                self.rx_thread.join(timeout=0.3)

        except Exception:
            pass

        self.rx_thread = None


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
            prevent_reset=prevent_reset
        )

        self.port = DEFAULT_SERIAL_PORT
        self.baud = DEFAULT_SERIAL_BAUD
        self.timeout = DEFAULT_SERIAL_TIMEOUT
        self.display_a = None
        self.display_b = None
        self.display_lock = threading.Lock()

    def _log(self, msg: str):
        if self.verbose:
            _dbg(msg)

    def list_ports(self):
        return self.handler.list_ports()

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

    def disconnect(self):
        self.handler.close()

    def start_reader(self, callback):
        if self.handler.rx_running:
            return
        self.connect()
        self.handler.start_reader(callback)

    def stop_reader(self):
        self.handler.stop_reader()

    def connect_displays(self):
        try:
            if self.app.display_port_a and self.display_a is None:
                self.display_a = serial.Serial(
                    port=None,
                    baudrate=int(self.app.display_baud_a),
                    timeout=1
                )
                self.display_a.port = self.app.display_port_a
                #self.display_a.dtr = False
                #self.display_a.rts = False
                self.display_a.open()
                time.sleep(1)

            if self.app.display_port_b and self.display_b is None:
                self.display_b = serial.Serial(
                    port=None,
                    baudrate=int(self.app.display_baud_b),
                    timeout=1
                )
                self.display_b.port = self.app.display_port_b
                #self.display_b.dtr = False
                #self.display_b.rts = False
                self.display_b.open()
                time.sleep(1)

        except Exception as e:
            self._log(f"Display connect error {e}")


    def send_display(self, id, text):
        self.connect_displays()

        if id == 1:
            ser = self.display_a
        elif id == 2:
            ser = self.display_b
        else:
            return False

        if ser is None or not ser.is_open:
            self.disconnect_displays()
            self.connect_displays()

            if id == 1:
                ser = self.display_a
            else:
                ser = self.display_b

        if ser is None:
            return False

        try:
            msg = (str(text) + "\r\n").encode()
            self._log(f"Display msg: {msg}")
            with self.display_lock:
                ser.write(msg)
                ser.flush()
            return True

        except Exception as e:
            self._log(f"Display error {e}")
            try:
                if id == 1 and self.display_a:
                    self.display_a.close()

                if id == 2 and self.display_b:
                    self.display_b.close()
            except:
                pass

            if id == 1:
                self.display_a = None
            if id == 2:
                self.display_b = None
            return False      


    def disconnect_displays(self):
        try:
            if self.display_a:
                self.display_a.close()
        except:
            pass

        try:
            if self.display_b:
                self.display_b.close()
        except:
            pass

        self.display_a = None
        self.display_b = None


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