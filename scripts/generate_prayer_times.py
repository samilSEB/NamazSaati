#!/usr/bin/env python3
"""
NamazSaati - Gebetszeiten-Generator für Ludwigsburg
Berechnet alle 5 täglichen Gebetszeiten nach der Diyanet-Methode
und gibt eine C-Header-Datei als Lookup-Table aus.

Diyanet-Parameter:
  Fajr:  18° unter Horizont
  Isha:  17° unter Horizont
  Asr:   Shafi (Schattenlänge = Objekthöhe + Schatten bei Sonnenhöchststand)

Verwendung:
  python3 generate_prayer_times.py [--year 2026] [--output ../lib/PrayerTimes/prayer_data.h]
"""

import math
import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Ludwigsburg, Deutschland
LATITUDE = 48.8975
LONGITUDE = 9.1925
TIMEZONE = ZoneInfo("Europe/Berlin")

# Diyanet-Methode
FAJR_ANGLE = 18.0
ISHA_ANGLE = 17.0
SUN_REFRACTION = 0.8333  # Atmosphärische Refraktion + Sonnendurchmesser


def julian_day(year: int, month: int, day: int) -> float:
    """Berechnet den Julianischen Tag (JD) für ein Datum."""
    if month <= 2:
        year -= 1
        month += 12
    A = math.floor(year / 100.0)
    B = 2 - A + math.floor(A / 4.0)
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + B - 1524.5


def sun_position(jd: float):
    """Berechnet Sonnendeklination und Zeitgleichung (equation of time)."""
    D = jd - 2451545.0  # Tage seit J2000.0

    # Mittlere Anomalie der Sonne
    g = 357.529 + 0.98560028 * D
    g = math.radians(g % 360)

    # Mittlere Länge der Sonne
    q = 280.459 + 0.98564736 * D
    q = q % 360

    # Ekliptikale Länge der Sonne
    L = q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)
    L_rad = math.radians(L % 360)

    # Schiefe der Ekliptik
    e = 23.439 - 0.00000036 * D
    e_rad = math.radians(e)

    # Rektaszension
    RA = math.degrees(math.atan2(math.cos(e_rad) * math.sin(L_rad), math.cos(L_rad))) / 15.0

    # Deklination
    decl = math.degrees(math.asin(math.sin(e_rad) * math.sin(L_rad)))

    # Zeitgleichung (equation of time) in Stunden
    EqT = (q / 15.0) - RA
    # Normalisieren auf [-12, 12]
    while EqT > 12:
        EqT -= 24
    while EqT < -12:
        EqT += 24

    return decl, EqT


def sun_hour_angle(angle: float, lat: float, decl: float) -> float | None:
    """Berechnet den Stundenwinkel für einen gegebenen Sonnenwinkel."""
    lat_rad = math.radians(lat)
    decl_rad = math.radians(decl)
    angle_rad = math.radians(angle)

    cos_ha = (math.sin(angle_rad) - math.sin(lat_rad) * math.sin(decl_rad)) / (
        math.cos(lat_rad) * math.cos(decl_rad)
    )

    if cos_ha < -1 or cos_ha > 1:
        return None  # Sonne geht nicht auf/unter bei diesem Winkel

    return math.degrees(math.acos(cos_ha)) / 15.0  # In Stunden


def asr_hour_angle(lat: float, decl: float) -> float | None:
    """Berechnet den Stundenwinkel für Asr (Shafi-Methode).
    Shafi: Schattenlänge = Objekthöhe + Schatten bei Sonnenhöchststand."""
    lat_rad = math.radians(lat)
    decl_rad = math.radians(decl)

    # Sonnenaltitude bei der Asr-Zeit
    # cot(a) = 1 + tan(|lat - decl|)  →  a = acot(1 + tan(|lat - decl|))
    shadow_ratio = 1.0 + math.tan(math.radians(abs(lat - decl)))
    asr_alt = math.atan(1.0 / shadow_ratio)  # Positiver Winkel (Sonne über Horizont)

    cos_ha = (math.sin(asr_alt) - math.sin(lat_rad) * math.sin(decl_rad)) / (
        math.cos(lat_rad) * math.cos(decl_rad)
    )

    if cos_ha < -1 or cos_ha > 1:
        return None

    return math.degrees(math.acos(cos_ha)) / 15.0


def calculate_prayer_times(year: int, month: int, day: int):
    """Berechnet alle 5 Gebetszeiten für ein Datum in UTC-Stunden."""
    jd = julian_day(year, month, day)
    decl, EqT = sun_position(jd + 0.5)  # Mittag

    # Transit (Sonnenhöchststand / Dhuhr)
    transit = 12.0 + (-LONGITUDE / 15.0) - EqT

    # Fajr
    fajr_ha = sun_hour_angle(-FAJR_ANGLE, LATITUDE, decl)
    fajr = transit - fajr_ha if fajr_ha else None

    # Sunrise (für Info, nicht als Gebet)
    sunrise_ha = sun_hour_angle(-SUN_REFRACTION, LATITUDE, decl)
    sunrise = transit - sunrise_ha if sunrise_ha else None

    # Dhuhr (etwas nach Transit, +2 Minuten Sicherheit wie bei Diyanet)
    dhuhr = transit + (2.0 / 60.0)

    # Asr
    asr_ha = asr_hour_angle(LATITUDE, decl)
    asr = transit + asr_ha if asr_ha else None

    # Maghrib (Sonnenuntergang)
    sunset_ha = sun_hour_angle(-SUN_REFRACTION, LATITUDE, decl)
    maghrib = transit + sunset_ha if sunset_ha else None

    # Isha
    isha_ha = sun_hour_angle(-ISHA_ANGLE, LATITUDE, decl)
    isha = transit + isha_ha if isha_ha else None

    return fajr, dhuhr, asr, maghrib, isha


def utc_hours_to_local_minutes(utc_hours: float, dt: date) -> int:
    """Konvertiert UTC-Stunden zu lokalen Minuten seit Mitternacht (DST-berücksichtigt)."""
    utc_dt = datetime(dt.year, dt.month, dt.day, tzinfo=ZoneInfo("UTC")) + timedelta(hours=utc_hours)
    local_dt = utc_dt.astimezone(TIMEZONE)
    return local_dt.hour * 60 + local_dt.minute


def generate_header(year: int, output_path: str):
    """Generiert die C-Header-Datei mit allen Gebetszeiten."""
    start_date = date(year, 1, 1)
    days_in_year = (date(year + 1, 1, 1) - start_date).days

    lines = []
    lines.append(f"// Auto-generated prayer times for Ludwigsburg, Germany ({LATITUDE}, {LONGITUDE})")
    lines.append(f"// Method: Diyanet (Fajr: {FAJR_ANGLE}°, Isha: {ISHA_ANGLE}°, Asr: Shafi)")
    lines.append(f"// Year: {year}, Timezone: Europe/Berlin (CET/CEST)")
    lines.append(f"// Format: minutes since midnight (local time, DST-adjusted)")
    lines.append(f"// Index: 0=Fajr, 1=Dhuhr, 2=Asr, 3=Maghrib, 4=Isha")
    lines.append(f"// Generated: {datetime.now().isoformat()}")
    lines.append("")
    lines.append("#pragma once")
    lines.append("#include <stdint.h>")
    lines.append("#include <pgmspace.h>")
    lines.append("")
    lines.append(f"constexpr int PRAYER_YEAR = {year};")
    lines.append(f"constexpr int DAYS_IN_YEAR = {days_in_year};")
    lines.append("")
    lines.append(f"const uint16_t PRAYER_TIMES[{days_in_year}][5] PROGMEM = {{")

    for day_idx in range(days_in_year):
        current_date = start_date + timedelta(days=day_idx)
        fajr, dhuhr, asr, maghrib, isha = calculate_prayer_times(
            current_date.year, current_date.month, current_date.day
        )

        # Konvertieren in lokale Minuten
        dhuhr_min = utc_hours_to_local_minutes(dhuhr, current_date) if dhuhr else 720
        asr_min = utc_hours_to_local_minutes(asr, current_date) if asr else 900
        maghrib_min = utc_hours_to_local_minutes(maghrib, current_date) if maghrib else 1080

        # Fajr/Isha: Bei hohen Breitengraden im Sommer kann die Sonne nicht
        # tief genug sinken. Diyanet nutzt dann die 1/7-Nacht-Regel:
        # Fajr = Sunrise - 1/7 * Nachtdauer
        # Isha = Sunset + 1/7 * Nachtdauer
        if fajr is not None:
            fajr_min = utc_hours_to_local_minutes(fajr, current_date)
        else:
            sunrise_ha = sun_hour_angle(-SUN_REFRACTION, LATITUDE,
                                        sun_position(julian_day(current_date.year, current_date.month, current_date.day) + 0.5)[0])
            if sunrise_ha:
                transit_utc = 12.0 + (-LONGITUDE / 15.0) - sun_position(julian_day(current_date.year, current_date.month, current_date.day) + 0.5)[1]
                sunrise_utc = transit_utc - sunrise_ha
                sunset_utc = transit_utc + sunrise_ha
                night_hours = 24.0 - (sunset_utc - sunrise_utc)
                fajr_utc = sunrise_utc - night_hours / 7.0
                fajr_min = utc_hours_to_local_minutes(fajr_utc, current_date)
            else:
                fajr_min = dhuhr_min - 90  # Absoluter Fallback

        if isha is not None:
            isha_min = utc_hours_to_local_minutes(isha, current_date)
        else:
            sunrise_ha = sun_hour_angle(-SUN_REFRACTION, LATITUDE,
                                        sun_position(julian_day(current_date.year, current_date.month, current_date.day) + 0.5)[0])
            if sunrise_ha:
                transit_utc = 12.0 + (-LONGITUDE / 15.0) - sun_position(julian_day(current_date.year, current_date.month, current_date.day) + 0.5)[1]
                sunrise_utc = transit_utc - sunrise_ha
                sunset_utc = transit_utc + sunrise_ha
                night_hours = 24.0 - (sunset_utc - sunrise_utc)
                isha_utc = sunset_utc + night_hours / 7.0
                isha_min = utc_hours_to_local_minutes(isha_utc, current_date)
            else:
                isha_min = maghrib_min + 90  # Absoluter Fallback

        times = [fajr_min, dhuhr_min, asr_min, maghrib_min, isha_min]

        # Formatierung: Minuten seit Mitternacht → HH:MM zur Lesbarkeit
        time_strs = [f"{t // 60:02d}:{t % 60:02d}" for t in times]
        comment = f"// {current_date.strftime('%b %d')}: {', '.join(time_strs)}"

        values = ", ".join(f"{t:4d}" for t in times)
        comma = "," if day_idx < days_in_year - 1 else ""
        lines.append(f"    {{{values}}}{comma}  {comment}")

    lines.append("};")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Generated {output_path}")
    print(f"  Year: {year}, Days: {days_in_year}")
    print(f"  Location: Ludwigsburg ({LATITUDE}, {LONGITUDE})")
    print(f"  Method: Diyanet (Fajr={FAJR_ANGLE}°, Isha={ISHA_ANGLE}°)")

    # Beispiel: ersten und letzten Tag anzeigen
    for day_idx in [0, days_in_year - 1]:
        current_date = start_date + timedelta(days=day_idx)
        fajr, dhuhr, asr, maghrib, isha = calculate_prayer_times(
            current_date.year, current_date.month, current_date.day
        )
        times = []
        for t in [fajr, dhuhr, asr, maghrib, isha]:
            if t is not None:
                m = utc_hours_to_local_minutes(t, current_date)
                times.append(f"{m // 60:02d}:{m % 60:02d}")
            else:
                times.append("--:--")
        print(f"  {current_date}: Fajr={times[0]} Dhuhr={times[1]} Asr={times[2]} Maghrib={times[3]} Isha={times[4]}")


def main():
    parser = argparse.ArgumentParser(description="NamazSaati Gebetszeiten-Generator")
    parser.add_argument("--year", type=int, default=2026, help="Jahr (Standard: 2026)")
    parser.add_argument(
        "--output",
        type=str,
        default="../lib/PrayerTimes/prayer_data.h",
        help="Ausgabepfad für C-Header",
    )
    args = parser.parse_args()

    generate_header(args.year, args.output)


if __name__ == "__main__":
    main()
