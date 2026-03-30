"""
Tests für prayer_calculator.py

Validierung der Gebetszeiten gegen bekannte Diyanet-Referenzwerte
für Ludwigsburg, Deutschland.

Referenz-Toleranz: ±3 Minuten (astronomische Berechnung ohne API-Lookup).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import date
from prayer_calculator import (
    get_prayer_times, get_next_prayer, PRAYER_NAMES,
    julian_day, sun_position, sun_hour_angle, asr_hour_angle,
    _utc_hours_to_local, _fetch_prayer_times_api,
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def minutes(h: int, m: int) -> int:
    return h * 60 + m


def assert_near(actual: tuple[int, int], expected: tuple[int, int], tol: int = 3, label: str = ""):
    actual_min = minutes(*actual)
    expected_min = minutes(*expected)
    diff = abs(actual_min - expected_min)
    assert diff <= tol, (
        f"{label}: got {actual[0]:02d}:{actual[1]:02d}, "
        f"expected {expected[0]:02d}:{expected[1]:02d} (diff={diff}min, tol={tol}min)"
    )


# ---------------------------------------------------------------------------
# Wintertag: 1. Januar 2026 (CET = UTC+1)
# ---------------------------------------------------------------------------

class TestWinter:
    def setup_method(self):
        self.times = get_prayer_times(2026, 1, 1)

    def test_all_prayers_present(self):
        for name in PRAYER_NAMES:
            assert name in self.times

    def test_fajr(self):
        assert_near(self.times["fajr"], (6, 21), label="Fajr Jan 1")

    def test_dhuhr(self):
        assert_near(self.times["dhuhr"], (12, 28), label="Dhuhr Jan 1")

    def test_asr(self):
        assert_near(self.times["asr"], (14, 19), label="Asr Jan 1")

    def test_maghrib(self):
        assert_near(self.times["maghrib"], (16, 36), label="Maghrib Jan 1")

    def test_isha(self):
        assert_near(self.times["isha"], (18, 26), label="Isha Jan 1")

    def test_order(self):
        """Gebete müssen in aufsteigender Reihenfolge sein."""
        mins = [minutes(*self.times[n]) for n in PRAYER_NAMES]
        assert mins == sorted(mins), f"Gebete nicht in Reihenfolge: {self.times}"


# ---------------------------------------------------------------------------
# Sommertag: 21. Juni 2026 (CEST = UTC+2, längster Tag)
# ---------------------------------------------------------------------------

class TestSummer:
    def setup_method(self):
        self.times = get_prayer_times(2026, 6, 21)

    def test_fajr_reasonable(self):
        h, m = self.times["fajr"]
        assert 3 <= h <= 5, f"Fajr Sommer sollte 03-05 Uhr sein, ist {h:02d}:{m:02d}"

    def test_dhuhr(self):
        assert_near(self.times["dhuhr"], (13, 27), label="Dhuhr Jun 21")

    def test_asr(self):
        assert_near(self.times["asr"], (17, 42), label="Asr Jun 21")

    def test_maghrib(self):
        assert_near(self.times["maghrib"], (21, 30), label="Maghrib Jun 21")

    def test_isha_reasonable(self):
        h, m = self.times["isha"]
        after_maghrib = h >= 22 or h <= 1
        assert after_maghrib, f"Isha Sommer sollte nach Maghrib sein, ist {h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# DST-Übergang: 29. März 2026
# ---------------------------------------------------------------------------

class TestDST:
    def test_before_dst(self):
        times = get_prayer_times(2026, 3, 28)
        h, _ = times["fajr"]
        assert 4 <= h <= 6, f"Fajr vor DST: {h}h"

    def test_after_dst(self):
        times_before = get_prayer_times(2026, 3, 28)
        times_after = get_prayer_times(2026, 3, 30)
        fajr_before = minutes(*times_before["fajr"])
        fajr_after = minutes(*times_after["fajr"])
        diff = fajr_after - fajr_before
        assert 50 <= diff <= 70, f"DST-Sprung erwartet ~60min, war {diff}min"


# ---------------------------------------------------------------------------
# Mitternacht-Rollover
# ---------------------------------------------------------------------------

class TestMidnightRollover:
    def test_after_isha_returns_fajr_sentinel(self):
        times = get_prayer_times(2026, 1, 1)
        name, h, m = get_next_prayer(times, 23, 59)
        assert name == "fajr"
        assert h == -1

    def test_before_fajr_returns_fajr(self):
        times = get_prayer_times(2026, 1, 1)
        name, h, m = get_next_prayer(times, 0, 0)
        assert name == "fajr"
        assert h >= 0

    def test_between_dhuhr_and_asr(self):
        times = get_prayer_times(2026, 1, 1)
        dhuhr_h, dhuhr_m = times["dhuhr"]
        name, h, m = get_next_prayer(times, dhuhr_h, dhuhr_m + 1)
        assert name == "asr"


# ---------------------------------------------------------------------------
# get_next_prayer — Edge Cases
# ---------------------------------------------------------------------------

class TestGetNextPrayer:
    def test_exact_prayer_minute_returns_that_prayer(self):
        """Genau zur Gebetsminute → dieses Gebet zurückgeben (nicht überspringen)."""
        times = get_prayer_times(2026, 1, 1)
        fajr_h, fajr_m = times["fajr"]
        name, h, m = get_next_prayer(times, fajr_h, fajr_m)
        assert name == "fajr", (
            f"Fajr wurde bei exakter Zeit übersprungen! Zurückgegeben: '{name}'"
        )

    def test_each_prayer_at_exact_minute(self):
        """Für jedes Gebet: exakt zur Zeit → wird zurückgegeben."""
        times = get_prayer_times(2026, 1, 1)
        for i, prayer_name in enumerate(PRAYER_NAMES[:-1]):  # Nicht Isha (letztes)
            ph, pm = times[prayer_name]
            name, _, _ = get_next_prayer(times, ph, pm)
            assert name == prayer_name, (
                f"{prayer_name}: bei exakter Zeit wurde '{name}' zurückgegeben"
            )

    def test_one_minute_after_prayer_returns_next(self):
        """Eine Minute nach Fajr → Dhuhr ist nächstes."""
        times = get_prayer_times(2026, 1, 1)
        fajr_h, fajr_m = times["fajr"]
        name, _, _ = get_next_prayer(times, fajr_h, fajr_m + 1)
        assert name == "dhuhr"


# ---------------------------------------------------------------------------
# Allgemeine Konsistenz
# ---------------------------------------------------------------------------

class TestConsistency:
    def test_full_year_order(self):
        """Für jeden Tag in 2026: Fajr < Dhuhr < Asr < Maghrib."""
        from datetime import date, timedelta
        start = date(2026, 1, 1)
        for i in range(365):
            d = start + timedelta(days=i)
            times = get_prayer_times(d.year, d.month, d.day)
            mins = [minutes(*times[n]) for n in PRAYER_NAMES]
            assert mins[0] < mins[1] < mins[2] < mins[3], (
                f"{d}: Reihenfolge verletzt: {times}"
            )

    def test_prayer_times_are_valid_clock_times(self):
        times = get_prayer_times(2026, 6, 15)
        for name, (h, m) in times.items():
            assert 0 <= h <= 23, f"{name}: Stunde {h} ungültig"
            assert 0 <= m <= 59, f"{name}: Minute {m} ungültig"


# ---------------------------------------------------------------------------
# Astronomische Hilfsfunktionen
# ---------------------------------------------------------------------------

class TestJulianDay:
    def test_known_value_j2000(self):
        """1. Januar 2000 12:00 UTC = JD 2451545.0"""
        jd = julian_day(2000, 1, 1)
        # JD für 2000-01-01 0h = 2451544.5
        assert abs(jd - 2451544.5) < 1

    def test_increases_each_day(self):
        jd1 = julian_day(2026, 1, 1)
        jd2 = julian_day(2026, 1, 2)
        assert jd2 - jd1 == 1.0

    def test_february_transition(self):
        """Januar/Februar-Grenze (Spezialfall im Algorithmus)."""
        jd_jan31 = julian_day(2026, 1, 31)
        jd_feb1 = julian_day(2026, 2, 1)
        assert jd_feb1 - jd_jan31 == 1.0


class TestSunPosition:
    def test_returns_two_values(self):
        jd = julian_day(2026, 1, 1) + 0.5
        result = sun_position(jd)
        assert len(result) == 2

    def test_declination_in_valid_range(self):
        """Deklination muss zwischen -23.5 und +23.5 Grad liegen."""
        jd = julian_day(2026, 6, 21) + 0.5  # Sommersonnenwende
        decl, _ = sun_position(jd)
        assert -24 <= decl <= 24

    def test_equation_of_time_reasonable(self):
        """Zeitgleichung muss zwischen -17 und +17 Minuten liegen."""
        for month in range(1, 13):
            jd = julian_day(2026, month, 15) + 0.5
            _, eqt = sun_position(jd)
            assert -0.3 <= eqt <= 0.3, f"Zeitgleichung im Monat {month}: {eqt}h"


class TestSunHourAngle:
    def test_returns_none_for_polar_night(self):
        """Polarnacht: cos_ha < -1 → None."""
        # Extreme Deklination + hohe Breite → kein Ergebnis
        result = sun_hour_angle(-18.0, 89.0, -23.0)  # Nordpol, Winter
        assert result is None

    def test_returns_positive_value_in_normal_conditions(self):
        """Normaler Wintertag: positiver Stundenwinkel."""
        jd = julian_day(2026, 1, 1) + 0.5
        decl, _ = sun_position(jd)
        result = sun_hour_angle(-0.8333, 48.9, decl)
        assert result is not None
        assert result > 0


class TestUtcToLocal:
    def test_winter_cet_plus_one(self):
        """Winter: UTC+1."""
        d = date(2026, 1, 1)
        h, m = _utc_hours_to_local(11.0, d)  # 11:00 UTC → 12:00 CET
        assert h == 12
        assert m == 0

    def test_summer_cest_plus_two(self):
        """Sommer: UTC+2."""
        d = date(2026, 6, 21)
        h, m = _utc_hours_to_local(11.0, d)  # 11:00 UTC → 13:00 CEST
        assert h == 13
        assert m == 0

    def test_minutes_conversion(self):
        """Dezimalstunden werden korrekt in Minuten umgerechnet."""
        d = date(2026, 1, 1)
        h, m = _utc_hours_to_local(11.5, d)  # 11:30 UTC → 12:30 CET
        assert h == 12
        assert m == 30


# ---------------------------------------------------------------------------
# API-Fallback
# ---------------------------------------------------------------------------

class TestFetchPrayerTimesApi:
    def test_returns_none_on_network_error(self):
        """Netzwerkfehler → None zurückgeben."""
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Kein Netz")):
            result = _fetch_prayer_times_api(2026, 1, 1)
        assert result is None

    def test_returns_none_on_timeout(self):
        """Timeout → None zurückgeben."""
        import socket
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")):
            result = _fetch_prayer_times_api(2026, 1, 1)
        assert result is None

    def test_returns_none_on_invalid_json(self):
        """Ungültiges JSON → None."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _fetch_prayer_times_api(2026, 1, 1)
        assert result is None

    def test_parses_valid_api_response(self):
        """Gültige API-Antwort wird korrekt geparst."""
        fake_response = {
            "data": {
                "timings": {
                    "Fajr": "06:21",
                    "Dhuhr": "12:28",
                    "Asr": "14:19",
                    "Maghrib": "16:36",
                    "Isha": "18:26",
                }
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake_response).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _fetch_prayer_times_api(2026, 1, 1)
        assert result is not None
        assert result["fajr"] == (6, 21)
        assert result["dhuhr"] == (12, 28)
        assert result["maghrib"] == (16, 36)

    def test_api_fallback_used_on_failure(self):
        """Bei API-Fehler wird lokale Berechnung verwendet."""
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("kein Netz")):
            result = get_prayer_times(2026, 1, 1)
        # Lokale Berechnung sollte trotzdem ein Ergebnis liefern
        assert result is not None
        assert len(result) == 5
        for name in PRAYER_NAMES:
            assert name in result
