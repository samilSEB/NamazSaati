# Hardware-Einkaufsliste

**Gesamtkosten: ~45€ — kein Löten, keine Elektronikkenntnisse nötig.**

---

## Was du brauchst

| # | Bauteil | Detail | ~Preis | Wo kaufen |
|---|---------|--------|--------|-----------|
| 1 | **Raspberry Pi Zero 2W** | Mit vorgelöteten Headern | ~20€ | [pi-shop.de](https://pi-shop.de) · [Amazon](https://amazon.de) |
| 2 | **MicroSD-Karte** | 16GB, Class 10 | ~5€ | Amazon |
| 3 | **Micro-USB Netzteil** | 5V, 2.5A | ~5€ | Amazon |
| 4 | **Bluetooth-Lautsprecher** | Beliebig — z.B. JBL Clip, Anker | ~15€ | Amazon · Mediamarkt |

**Schon vorhanden:**
- PC oder Mac (zum Einrichten, einmalig)
- WLAN-Router zuhause

---

## Wichtig beim Kauf des Raspberry Pi

Achte beim Kauf auf:
- **Raspberry Pi Zero 2W** (nicht Zero 1 oder Zero W ohne 2)
- **"with headers"** oder **"mit vorgelöteten Headern"** — dann sind die Pins bereits dran

---

## Aufbau (keine Elektronikkenntnisse nötig)

```
Bluetooth-Lautsprecher  ←(Bluetooth)←  Raspberry Pi Zero 2W
                                               ↑
                                        Micro-USB-Kabel
                                               ↑
                                        USB-Netzteil
                                               ↑
                                          Steckdose
```

**Das war's.** Keine Kabel löten, keine Elektronik zusammenbauen.
Der Raspberry Pi ist ein kleiner Computer — einfach einschalten und er läuft.

---

## Lautsprecher-Verbindung

Du hast zwei Möglichkeiten:

### Option A: Bluetooth (empfohlen)
Einmalig koppeln (5 Minuten), danach verbindet sich der Lautsprecher
automatisch. Kein Kabel nötig.

### Option B: USB-Lautsprecher
Einen USB-Lautsprecher per Micro-USB-OTG-Adapter anschließen.
Benötigt: "Micro-USB OTG Adapter" (~2€) + USB-Lautsprecher.

---

## Fertig

Sobald alles eingesteckt ist: [SETUP.md](SETUP.md) befolgen.
Der einzige "Aufwand": SD-Karte bespielen und einmalig einrichten (~30 Minuten).
