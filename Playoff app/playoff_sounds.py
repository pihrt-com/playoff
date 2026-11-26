"""Sound assignments, local media and portable Playoff setup files."""

import ctypes
import hashlib
import json
import math
import os
import re
import struct
import tempfile
import threading
import wave
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile, is_zipfile


BUILTINS = {"short": ("Krátké pípnutí", 0.12), "long": ("Dlouhé pípnutí", 0.55)}
EVENTS = {
    "click": "Provozní kliknutí",
    "start": "PLAYOFF · START závodu",
    "start_error": "PLAYOFF · START – chyba spojení",
    "playoff_end": "PLAYOFF · Vypršení odpočtu",
    "promo": "Zapnutí PROMO",
    "laps_end": "LAPS · Vypršení odpočtu",
    "laps_warning": "LAPS · Upozornění před vypršením",
}
for device in ("GATE", "ID1", "ID2", "ID3", "ID4"):
    EVENTS[f"{device}_lost"] = f"{device} · Výpadek USB"
    EVENTS[f"{device}_restored"] = f"{device} · Obnovení USB"

SOUND_ID = re.compile(r"[0-9a-f]{64}--[\w -]{1,60}\.(?:wav|mp3)")
MEDIA_LIMIT = 64 * 1024 * 1024
ARCHIVE_LIMIT = 512 * 1024 * 1024
MAX_SIMULTANEOUS_SOUNDS = 8


def bounded_int(value, minimum, maximum, default):
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def normalize_sounds(value):
    value = value if isinstance(value, dict) else {}
    result = {}
    for event in EVENTS:
        item = value.get(event)
        item = item if isinstance(item, dict) else {}
        sound = item.get("sound", "long" if event.endswith("_end") else "short")
        if not isinstance(sound, str) or (sound not in BUILTINS and not SOUND_ID.fullmatch(sound)):
            sound = "short"
        result[event] = {
            "sound": sound,
            "enabled": item.get("enabled") is True,
            "volume": bounded_int(item.get("volume"), 0, 100, 75),
        }
    return result


def media_root():
    return Path.home() / ".playoff_assets"


def sound_library():
    sounds = {key: value[0] for key, value in BUILTINS.items()}
    folder = media_root() / "sounds"
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.is_file() and SOUND_ID.fullmatch(path.name):
                sounds[path.name] = f"{path.name[66:]} [{path.name[:8]}]"
    return sounds


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def add_sound(source):
    source = Path(source)
    suffix = source.suffix.lower()
    if suffix not in (".wav", ".mp3"):
        raise ValueError("Vyberte soubor WAV nebo MP3.")
    with source.open("rb") as handle:
        data = handle.read(MEDIA_LIMIT + 1)
    if not data or len(data) > MEDIA_LIMIT:
        raise ValueError("Zvuk musí mít velikost mezi 1 bajtem a 64 MiB.")
    name = re.sub(r"[^\w -]", "_", source.stem)[:60].strip() or "Zvuk"
    sound = f"{hashlib.sha256(data).hexdigest()}--{name}{suffix}"
    write_bytes(media_root() / "sounds" / sound, data)
    return sound


def add_sounds(sources):
    """Import each file independently and report failures without losing successes."""
    added, errors = [], []
    for source in sources:
        try:
            added.append(add_sound(source))
        except (OSError, ValueError) as error:
            errors.append(f"{Path(source).name}: {error}")
    return added, errors


def sound_path(sound):
    if sound not in BUILTINS:
        if not SOUND_ID.fullmatch(sound):
            raise ValueError("Neplatný zvuk.")
        path = media_root() / "sounds" / sound
        if not path.is_file():
            raise FileNotFoundError("Zvuk chybí. Načtěte nastavení ze ZIPu nebo ho přidejte do úložiště.")
        return path

    path = media_root() / "builtins" / f"{sound}.wav"
    if not path.is_file():
        rate = 22050
        count = int(rate * BUILTINS[sound][1])
        samples = (
            int(15000 * math.sin(2 * math.pi * 850 * i / rate)
                * min(1, i / 150, (count - i) / 150))
            for i in range(count)
        )
        buffer = BytesIO()
        with wave.open(buffer, "wb") as file:
            file.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            file.writeframes(struct.pack(f"<{count}h", *samples))
        write_bytes(path, buffer.getvalue())
    return path


class SoundPlayer:
    """Play on Windows' default output without blocking the Tk event loop."""

    def __init__(self):
        self.executor = ThreadPoolExecutor(
            max_workers=MAX_SIMULTANEOUS_SOUNDS, thread_name_prefix="PlayoffAudio")
        self.pending = set()
        self.stopping = threading.Event()

    def play(self, sound, volume):
        self.pending = {job for job in self.pending if not job.done()}
        if len(self.pending) >= MAX_SIMULTANEOUS_SOUNDS:
            job = Future()
            job.set_exception(RuntimeError("Přehrávač je vytížený. Zkuste to znovu."))
        else:
            job = self.executor.submit(self._play, sound, volume, self.stopping)
            self.pending.add(job)
        return job

    def close(self):
        self.stopping.set()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def stop(self):
        """Stop current sounds without disabling future playback."""
        self.stopping.set()
        self.stopping = threading.Event()

    @staticmethod
    def _play(sound, volume, stopping=None):
        import time
        from uuid import uuid4

        if stopping is not None and stopping.is_set():
            return
        path = sound_path(sound)
        if os.name != "nt":
            raise RuntimeError("Přehrávání vyžaduje Windows.")
        api = ctypes.windll.winmm
        alias = f"playoff{uuid4().hex}"

        def command(value):
            reply = ctypes.create_unicode_buffer(256)
            code = api.mciSendStringW(value, reply, len(reply), None)
            if code:
                api.mciGetErrorStringW(code, reply, len(reply))
                raise RuntimeError(reply.value or f"Chyba přehrávání ({code})")
            return reply.value

        command(f'open "{path}" type mpegvideo alias {alias}')
        try:
            command(f"setaudio {alias} volume to {volume * 10}")
            if stopping is not None and stopping.is_set():
                return
            command(f"play {alias}")
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline and command(f"status {alias} mode") == "playing":
                if stopping is not None:
                    if stopping.wait(0.05):
                        break
                else:
                    time.sleep(0.05)
        finally:
            command(f"close {alias}")


def save_portable_setup(filename, settings, background=None):
    sounds = [
        media_root() / "sounds" / sound for sound in sound_library() if sound not in BUILTINS
    ]
    referenced = {item["sound"] for item in normalize_sounds(settings.get("sounds")).values()}
    missing = referenced - BUILTINS.keys() - {path.name for path in sounds}
    if missing:
        raise ValueError("Některý přiřazený zvuk chybí v úložišti.")
    data = json.dumps(dict(settings, bg_path=None, portable_setup=1), ensure_ascii=False, indent=2).encode("utf-8")
    image = BytesIO()
    if background is not None:
        background.save(image, format="PNG")
    sizes = [len(data), image.tell(), *(path.stat().st_size for path in sounds)]
    if sum(sizes) > ARCHIVE_LIMIT or max(sizes) > MEDIA_LIMIT:
        raise ValueError("Přenosné nastavení překračuje povolenou velikost souborů.")
    filename = Path(filename)
    with tempfile.NamedTemporaryFile(dir=filename.parent, delete=False) as output:
        temporary = Path(output.name)
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
            archive.writestr("settings.json", data)
            for path in sounds:
                archive.write(path, f"sounds/{path.name}")
            if background is not None:
                archive.writestr("background.png", image.getvalue())
        os.replace(temporary, filename)
    finally:
        temporary.unlink(missing_ok=True)


def load_setup_file(filename):
    if not is_zipfile(filename):
        with open(filename, encoding="utf-8-sig") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Nastavení musí být objekt JSON.")
        return data

    with ZipFile(filename) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        if (len({name.casefold() for name in names}) != len(entries) or "settings.json" not in names
                or sum(entry.file_size for entry in entries) > ARCHIVE_LIMIT):
            raise ValueError("ZIP má neplatnou strukturu nebo velikost.")
        for entry in entries:
            name = entry.filename
            valid = name in ("settings.json", "background.png") or (
                name.startswith("sounds/") and SOUND_ID.fullmatch(name[7:])
            )
            if not valid or entry.file_size > MEDIA_LIMIT:
                raise ValueError("ZIP obsahuje nepovolenou položku nebo příliš velký soubor.")

        data = json.loads(archive.read("settings.json"))
        if not isinstance(data, dict) or data.get("portable_setup") != 1:
            raise ValueError("ZIP není přenosné nastavení Playoff.")
        referenced = {item["sound"] for item in normalize_sounds(data.get("sounds")).values()}
        if any(f"sounds/{sound}" not in names for sound in referenced - BUILTINS.keys()):
            raise ValueError("V ZIPu chybí přiřazený zvuk.")

        data["bg_path"] = None
        assets = {}
        if "background.png" in names:
            from PIL import Image
            background = archive.read("background.png")
            with Image.open(BytesIO(background), formats=("PNG",)) as image:
                image.verify()
            path = media_root() / "backgrounds" / (hashlib.sha256(background).hexdigest() + ".png")
            assets[path] = background
            data["bg_path"] = str(path)
        for name in names:
            if name.startswith("sounds/"):
                content = archive.read(name)
                if hashlib.sha256(content).hexdigest() != name[7:71]:
                    raise ValueError("Poškozený zvuk v ZIPu.")
                assets[media_root() / name] = content
        for path, content in assets.items():
            if not path.exists() or path.read_bytes() != content:
                write_bytes(path, content)
        return data
