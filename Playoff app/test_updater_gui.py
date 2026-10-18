import hashlib
import io
import os
import tempfile
import threading
import tkinter as tk
import unittest
import urllib.error
from types import SimpleNamespace
from unittest import mock

import updater


class FakeResponse:
    def __init__(self, data, include_length=True):
        self.stream = io.BytesIO(data)
        self.headers = {}
        if include_length:
            self.headers["Content-Length"] = str(len(data))

    def read(self, size):
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class UpdaterDownloadTests(unittest.TestCase):
    def test_download_reports_progress_and_verifies_file(self):
        data = b"Playoff installer data" * 100
        expected_hash = hashlib.sha256(data).hexdigest()
        progress = []

        def opener(request, timeout):
            self.assertEqual(request.full_url, "https://example.test/setup.exe")
            self.assertEqual(timeout, updater.DOWNLOAD_TIMEOUT)
            return FakeResponse(data)

        with tempfile.TemporaryDirectory() as directory:
            destination = os.path.join(directory, "setup.exe")
            received, digest = updater.download_installer(
                "https://example.test/setup.exe",
                destination,
                expected_sha256=expected_hash,
                expected_size=len(data),
                progress_callback=lambda current, total: progress.append((current, total)),
                opener=opener,
            )

            self.assertEqual(received, len(data))
            self.assertEqual(digest, expected_hash)
            self.assertEqual(open(destination, "rb").read(), data)
            self.assertFalse(os.path.exists(destination + ".part"))
            self.assertEqual(progress[0], (0, len(data)))
            self.assertEqual(progress[-1], (len(data), len(data)))

    def test_bad_checksum_removes_partial_file(self):
        data = b"damaged"
        with tempfile.TemporaryDirectory() as directory:
            destination = os.path.join(directory, "setup.exe")
            with self.assertRaises(updater.IntegrityError):
                updater.download_installer(
                    "https://example.test/setup.exe",
                    destination,
                    expected_sha256="0" * 64,
                    opener=lambda request, timeout: FakeResponse(data),
                )

            self.assertFalse(os.path.exists(destination))
            self.assertFalse(os.path.exists(destination + ".part"))

    def test_cancelled_download_removes_partial_file(self):
        cancel_event = threading.Event()
        cancel_event.set()
        with tempfile.TemporaryDirectory() as directory:
            destination = os.path.join(directory, "setup.exe")
            with self.assertRaises(updater.DownloadCancelled):
                updater.download_installer(
                    "https://example.test/setup.exe",
                    destination,
                    cancel_event=cancel_event,
                    opener=lambda request, timeout: FakeResponse(b"data"),
                )

            self.assertFalse(os.path.exists(destination + ".part"))

    def test_error_messages_are_user_friendly(self):
        not_found = urllib.error.HTTPError(
            "https://example.test/setup.exe", 404, "Not Found", {}, None
        )
        self.assertIn("HTTP 404", updater.describe_error(not_found))
        self.assertIn(
            "nepodařilo připojit",
            updater.describe_error(urllib.error.URLError("offline")),
        )

    def test_argument_parser_accepts_integrity_options(self):
        args = updater.parse_arguments([
            "playoff.exe",
            "https://example.test/setup.exe",
            "--version", "1.0.13",
            "--sha256", "a" * 64,
            "--size", "456",
        ])
        self.assertEqual(args.version, "1.0.13")
        self.assertEqual(args.sha256, "a" * 64)
        self.assertEqual(args.size, 456)

    @mock.patch.object(updater.subprocess, "Popen")
    def test_installer_is_started_detached(self, popen):
        updater.launch_installer("setup.exe")
        popen.assert_called_once_with(
            ["setup.exe"],
            creationflags=updater.detached_creation_flags(),
            close_fds=True,
        )


class UpdaterWindowTests(unittest.TestCase):
    def test_window_contains_progress_status_log_and_recovery_buttons(self):
        root = tk.Tk()
        root.withdraw()
        try:
            args = SimpleNamespace(
                target_exe="playoff.exe",
                installer_url="https://example.test/setup.exe",
                version="1.0.13",
                sha256="",
                size=0,
            )
            window = updater.UpdaterWindow(root, args, auto_start=False)
            root.update_idletasks()

            self.assertEqual(root.title(), "Aktualizace Playoff")
            self.assertEqual(window.progress.cget("maximum"), 100)
            self.assertEqual(window.status_var.get(), "Připravuji aktualizaci…")
            self.assertEqual(window.retry_button.cget("text"), "Zkusit znovu")
            self.assertEqual(
                window.restart_button.cget("text"), "Spustit původní Playoff"
            )
            self.assertIn("Updater byl spuštěn.", window.log_text.get("1.0", "end"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
