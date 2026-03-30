"""
Tests für namazsaati.py (Ezan-Daemon)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import subprocess
from unittest.mock import patch, MagicMock, call
from datetime import datetime
from zoneinfo import ZoneInfo

from namazsaati import (
    seconds_until, play_ezan, EZAN_FILE,
    _mac_to_sink, _bluetooth_sink_active,
    set_volume, keep_bluetooth_alive, sleep_with_keepalive,
)
from prayer_calculator import get_next_prayer, get_prayer_times

BERLIN = ZoneInfo("Europe/Berlin")
BOSE_MAC = "60:AB:D2:11:7D:7D"
BOSE_SINK = "bluez_sink.60_AB_D2_11_7D_7D.a2dp_sink"


# ---------------------------------------------------------------------------
# _mac_to_sink
# ---------------------------------------------------------------------------

class TestMacToSink:
    def test_replaces_colons_with_underscores(self):
        result = _mac_to_sink("60:AB:D2:11:7D:7D")
        assert "60_AB_D2_11_7D_7D" in result

    def test_adds_bluez_prefix(self):
        result = _mac_to_sink("AA:BB:CC:DD:EE:FF")
        assert result.startswith("bluez_sink.")

    def test_adds_a2dp_suffix(self):
        result = _mac_to_sink("AA:BB:CC:DD:EE:FF")
        assert result.endswith(".a2dp_sink")

    def test_full_sink_name(self):
        assert _mac_to_sink("60:AB:D2:11:7D:7D") == BOSE_SINK


# ---------------------------------------------------------------------------
# _bluetooth_sink_active
# ---------------------------------------------------------------------------

class TestBluetoothSinkActive:
    def test_returns_true_when_sink_present(self):
        with patch("namazsaati.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=BOSE_SINK.encode(), returncode=0)
            assert _bluetooth_sink_active(BOSE_SINK) is True

    def test_returns_false_when_sink_absent(self):
        with patch("namazsaati.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=b"auto_null.monitor", returncode=0)
            assert _bluetooth_sink_active(BOSE_SINK) is False

    def test_returns_false_on_exception(self):
        with patch("namazsaati.subprocess.run", side_effect=Exception("pactl fehlt")):
            assert _bluetooth_sink_active(BOSE_SINK) is False

    def test_returns_false_on_timeout(self):
        with patch("namazsaati.subprocess.run", side_effect=subprocess.TimeoutExpired("pactl", 5)):
            assert _bluetooth_sink_active(BOSE_SINK) is False


# ---------------------------------------------------------------------------
# set_volume
# ---------------------------------------------------------------------------

class TestSetVolume:
    def test_calls_pactl_with_correct_percentage(self):
        with patch("namazsaati.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            set_volume(70)
        cmd = mock_run.call_args[0][0]
        assert "pactl" in cmd
        assert "70%" in cmd

    def test_clamps_volume_above_100(self):
        with patch("namazsaati.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            set_volume(150)
        cmd = mock_run.call_args[0][0]
        assert "100%" in cmd

    def test_clamps_volume_below_0(self):
        with patch("namazsaati.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            set_volume(-10)
        cmd = mock_run.call_args[0][0]
        assert "0%" in cmd

    def test_ignores_pactl_exception(self):
        with patch("namazsaati.subprocess.run", side_effect=Exception("kein pactl")):
            set_volume(50)  # Darf nicht werfen


# ---------------------------------------------------------------------------
# seconds_until
# ---------------------------------------------------------------------------

class TestSecondsUntil:
    def test_future_time_today(self):
        """Zeit in der Zukunft heute → positive Sekunden."""
        with patch("namazsaati.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 1, 10, 0, 0, tzinfo=BERLIN)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = seconds_until(12, 28)
        assert result > 0
        assert abs(result - (2 * 3600 + 28 * 60)) < 5

    def test_past_time_today_returns_tomorrow(self):
        """Zeit in der Vergangenheit → Sekunden bis morgen."""
        with patch("namazsaati.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 1, 20, 0, 0, tzinfo=BERLIN)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = seconds_until(6, 21)
        assert result > 0
        assert result < 24 * 3600

    def test_same_minute_returns_zero_or_small(self):
        """Innerhalb der Gebetsminute → 0 oder sehr kleine Zahl (sofort abspielen)."""
        with patch("namazsaati.datetime") as mock_dt:
            # Es ist 13:00:30 — Gebet ist um 13:00
            mock_dt.now.return_value = datetime(2026, 1, 1, 13, 0, 30, tzinfo=BERLIN)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = seconds_until(13, 0)
        # Soll sofort abspielen (≤ 60s), NICHT morgen warten (~86400s)
        assert result <= 60, f"seconds_until sollte ≤60 sein, war {result:.1f}s"


# ---------------------------------------------------------------------------
# sleep_with_keepalive
# ---------------------------------------------------------------------------

class TestSleepWithKeepalive:
    def test_calls_keepalive_after_interval(self):
        """Ruft keep_bluetooth_alive nach dem Keep-Alive-Intervall auf."""
        call_count = {"n": 0}

        def fake_keepalive():
            call_count["n"] += 1

        # Simuliere: sleep dauert 2 * KEEP_ALIVE_INTERVAL (2 Aufrufe erwartet)
        with patch("namazsaati.keep_bluetooth_alive", side_effect=fake_keepalive), \
             patch("namazsaati.time.sleep"), \
             patch("namazsaati.time.time") as mock_time:
            # Simuliere: start=0, nach erstem chunk=840, nach zweitem chunk=1680, Ende=1700
            mock_time.side_effect = [0, 0, 840, 840, 1680, 1680, 1700]
            sleep_with_keepalive(1700)

        assert call_count["n"] >= 1

    def test_does_not_call_keepalive_for_very_short_sleep(self):
        """Kurzer Schlaf (< Intervall) → keep_bluetooth_alive wird nicht aufgerufen."""
        with patch("namazsaati.keep_bluetooth_alive") as mock_keepalive, \
             patch("namazsaati.time.sleep"), \
             patch("namazsaati.time.time") as mock_time:
            mock_time.side_effect = [0, 0, 30, 30]
            sleep_with_keepalive(30)

        mock_keepalive.assert_not_called()


# ---------------------------------------------------------------------------
# play_ezan
# ---------------------------------------------------------------------------

class TestPlayEzan:
    def test_missing_file_returns_false(self):
        """Fehlende Ezan-Datei → play_ezan gibt False zurück."""
        with patch("namazsaati.EZAN_FILE") as mock_path:
            mock_path.exists.return_value = False
            result = play_ezan()
        assert result is False

    def test_mpg123_called_with_correct_args(self):
        """mpg123 wird mit der richtigen Datei aufgerufen."""
        with patch("namazsaati.EZAN_FILE") as mock_path, \
             patch("namazsaati.subprocess.run") as mock_run, \
             patch("namazsaati.load_config", return_value={"volume": 70}):
            mock_path.exists.return_value = True
            mock_path.__str__ = lambda s: "/fake/ezan.mp3"
            mock_run.return_value = MagicMock(returncode=0)
            play_ezan()
        mock_run.assert_called()
        # Prüfe mpg123-Aufruf
        mpg_calls = [c for c in mock_run.call_args_list if c[0][0][0] == "mpg123"]
        assert len(mpg_calls) >= 1
        assert "-q" in mpg_calls[0][0][0]

    def test_mpg123_not_found_returns_false(self):
        """mpg123 nicht installiert → gibt False zurück."""
        with patch("namazsaati.EZAN_FILE") as mock_path, \
             patch("namazsaati.subprocess.run", side_effect=FileNotFoundError), \
             patch("namazsaati.load_config", return_value={"volume": 70}):
            mock_path.exists.return_value = True
            result = play_ezan()
        assert result is False

    def test_timeout_returns_false(self):
        """Timeout beim Abspielen → gibt False zurück."""
        with patch("namazsaati.EZAN_FILE") as mock_path, \
             patch("namazsaati.load_config", return_value={"volume": 70}), \
             patch("namazsaati.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("mpg123", 600)):
            mock_path.exists.return_value = True
            result = play_ezan()
        assert result is False

    def test_called_process_error_returns_false(self):
        """mpg123 gibt Fehlercode zurück → gibt False zurück."""
        with patch("namazsaati.EZAN_FILE") as mock_path, \
             patch("namazsaati.load_config", return_value={"volume": 70}), \
             patch("namazsaati.subprocess.run",
                   side_effect=subprocess.CalledProcessError(1, "mpg123")):
            mock_path.exists.return_value = True
            result = play_ezan()
        assert result is False

    def test_returns_true_on_success(self):
        """Erfolgreiches Abspielen → gibt True zurück."""
        with patch("namazsaati.EZAN_FILE") as mock_path, \
             patch("namazsaati.subprocess.run") as mock_run, \
             patch("namazsaati.load_config", return_value={"volume": 70}):
            mock_path.exists.return_value = True
            mock_run.return_value = MagicMock(returncode=0)
            result = play_ezan()
        assert result is True

    def test_sets_volume_before_playing(self):
        """Lautstärke wird vor mpg123-Aufruf gesetzt."""
        calls = []

        def track(cmd, **kwargs):
            calls.append(cmd[0])
            return MagicMock(returncode=0)

        with patch("namazsaati.EZAN_FILE") as mock_path, \
             patch("namazsaati.subprocess.run", side_effect=track), \
             patch("namazsaati.load_config", return_value={"volume": 80}):
            mock_path.exists.return_value = True
            play_ezan()

        assert "pactl" in calls, "pactl für Lautstärke nicht aufgerufen"
        assert "mpg123" in calls, "mpg123 nicht aufgerufen"
        assert calls.index("pactl") < calls.index("mpg123"), "pactl muss vor mpg123 aufgerufen werden"


# ---------------------------------------------------------------------------
# get_next_prayer
# ---------------------------------------------------------------------------

class TestGetNextPrayer:
    def test_morning_before_fajr(self):
        """Um 3 Uhr morgens: nächstes Gebet ist Fajr."""
        times = get_prayer_times(2026, 1, 1)
        name, h, m = get_next_prayer(times, 3, 0)
        assert name == "fajr"
        assert h > 3

    def test_after_all_prayers(self):
        """Nach allen Gebeten: Sentinel (h=-1) für Fajr morgen."""
        times = get_prayer_times(2026, 1, 1)
        name, h, m = get_next_prayer(times, 23, 59)
        assert name == "fajr"
        assert h == -1

    def test_between_prayers(self):
        """Zwischen Maghrib und Isha: nächstes ist Isha."""
        times = get_prayer_times(2026, 1, 1)
        mag_h, mag_m = times["maghrib"]
        name, h, m = get_next_prayer(times, mag_h, mag_m + 5)
        assert name == "isha"

    def test_exact_prayer_minute_not_skipped(self):
        """Exakt zur Gebetsminute gestartet → Gebet darf nicht übersprungen werden."""
        times = get_prayer_times(2026, 1, 1)
        dhuhr_h, dhuhr_m = times["dhuhr"]
        name, h, m = get_next_prayer(times, dhuhr_h, dhuhr_m)
        # Dhuhr DARF nicht übersprungen werden (Bug: > statt >=)
        assert name == "dhuhr", (
            f"Dhuhr wurde übersprungen! get_next_prayer gab '{name}' zurück "
            f"obwohl es genau {dhuhr_h:02d}:{dhuhr_m:02d} ist."
        )


# ---------------------------------------------------------------------------
# keep_bluetooth_alive
# ---------------------------------------------------------------------------

class TestKeepBluetoothAlive:
    def test_plays_silence_via_paplay(self):
        """Keep-alive spielt Stille über paplay."""
        with patch("namazsaati._bluetooth_sink_active", return_value=True), \
             patch("namazsaati.load_config", return_value={
                 "bluetooth_mac": BOSE_MAC, "volume": 70, "prayers_enabled": {}
             }), \
             patch("namazsaati.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            keep_bluetooth_alive()

        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert any(c[0] == "paplay" for c in cmds), \
            f"paplay wurde nicht aufgerufen. Stattdessen: {cmds}"

    def test_reconnects_when_sink_missing(self):
        """Wenn Sink fehlt → ensure_bluetooth_connected wird aufgerufen."""
        with patch("namazsaati._bluetooth_sink_active", return_value=False), \
             patch("namazsaati.load_config", return_value={
                 "bluetooth_mac": BOSE_MAC, "volume": 70, "prayers_enabled": {}
             }), \
             patch("namazsaati.ensure_bluetooth_connected") as mock_connect:
            keep_bluetooth_alive()

        mock_connect.assert_called_once()

    def test_no_paplay_when_sink_missing(self):
        """Wenn Sink fehlt → kein paplay, nur reconnect."""
        with patch("namazsaati._bluetooth_sink_active", return_value=False), \
             patch("namazsaati.load_config", return_value={
                 "bluetooth_mac": BOSE_MAC, "volume": 70, "prayers_enabled": {}
             }), \
             patch("namazsaati.ensure_bluetooth_connected"), \
             patch("namazsaati.subprocess.run") as mock_run:
            keep_bluetooth_alive()

        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert not any(c[0] == "paplay" for c in cmds)
