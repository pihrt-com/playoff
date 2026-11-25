from pathlib import Path

import pytest


ARDUINO = Path(__file__).resolve().parents[1] / "Arduino"


@pytest.mark.parametrize(
    ("device", "versions"),
    [
        ("7 segment display", ("1.0", "1.1", "1.2")),
        ("matrix display", ("1.0",)),
        ("gate semaphore", ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5", "1.6")),
    ],
)
def test_versioned_arduino_sketches_are_in_matching_folders(device, versions):
    for version in versions:
        sketch_name = f"fw{version}"
        sketch = ARDUINO / device / sketch_name / f"{sketch_name}.ino"
        assert sketch.is_file(), f"Chybí Arduino sketch: {sketch}"
        source = sketch.read_text(encoding="utf-8")
        assert "void setup(" in source
        assert "void loop(" in source
