"""
Tests für web_app.py (Flask Web-Interface)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import json
import io
from unittest.mock import patch, MagicMock
from web_app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Index-Seite
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# /api/times
# ---------------------------------------------------------------------------

class TestApiTimes:
    def test_returns_200(self, client):
        response = client.get("/api/times")
        assert response.status_code == 200

    def test_returns_json(self, client):
        response = client.get("/api/times")
        assert response.content_type == "application/json"

    def test_json_has_prayers_list(self, client):
        """API gibt 'prayers' (Liste) und 'next_prayer' zurück."""
        response = client.get("/api/times")
        data = json.loads(response.data)
        assert "prayers" in data, f"'prayers' fehlt. Schlüssel: {list(data.keys())}"
        assert "next_prayer" in data

    def test_prayers_list_has_five_entries(self, client):
        response = client.get("/api/times")
        data = json.loads(response.data)
        assert len(data["prayers"]) == 5

    def test_all_prayer_names_in_list(self, client):
        response = client.get("/api/times")
        data = json.loads(response.data)
        names = {p["name"] for p in data["prayers"]}
        for prayer in ["fajr", "dhuhr", "asr", "maghrib", "isha"]:
            assert prayer in names, f"{prayer} fehlt in prayers"

    def test_prayer_entry_has_required_fields(self, client):
        response = client.get("/api/times")
        data = json.loads(response.data)
        for p in data["prayers"]:
            assert "name" in p
            assert "time_str" in p
            assert "is_done" in p
            assert "is_next" in p
            assert "css_class" in p
            assert "display_name" in p

    def test_time_format_hhmm(self, client):
        """Gebetszeiten im Format HH:MM."""
        import re
        response = client.get("/api/times")
        data = json.loads(response.data)
        for p in data["prayers"]:
            assert re.match(r"^\d{2}:\d{2}$", p["time_str"]), (
                f"{p['name']}: ungültiges Format '{p['time_str']}'"
            )

    def test_next_prayer_has_required_fields(self, client):
        response = client.get("/api/times")
        data = json.loads(response.data)
        np = data["next_prayer"]
        assert "name" in np
        assert "name_display" in np
        assert "time" in np
        assert "seconds_remaining" in np

    def test_next_prayer_name_is_valid(self, client):
        response = client.get("/api/times")
        data = json.loads(response.data)
        assert data["next_prayer"]["name"] in ["fajr", "dhuhr", "asr", "maghrib", "isha"]

    def test_exactly_one_prayer_is_next(self, client):
        """Genau ein oder kein Gebet hat is_next=True."""
        response = client.get("/api/times")
        data = json.loads(response.data)
        next_count = sum(1 for p in data["prayers"] if p["is_next"])
        assert next_count <= 1


# ---------------------------------------------------------------------------
# /api/config
# ---------------------------------------------------------------------------

class TestApiConfig:
    def test_get_returns_200(self, client):
        response = client.get("/api/config")
        assert response.status_code == 200

    def test_get_returns_json(self, client):
        response = client.get("/api/config")
        assert response.content_type == "application/json"

    def test_get_has_required_keys(self, client):
        response = client.get("/api/config")
        data = json.loads(response.data)
        for key in ("volume", "bluetooth_mac", "prayers_enabled"):
            assert key in data, f"'{key}' fehlt in /api/config"

    def test_post_saves_volume(self, client):
        saved = {}

        def fake_save(cfg):
            saved.update(cfg)

        with patch("web_app.save_config", side_effect=fake_save), \
             patch("web_app.load_config", return_value={
                 "volume": 70, "bluetooth_mac": "", "bluetooth_name": "",
                 "prayers_enabled": {}
             }):
            response = client.post("/api/config",
                                   data=json.dumps({"volume": 55}),
                                   content_type="application/json")
        assert response.status_code == 200
        assert saved.get("volume") == 55

    def test_post_saves_prayers_enabled(self, client):
        saved = {}

        def fake_save(cfg):
            saved.update(cfg)

        with patch("web_app.save_config", side_effect=fake_save), \
             patch("web_app.load_config", return_value={
                 "volume": 70, "bluetooth_mac": "", "bluetooth_name": "",
                 "prayers_enabled": {"fajr": False}
             }):
            response = client.post("/api/config",
                                   data=json.dumps({"prayers_enabled": {"fajr": True, "dhuhr": True}}),
                                   content_type="application/json")
        assert response.status_code == 200
        assert saved["prayers_enabled"]["fajr"] is True

    def test_post_returns_ok_true(self, client):
        with patch("web_app.save_config"), \
             patch("web_app.load_config", return_value={
                 "volume": 70, "bluetooth_mac": "", "bluetooth_name": "",
                 "prayers_enabled": {}
             }):
            response = client.post("/api/config",
                                   data=json.dumps({"volume": 60}),
                                   content_type="application/json")
        data = json.loads(response.data)
        assert data["ok"] is True


# ---------------------------------------------------------------------------
# /api/ezan/test und /api/ezan/stop
# ---------------------------------------------------------------------------

class TestApiEzan:
    def test_test_ezan_missing_file_returns_404(self, client):
        with patch("web_app.AUDIO_DIR") as mock_dir:
            mock_dir.__truediv__ = lambda s, p: MagicMock(exists=lambda: False)
            response = client.post("/api/ezan/test")
        assert response.status_code == 404

    def test_test_ezan_calls_mpg123(self, client, tmp_path):
        """mpg123 wird via Popen gestartet."""
        fake_file = tmp_path / "ezan.mp3"
        fake_file.write_text("fake")
        with patch("web_app.AUDIO_DIR", tmp_path), \
             patch("web_app.subprocess.run") as mock_run, \
             patch("web_app.subprocess.Popen") as mock_popen, \
             patch("web_app.load_config", return_value={"volume": 70}):
            mock_run.return_value = MagicMock(returncode=0)
            response = client.post("/api/ezan/test")
        assert response.status_code == 200
        mock_popen.assert_called_once()
        assert "mpg123" in mock_popen.call_args[0][0]

    def test_stop_ezan_returns_200(self, client):
        with patch("web_app.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            response = client.post("/api/ezan/stop")
        assert response.status_code == 200

    def test_stop_ezan_calls_pkill(self, client):
        with patch("web_app.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            client.post("/api/ezan/stop")
        cmd = mock_run.call_args[0][0]
        assert "pkill" in cmd
        assert "mpg123" in cmd

    def test_stop_ezan_returns_ok_true(self, client):
        with patch("web_app.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            response = client.post("/api/ezan/stop")
        data = json.loads(response.data)
        assert data["ok"] is True


# ---------------------------------------------------------------------------
# /api/audio/upload
# ---------------------------------------------------------------------------

class TestApiAudioUpload:
    def test_upload_without_file_returns_400(self, client):
        response = client.post("/api/audio/upload")
        assert response.status_code == 400

    def test_upload_saves_file(self, client, tmp_path):
        """Hochgeladene Datei wird als ezan.mp3 gespeichert."""
        with patch("web_app.AUDIO_DIR", tmp_path):
            data = {"file": (io.BytesIO(b"fake mp3 data"), "test.mp3")}
            response = client.post("/api/audio/upload",
                                   data=data,
                                   content_type="multipart/form-data")
        assert response.status_code == 200
        assert (tmp_path / "ezan.mp3").exists()

    def test_upload_returns_ok_true(self, client, tmp_path):
        with patch("web_app.AUDIO_DIR", tmp_path):
            data = {"file": (io.BytesIO(b"fake mp3 data"), "test.mp3")}
            response = client.post("/api/audio/upload",
                                   data=data,
                                   content_type="multipart/form-data")
        result = json.loads(response.data)
        assert result["ok"] is True

    def test_upload_empty_filename_returns_400(self, client):
        data = {"file": (io.BytesIO(b""), "")}
        response = client.post("/api/audio/upload",
                               data=data,
                               content_type="multipart/form-data")
        assert response.status_code == 400
