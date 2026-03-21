"""
Tests für web_app.py (Flask Web-Interface)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import json
from web_app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestIndexPage:
    def test_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_contains_namazsaati(self, client):
        response = client.get("/")
        assert b"NamazSaati" in response.data

    def test_contains_all_prayer_names(self, client):
        response = client.get("/")
        for name in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
            assert name.encode() in response.data, f"{name} fehlt auf der Seite"

    def test_contains_time_format(self, client):
        """Seite enthält Zeiten im Format HH:MM."""
        import re
        response = client.get("/")
        times = re.findall(rb"\d{2}:\d{2}", response.data)
        assert len(times) >= 5, "Nicht genug Zeiten auf der Seite"

    def test_auto_refresh_meta_tag(self, client):
        """Seite hat Meta-Refresh für automatisches Neuladen."""
        response = client.get("/")
        assert b'http-equiv="refresh"' in response.data


class TestApiTimes:
    def test_returns_200(self, client):
        response = client.get("/api/times")
        assert response.status_code == 200

    def test_returns_json(self, client):
        response = client.get("/api/times")
        assert response.content_type == "application/json"

    def test_json_structure(self, client):
        response = client.get("/api/times")
        data = json.loads(response.data)
        assert "date" in data
        assert "times" in data
        assert "next_prayer" in data

    def test_all_prayers_in_json(self, client):
        response = client.get("/api/times")
        data = json.loads(response.data)
        for name in ["fajr", "dhuhr", "asr", "maghrib", "isha"]:
            assert name in data["times"], f"{name} fehlt in API-Antwort"

    def test_time_format_in_json(self, client):
        """Gebetszeiten im Format HH:MM."""
        import re
        response = client.get("/api/times")
        data = json.loads(response.data)
        for name, time_str in data["times"].items():
            assert re.match(r"^\d{2}:\d{2}$", time_str), (
                f"{name}: ungültiges Format '{time_str}'"
            )

    def test_next_prayer_has_name_and_time(self, client):
        response = client.get("/api/times")
        data = json.loads(response.data)
        assert "name" in data["next_prayer"]
        assert "time" in data["next_prayer"]
        assert data["next_prayer"]["name"] in ["fajr", "dhuhr", "asr", "maghrib", "isha"]

    def test_date_format(self, client):
        """Datum im Format YYYY-MM-DD."""
        import re
        response = client.get("/api/times")
        data = json.loads(response.data)
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", data["date"])
