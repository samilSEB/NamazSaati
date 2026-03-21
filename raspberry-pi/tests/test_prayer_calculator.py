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
from prayer_calculator import get_prayer_times, get_next_prayer, PRAYER_NAMES


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
# Referenz-Erwartung: Fajr ~06:21, Dhuhr ~12:28, Asr ~14:19, Maghrib ~16:36, Isha ~18:26
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
# Fajr und Isha nicht kalkulierbar → 1/7-Nacht-Regel
# ---------------------------------------------------------------------------

class TestSummer:
    def setup_method(self):
        self.times = get_prayer_times(2026, 6, 21)

    def test_fajr_reasonable(self):
        """Fajr im Sommer: irgendwann früh morgens via 1/7-Nacht-Regel."""
        h, m = self.times["fajr"]
        assert 3 <= h <= 5, f"Fajr Sommer sollte 03-05 Uhr sein, ist {h:02d}:{m:02d}"

    def test_dhuhr(self):
        assert_near(self.times["dhuhr"], (13, 27), label="Dhuhr Jun 21")

    def test_asr(self):
        assert_near(self.times["asr"], (17, 42), label="Asr Jun 21")

    def test_maghrib(self):
        assert_near(self.times["maghrib"], (21, 30), label="Maghrib Jun 21")

    def test_isha_reasonable(self):
        """Isha im Sommer: spät abends oder kurz nach Mitternacht."""
        h, m = self.times["isha"]
        # Entweder nach 22 Uhr oder 0-1 Uhr (kurz nach Mitternacht)
        after_maghrib = h >= 22 or h <= 1
        assert after_maghrib, f"Isha Sommer sollte nach Maghrib sein, ist {h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# DST-Übergang: 29. März 2026 (Uhren springen 02:00 → 03:00)
# ---------------------------------------------------------------------------

class TestDST:
    def test_before_dst(self):
        """28. März: noch CET (UTC+1)."""
        times = get_prayer_times(2026, 3, 28)
        h, _ = times["fajr"]
        # Fajr Ende März früh morgens, CET: ca. 05:xx
        assert 4 <= h <= 6, f"Fajr vor DST: {h}h"

    def test_after_dst(self):
        """30. März: CEST (UTC+2), Gebetszeiten 1h später in Lokalzeit."""
        times_before = get_prayer_times(2026, 3, 28)
        times_after = get_prayer_times(2026, 3, 30)
        # Nach DST-Umstellung sollte Fajr ~1h später in Lokalzeit erscheinen
        fajr_before = minutes(*times_before["fajr"])
        fajr_after = minutes(*times_after["fajr"])
        diff = fajr_after - fajr_before
        # Differenz ~60min (DST) + kleine astronomische Änderung (~1-2min/Tag)
        assert 50 <= diff <= 70, f"DST-Sprung erwartet ~60min, war {diff}min"


# ---------------------------------------------------------------------------
# Mitternacht-Rollover: Nächstes Gebet nach Isha = Fajr morgen
# ---------------------------------------------------------------------------

class TestMidnightRollover:
    def test_after_isha_returns_fajr_sentinel(self):
        """Nach dem letzten Gebet: get_next_prayer gibt Fajr-Sentinel zurück."""
        times = get_prayer_times(2026, 1, 1)
        # Simuliere: es ist 23:59 (nach Isha ~18:26)
        name, h, m = get_next_prayer(times, 23, 59)
        assert name == "fajr"
        assert h == -1  # Sentinel: morgen neu berechnen

    def test_before_fajr_returns_fajr(self):
        """Vor Fajr: nächstes Gebet ist Fajr."""
        times = get_prayer_times(2026, 1, 1)
        name, h, m = get_next_prayer(times, 0, 0)
        assert name == "fajr"
        assert h >= 0  # Kein Sentinel

    def test_between_dhuhr_and_asr(self):
        """Zwischen Dhuhr und Asr: nächstes Gebet ist Asr."""
        times = get_prayer_times(2026, 1, 1)
        dhuhr_h, dhuhr_m = times["dhuhr"]
        name, h, m = get_next_prayer(times, dhuhr_h, dhuhr_m + 1)
        assert name == "asr"


# ---------------------------------------------------------------------------
# Allgemeine Konsistenz
# ---------------------------------------------------------------------------

class TestConsistency:
    def test_full_year_order(self):
        """Für jeden Tag in 2026: Gebete in aufsteigender Reihenfolge."""
        from datetime import date, timedelta
        start = date(2026, 1, 1)
        for i in range(365):
            d = start + timedelta(days=i)
            times = get_prayer_times(d.year, d.month, d.day)
            mins = [minutes(*times[n]) for n in PRAYER_NAMES]
            # Erlaube Ausnahme: Isha kann nach Mitternacht liegen (> 1440 nicht darstellbar)
            # Prüfe nur dass Fajr < Dhuhr < Asr < Maghrib
            assert mins[0] < mins[1] < mins[2] < mins[3], (
                f"{d}: Reihenfolge verletzt: {times}"
            )

    def test_prayer_times_are_valid_clock_times(self):
        """Alle Zeiten müssen gültige Uhrzeiten sein (0-23 Stunden, 0-59 Minuten)."""
        times = get_prayer_times(2026, 6, 15)
        for name, (h, m) in times.items():
            assert 0 <= h <= 23, f"{name}: Stunde {h} ungültig"
            assert 0 <= m <= 59, f"{name}: Minute {m} ungültig"
