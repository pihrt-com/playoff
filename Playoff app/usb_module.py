# usb_module.py
"""
USB/Serial helper module for playoff.py
Vylepšeno pro debugging:
 - verbose režim (tisk časovaných debug zpráv)
 - volitelný prevent_reset (nechat DTR/RTS False) -> zabraňuje resetu Arduina
 - robustní open s retry a detailní chybové hlášky
 - send_start_sync (blokující, vrací (ok, reason)) a send_start_async (callback)
 - detailní čtení odpovědi po bajtu, kontrola 'ok' case-insensitive
 - kompatibilita když pyserial chybí (vrací jasné chyby)
"""

from __future__ import annotations
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
DEFAULT_SERIAL_BAUD = 9600
DEFAULT_SERIAL_TIMEOUT = 2.0


def _now():
    return time.strftime("%H:%M:%S")


def _dbg(msg: str):
    # Jednoduchý debug výstup s časem - přepnout/redirektovat pokud chceš
    print(f"[usb_module {_now()}] {msg}", file=sys.stderr)


class SerialHandler:
    """
    Nízká vrstva: otevírání, čtení, zápis.
    Používej metody open/close a send_and_wait_ok (synchronní).
    """

    def __init__(self, verbose: bool = False, prevent_reset: bool = True):
        self.ser = None
        self.port = DEFAULT_SERIAL_PORT
        self.baud = DEFAULT_SERIAL_BAUD
        self.timeout = DEFAULT_SERIAL_TIMEOUT
        self.verbose = verbose
        self.prevent_reset = prevent_reset

    def _log(self, msg: str):
        if self.verbose:
            _dbg(msg)

    def list_ports(self):
        if not PY_SERIAL_AVAILABLE:
            self._log("pyserial není dostupný, list_ports vrací []")
            return []
        try:
            ports = [p.device for p in list_ports.comports()]
            self._log(f"list_ports -> {ports}")
            return ports
        except Exception as e:
            self._log(f"Chyba při získávání portů: {e}")
            return []

    def open(self, port=None, baud=None, timeout=None, retries: int = 2, retry_delay: float = 0.12):
        if not PY_SERIAL_AVAILABLE:
            raise RuntimeError("pyserial není nainstalován (pip install pyserial)")

        if port:
            self.port = port
        if baud:
            self.baud = int(baud)
        if timeout is not None:
            self.timeout = float(timeout)

        last_exc = None

        for attempt in range(1, retries + 1):
            try:
                self._log(f"Otevírám port {self.port} @ {self.baud}, attempt {attempt}/{retries}")

                # ⬇⬇⬇ OPRAVA ZDE - OTEVÍRAT AŽ PO NASTAVENÍ DTR/RTS ⬇⬇⬇
                self.ser = serial.Serial()
                self.ser.port = self.port
                self.ser.baudrate = self.baud
                self.ser.timeout = 0
                self.ser.write_timeout = 1

                if self.prevent_reset:
                    try:
                        self.ser.dtr = False
                        self.ser.rts = False
                        self._log("Nastaveno DTR/RTS = False (prevent_reset=True) — před open()")
                    except Exception as e:
                        self._log(f"Nelze nastavit DTR/RTS před open: {e}")

                self.ser.open()
                # ⬆⬆⬆ END OF FIX ⬆⬆⬆

                time.sleep(0.05)

                # Vyčistit buffery
                try:
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                except Exception as e:
                    self._log(f"reset buffer chybka: {e}")

                self._log("Port otevřen OK")
                return

            except Exception as e:
                last_exc = e
                self._log(f"Chyba při otevírání portu (attempt {attempt}): {e}")

                try:
                    if self.ser:
                        self.ser.close()
                except Exception:
                    pass

                self.ser = None
                time.sleep(retry_delay)

        raise last_exc


    def close(self):
        try:
            if self.ser:
                self._log("Zavírám serial port")
                self.ser.close()
        except Exception as e:
            self._log(f"Chyba při close: {e}")
        self.ser = None

    def send_and_wait_ok(self, payload: bytes = b"start\n"):
        """
        Synchronně pošle payload a čeká až 'ok' přijde do self.timeout sekund.
        Vrací (True, "ok") nebo (False, reason).
        """
        if not PY_SERIAL_AVAILABLE:
            return False, "pyserial_missing"

        # otevřít port (pokud se nepodaří, vrátit open_error)
        try:
            self.open(self.port, self.baud, self.timeout)
        except Exception as e:
            return False, f"open_error: {e}"

        try:
            self._log(f"Odesílám -> {payload!r}")
            # write + flush
            try:
                self.ser.write(payload)
                if hasattr(self.ser, "flush"):
                    self.ser.flush()
            except Exception as e:
                self._log(f"Chyba při zápisu: {e}")
                self.close()
                return False, f"write_error: {e}"

            deadline = time.time() + float(self.timeout)
            buffer = b""
            self._log(f"Čekám odpověď do {self.timeout} s (deadline {deadline})")
            while time.time() < deadline:
                try:
                    waiting = 0
                    try:
                        waiting = self.ser.in_waiting
                    except Exception:
                        # in_waiting může házet u některých ovladačů, fallback na read(1)
                        waiting = 0

                    if waiting:
                        chunk = self.ser.read(waiting)
                        if not chunk:
                            # nic nepřišlo — pauza
                            time.sleep(0.01)
                            continue
                        buffer += chunk
                        self._log(f"Přijato chunk -> {chunk!r}; buffer teraz {buffer!r}")
                        # rychlá kontrola substringu 'ok' case-insensitive
                        try:
                            if b"ok" in buffer.lower():
                                self._log("Detekováno 'ok' v bufferu")
                                self.close()
                                return True, "ok"
                        except Exception:
                            pass
                    else:
                        # není nic k přečtení: pokusíme se přečíst 1 byte jako fallback
                        ch = self.ser.read(1)
                        if ch:
                            buffer += ch
                            self._log(f"Přijato fallback byte -> {ch!r}; buffer teraz {buffer!r}")
                            try:
                                if b"ok" in buffer.lower():
                                    self._log("Detekováno 'ok' v bufferu")
                                    self.close()
                                    return True, "ok"
                            except Exception:
                                pass
                        else:
                            time.sleep(0.01)
                except Exception as e:
                    self._log(f"Chyba při čtení: {e}")
                    self.close()
                    return False, f"read_error: {e}"

            # timeout reached
            self._log("Timeout: žádná odpověď do deadlinu")
            self.close()
            return False, "timeout"
        finally:
            # jistě zavřeme i ve finally (close volá beze zbytku)
            try:
                if self.ser:
                    self.close()
            except Exception:
                pass


class USBManager:
    """
    Vyšší vrstva používaná aplikací:
     - může se inicializovat s verbose=True pro debug
     - prevent_reset (default True) zabrání resetu Arduina při otevření
    """

    def __init__(self, app=None, verbose: bool = True, prevent_reset: bool = True):
        """
        app: volitelná reference na GUI aplikaci (nepovinné)
        verbose: tisk debug zpráv
        prevent_reset: pokud True nastavíme DTR/RTS False při otevření -> zabrání resetu Arduina
        """
        self.app = app
        self.handler = SerialHandler(verbose=verbose, prevent_reset=prevent_reset)
        self.port = DEFAULT_SERIAL_PORT
        self.baud = DEFAULT_SERIAL_BAUD
        self.timeout = DEFAULT_SERIAL_TIMEOUT
        self.verbose = verbose
        self.prevent_reset = prevent_reset
        if self.verbose:
            _dbg(f"USBManager init: verbose={verbose}, prevent_reset={prevent_reset}")

    def _log(self, msg: str):
        if self.verbose:
            _dbg(msg)

    def list_ports(self):
        return self.handler.list_ports()

    def validate_and_set(self, port: str, baud: int, timeout: float):
        """
        Uloží parametry (neprovádí blockující open).
        """
        self.port = (port or "").strip()
        try:
            self.baud = int(baud)
        except Exception:
            self.baud = DEFAULT_SERIAL_BAUD
        try:
            self.timeout = float(timeout)
        except Exception:
            self.timeout = DEFAULT_SERIAL_TIMEOUT

        # Propaguj do handleru
        self.handler.port = self.port
        self.handler.baud = self.baud
        self.handler.timeout = self.timeout
        self.handler.prevent_reset = self.prevent_reset

        self._log(f"validate_and_set: port={self.port} baud={self.baud} timeout={self.timeout}")

    def send_start_async(self, on_result):
        """
        Asynchroně pošle 'start' a zavolá on_result(ok_bool, reason_str).
        on_result bude volán z worker threadu — GUI musí marshallowat do mainloop.
        """
        def worker():
            self._log(f"[async] worker spouští send_and_wait_ok (port={self.port})")
            ok, reason = self.handler.send_and_wait_ok(b"start\n")
            self._log(f"[async] worker dokončen -> ok={ok} reason={reason}")
            try:
                on_result(ok, reason)
            except Exception as e:
                self._log(f"[async] chyba v on_result callbacku: {e}")

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        return t

    def send_start_sync(self, timeout_override: float = None):
        """
        Blokující verze, vrací (ok_bool, reason_str). Uživatelsky užitečné pro testy.
        """
        if timeout_override is not None:
            old = self.handler.timeout
            self.handler.timeout = float(timeout_override)
            self._log(f"send_start_sync: dočasně nastavím timeout na {timeout_override}")
            try:
                ok, reason = self.handler.send_and_wait_ok(b"start\n")
            finally:
                self.handler.timeout = old
            return ok, reason
        else:
            return self.handler.send_and_wait_ok(b"start\n")


# Pokud modul spouštíš přímo, ukáže se rychlý test:
if __name__ == "__main__":
    print("usb_module selftest (verbose).")
    print("pyserial:", PY_SERIAL_AVAILABLE)
    um = USBManager(verbose=True, prevent_reset=True)
    ports = um.list_ports()
    print("Ports:", ports)
    if ports:
        p = ports[0]
        print(f"Testing port {p} -> sending 'start' (timeout {um.timeout}s)")
        um.validate_and_set(p, um.baud, um.timeout)
        ok, reason = um.send_start_sync()
        print("Result:", ok, reason)
    else:
        print("No ports found.")
