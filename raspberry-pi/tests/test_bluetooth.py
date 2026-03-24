"""
Tests für Bluetooth-Connect und Keep-Alive Logik.
"""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock, call
import subprocess


# ── web_app Bluetooth-Endpunkte ──────────────────────────────────────────────

@pytest.fixture
def client():
    from web_app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


BOSE_MAC = "60:AB:D2:11:7D:7D"
BOSE_SINK = "bluez_sink.60_AB_D2_11_7D_7D.a2dp_sink"


class TestBluetoothStatus:
    def test_returns_200(self, client):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=b"", returncode=0)
            r = client.get("/api/bluetooth/status")
        assert r.status_code == 200

    def test_connected_when_sink_present(self, client):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=BOSE_SINK.encode(), returncode=0
            )
            r = client.get("/api/bluetooth/status")
        data = json.loads(r.data)
        assert data["connected"] is True

    def test_not_connected_when_sink_absent(self, client):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=b"auto_null", returncode=0)
            r = client.get("/api/bluetooth/status")
        data = json.loads(r.data)
        assert data["connected"] is False

    def test_returns_mac_and_name(self, client):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=b"", returncode=0)
            r = client.get("/api/bluetooth/status")
        data = json.loads(r.data)
        assert "mac" in data
        assert "name" in data


class TestBluetoothConnect:
    def _sink_active_side_effect(self, cmd, **kwargs):
        """Gibt nach 2 Aufrufen den Sink zurück (simuliert kurze Verbindungszeit)."""
        if "sinks" in cmd:
            self._sink_call_count = getattr(self, "_sink_call_count", 0) + 1
            if self._sink_call_count >= 2:
                return MagicMock(stdout=BOSE_SINK.encode(), returncode=0)
            return MagicMock(stdout=b"auto_null", returncode=0)
        if "info" in cmd:
            # bluetoothctl info verwendet text=True → stdout ist str
            return MagicMock(stdout="Paired: yes\nConnected: yes\n", returncode=0)
        return MagicMock(stdout=b"", returncode=0)

    def test_connect_already_paired_success(self, client):
        """Gerät bereits gepairt → verbinden → Sink erscheint → OK."""
        self._sink_call_count = 0
        with patch("subprocess.run", side_effect=self._sink_active_side_effect), \
             patch("time.sleep"):
            r = client.post("/api/bluetooth/connect",
                            json={"mac": BOSE_MAC, "name": "Bose Mini II SoundLink"})
        data = json.loads(r.data)
        assert r.status_code == 200
        assert data["ok"] is True
        assert "Bose" in data["message"]

    def test_connect_saves_to_config(self, client):
        """Nach erfolgreichem Verbinden wird MAC in config gespeichert."""
        self._sink_call_count = 0
        saved = {}

        def fake_save(cfg):
            saved.update(cfg)

        with patch("subprocess.run", side_effect=self._sink_active_side_effect), \
             patch("time.sleep"), \
             patch("web_app.save_config", side_effect=fake_save):
            client.post("/api/bluetooth/connect",
                        json={"mac": BOSE_MAC, "name": "Bose"})

        assert saved.get("bluetooth_mac") == BOSE_MAC

    def test_connect_no_mac_returns_400(self, client):
        r = client.post("/api/bluetooth/connect", json={})
        assert r.status_code == 400

    def test_connect_sink_never_appears_returns_500(self, client):
        """Sink erscheint nicht → Fehler zurückgeben."""
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.return_value = MagicMock(
                stdout=b"auto_null Paired: yes", returncode=0
            )
            r = client.post("/api/bluetooth/connect",
                            json={"mac": BOSE_MAC, "name": "Bose"})
        assert r.status_code == 500
        data = json.loads(r.data)
        assert data["ok"] is False

    def test_connect_pairs_if_not_paired(self, client):
        """Gepairt noch nicht → pair + trust werden aufgerufen."""
        calls = []

        def track(cmd, **kwargs):
            calls.append(cmd)
            if "sinks" in cmd:
                return MagicMock(stdout=BOSE_SINK.encode(), returncode=0)
            if "info" in cmd:
                # text=True → stdout ist str
                return MagicMock(stdout="Paired: no\n", returncode=0)
            return MagicMock(stdout=b"", returncode=0)

        with patch("subprocess.run", side_effect=track), patch("time.sleep"):
            client.post("/api/bluetooth/connect",
                        json={"mac": BOSE_MAC, "name": "Bose"})

        cmds = [" ".join(c) for c in calls]
        assert any("pair" in c for c in cmds), "pair wurde nicht aufgerufen"
        assert any("trust" in c for c in cmds), "trust wurde nicht aufgerufen"


class TestBluetoothDisconnect:
    def test_disconnect_calls_bluetoothctl(self, client):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            r = client.post("/api/bluetooth/disconnect")
        assert r.status_code == 200
        cmds = [" ".join(c.args[0]) for c in mock_run.call_args_list]
        assert any("disconnect" in c for c in cmds)


class TestBluetoothScan:
    def test_scan_returns_device_list(self, client):
        scan_output = (
            "Device 60:AB:D2:11:7D:7D Bose Mini II SoundLink\n"
            "Device AA:BB:CC:DD:EE:FF JBL Clip\n"
        )
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.return_value = MagicMock(
                stdout=scan_output, returncode=0
            )
            r = client.get("/api/bluetooth/scan")
        data = json.loads(r.data)
        assert "devices" in data
        assert len(data["devices"]) >= 1

    def test_scan_parses_mac_and_name(self, client):
        scan_output = "Device 60:AB:D2:11:7D:7D Bose Mini II SoundLink\n"
        with patch("subprocess.run") as mock_run, patch("time.sleep"):
            mock_run.return_value = MagicMock(stdout=scan_output, returncode=0)
            r = client.get("/api/bluetooth/scan")
        data = json.loads(r.data)
        if data["devices"]:
            dev = data["devices"][0]
            assert "mac" in dev
            assert "name" in dev


# ── namazsaati Keep-Alive ────────────────────────────────────────────────────

class TestKeepBluetoothAlive:
    def test_plays_silence_via_paplay(self):
        """Keep-alive spielt Stille über paplay (PulseAudio), nicht aplay."""
        from namazsaati import keep_bluetooth_alive

        with patch("namazsaati._bluetooth_sink_active", return_value=True), \
             patch("namazsaati.load_config", return_value={
                 "bluetooth_mac": BOSE_MAC, "volume": 70, "prayers_enabled": {}
             }), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            keep_bluetooth_alive()

        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert any(c[0] == "paplay" for c in cmds), \
            f"paplay wurde nicht aufgerufen. Stattdessen: {cmds}"

    def test_reconnects_when_sink_missing(self):
        """Wenn Sink fehlt → ensure_bluetooth_connected wird aufgerufen."""
        from namazsaati import keep_bluetooth_alive

        with patch("namazsaati._bluetooth_sink_active", return_value=False), \
             patch("namazsaati.load_config", return_value={
                 "bluetooth_mac": BOSE_MAC, "volume": 70, "prayers_enabled": {}
             }), \
             patch("namazsaati.ensure_bluetooth_connected") as mock_connect:
            keep_bluetooth_alive()

        mock_connect.assert_called_once()

    def test_no_paplay_when_sink_missing(self):
        """Wenn Sink fehlt → kein paplay, nur reconnect."""
        from namazsaati import keep_bluetooth_alive

        with patch("namazsaati._bluetooth_sink_active", return_value=False), \
             patch("namazsaati.load_config", return_value={
                 "bluetooth_mac": BOSE_MAC, "volume": 70, "prayers_enabled": {}
             }), \
             patch("namazsaati.ensure_bluetooth_connected"), \
             patch("subprocess.run") as mock_run:
            keep_bluetooth_alive()

        cmds = [c.args[0] for c in mock_run.call_args_list]
        assert not any(c[0] == "paplay" for c in cmds)
