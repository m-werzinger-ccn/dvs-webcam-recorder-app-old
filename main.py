#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Haupteinstiegspunkt für die Webcam-Aufnahme-Anwendung.
"""

import sys
import os
import time
from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

# Erst die grundlegenden Module importieren
import config
from utils import (
    create_desktop_shortcut,
    get_available_cameras,
    check_available_codecs,
    get_best_codec,
)

# Besten Codec ermitteln und Konfiguration aktualisieren
try:
    best_codec, ext = get_best_codec()
    # Wenn Codec-Erkennung erfolgreich war, Konfiguration aktualisieren
    config.DEFAULT_VIDEO_CODEC = best_codec
    config.DEFAULT_VIDEO_EXTENSION = ext
    print(f"Verwende Codec: {best_codec} mit Erweiterung {ext}")
except Exception as e:
    print(f"Fehler bei der Codec-Erkennung: {e}")
    print(
        f"Verwende Standard-Codec: {config.DEFAULT_VIDEO_CODEC} mit Erweiterung {config.DEFAULT_VIDEO_EXTENSION}"
    )

# UI-Komponenten importieren
from ui import MainWindow


def main():
    # Anwendung starten
    app = QApplication(sys.argv)

    # Splash-Screen erstellen (optional)
    splash_pixmap = QPixmap(500, 300)
    splash_pixmap.fill(Qt.white)
    splash = QSplashScreen(splash_pixmap)
    splash.showMessage(
        "Webcam Recorder wird gestartet...\nKameras werden gesucht...",
        Qt.AlignCenter,
        Qt.darkBlue,
    )
    splash.show()
    app.processEvents()

    # Desktop-Verknüpfung erstellen
    try:
        create_desktop_shortcut()
    except Exception as e:
        print(f"Fehler beim Erstellen der Desktop-Verknüpfung: {e}")

    # Prüfen, ob es sich um ein Qt-Wayland-Problem handelt und eine Warnung anzeigen
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        print(
            "Hinweis: Bei Problemen unter Wayland, versuchen Sie den folgenden Befehl:"
        )
        print("QT_QPA_PLATFORM=wayland python3 main.py")

    # Kurze Verzögerung für den Splash-Screen
    time.sleep(1)

    # Hauptfenster anzeigen
    window = MainWindow()
    window.show()

    # Splash-Screen ausblenden
    splash.finish(window)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
