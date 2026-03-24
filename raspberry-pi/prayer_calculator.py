"""
NamazSaati - Gebetszeit-Berechnung
Diyanet-Methode: Fajr 18°, Isha 17°, Asr Shafi
Standort: Ludwigsburg, Deutschland (48.8975°N, 9.1925°E)

Holt Gebetszeiten von der AlAdhan-API (Diyanet-Methode).
Fallback auf lokale Berechnung wenn kein Internet verfügbar.
"""

import math
import urllib.request
import json
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger("namazsaati")

# --- Standort & Methode ---
LATITUDE = 48.8975
LONGITUDE = 9.1925
TIMEZONE = ZoneInfo("Europe/Berlin")

FAJR_ANGLE = 18.0
ISHA_ANGLE = 17.0
SUN_REFRACTION = 0.8333

PRAYER_NAMES = ["fajr", "dhuhr", "asr", "maghrib", "isha"]


def julian_day(year: int, month: int, day: int) -> float:
    """Julianischer Tag für ein Datum."""
    if month <= 2:
        year -= 1
        month += 12
    A = math.floor(year / 100.0)
    B = 2 - A + math.floor(A / 4.0)
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + B - 1524.5


def sun_position(jd: float) -> tuple[float, float]:
    """Sonnendeklination und Zeitgleichung (in Stunden) für einen JD."""
    D = jd - 2451545.0
    g = math.radians((357.529 + 0.98560028 * D) % 360)
    q = (280.459 + 0.98564736 * D) % 360
    L_rad = math.radians((q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360)
    e_rad = math.radians(23.439 - 0.00000036 * D)
    RA = math.degrees(math.atan2(math.cos(e_rad) * math.sin(L_rad), math.cos(L_rad))) / 15.0
    decl = math.degrees(math.asin(math.sin(e_rad) * math.sin(L_rad)))
    EqT = (q / 15.0) - RA
    while EqT > 12:
        EqT -= 24
    while EqT < -12:
        EqT += 24
    return decl, EqT


def sun_hour_angle(angle: float, lat: float, decl: float) -> float | None:
    """Stundenwinkel für einen gegebenen Sonnenwinkel (in Stunden)."""
    cos_ha = (math.sin(math.radians(angle)) - math.sin(math.radians(lat)) * math.sin(math.radians(decl))) / (
        math.cos(math.radians(lat)) * math.cos(math.radians(decl))
    )
    if cos_ha < -1 or cos_ha > 1:
        return None
    return math.degrees(math.acos(cos_ha)) / 15.0


def asr_hour_angle(lat: float, decl: float) -> float | None:
    """Stundenwinkel für Asr (Shafi-Methode)."""
    shadow_ratio = 1.0 + math.tan(math.radians(abs(lat - decl)))
    asr_alt = math.atan(1.0 / shadow_ratio)
    cos_ha = (math.sin(asr_alt) - math.sin(math.radians(lat)) * math.sin(math.radians(decl))) / (
        math.cos(math.radians(lat)) * math.cos(math.radians(decl))
    )
    if cos_ha < -1 or cos_ha > 1:
        return None
    return math.degrees(math.acos(cos_ha)) / 15.0


def _utc_hours_to_local(utc_hours: float, dt: date) -> tuple[int, int]:
    """UTC-Stunden → lokale (Stunde, Minute) unter Berücksichtigung von DST."""
    utc_dt = datetime(dt.year, dt.month, dt.day, tzinfo=ZoneInfo("UTC")) + timedelta(hours=utc_hours)
    local = utc_dt.astimezone(TIMEZONE)
    return local.hour, local.minute


def _night_fallback(transit_utc: float, sunrise_ha: float, dt: date, is_fajr: bool) -> tuple[int, int]:
    """
    Fallback für Fajr/Isha wenn die Sonne den Winkel im Sommer nicht erreicht.
    Diyanet nutzt die 1/7-Nacht-Regel:
      Fajr  = Sonnenaufgang − Nacht/7
      Isha  = Sonnenuntergang + Nacht/7
    """
    sunrise_utc = transit_utc - sunrise_ha
    sunset_utc = transit_utc + sunrise_ha
    night_hours = 24.0 - (sunset_utc - sunrise_utc)
    if is_fajr:
        return _utc_hours_to_local(sunrise_utc - night_hours / 7.0, dt)
    else:
        return _utc_hours_to_local(sunset_utc + night_hours / 7.0, dt)


def _fetch_prayer_times_api(year: int, month: int, day: int) -> dict[str, tuple[int, int]] | None:
    """
    Holt Gebetszeiten von der AlAdhan-API (Diyanet-Methode 13).
    Gibt None zurück wenn die API nicht erreichbar ist.
    """
    url = (
        f"https://api.aladhan.com/v1/timings/{day:02d}-{month:02d}-{year}"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}&method=13"
        f"&timezonestring=Europe/Berlin"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        timings = data["data"]["timings"]

        def parse(t: str) -> tuple[int, int]:
            h, m = t.split(":")
            return int(h), int(m)

        return {
            "fajr":    parse(timings["Fajr"]),
            "dhuhr":   parse(timings["Dhuhr"]),
            "asr":     parse(timings["Asr"]),
            "maghrib": parse(timings["Maghrib"]),
            "isha":    parse(timings["Isha"]),
        }
    except Exception as e:
        log.warning("AlAdhan-API nicht erreichbar, nutze lokale Berechnung: %s", e)
        return None


def get_prayer_times(year: int, month: int, day: int) -> dict[str, tuple[int, int]]:
    """
    Berechnet alle 5 Gebetszeiten für ein Datum.

    Rückgabe: {"fajr": (h, m), "dhuhr": (h, m), "asr": (h, m),
               "maghrib": (h, m), "isha": (h, m)}
    Alle Zeiten in Lokalzeit (Europe/Berlin, inkl. Sommerzeit).
    """
    api_result = _fetch_prayer_times_api(year, month, day)
    if api_result:
        return api_result

    dt = date(year, month, day)
    jd = julian_day(year, month, day)
    decl, EqT = sun_position(jd + 0.5)
    transit_utc = 12.0 + (-LONGITUDE / 15.0) - EqT

    sunrise_ha = sun_hour_angle(-SUN_REFRACTION, LATITUDE, decl)

    # Dhuhr
    dhuhr = _utc_hours_to_local(transit_utc + 2.0 / 60.0, dt)

    # Asr
    ha = asr_hour_angle(LATITUDE, decl)
    asr = _utc_hours_to_local(transit_utc + ha, dt) if ha else dhuhr

    # Maghrib (Sonnenuntergang)
    maghrib = _utc_hours_to_local(transit_utc + sunrise_ha, dt) if sunrise_ha else dhuhr

    # Fajr
    ha = sun_hour_angle(-FAJR_ANGLE, LATITUDE, decl)
    if ha:
        fajr = _utc_hours_to_local(transit_utc - ha, dt)
    else:
        fajr = _night_fallback(transit_utc, sunrise_ha or 6.0, dt, is_fajr=True)

    # Isha
    ha = sun_hour_angle(-ISHA_ANGLE, LATITUDE, decl)
    if ha:
        isha = _utc_hours_to_local(transit_utc + ha, dt)
    else:
        isha = _night_fallback(transit_utc, sunrise_ha or 6.0, dt, is_fajr=False)

    return {
        "fajr": fajr,
        "dhuhr": dhuhr,
        "asr": asr,
        "maghrib": maghrib,
        "isha": isha,
    }


def get_next_prayer(times: dict[str, tuple[int, int]], hour: int, minute: int) -> tuple[str, int, int]:
    """
    Findet das nächste Gebet basierend auf der aktuellen Zeit.

    Rückgabe: (name, stunde, minute) des nächsten Gebets.
    Wenn alle Gebete für heute vorbei sind, wird Fajr des nächsten
    Tages zurückgegeben (Stunde kann > 23 sein für Darstellung).
    """
    current = hour * 60 + minute
    for name in PRAYER_NAMES:
        h, m = times[name]
        prayer_min = h * 60 + m
        if prayer_min > current:
            return name, h, m
    # Alle Gebete vorbei → Fajr morgen
    return "fajr", -1, -1  # Sentinel: morgen neu berechnen
