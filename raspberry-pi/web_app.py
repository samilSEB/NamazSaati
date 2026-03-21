#!/usr/bin/env python3
"""
NamazSaati - Web-Interface

Zeigt alle heutigen Gebetszeiten + Countdown zum nächsten Gebet.
Erreichbar unter http://namazsaati.local:5000 im Heimnetzwerk.
Kein App-Download nötig — einfach Browser öffnen.
"""

from flask import Flask, jsonify, render_template_string
from datetime import datetime
from zoneinfo import ZoneInfo

from prayer_calculator import get_prayer_times, get_next_prayer, PRAYER_NAMES

app = Flask(__name__)
TIMEZONE = ZoneInfo("Europe/Berlin")

PRAYER_DISPLAY_NAMES = {
    "fajr": "Fajr",
    "dhuhr": "Dhuhr",
    "asr": "Asr",
    "maghrib": "Maghrib",
    "isha": "Isha",
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="30">
    <title>NamazSaati</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #1a1a2e;
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .card {
            background: #16213e;
            border-radius: 16px;
            padding: 28px 32px;
            max-width: 380px;
            width: 95%;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 1px solid #0f3460;
            padding-bottom: 16px;
        }
        .header h1 { font-size: 1.6rem; color: #e2b96f; letter-spacing: 2px; }
        .header .date { font-size: 0.85rem; color: #8899aa; margin-top: 4px; }
        .prayers { list-style: none; }
        .prayers li {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 8px;
            border-radius: 8px;
            margin-bottom: 4px;
            transition: background 0.2s;
        }
        .prayers li.done { opacity: 0.45; }
        .prayers li.next {
            background: #0f3460;
            border: 1px solid #e2b96f;
        }
        .prayer-name { font-weight: 600; font-size: 1rem; }
        .prayer-time { font-size: 1rem; font-variant-numeric: tabular-nums; }
        .badge {
            font-size: 0.7rem;
            background: #e2b96f;
            color: #1a1a2e;
            padding: 2px 8px;
            border-radius: 99px;
            font-weight: 700;
            text-transform: uppercase;
        }
        .next-info {
            text-align: center;
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid #0f3460;
            font-size: 0.9rem;
            color: #8899aa;
        }
        .next-info strong { color: #e2b96f; }
        .check { color: #4caf50; margin-right: 4px; }
        .arrow { color: #e2b96f; margin-right: 4px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h1>NamazSaati</h1>
            <div class="date">{{ date_str }} &middot; {{ time_str }}</div>
        </div>
        <ul class="prayers">
            {% for p in prayers %}
            <li class="{{ p.css_class }}">
                <span class="prayer-name">
                    {% if p.is_done %}<span class="check">&#10003;</span>{% endif %}
                    {% if p.is_next %}<span class="arrow">&#8594;</span>{% endif %}
                    {{ p.display_name }}
                </span>
                <span class="prayer-time">{{ p.time_str }}</span>
                {% if p.is_next %}<span class="badge">Nächstes</span>{% endif %}
            </li>
            {% endfor %}
        </ul>
        <div class="next-info">
            {% if next_in_minutes >= 0 %}
                Nächstes: <strong>{{ next_name }}</strong> in
                {% if next_in_minutes >= 60 %}
                    <strong>{{ next_in_minutes // 60 }}h {{ next_in_minutes % 60 }}min</strong>
                {% else %}
                    <strong>{{ next_in_minutes }}min</strong>
                {% endif %}
            {% else %}
                Nächstes Gebet: <strong>Fajr morgen</strong>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""


def _build_context():
    now = datetime.now(TIMEZONE)
    times = get_prayer_times(now.year, now.month, now.day)
    current_min = now.hour * 60 + now.minute

    next_name_key, next_h, next_m = get_next_prayer(times, now.hour, now.minute)
    next_in_minutes = -1
    if next_h != -1:
        next_in_minutes = (next_h * 60 + next_m) - current_min

    prayers = []
    for name in PRAYER_NAMES:
        h, m = times[name]
        prayer_min = h * 60 + m
        is_done = prayer_min < current_min and name != next_name_key
        is_next = name == next_name_key and next_h != -1
        css = "done" if is_done else ("next" if is_next else "")
        prayers.append({
            "display_name": PRAYER_DISPLAY_NAMES[name],
            "time_str": f"{h:02d}:{m:02d}",
            "is_done": is_done,
            "is_next": is_next,
            "css_class": css,
        })

    month_names = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                   "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    dow = weekdays[now.weekday()]
    mon = month_names[now.month - 1]

    return {
        "date_str": f"{dow}, {now.day}. {mon} {now.year}",
        "time_str": f"{now.hour:02d}:{now.minute:02d}",
        "prayers": prayers,
        "next_name": PRAYER_DISPLAY_NAMES.get(next_name_key, "Fajr"),
        "next_in_minutes": next_in_minutes,
    }


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, **_build_context())


@app.route("/api/times")
def api_times():
    """JSON-API für Gebetszeiten. Für Tests und externe Nutzung."""
    now = datetime.now(TIMEZONE)
    times = get_prayer_times(now.year, now.month, now.day)
    next_name, next_h, next_m = get_next_prayer(times, now.hour, now.minute)
    return jsonify({
        "date": now.strftime("%Y-%m-%d"),
        "current_time": f"{now.hour:02d}:{now.minute:02d}",
        "times": {name: f"{h:02d}:{m:02d}" for name, (h, m) in times.items()},
        "next_prayer": {
            "name": next_name,
            "time": f"{next_h:02d}:{next_m:02d}" if next_h != -1 else "morgen",
        },
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
