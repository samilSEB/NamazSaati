"""
Tests für namazsaati.py (Ezan-Daemon)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo

from namazsaati import seconds_until, play_ezan, EZAN_FILE
from prayer_calculator import get_next_prayer, get_prayer_times

BERLIN = ZoneInfo("Europe/Berlin")


class TestSecondsUntil:
    def test_future_time_today(self):
        """Zeit in der Zukunft heute → positive Sekunden."""
        with patch("namazsaati.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 1, 10, 0, 0, tzinfo=BERLIN)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = seconds_until(12, 28)
        assert result > 0
        assert abs(result - (2 * 3600 + 28 * 60)) < 5  # ~2h28min in Sekunden, -/+5s Toleranz

    def test_past_time_today_returns_tomorrow(self):
        """Zeit in der Vergangenheit → Sekunden bis morgen."""
        with patch("namazsaati.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 1, 20, 0, 0, tzinfo=BERLIN)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = seconds_until(6, 21)  # Fajr schon vorbei
        # Sollte ~10h 21min in Sekunden sein (bis morgen 06:21)
        assert result > 0
        assert result < 24 * 3600


class TestGetNextPrayer:
    def test_morning_before_fajr(self):
        """Um 3 Uhr morgens: nächstes Gebet ist Fajr."""
        times = get_prayer_times(2026, 1, 1)
        name, h, m = get_next_prayer(times, 3, 0)
        assert name == "fajr"
        assert h > 3  # Fajr nach 3 Uhr

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
             patch("namazsaati.subprocess.run") as mock_run:
            mock_path.exists.return_value = True
            mock_path.__str__ = lambda s: "/fake/ezan.mp3"
            mock_run.return_value = MagicMock(returncode=0)
            play_ezan()
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "mpg123"
        assert "-q" in call_args

    def test_mpg123_not_found_returns_false(self):
        """mpg123 nicht installiert → gibt False zurück."""
        with patch("namazsaati.EZAN_FILE") as mock_path, \
             patch("namazsaati.subprocess.run", side_effect=FileNotFoundError):
            mock_path.exists.return_value = True
            result = play_ezan()
        assert result is False
