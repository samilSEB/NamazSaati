"""
NamazSaati - Konfigurationsverwaltung

Liest und schreibt ~/.config/namazsaati/config.json.
"""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "namazsaati"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "bluetooth_mac": "60:AB:D2:11:7D:7D",
    "bluetooth_name": "Bose Mini II SoundLink",
    "volume": 70,
    "prayers_enabled": {
        "fajr": False,
        "dhuhr": True,
        "asr": True,
        "maghrib": True,
        "isha": True,
    },
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            # Fehlende Felder mit Defaults auffüllen
            for key, val in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = val
            return data
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
