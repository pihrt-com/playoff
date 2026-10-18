import argparse
import hashlib
import os
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import tkinter as tk
from tkinter import messagebox, ttk


CHUNK_SIZE = 256 * 1024
DOWNLOAD_TIMEOUT = 30


class DownloadCancelled(Exception):
    pass


class IntegrityError(Exception):
    pass


def format_bytes(value):
    value = max(0, int(value or 0))
    units = ("B", "KB", "MB", "GB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024


def describe_error(error):
    if isinstance(error, urllib.error.HTTPError):
        if error.code == 404:
            return "Instalační soubor nebyl na serveru nalezen (HTTP 404)."
        return f"Server vrátil chybu HTTP {error.code}."
    if isinstance(error, urllib.error.URLError):
        reason = error.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return "Připojení k serveru vypršelo."
        return "K serveru se nepodařilo připojit."
    if isinstance(error, (socket.timeout, TimeoutError)):
        return "Připojení k serveru vypršelo."
    if isinstance(error, PermissionError):
        return "Stažený soubor nelze uložit nebo spustit kvůli oprávnění systému."
    if isinstance(error, IntegrityError):
        return str(error)
    return f"Aktualizaci se nepodařilo dokončit: {error}"


def _content_length(response):
    value = response.headers.get("Content-Length")
    try:
        return int(value) if value else 0
    except (TypeError, ValueError):
        return 0


def download_installer(
    url,
    destination,
    expected_sha256="",
    expected_size=0,
    progress_callback=None,
    cancel_event=None,
    timeout=DOWNLOAD_TIMEOUT,
    opener=None,
):
    opener = opener or urllib.request.urlopen
    expected_sha256 = (expected_sha256 or "").strip().lower()
    expected_size = int(expected_size or 0)
    cancel_event = cancel_event or threading.Event()
    part_path = destination + ".part"
    os.makedirs(os.path.dirname(destination), exist_ok=True)

    try:
        if os.path.exists(part_path):
            os.remove(part_path)

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Playoff-Updater/1.0"},
        )
        digest = hashlib.sha256()
        received = 0

        with opener(request, timeout=timeout) as response:
            total = expected_size or _content_length(response)
            if progress_callback:
                progress_callback(received, total)

            with open(part_path, "wb") as output:
                while True:
                    if cancel_event.is_set():
                        raise DownloadCancelled("Stahování bylo zrušeno.")
                    block = response.read(CHUNK_SIZE)
                    if not block:
                        break
                    output.write(block)
                    digest.update(block)
                    received += len(block)
                    if progress_callback:
                        progress_callback(received, total)

        if cancel_event.is_set():
            raise DownloadCancelled("Stahování bylo zrušeno.")
        if received == 0:
            raise IntegrityError("Server vrátil prázdný instalační soubor.")
        if expected_size and received != expected_size:
            raise IntegrityError(
                f"Stažený soubor má nesprávnou velikost ({format_bytes(received)} místo {format_bytes(expected_size)})."
            )
        if expected_sha256 and digest.hexdigest().lower() != expected_sha256:
            raise IntegrityError("Kontrolní součet staženého instalátoru nesouhlasí.")

        os.replace(part_path, destination)
        return received, digest.hexdigest().lower()
    except Exception:
        try:
            if os.path.exists(part_path):
                os.remove(part_path)
        except OSError:
            pass
        raise


def detached_creation_flags():
    return (
        getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )


def launch_installer(installer_path):
    return subprocess.Popen(
        [installer_path],
        creationflags=detached_creation_flags(),
        close_fds=True,
    )


def launch_original_application(target_path):
    if not target_path or not os.path.exists(target_path):
        raise FileNotFoundError("Původní aplikace nebyla nalezena.")
    command = [target_path]
    if target_path.lower().endswith(".py"):
        command = [sys.executable, target_path]
    return subprocess.Popen(command, close_fds=True)


def installer_destination(version):
    safe_version = "".join(
        char for char in (version or "update") if char.isalnum() or char in ".-_"
    ) or "update"
    directory = os.path.join(tempfile.gettempdir(), "PlayoffUpdater")
    return os.path.join(directory, f"PlayoffSetup_{safe_version}.exe")


class UpdaterWindow:
    def __init__(self, root, args, auto_start=True):
        self.root = root
        self.args = args
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker = None
        self.running = False
        self.indeterminate = False

        root.title("Aktualizace Playoff")
        root.geometry("570x360")
        root.minsize(520, 330)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        container = ttk.Frame(root, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Aktualizace Playoff",
            font=("Arial", 15, "bold"),
        ).pack(anchor="w")

        self.status_var = tk.StringVar(value="Připravuji aktualizaci…")
        ttk.Label(container, textvariable=self.status_var).pack(anchor="w", pady=(12, 5))

        self.progress = ttk.Progressbar(container, mode="determinate", maximum=100)
        self.progress.pack(fill="x")

        self.detail_var = tk.StringVar(value="")
        ttk.Label(container, textvariable=self.detail_var).pack(anchor="w", pady=(5, 10))

        self.log_text = tk.Text(container, height=8, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

        button_frame = ttk.Frame(container)
        button_frame.pack(fill="x", pady=(12, 0))

        self.retry_button = ttk.Button(button_frame, text="Zkusit znovu", command=self.start_download)
        self.retry_button.pack(side="left")
        self.retry_button.pack_forget()

        self.restart_button = ttk.Button(
            button_frame,
            text="Spustit původní Playoff",
            command=self.restart_original,
        )
        self.restart_button.pack(side="left", padx=(8, 0))
        self.restart_button.pack_forget()

        self.close_button = ttk.Button(button_frame, text="Zrušit", command=self.on_close)
        self.close_button.pack(side="right")

        self.log("Updater byl spuštěn.")
        self.root.after(100, self.poll_events)
        if auto_start:
            self.root.after(150, self.start_download)

    def log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def set_indeterminate(self, enabled):
        if enabled and not self.indeterminate:
            self.progress.config(mode="indeterminate")
            self.progress.start(12)
            self.indeterminate = True
        elif not enabled and self.indeterminate:
            self.progress.stop()
            self.progress.config(mode="determinate")
            self.indeterminate = False

    def start_download(self):
        if self.running:
            return
        self.running = True
        self.cancel_event = threading.Event()
        self.progress.config(value=0)
        self.status_var.set("Připojuji se k serveru…")
        self.detail_var.set("")
        self.retry_button.pack_forget()
        self.restart_button.pack_forget()
        self.close_button.config(text="Zrušit", state="normal")
        self.log("Připojuji se k serveru.")

        self.worker = threading.Thread(target=self.download_worker, daemon=True)
        self.worker.start()

    def download_worker(self):
        destination = installer_destination(self.args.version)

        def report(received, total):
            self.events.put(("progress", received, total))

        try:
            received, digest = download_installer(
                self.args.installer_url,
                destination,
                expected_sha256=self.args.sha256,
                expected_size=self.args.size,
                progress_callback=report,
                cancel_event=self.cancel_event,
            )
            self.events.put(("verified", received, digest))
            self.events.put(("status", "Spouštím instalaci…"))
            launch_installer(destination)
            self.events.put(("launched", destination))
        except DownloadCancelled:
            self.events.put(("cancelled",))
        except Exception as error:
            self.events.put(("error", error))

    def handle_progress(self, received, total):
        self.status_var.set("Stahuji instalační soubor…")
        if total > 0:
            self.set_indeterminate(False)
            percent = min(100, received * 100 / total)
            self.progress.config(value=percent)
            self.detail_var.set(
                f"{format_bytes(received)} z {format_bytes(total)}  ({percent:.0f} %)"
            )
        else:
            self.set_indeterminate(True)
            self.detail_var.set(f"Staženo {format_bytes(received)}")

    def show_recovery_buttons(self):
        self.retry_button.pack(side="left")
        if self.args.target_exe and os.path.exists(self.args.target_exe):
            self.restart_button.pack(side="left", padx=(8, 0))
        self.close_button.config(text="Zavřít", state="normal")

    def poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    self.handle_progress(event[1], event[2])
                elif kind == "verified":
                    self.set_indeterminate(False)
                    self.progress.config(value=100)
                    self.status_var.set("Stahování dokončeno. Ověřuji soubor…")
                    self.detail_var.set(f"Staženo {format_bytes(event[1])}")
                    self.log("Instalační soubor byl stažen a úspěšně ověřen.")
                elif kind == "status":
                    self.status_var.set(event[1])
                    self.log(event[1])
                elif kind == "launched":
                    self.running = False
                    self.status_var.set("Instalátor byl spuštěn.")
                    self.detail_var.set("Pokračujte v otevřeném okně instalace.")
                    self.log("Instalátor byl spuštěn. Updater se ukončí.")
                    self.close_button.config(state="disabled")
                    self.root.after(1800, self.root.destroy)
                elif kind == "cancelled":
                    self.running = False
                    self.set_indeterminate(False)
                    self.status_var.set("Aktualizace byla zrušena.")
                    self.detail_var.set("")
                    self.log("Stahování bylo zrušeno.")
                    self.show_recovery_buttons()
                elif kind == "error":
                    self.running = False
                    self.set_indeterminate(False)
                    error = event[1]
                    friendly = describe_error(error)
                    self.status_var.set("Aktualizace se nezdařila.")
                    self.detail_var.set(friendly)
                    self.log(f"CHYBA: {friendly}")
                    self.log(f"Technické podrobnosti: {type(error).__name__}: {error}")
                    self.show_recovery_buttons()
        except queue.Empty:
            pass

        if self.root.winfo_exists():
            self.root.after(100, self.poll_events)

    def restart_original(self):
        try:
            launch_original_application(self.args.target_exe)
        except Exception as error:
            messagebox.showerror(
                "Aktualizace Playoff",
                f"Původní aplikaci se nepodařilo spustit:\n{error}",
                parent=self.root,
            )
            return
        self.root.destroy()

    def on_close(self):
        if self.running:
            self.cancel_event.set()
            self.status_var.set("Ruším stahování…")
            self.close_button.config(state="disabled")
            return
        self.root.destroy()


def parse_arguments(argv):
    parser = argparse.ArgumentParser(description="Playoff updater")
    parser.add_argument("target_exe")
    parser.add_argument("installer_url")
    parser.add_argument("--version", default="update")
    parser.add_argument("--sha256", default="")
    parser.add_argument("--size", type=int, default=0)
    return parser.parse_args(argv)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        args = parse_arguments(argv)
    except SystemExit:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Aktualizace Playoff",
            "Updater nedostal potřebné informace pro stažení aktualizace.",
            parent=root,
        )
        root.destroy()
        return 1

    root = tk.Tk()
    UpdaterWindow(root, args)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
