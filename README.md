# NamazSaati — Gebetserinnerung

Automatischer Gebetswecker für Ludwigsburg (Diyanet-Methode).
Läuft auf einem Raspberry Pi Zero 2W — kein Löten, einfach einstecken.

## Was es macht

- Spielt den Ezan automatisch zu jeder der 5 täglichen Gebetszeiten
- Zeigt alle Gebetszeiten + Countdown im Browser an (`http://namazsaati.local:5000`)
- Läuft für immer — startet automatisch beim Einschalten

## Hardware (kein Löten, ~45€)

| Bauteil | Preis |
|---------|-------|
| Raspberry Pi Zero 2W | ~20€ |
| 16GB MicroSD | ~5€ |
| Micro-USB Netzteil (5V 2.5A) | ~5€ |
| Bluetooth-Lautsprecher | ~15€ |

Details: [raspberry-pi/docs/HARDWARE.md](raspberry-pi/docs/HARDWARE.md)

## Schnellstart

```bash
git clone https://github.com/samilSEB/NamazSaati
cd NamazSaati/raspberry-pi
bash setup.sh
```

Vollständige Anleitung: [raspberry-pi/docs/SETUP.md](raspberry-pi/docs/SETUP.md)

## Gebetszeiten

- Standort: Ludwigsburg (48.8975°N, 9.1925°E)
- Methode: Diyanet (Fajr 18°, Isha 17°, Asr Shafi)
- Sommerzeit (DST) wird automatisch berücksichtigt

## Tests

```bash
cd raspberry-pi
pip install pytest flask
pytest tests/ -v
```
