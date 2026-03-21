# Setup-Anleitung

Schritt-für-Schritt Einrichtung von NamazSaati auf dem Raspberry Pi.
Dauer: **ca. 30 Minuten**, einmalig.

Nach der Einrichtung läuft das Gerät vollautomatisch — auch nach
einem Stromausfall startet es von selbst neu und spielt pünktlich.

---

## Was du brauchst

- Raspberry Pi Zero 2W + MicroSD-Karte + Netzteil (siehe [HARDWARE.md](HARDWARE.md))
- Einen PC oder Mac
- WLAN-Name und WLAN-Passwort
- Eine Ezan-MP3-Datei (z.B. von YouTube herunterladen, max. 10 Minuten)

---

## Schritt 1: Raspberry Pi OS auf SD-Karte installieren

1. **Raspberry Pi Imager** herunterladen und installieren:
   - Windows/Mac: [raspberrypi.com/software](https://www.raspberrypi.com/software/)

2. SD-Karte in den PC/Mac stecken (MicroSD + Adapter)

3. Imager öffnen:
   - "Raspberry Pi Zero 2W" auswählen
   - "Raspberry Pi OS Lite (64-bit)" auswählen
   - Deine SD-Karte auswählen
   - Rechts oben auf das **Zahnrad ⚙️** klicken (Erweiterte Einstellungen)

4. Im Einstellungsfenster:
   - ✅ **SSH aktivieren** (Passwort-Authentifizierung)
   - ✅ **WLAN konfigurieren** → WLAN-Name und Passwort eingeben
   - ✅ **Benutzername** `pi`, Passwort nach Wahl
   - ✅ **Hostname** auf `namazsaati` setzen
   - **Speichern** → **Schreiben**

5. Warten bis Schreiben fertig (ca. 3 Minuten)

---

## Schritt 2: Raspberry Pi starten

1. SD-Karte aus dem PC/Mac herausnehmen
2. In den Raspberry Pi stecken (kleiner Schlitz auf der Platine)
3. USB-Netzteil einstecken → Raspberry Pi startet automatisch
4. **2 Minuten warten** (erster Boot dauert etwas länger)

---

## Schritt 3: Per SSH verbinden

Auf dem PC/Mac ein Terminal öffnen:

```bash
ssh pi@namazsaati.local
```

Beim ersten Mal: Sicherheitsfrage mit `yes` bestätigen, dann Passwort eingeben.

> **Windows:** Terminal-App oder PowerShell verwenden.
> Falls `namazsaati.local` nicht funktioniert: Router-Oberfläche öffnen und
> IP-Adresse des Raspberry Pi herausfinden, dann `ssh pi@192.168.x.x` verwenden.

---

## Schritt 4: Software einrichten

```bash
# Repository klonen
git clone https://github.com/samilSEB/NamazSaati
cd NamazSaati/raspberry-pi

# Setup-Skript ausführen (installiert alles automatisch)
bash setup.sh
```

Das Skript:
- Installiert alle benötigten Programme (`mpg123`, `flask`)
- Richtet den automatischen Start beim Booten ein
- Zeigt am Ende weitere Schritte an

---

## Schritt 5: Ezan-Datei hochladen

Die Ezan-MP3-Datei vom PC/Mac auf den Raspberry Pi kopieren.
**In einem neuen Terminal-Fenster** auf dem PC/Mac:

```bash
scp /pfad/zu/ezan.mp3 pi@namazsaati.local:~/NamazSaati/raspberry-pi/audio/
```

Beispiel (Windows, Datei auf Desktop):
```
scp C:\Users\Dein-Name\Desktop\ezan.mp3 pi@namazsaati.local:~/NamazSaati/raspberry-pi/audio/
```

> Die Datei muss `ezan.mp3` heißen.
> Unterstützte Formate: MP3. Empfohlene Länge: 3–7 Minuten.

---

## Schritt 6: Bluetooth-Lautsprecher koppeln

Im SSH-Fenster (Raspberry Pi):

```bash
bluetoothctl
```

Dann diese Befehle nacheinander eingeben:
```
scan on
```
Warten bis dein Lautsprecher erscheint (z.B. `JBL Clip 4`), dann die
angezeigte Adresse (Format `XX:XX:XX:XX:XX:XX`) notieren.

```
pair XX:XX:XX:XX:XX:XX
connect XX:XX:XX:XX:XX:XX
trust XX:XX:XX:XX:XX:XX
exit
```

> **Bluetooth-Lautsprecher einschalten**, bevor du `scan on` eingibst.

---

## Schritt 7: Testen

```bash
# Ezan sofort abspielen (Test)
cd ~/NamazSaati/raspberry-pi
python3 namazsaati.py --test
```

Du solltest jetzt den Ezan über den Lautsprecher hören.

```bash
# Service starten
sudo systemctl start namazsaati

# Status prüfen
sudo systemctl status namazsaati
```

Im Browser öffnen: **http://namazsaati.local:5000**

---

## Fertig!

Der Raspberry Pi spielt ab jetzt automatisch den Ezan zur richtigen Zeit.
**Keine weitere Einrichtung nötig** — auch nach Stromausfall oder Neustart.

---

## Häufige Fragen

**Was passiert bei einem Stromausfall?**
Der Raspberry Pi startet automatisch neu und NamazSaati läuft direkt weiter.
Keine Einstellungen gehen verloren.

**Gebetszeiten falsch?**
Die Zeiten werden täglich neu nach Diyanet-Methode für Ludwigsburg berechnet.
Sommer- und Winterzeit werden automatisch berücksichtigt.

**Wie laut ist der Ezan?**
Die Lautstärke hängt vom Bluetooth-Lautsprecher ab. Einfach am
Lautsprecher selbst einstellen.

**Kann ich die Ezan-Datei wechseln?**
Ja — einfach die neue Datei als `ezan.mp3` in `audio/` kopieren.
Service neu starten: `sudo systemctl restart namazsaati`

**Log-Ausgabe ansehen:**
```bash
journalctl -u namazsaati -f
```
