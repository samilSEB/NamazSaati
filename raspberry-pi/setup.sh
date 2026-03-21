#!/bin/bash
# NamazSaati Setup-Skript
# Einmalig ausführen auf dem Raspberry Pi: bash setup.sh
set -e

INSTALL_DIR="$HOME/NamazSaati/raspberry-pi"
SERVICE_NAME="namazsaati"

echo "=== NamazSaati Setup ==="
echo ""

# 1. Abhängigkeiten installieren
echo "[1/5] Pakete installieren..."
sudo apt-get update -qq
sudo apt-get install -y -qq mpg123 python3-pip python3-flask git

echo "[2/5] Python-Abhängigkeiten installieren..."
pip3 install flask --break-system-packages --quiet

# 3. Audio-Verzeichnis erstellen
echo "[3/5] Verzeichnisse erstellen..."
mkdir -p "$INSTALL_DIR/audio"

# 4. systemd-Service installieren
echo "[4/5] Systemd-Service einrichten..."
sudo cp "$INSTALL_DIR/namazsaati.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# 5. Ezan-Datei prüfen
echo "[5/5] Prüfe Ezan-Datei..."
if [ ! -f "$INSTALL_DIR/audio/ezan.mp3" ]; then
    echo ""
    echo "  WICHTIG: Ezan-Datei fehlt!"
    echo "  Bitte ezan.mp3 in dieses Verzeichnis kopieren:"
    echo "  $INSTALL_DIR/audio/ezan.mp3"
    echo ""
    echo "  Von einem anderen Computer:"
    echo "  scp ezan.mp3 pi@namazsaati.local:$INSTALL_DIR/audio/"
    echo ""
else
    echo "  Ezan-Datei gefunden."
fi

echo ""
echo "=== Setup abgeschlossen! ==="
echo ""
echo "Nächste Schritte:"
echo ""
echo "1. Bluetooth-Lautsprecher koppeln:"
echo "   bluetoothctl"
echo "   > scan on"
echo "   > pair XX:XX:XX:XX:XX:XX"
echo "   > connect XX:XX:XX:XX:XX:XX"
echo "   > trust XX:XX:XX:XX:XX:XX"
echo ""
echo "2. Service starten:"
echo "   sudo systemctl start namazsaati"
echo ""
echo "3. Im Browser öffnen:"
echo "   http://namazsaati.local:5000"
echo ""
echo "4. Ezan testen:"
echo "   cd $INSTALL_DIR && python3 namazsaati.py --test"
echo ""
echo "Der Service startet automatisch nach jedem Neustart und"
echo "Stromausfall — keine erneute Einrichtung nötig."
