#!/bin/bash
# NamazSaati - Audio-Konvertierung
# Konvertiert Ezan-Aufnahmen in das optimale Format für ESP32
# Benötigt: ffmpeg
#
# Verwendung:
#   ./convert_audio.sh input_ezan.mp3 output_ezan.mp3
#   ./convert_audio.sh input_fajr.mp3 ../data/ezan_fajr.mp3

set -e

if [ $# -lt 2 ]; then
    echo "Verwendung: $0 <input> <output>"
    echo "Beispiel:   $0 ezan_original.mp3 ../data/ezan.mp3"
    exit 1
fi

INPUT="$1"
OUTPUT="$2"

if [ ! -f "$INPUT" ]; then
    echo "Fehler: Eingabedatei '$INPUT' nicht gefunden!"
    exit 1
fi

echo "Konvertiere: $INPUT -> $OUTPUT"
echo "Format: MP3, 22050Hz, Mono, 64kbps"

ffmpeg -y -i "$INPUT" \
    -ar 22050 \
    -ac 1 \
    -b:a 64k \
    -map_metadata -1 \
    "$OUTPUT"

# Dateigröße anzeigen
SIZE=$(stat -f%z "$OUTPUT" 2>/dev/null || stat -c%s "$OUTPUT" 2>/dev/null)
SIZE_KB=$((SIZE / 1024))
echo "Fertig! Dateigröße: ${SIZE_KB} KB"

# Warnung wenn zu groß für Flash
if [ "$SIZE_KB" -gt 2000 ]; then
    echo "WARNUNG: Datei > 2MB - könnte nicht in Flash passen!"
    echo "Tipp: Verwende niedrigere Bitrate (32kbps) oder kürze die Aufnahme"
fi
