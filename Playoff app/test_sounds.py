import json
import threading
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from PIL import Image

import playoff
import playoff_sounds as sounds


def test_portable_setup_round_trip_on_an_empty_profile(tmp_path, monkeypatch):
    source_profile = tmp_path / "source"
    target_profile = tmp_path / "target"
    monkeypatch.setattr(sounds, "media_root", lambda: source_profile)
    original = sounds.sound_path("short")
    sound = sounds.add_sound(original)
    extra = sounds.add_sound(sounds.sound_path("long"))
    settings = {"team_count": 12, "bg_path": "C:/old/pozadi.jpg",
                "sounds": {"start": {"sound": sound, "enabled": False, "volume": 28}},
                "laps_sound_warning_seconds": 17}
    zip_path = tmp_path / "nastavení.zip"
    sounds.save_portable_setup(zip_path, settings, Image.new("RGB", (2, 3), "red"))
    monkeypatch.setattr(sounds, "media_root", lambda: target_profile)
    restored = sounds.load_setup_file(zip_path)
    assert restored["sounds"] == settings["sounds"]
    assert restored["laps_sound_warning_seconds"] == 17
    assert restored["team_count"] == 12
    assert extra in sounds.sound_library()
    assert sounds.sound_path(sound).read_bytes() == original.read_bytes()
    with Image.open(restored["bg_path"]) as image:
        assert image.size == (2, 3)
        assert image.getpixel((0, 0)) == (255, 0, 0)


def test_setup_rejects_unexpected_archive_entries_and_reads_old_json(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "media_root", lambda: tmp_path / "profile")
    zip_path = tmp_path / "bad.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("settings.json", '{"portable_setup": 1}')
        archive.writestr("../out.wav", b"content")
    with pytest.raises(ValueError):
        sounds.load_setup_file(zip_path)
    assert not sounds.media_root().exists()
    setup = tmp_path / "old.setup"
    setup.write_text(json.dumps({"team_count": 8}), encoding="utf-8")
    assert sounds.load_setup_file(setup) == {"team_count": 8}
    assert all(not item["enabled"] for item in sounds.normalize_sounds(None).values())


def test_live_audio_returns_without_waiting_for_the_player(monkeypatch):
    started = threading.Event()
    finish = threading.Event()
    calls = []

    def playback(sound, volume, stopping):
        calls.append((sound, volume, threading.current_thread()))
        started.set()
        finish.wait(2)

    monkeypatch.setattr(sounds.SoundPlayer, "_play", staticmethod(playback))
    player = sounds.SoundPlayer()
    try:
        job = player.play("short", 31)
        assert started.wait(1)
        assert not job.done()
        assert calls == [("short", 31, calls[0][2])]
        assert calls[0][2] is not threading.current_thread()
    finally:
        finish.set()
        player.close()


def test_usb_sound_only_on_lost_or_confirmed_ready_transitions():
    app = playoff.PlayoffApp.__new__(playoff.PlayoffApp)
    app.sound_usb_states = {}
    app.play_sound = Mock()
    for state in ("syncing", "ready", "ready", False, "syncing", False, "syncing", "ready"):
        app.notify_usb_sound("ID2", "COM5", state)
    app.notify_usb_sound("ID2", "", False)
    assert [args[0] for args, _ in app.play_sound.call_args_list] == ["ID2_lost", "ID2_restored"]


def test_countdown_sounds_at_zero_and_once_per_laps_cycle():
    app = playoff.PlayoffApp.__new__(playoff.PlayoffApp)
    app.root = Mock()
    app.timer_label = Mock()
    app.play_sound = Mock()
    app.refresh_panels_for_content = Mock()
    app.update_laps_countdown_warning = Mock()
    app.stop_laps_countdown_blink = Mock()
    app.laps_countdown_running = app.enable_timer = True
    app.view_mode = "laps"
    app.timer_value = "00:03"
    app.laps_countdown_seconds = 3
    app.laps_sound_warning_seconds = 2
    for _ in range(6):
        app.laps_countdown_tick()
    assert [args[0] for args, _ in app.play_sound.call_args_list] == ["laps_warning", "laps_end"] * 2
    app.play_sound.reset_mock()
    app.timer_running = True
    app.current_seconds = 1
    app.lap_after_id = None
    app.update_promo_button_state = Mock()
    app.start_blinking = Mock()
    app.countdown_tick()
    app.countdown_tick()
    app.play_sound.assert_called_once_with("playoff_end")
