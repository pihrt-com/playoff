"""Exercise the actual matrix UTF-8 decoder and glyph table on a host compiler."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_latest_matrix_decoder_handles_names_and_bad_input(tmp_path):
    compiler = shutil.which("g++")
    if not compiler:
        pytest.skip("Host C++ compiler is not installed")
    from test_firmware_layout import firmware_sketches

    folder = firmware_sketches("matrix display")[-1]
    source = (folder / f"{folder.name}.ino").read_text(encoding="utf-8")
    glyph_code = source[source.index("struct Glyph"):source.index("void sendAll(")]
    harness = r'''
#include <cstdint>
#include <cassert>
using byte = uint8_t;
''' + glyph_code + r'''
int main() {
    const char* text = u8"ÄÖÜäöü ÇĞİŞçğış ČŽü王😀";
    const uint32_t expected[] = {0xC4,0xD6,0xDC,0xE4,0xF6,0xFC,32,
        0xC7,0x11E,0x130,0x15E,0xE7,0x11F,0x131,0x15F,32,
        0x10C,0x17D,0xFC,0x738B,0x1F600};
    for (uint32_t code : expected) assert(utf8Char(text) == code);
    assert(*text == 0);
    assert(latinGlyph(0xC4).accent == ACCENT_UMLAUT);
    assert(latinGlyph(0xDC).accent == ACCENT_UMLAUT);
    assert(latinGlyph(0x11E).base == 'G');
    assert(latinGlyph(0x15F).base == 'S');
    assert(latinGlyph(0x131).base == 'I');
    assert(latinGlyph(0x738B).base == '?');
    assert(latinGlyph(0x1F600).base == '?');
    const char malformed[] = {char(0xE2), char(0x82), 0};
    const char* broken = malformed;
    assert(utf8Char(broken) == 0xFFFD && *broken == 0);
    const char invalid[] = {char(0xC2), 'A', 0};
    broken = invalid;
    assert(utf8Char(broken) == 0xFFFD);
    assert(utf8Char(broken) == 'A');
    const char overlong[] = {char(0xE0), char(0x80), char(0x80), 0};
    broken = overlong;
    assert(utf8Char(broken) == 0xFFFD);
    return 0;
}
'''
    source_file = tmp_path / "matrix_utf8.cpp"
    exe = tmp_path / "matrix_utf8"
    source_file.write_text(harness, encoding="utf-8")
    subprocess.run([compiler, "-std=c++11", str(source_file), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
