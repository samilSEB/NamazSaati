#!/usr/bin/env python3
"""
NamazSaati - Ezan-Daemon

Spielt den Ezan automatisch zu jeder der 5 täglichen Gebetszeiten.
Startet beim Booten des Raspberry Pi automatisch (via systemd).
Benötigt keine Einrichtung nach einem Stromausfall.

Verwendung:
  python3 namazsaati.py          # Normalbetrieb (wartet auf Gebetszeit)
  python3 namazsaati.py --test   # Spielt Ezan sofort (für Tests)
"""

import sys
import time
import subprocess
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from prayer_calculator import get_prayer_times, get_next_prayer, PRAYER_NAMES

# --- Konfiguration ---
AUDIO_DIR = Path(__file__).parent / "audio"
EZAN_FILE = AUDIO_DIR / "ezan.mp3"
TIMEZONE = ZoneInfo("Europe/Berlin")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("namazsaati")


def play_ezan() -> bool:
    """
    Spielt die Ezan-Datei über den Standard-Audio-Ausgang.
    Gibt True zurück wenn erfolgreich, False wenn Datei fehlt.
    """
    if not EZAN_FILE.exists():
        log.error(
            "Ezan-Datei nicht gefunden: %s\n"
            "Bitte ezan.mp3 in das audio/-Verzeichnis kopieren.\n"
            "Anleitung: raspberry-pi/docs/SETUP.md",
            EZAN_FILE,
        )
        return False

    log.info("Ezan wird abgespielt...")
    try:
        subprocess.run(
            ["mpg123", "-q", str(EZAN_FILE)],
            check=True,
            timeout=600,  # Max. 10 Minuten Timeout
        )
        log.info("Ezan fertig.")
        return True
    except subprocess.CalledProcessError as e:
        log.error("Fehler beim Abspielen: %s", e)
        return False
    except subprocess.TimeoutExpired:
        log.error("Ezan-Wiedergabe hat 10 Minuten überschritten — abgebrochen.")
        return False
    except FileNotFoundError:
        log.error(
            "mpg123 nicht gefunden. Installation: sudo apt install mpg123"
        )
        return False


def seconds_until(target_hour: int, target_minute: int) -> float:
    """Sekunden bis zu einer Uhrzeit (heute oder morgen)."""
    now = datetime.now(TIMEZONE)
    target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def log_todays_times(times: dict) -> None:
    """Gibt alle heutigen Gebetszeiten ins Log aus."""
    log.info("Heutige Gebetszeiten (Ludwigsburg, Diyanet):")
    for name in PRAYER_NAMES:
        h, m = times[name]
        log.info("  %-8s %02d:%02d", name.capitalize(), h, m)


def run_daemon() -> None:
    """
    Haupt-Loop: berechnet Gebetszeiten, wartet, spielt Ezan.
    Läuft für immer. Neuberechnung bei jedem Gebet (tagesaktuell).
    """
    log.info("NamazSaati gestartet.")

    if not EZAN_FILE.exists():
        log.warning(
            "Ezan-Datei fehlt (%s). Daemon läuft weiter, "
            "spielt aber keinen Ton bis die Datei vorhanden ist.",
            EZAN_FILE,
        )

    while True:
        now = datetime.now(TIMEZONE)
        times = get_prayer_times(now.year, now.month, now.day)
        log_todays_times(times)

        # Nächstes Gebet bestimmen
        name, h, m = get_next_prayer(times, now.hour, now.minute)

        if h == -1:
            # Alle Gebete für heute vorbei → Fajr morgen
            tomorrow = date.today() + timedelta(days=1)
            tomorrow_times = get_prayer_times(tomorrow.year, tomorrow.month, tomorrow.day)
            h, m = tomorrow_times["fajr"]
            name = "fajr"
            log.info("Alle Gebete vorbei. Nächstes: Fajr morgen um %02d:%02d", h, m)
        else:
            log.info("Nächstes Gebet: %s um %02d:%02d", name.capitalize(), h, m)

        wait = seconds_until(h, m)
        log.info("Warte %.0f Sekunden (%.1f Stunden)...", wait, wait / 3600)
        time.sleep(wait)

        # Kurz nach dem Aufwachen: Zeit nochmal prüfen (Schlaf kann ungenau sein)
        now_check = datetime.now(TIMEZONE)
        log.info("Aufgewacht um %02d:%02d — Zeit für %s", now_check.hour, now_check.minute, name.capitalize())
        play_ezan()

        # 2 Minuten warten, damit das gleiche Gebet nicht doppelt ausgelöst wird
        time.sleep(120)


def run_test() -> None:
    """Test-Modus: Zeigt heutige Gebetszeiten und spielt Ezan sofort."""
    now = datetime.now(TIMEZONE)
    times = get_prayer_times(now.year, now.month, now.day)
    log_todays_times(times)

    name, h, m = get_next_prayer(times, now.hour, now.minute)
    if h == -1:
        log.info("Nächstes Gebet: Fajr morgen")
    else:
        log.info("Nächstes Gebet: %s um %02d:%02d", name.capitalize(), h, m)

    log.info("Test-Modus: Ezan wird jetzt sofort abgespielt.")
    play_ezan()


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_test()
    else:
        try:
            run_daemon()
        except KeyboardInterrupt:
            log.info("NamazSaati beendet.")
