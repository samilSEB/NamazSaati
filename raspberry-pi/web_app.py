#!/usr/bin/env python3
"""
NamazSaati - Web-Interface

3 Tabs: Zeiten / Einstellungen / Bluetooth
Erreichbar unter http://namazsaati.local:5000
"""

import subprocess
import threading
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template_string, request

from prayer_calculator import get_prayer_times, get_next_prayer, PRAYER_NAMES
from config import load_config, save_config

app = Flask(__name__)
TIMEZONE = ZoneInfo("Europe/Berlin")
AUDIO_DIR = Path(__file__).parent / "audio"

PRAYER_DISPLAY = {
    "fajr": "Fajr",
    "dhuhr": "Dhuhr",
    "asr": "Asr",
    "maghrib": "Maghrib",
    "isha": "Isha",
}

# Bluetooth-Scan läuft im Hintergrund
_bt_scan_lock = threading.Lock()
_bt_devices: list[dict] = []
_bt_scanning = False


HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NamazSaati</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#1a1a2e;color:#e0e0e0;min-height:100vh;display:flex;align-items:flex-start;justify-content:center;padding:20px}
.card{background:#16213e;border-radius:16px;padding:28px 32px;max-width:420px;width:100%;box-shadow:0 8px 32px rgba(0,0,0,.4)}
.header{text-align:center;margin-bottom:20px;border-bottom:1px solid #0f3460;padding-bottom:16px}
.header h1{font-size:1.6rem;color:#e2b96f;letter-spacing:2px}
.header .date{font-size:.85rem;color:#8899aa;margin-top:4px}
.tabs{display:flex;gap:8px;margin-bottom:20px}
.tab{flex:1;padding:8px;background:#0f3460;border:none;border-radius:8px;color:#8899aa;cursor:pointer;font-size:.85rem;transition:all .2s}
.tab.active{background:#e2b96f;color:#1a1a2e;font-weight:700}
.panel{display:none}
.panel.active{display:block}

/* Zeiten */
.prayers{list-style:none}
.prayers li{display:flex;justify-content:space-between;align-items:center;padding:12px 8px;border-radius:8px;margin-bottom:4px}
.prayers li.done{opacity:.45}
.prayers li.next{background:#0f3460;border:1px solid #e2b96f}
.prayer-name{font-weight:600}
.prayer-time{font-variant-numeric:tabular-nums}
.badge{font-size:.7rem;background:#e2b96f;color:#1a1a2e;padding:2px 8px;border-radius:99px;font-weight:700;text-transform:uppercase}
.next-info{text-align:center;margin-top:20px;padding-top:16px;border-top:1px solid #0f3460;font-size:.9rem;color:#8899aa}
.next-info strong{color:#e2b96f}
.check{color:#4caf50;margin-right:4px}
.arrow{color:#e2b96f;margin-right:4px}
#countdown{font-size:1.1rem;font-weight:700;color:#e2b96f}

/* Einstellungen */
.setting-row{display:flex;justify-content:space-between;align-items:center;padding:12px 8px;border-radius:8px;margin-bottom:4px}
.setting-row:hover{background:#0f3460}
.toggle{position:relative;width:44px;height:24px;cursor:pointer}
.toggle input{opacity:0;width:0;height:0}
.slider-toggle{position:absolute;inset:0;background:#333;border-radius:24px;transition:.3s}
.slider-toggle:before{content:"";position:absolute;width:18px;height:18px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.3s}
input:checked+.slider-toggle{background:#e2b96f}
input:checked+.slider-toggle:before{transform:translateX(20px)}
.volume-row{padding:12px 8px;margin-top:12px}
.volume-row label{display:block;margin-bottom:8px;font-size:.9rem;color:#8899aa}
input[type=range]{width:100%;accent-color:#e2b96f}
.vol-val{color:#e2b96f;font-weight:700}

/* Buttons */
.btn{width:100%;padding:12px;border:none;border-radius:8px;font-size:.95rem;cursor:pointer;margin-top:8px;font-weight:600;transition:all .2s}
.btn-gold{background:#e2b96f;color:#1a1a2e}
.btn-gold:hover{background:#f0cc88}
.btn-outline{background:transparent;color:#e2b96f;border:1px solid #e2b96f}
.btn-outline:hover{background:#e2b96f22}
.btn-danger{background:#c0392b;color:#fff}
.btn-danger:hover{background:#e74c3c}
.btn:disabled{opacity:.5;cursor:not-allowed}

/* Bluetooth */
.bt-status{display:flex;align-items:center;gap:8px;padding:12px 8px;background:#0f3460;border-radius:8px;margin-bottom:16px}
.bt-dot{width:10px;height:10px;border-radius:50%;background:#555}
.bt-dot.connected{background:#4caf50}
.bt-dot.scanning{background:#e2b96f;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.bt-list{list-style:none;margin-top:12px}
.bt-list li{display:flex;justify-content:space-between;align-items:center;padding:10px 8px;border-radius:8px;margin-bottom:4px;background:#0f3460}
.bt-list li .name{font-size:.9rem}
.bt-list li .mac{font-size:.75rem;color:#8899aa}
.btn-sm{padding:6px 14px;font-size:.8rem;border:none;border-radius:6px;cursor:pointer;background:#e2b96f;color:#1a1a2e;font-weight:700}

/* Upload */
.upload-area{border:2px dashed #0f3460;border-radius:8px;padding:20px;text-align:center;margin-top:12px;color:#8899aa;font-size:.85rem}
.upload-area input[type=file]{display:none}
.upload-area label{cursor:pointer;color:#e2b96f;text-decoration:underline}

.msg{margin-top:10px;padding:8px 12px;border-radius:6px;font-size:.85rem;display:none}
.msg.ok{background:#1b4332;color:#4caf50;display:block}
.msg.err{background:#4a1010;color:#e57373;display:block}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>NamazSaati</h1>
    <div class="date" id="hdr-date">Lädt...</div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="showTab('zeiten')">Zeiten</button>
    <button class="tab" onclick="showTab('einstellungen')">Einstellungen</button>
    <button class="tab" onclick="showTab('bluetooth')">Bluetooth</button>
  </div>

  <!-- TAB: ZEITEN -->
  <div class="panel active" id="tab-zeiten">
    <ul class="prayers" id="prayer-list"></ul>
    <div class="next-info">
      Nächstes: <strong id="next-name">–</strong> in <span id="countdown">–</span>
    </div>
  </div>

  <!-- TAB: EINSTELLUNGEN -->
  <div class="panel" id="tab-einstellungen">
    <div id="prayer-toggles"></div>
    <div class="volume-row">
      <label>Lautstärke: <span class="vol-val" id="vol-val">70</span>%</label>
      <input type="range" min="0" max="100" value="70" id="vol-slider" oninput="document.getElementById('vol-val').textContent=this.value">
    </div>
    <button class="btn btn-gold" onclick="saveSettings()">Speichern</button>
    <button class="btn btn-outline" style="margin-top:8px" onclick="testEzan()">▶ Ezan jetzt abspielen</button>
    <button class="btn btn-danger" style="margin-top:8px" onclick="stopEzan()">■ Ezan stoppen</button>
    <div class="upload-area">
      <p>Ezan-Datei hochladen</p>
      <input type="file" id="audio-file" accept=".mp3,.wav,.ogg" onchange="uploadAudio(this)">
      <label for="audio-file">Datei auswählen (MP3)</label>
    </div>
    <div class="msg" id="settings-msg"></div>
  </div>

  <!-- TAB: BLUETOOTH -->
  <div class="panel" id="tab-bluetooth">
    <div class="bt-status">
      <div class="bt-dot" id="bt-dot"></div>
      <span id="bt-label">Prüfe Verbindung...</span>
    </div>
    <button class="btn btn-gold" onclick="startScan()" id="scan-btn">Geräte suchen</button>
    <button class="btn btn-danger" style="display:none" id="disc-btn" onclick="disconnectBt()">Verbindung trennen</button>
    <ul class="bt-list" id="bt-list"></ul>
    <div class="msg" id="bt-msg"></div>
  </div>
</div>

<script>
let nextPrayerSecs = 0;
let nextPrayerName = '';

function showTab(id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  event.target.classList.add('active');
  if (id === 'bluetooth') loadBtStatus();
  if (id === 'einstellungen') loadSettings();
}

// ---- ZEITEN ----
async function loadTimes() {
  const r = await fetch('/api/times');
  const d = await r.json();
  const now = new Date();
  const dow = ['So','Mo','Di','Mi','Do','Fr','Sa'][now.getDay()];
  const mon = ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez'][now.getMonth()];
  document.getElementById('hdr-date').textContent = `${dow}, ${now.getDate()}. ${mon} ${now.getFullYear()} · ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

  const list = document.getElementById('prayer-list');
  list.innerHTML = '';
  for (const p of d.prayers) {
    const li = document.createElement('li');
    li.className = p.css_class;
    li.innerHTML = `
      <span class="prayer-name">
        ${p.is_done ? '<span class="check">✓</span>' : ''}
        ${p.is_next ? '<span class="arrow">→</span>' : ''}
        ${p.display_name}
      </span>
      <span class="prayer-time">${p.time_str}</span>
      ${p.is_next ? '<span class="badge">Nächstes</span>' : ''}`;
    list.appendChild(li);
  }
  document.getElementById('next-name').textContent = d.next_prayer.name_display;
  nextPrayerSecs = d.next_prayer.seconds_remaining;
  nextPrayerName = d.next_prayer.name_display;
}

function updateCountdown() {
  if (nextPrayerSecs <= 0) { loadTimes(); return; }
  nextPrayerSecs--;
  const h = Math.floor(nextPrayerSecs / 3600);
  const m = Math.floor((nextPrayerSecs % 3600) / 60);
  const s = nextPrayerSecs % 60;
  let txt = h > 0 ? `${h}h ${m}min` : m > 0 ? `${m}min ${s}s` : `${s}s`;
  document.getElementById('countdown').textContent = txt;
}

// ---- EINSTELLUNGEN ----
async function loadSettings() {
  const r = await fetch('/api/config');
  const cfg = await r.json();
  const names = {fajr:'Fajr', dhuhr:'Dhuhr', asr:'Asr', maghrib:'Maghrib', isha:'Isha'};
  const cont = document.getElementById('prayer-toggles');
  cont.innerHTML = '';
  for (const [key, label] of Object.entries(names)) {
    const checked = cfg.prayers_enabled[key] ? 'checked' : '';
    cont.innerHTML += `
      <div class="setting-row">
        <span>${label}</span>
        <label class="toggle">
          <input type="checkbox" id="tog-${key}" ${checked}>
          <span class="slider-toggle"></span>
        </label>
      </div>`;
  }
  document.getElementById('vol-slider').value = cfg.volume || 70;
  document.getElementById('vol-val').textContent = cfg.volume || 70;
}

async function saveSettings() {
  const r = await fetch('/api/config');
  const cfg = await r.json();
  for (const key of ['fajr','dhuhr','asr','maghrib','isha']) {
    cfg.prayers_enabled[key] = document.getElementById('tog-' + key).checked;
  }
  cfg.volume = parseInt(document.getElementById('vol-slider').value);
  const res = await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(cfg)});
  showMsg('settings-msg', res.ok ? 'Gespeichert.' : 'Fehler beim Speichern.', res.ok);
}

async function testEzan() {
  const res = await fetch('/api/ezan/test', {method:'POST'});
  showMsg('settings-msg', res.ok ? 'Ezan wird abgespielt...' : 'Fehler.', res.ok);
}

async function stopEzan() {
  const res = await fetch('/api/ezan/stop', {method:'POST'});
  showMsg('settings-msg', res.ok ? 'Gestoppt.' : 'Fehler.', res.ok);
}

async function uploadAudio(input) {
  if (!input.files[0]) return;
  const fd = new FormData();
  fd.append('file', input.files[0]);
  const res = await fetch('/api/audio/upload', {method:'POST', body:fd});
  showMsg('settings-msg', res.ok ? 'Datei hochgeladen.' : 'Upload fehlgeschlagen.', res.ok);
}

// ---- BLUETOOTH ----
async function loadBtStatus() {
  const r = await fetch('/api/bluetooth/status');
  const d = await r.json();
  const dot = document.getElementById('bt-dot');
  const lbl = document.getElementById('bt-label');
  const discBtn = document.getElementById('disc-btn');
  if (d.connected) {
    dot.className = 'bt-dot connected';
    lbl.textContent = `Verbunden: ${d.name || d.mac}`;
    discBtn.style.display = 'block';
  } else {
    dot.className = 'bt-dot';
    lbl.textContent = 'Nicht verbunden';
    discBtn.style.display = 'none';
  }
}

async function startScan() {
  document.getElementById('bt-dot').className = 'bt-dot scanning';
  document.getElementById('bt-label').textContent = 'Suche Geräte...';
  document.getElementById('scan-btn').disabled = true;
  document.getElementById('bt-list').innerHTML = '';
  const r = await fetch('/api/bluetooth/scan');
  const d = await r.json();
  document.getElementById('scan-btn').disabled = false;
  loadBtStatus();
  const list = document.getElementById('bt-list');
  if (!d.devices || d.devices.length === 0) {
    list.innerHTML = '<li style="color:#8899aa;padding:10px 8px">Keine Geräte gefunden.</li>';
    return;
  }
  for (const dev of d.devices) {
    const li = document.createElement('li');
    li.innerHTML = `
      <div><div class="name">${dev.name}</div><div class="mac">${dev.mac}</div></div>
      <button class="btn-sm" onclick="connectDevice('${dev.mac}','${dev.name.replace(/'/g,"\\'")}')">Verbinden</button>`;
    list.appendChild(li);
  }
}

async function connectDevice(mac, name) {
  document.getElementById('bt-label').textContent = `Verbinde mit ${name}...`;
  document.getElementById('bt-dot').className = 'bt-dot scanning';
  const res = await fetch('/api/bluetooth/connect', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({mac, name})
  });
  const d = await res.json();
  showMsg('bt-msg', d.message || (res.ok ? 'Verbunden.' : 'Fehler.'), res.ok);
  loadBtStatus();
}

async function disconnectBt() {
  await fetch('/api/bluetooth/disconnect', {method:'POST'});
  loadBtStatus();
}

// ---- UTILS ----
function showMsg(id, text, ok) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = 'msg ' + (ok ? 'ok' : 'err');
  setTimeout(() => el.className = 'msg', 4000);
}

// Init
loadTimes();
setInterval(updateCountdown, 1000);
setInterval(loadTimes, 60000);
</script>
</body>
</html>"""


def _build_times_data():
    now = datetime.now(TIMEZONE)
    times = get_prayer_times(now.year, now.month, now.day)
    current_min = now.hour * 60 + now.minute

    next_key, next_h, next_m = get_next_prayer(times, now.hour, now.minute)
    seconds_remaining = -1
    if next_h != -1:
        target_min = next_h * 60 + next_m
        seconds_remaining = (target_min - current_min) * 60 - now.second

    prayers = []
    for name in PRAYER_NAMES:
        h, m = times[name]
        prayer_min = h * 60 + m
        is_done = prayer_min < current_min and name != next_key
        is_next = name == next_key and next_h != -1
        prayers.append({
            "name": name,
            "display_name": PRAYER_DISPLAY[name],
            "time_str": f"{h:02d}:{m:02d}",
            "is_done": is_done,
            "is_next": is_next,
            "css_class": "done" if is_done else ("next" if is_next else ""),
        })

    return {
        "prayers": prayers,
        "next_prayer": {
            "name": next_key,
            "name_display": PRAYER_DISPLAY.get(next_key, "Fajr"),
            "time": f"{next_h:02d}:{next_m:02d}" if next_h != -1 else "morgen",
            "seconds_remaining": seconds_remaining,
        },
    }


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/times")
def api_times():
    return jsonify(_build_times_data())


@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(load_config())


@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.get_json(force=True)
    cfg = load_config()
    for key in ("bluetooth_mac", "bluetooth_name", "volume", "prayers_enabled"):
        if key in data:
            cfg[key] = data[key]
    save_config(cfg)
    return jsonify({"ok": True})


@app.route("/api/ezan/test", methods=["POST"])
def test_ezan():
    ezan_file = AUDIO_DIR / "ezan.mp3"
    if not ezan_file.exists():
        return jsonify({"ok": False, "error": "ezan.mp3 nicht gefunden"}), 404
    cfg = load_config()
    vol = cfg.get("volume", 70)
    try:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{vol}%"],
                       capture_output=True, timeout=5)
        subprocess.Popen(["mpg123", "-q", str(ezan_file)])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ezan/stop", methods=["POST"])
def stop_ezan():
    try:
        subprocess.run(["pkill", "-f", "mpg123"], capture_output=True, timeout=5)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/audio/upload", methods=["POST"])
def upload_audio():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Keine Datei"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"ok": False, "error": "Kein Dateiname"}), 400
    AUDIO_DIR.mkdir(exist_ok=True)
    dest = AUDIO_DIR / "ezan.mp3"
    f.save(str(dest))
    return jsonify({"ok": True})


@app.route("/api/bluetooth/status")
def bt_status():
    cfg = load_config()
    mac = cfg.get("bluetooth_mac", "")
    sink = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"
    try:
        result = subprocess.run(["pactl", "list", "short", "sinks"],
                                capture_output=True, timeout=5)
        connected = sink.encode() in result.stdout
    except Exception:
        connected = False
    return jsonify({
        "connected": connected,
        "mac": mac,
        "name": cfg.get("bluetooth_name", mac),
    })


@app.route("/api/bluetooth/scan")
def bt_scan():
    global _bt_devices, _bt_scanning
    with _bt_scan_lock:
        _bt_scanning = True
        _bt_devices = []

    try:
        # Scan starten
        subprocess.run(["bluetoothctl", "scan", "on"],
                       capture_output=True, timeout=2)
        import time
        time.sleep(8)
        subprocess.run(["bluetoothctl", "scan", "off"],
                       capture_output=True, timeout=2)

        # Geräteliste lesen
        result = subprocess.run(["bluetoothctl", "devices"],
                                capture_output=True, timeout=5, text=True)
        devices = []
        for line in result.stdout.splitlines():
            parts = line.strip().split(" ", 2)
            if len(parts) >= 3 and parts[0] == "Device":
                devices.append({"mac": parts[1], "name": parts[2]})
        with _bt_scan_lock:
            _bt_devices = devices
            _bt_scanning = False
        return jsonify({"devices": devices})
    except Exception as e:
        with _bt_scan_lock:
            _bt_scanning = False
        return jsonify({"devices": [], "error": str(e)})


@app.route("/api/bluetooth/connect", methods=["POST"])
def bt_connect():
    import time
    data = request.get_json(force=True)
    mac = data.get("mac", "")
    name = data.get("name", mac)
    if not mac:
        return jsonify({"ok": False, "message": "Keine MAC-Adresse"}), 400

    sink = "bluez_sink." + mac.replace(":", "_") + ".a2dp_sink"

    def sink_active():
        try:
            r = subprocess.run(["pactl", "list", "short", "sinks"],
                               capture_output=True, timeout=5)
            return sink.encode() in r.stdout
        except Exception:
            return False

    try:
        # Pairen falls noch nicht bekannt
        info = subprocess.run(["bluetoothctl", "info", mac],
                              capture_output=True, timeout=5, text=True)
        if "Paired: yes" not in info.stdout:
            subprocess.run(["bluetoothctl", "pair", mac],
                           capture_output=True, timeout=30)
            subprocess.run(["bluetoothctl", "trust", mac],
                           capture_output=True, timeout=5)

        # Verbinden
        subprocess.run(["bluetoothctl", "connect", mac],
                       capture_output=True, timeout=20)

        # Warte bis Sink erscheint (max 15s) — das ist der echte Erfolgsindikator
        for _ in range(8):
            time.sleep(2)
            if sink_active():
                subprocess.run(["pactl", "set-default-sink", sink],
                               capture_output=True, timeout=5)
                cfg = load_config()
                cfg["bluetooth_mac"] = mac
                cfg["bluetooth_name"] = name
                save_config(cfg)
                return jsonify({"ok": True, "message": f"Verbunden mit {name}"})

        return jsonify({"ok": False, "message": "Verbindung fehlgeschlagen — Lautsprecher einschalten?"}), 500
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/bluetooth/disconnect", methods=["POST"])
def bt_disconnect():
    cfg = load_config()
    mac = cfg.get("bluetooth_mac", "")
    try:
        subprocess.run(["bluetoothctl", "disconnect", mac],
                       capture_output=True, timeout=10)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
