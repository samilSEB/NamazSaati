"""
Tests für config.py (Konfigurationsverwaltung)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from config import load_config, save_config, DEFAULT_CONFIG, CONFIG_FILE


class TestLoadConfig:
    def test_default_config_when_no_file(self, tmp_path):
        """Keine Konfigurationsdatei → Standard-Config wird zurückgegeben."""
        fake_config = tmp_path / "config.json"
        with patch("config.CONFIG_FILE", fake_config):
            result = load_config()
        assert result["volume"] == DEFAULT_CONFIG["volume"]
        assert result["bluetooth_mac"] == DEFAULT_CONFIG["bluetooth_mac"]
        assert "prayers_enabled" in result

    def test_loads_existing_config(self, tmp_path):
        """Vorhandene Datei wird korrekt gelesen."""
        cfg = {"volume": 85, "bluetooth_mac": "AA:BB:CC:DD:EE:FF",
               "bluetooth_name": "TestBox", "prayers_enabled": {"fajr": True}}
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps(cfg))
        with patch("config.CONFIG_FILE", fake_file):
            result = load_config()
        assert result["volume"] == 85
        assert result["bluetooth_mac"] == "AA:BB:CC:DD:EE:FF"

    def test_fills_missing_keys_with_defaults(self, tmp_path):
        """Partial-Config → fehlende Schlüssel werden mit Defaults aufgefüllt."""
        partial = {"volume": 50}
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps(partial))
        with patch("config.CONFIG_FILE", fake_file):
            result = load_config()
        assert result["volume"] == 50
        assert "bluetooth_mac" in result
        assert "prayers_enabled" in result

    def test_corrupted_json_returns_default(self, tmp_path):
        """Kaputtes JSON → Standard-Config."""
        fake_file = tmp_path / "config.json"
        fake_file.write_text("{invalid json{{")
        with patch("config.CONFIG_FILE", fake_file):
            result = load_config()
        assert result == DEFAULT_CONFIG

    def test_all_required_keys_present(self, tmp_path):
        """Default-Config enthält alle benötigten Schlüssel."""
        fake_file = tmp_path / "no_file.json"
        with patch("config.CONFIG_FILE", fake_file):
            result = load_config()
        for key in ("volume", "bluetooth_mac", "bluetooth_name", "prayers_enabled"):
            assert key in result, f"Schlüssel '{key}' fehlt in load_config()"

    def test_prayers_enabled_has_all_five(self, tmp_path):
        """prayers_enabled enthält alle 5 Gebete."""
        fake_file = tmp_path / "no_file.json"
        with patch("config.CONFIG_FILE", fake_file):
            result = load_config()
        for prayer in ("fajr", "dhuhr", "asr", "maghrib", "isha"):
            assert prayer in result["prayers_enabled"], f"{prayer} fehlt in prayers_enabled"

    def test_fajr_disabled_by_default(self, tmp_path):
        """Fajr ist standardmäßig deaktiviert."""
        fake_file = tmp_path / "no_file.json"
        with patch("config.CONFIG_FILE", fake_file):
            result = load_config()
        assert result["prayers_enabled"]["fajr"] is False

    def test_volume_in_valid_range(self, tmp_path):
        """Standard-Lautstärke ist zwischen 0 und 100."""
        fake_file = tmp_path / "no_file.json"
        with patch("config.CONFIG_FILE", fake_file):
            result = load_config()
        assert 0 <= result["volume"] <= 100


class TestSaveConfig:
    def test_creates_directory_if_missing(self, tmp_path):
        """Speichert auch wenn das Verzeichnis noch nicht existiert."""
        fake_dir = tmp_path / "subdir" / "namazsaati"
        fake_file = fake_dir / "config.json"
        cfg = {"volume": 60, "bluetooth_mac": "11:22:33:44:55:66",
               "bluetooth_name": "Test", "prayers_enabled": {}}
        with patch("config.CONFIG_DIR", fake_dir), \
             patch("config.CONFIG_FILE", fake_file):
            save_config(cfg)
        assert fake_file.exists()

    def test_saves_correct_content(self, tmp_path):
        """Gespeicherter Inhalt stimmt mit Input überein."""
        fake_dir = tmp_path
        fake_file = tmp_path / "config.json"
        cfg = {"volume": 42, "bluetooth_mac": "DE:AD:BE:EF:00:01",
               "bluetooth_name": "Lautsprecher", "prayers_enabled": {"fajr": True, "dhuhr": False}}
        with patch("config.CONFIG_DIR", fake_dir), \
             patch("config.CONFIG_FILE", fake_file):
            save_config(cfg)
        loaded = json.loads(fake_file.read_text())
        assert loaded["volume"] == 42
        assert loaded["bluetooth_mac"] == "DE:AD:BE:EF:00:01"
        assert loaded["prayers_enabled"]["fajr"] is True

    def test_overwrites_existing_file(self, tmp_path):
        """Überschreibt vorhandene Datei."""
        fake_dir = tmp_path
        fake_file = tmp_path / "config.json"
        fake_file.write_text(json.dumps({"volume": 99}))
        cfg = {"volume": 10, "bluetooth_mac": "", "bluetooth_name": "", "prayers_enabled": {}}
        with patch("config.CONFIG_DIR", fake_dir), \
             patch("config.CONFIG_FILE", fake_file):
            save_config(cfg)
        loaded = json.loads(fake_file.read_text())
        assert loaded["volume"] == 10

    def test_roundtrip_load_save_load(self, tmp_path):
        """Speichern und Laden ergibt dieselbe Config."""
        fake_dir = tmp_path
        fake_file = tmp_path / "config.json"
        original = {"volume": 77, "bluetooth_mac": "AA:BB:CC:DD:EE:FF",
                    "bluetooth_name": "Bose", "prayers_enabled": {"fajr": False, "dhuhr": True}}
        with patch("config.CONFIG_DIR", fake_dir), \
             patch("config.CONFIG_FILE", fake_file):
            save_config(original)
            loaded = load_config()
        assert loaded["volume"] == original["volume"]
        assert loaded["bluetooth_mac"] == original["bluetooth_mac"]
