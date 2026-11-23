## 1. Systemvoraussetzungen

- **Betriebssystem**: Linux Ubunto 22.04
- **Python**: Version 3.10
- **Webcam**: Standard-USB-Webcam (UGREEN)
- **DVS-Kamera**: Prophesee DVS-Kamera

## 2. Installation der Abhängigkeiten

### 2.1 Python-Pakete

Installieren Sie die erforderlichen Python-Pakete mit pip:

```bash
pip install PyQt5 opencv-python numpy pyaudio
```

### 2.2 Metavision SDK Installation (für DVS-Kamera-Unterstützung)

Besuchen Sie die [offizielle Prophesee-Dokumentation](https://docs.prophesee.ai/stable/installation/index.html) für detaillierte Installationsanweisungen.

## 3. Anwendung installieren

### 3.1 Repository klonen oder Dateien kopieren

Kopieren Sie alle Dateien in ein Verzeichnis Ihrer Wahl oder klonen Sie das Repository (falls verfügbar).

## 4. Anwendung starten

Führen Sie die Anwendung mit Python aus:

```bash
python main.py
```

## 5. Fehlerbehebung

### 5.1 Wenn keine Kameras gefunden werden:

- Stellen Sie sicher, dass Ihre Webcam angeschlossen und vom System erkannt wird
- Überprüfen Sie die Berechtigungen für Kamerazugriff
- Für Linux: Fügen Sie Ihren Benutzer zur `video`-Gruppe hinzu: `sudo usermod -a -G video $USER`

### 5.2 Wenn die DVS-Kamera nicht erkannt wird:

- Überprüfen Sie, ob die Metavision SDK korrekt installiert ist
- Stellen Sie sicher, dass die DVS-Kamera angeschlossen und eingeschaltet ist
- Überprüfen Sie die USB-Verbindung (USB 3.0 empfohlen)
- Testen Sie die Kamera mit den Metavision-Beispielprogrammen

### 5.3 Audio-Probleme:

- Stellen Sie sicher, dass PyAudio korrekt installiert ist
- Überprüfen Sie die Audiogeräte-Einstellungen Ihres Systems
- Für Linux: Installieren Sie zusätzlich `sudo apt-get install portaudio19-dev python-pyaudio`