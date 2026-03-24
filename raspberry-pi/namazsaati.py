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
from config import load_config

# --- Konstanten ---
AUDIO_DIR = Path(__file__).parent / "audio"
EZAN_FILE = AUDIO_DIR / "ezan.mp3"
TIMEZONE = ZoneInfo("Europe/Berlin")
KEEP_ALIVE_INTERVAL = 14 * 60  # 14 Minuten

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("namazsaati")


def _mac_to_sink(mac: str) -> str:
    return "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"


def _bluetooth_sink_active(sink: str) -> bool:
    try:
        result = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True, timeout=5)
        return sink.encode() in result.stdout
    except Exception:
        return False


def ensure_bluetooth_connected() -> None:
    """Verbindet Bluetooth-Lautsprecher falls nicht verbunden. Wartet auf PulseAudio."""
    cfg = load_config()
    mac = cfg["bluetooth_mac"]
    sink = _mac_to_sink(mac)

    # Warte bis PulseAudio bereit ist (max. 60 Sekunden)
    for _ in range(30):
        result = subprocess.run(["pactl", "info"], capture_output=True, timeout=5)
        if result.returncode == 0:
            break
        time.sleep(2)
    else:
        log.warning("PulseAudio nicht erreichbar — Bluetooth-Setup übersprungen.")
        return

    if _bluetooth_sink_active(sink):
        return  # Bereits verbunden

    log.info("Verbinde Bluetooth-Lautsprecher %s...", mac)
    try:
        subprocess.run(["bluetoothctl", "connect", mac], timeout=15, capture_output=True)
        # Warte bis der Bluetooth-Sink erscheint (max. 20 Sekunden)
        for _ in range(10):
            time.sleep(2)
            if _bluetooth_sink_active(sink):
                break
        subprocess.run(["pactl", "set-default-sink", sink], timeout=5, capture_output=True)
        log.info("Bluetooth verbunden und als Audio-Ausgabe gesetzt.")
    except Exception as e:
        log.warning("Bluetooth nicht erreichbar, nächster Versuch in 14 Minuten: %s", e)


def keep_bluetooth_alive() -> None:
    """Hält Bluetooth verbunden: reconnect falls getrennt, sonst Stille spielen."""
    cfg = load_config()
    sink = _mac_to_sink(cfg["bluetooth_mac"])
    if not _bluetooth_sink_active(sink):
        ensure_bluetooth_connected()
        return
    try:
        subprocess.run(
            ["aplay", "-q", "-d", "1", "-f", "S16_LE", "-c", "2", "-r", "44100", "/dev/zero"],
            timeout=5,
            capture_output=True,
        )
    except Exception:
        pass


def sleep_with_keepalive(seconds: float) -> None:
    """Schläft die angegebene Zeit, hält dabei alle 14 Minuten den Bluetooth wach."""
    end = time.time() + seconds
    while True:
        remaining = end - time.time()
        if remaining <= 0:
            break
        chunk = min(remaining, KEEP_ALIVE_INTERVAL)
        time.sleep(chunk)
        if time.time() < end:
            keep_bluetooth_alive()


def set_volume(volume: int) -> None:
    """Setzt die PulseAudio-Lautstärke (0-100)."""
    try:
        pct = f"{max(0, min(100, volume))}%"
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", pct],
                       capture_output=True, timeout=5)
    except Exception:
        pass


def play_ezan() -> bool:
    """
    Spielt die Ezan-Datei über den Standard-Audio-Ausgang.
    Gibt True zurück wenn erfolgreich, False wenn Datei fehlt.
    """
    if not EZAN_FILE.exists():
        log.error(
            "Ezan-Datei nicht gefunden: %s\n"
            "Bitte ezan.mp3 in das audio/-Verzeichnis kopieren.",
            EZAN_FILE,
        )
        return False

    cfg = load_config()
    set_volume(cfg.get("volume", 70))

    log.info("Ezan wird abgespielt...")
    try:
        subprocess.run(
            ["mpg123", "-q", str(EZAN_FILE)],
            check=True,
            timeout=600,
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
        log.error("mpg123 nicht gefunden. Installation: sudo apt install mpg123")
        return False


def seconds_until(target_hour: int, target_minute: int) -> float:
    """Sekunden bis zu einer Uhrzeit (heute oder morgen)."""
    now = datetime.now(TIMEZONE)
    target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def log_todays_times(times: dict) -> None:
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
    ensure_bluetooth_connected()

    if not EZAN_FILE.exists():
        log.warning(
            "Ezan-Datei fehlt (%s). Daemon läuft weiter, "
            "spielt aber keinen Ton bis die Datei vorhanden ist.",
            EZAN_FILE,
        )

    while True:
        cfg = load_config()  # Config bei jedem Gebet neu laden
        prayers_enabled = cfg.get("prayers_enabled", {})

        now = datetime.now(TIMEZONE)
        times = get_prayer_times(now.year, now.month, now.day)
        log_todays_times(times)

        name, h, m = get_next_prayer(times, now.hour, now.minute)

        if h == -1:
            tomorrow = date.today() + timedelta(days=1)
            tomorrow_times = get_prayer_times(tomorrow.year, tomorrow.month, tomorrow.day)
            h, m = tomorrow_times["fajr"]
            name = "fajr"
            log.info("Alle Gebete vorbei. Nächstes: Fajr morgen um %02d:%02d", h, m)
        else:
            log.info("Nächstes Gebet: %s um %02d:%02d", name.capitalize(), h, m)

        wait = seconds_until(h, m)
        log.info("Warte %.0f Sekunden (%.1f Stunden)...", wait, wait / 3600)
        sleep_with_keepalive(wait)

        now_check = datetime.now(TIMEZONE)
        log.info("Aufgewacht um %02d:%02d — Zeit für %s", now_check.hour, now_check.minute, name.capitalize())

        if prayers_enabled.get(name, True):
            play_ezan()
        else:
            log.info("%s — Ezan deaktiviert (Einstellungen).", name.capitalize())

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
