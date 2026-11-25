from pathlib import Path
import re

import pytest


ARDUINO = Path(__file__).resolve().parents[1] / "Arduino"


def firmware_sketches(device):
    folders = [p for p in (ARDUINO / device).iterdir() if p.is_dir() and re.fullmatch(r"fw\d+(?:\.\d+)+", p.name)]
    return sorted(folders, key=lambda p: tuple(map(int, p.name[2:].split("."))))


@pytest.mark.parametrize("device", ["7 segment display", "matrix display", "gate semaphore"])
def test_versioned_arduino_sketches_are_in_matching_folders(device):
    folders = firmware_sketches(device)
    assert folders, f"Chybí verze firmware: {device}"
    for folder in folders:
        sketch = folder / f"{folder.name}.ino"
        assert sketch.is_file(), f"Chybí Arduino sketch: {sketch}"
        source = sketch.read_text(encoding="utf-8")
        assert "void setup(" in source
        assert "void loop(" in source


@pytest.mark.parametrize("device", ["7 segment display", "matrix display", "gate semaphore"])
def test_latest_version_response_matches_folder(device):
    folder = firmware_sketches(device)[-1]
    source = (folder / f"{folder.name}.ino").read_text(encoding="utf-8")
    assert re.search(r'Serial\.println\(F\("(?:MATRIX |GATE )?FW ' + re.escape(folder.name[2:]) + r'"\)\)', source)
    assert re.search(r'(?i)"ver"', source)
