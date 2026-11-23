#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DVS-Kamera-Recorder für die Webcam-Aufnahme-Anwendung.
Verwendet Metavision SDK zur Aufnahme von Ereignissen einer DVS-Kamera.
Direkt basierend auf den Beispielen des Herstellers.
"""

import os
import cv2
import time
import threading
import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QMessageBox, QApplication

# Metavision SDK Imports
try:
    from metavision_core.event_io import EventsIterator
    from metavision_core.event_io.raw_reader import initiate_device
    from metavision_sdk_core import PeriodicFrameGenerationAlgorithm, ColorPalette

    HAS_METAVISION = True
except ImportError:
    print(
        "Warnung: Metavision SDK nicht gefunden. DVS-Kamera-Funktionalität deaktiviert."
    )
    HAS_METAVISION = False


class DVSRecorder(QThread):
    """Thread für die DVS-Kamera-Aufnahme mit Metavision SDK"""

    update_frame = pyqtSignal(QImage)
    error_signal = pyqtSignal(str)

    def __init__(self, save_dir="", file_name=""):
        super().__init__()
        self.save_dir = save_dir
        self.file_name = file_name
        self.running = False
        self.recording = False

        # Für Thread-Sicherheit
        self.mutex = threading.Lock()

        # Metavision-spezifische Attribute
        self.device = None
        self.mv_iterator = None
        self.event_frame_gen = None
        self.width = 640  # Standardwerte
        self.height = 480  # Standardwerte
        self.fps = 25

        # Dummy-Frame für den Fall, dass keine Kamera verfügbar ist
        self.dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(
            self.dummy_frame,
            "Keine DVS-Kamera verfügbar",
            (100, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )

        # Prüfen, ob Metavision verfügbar ist
        if not HAS_METAVISION:
            self.error_signal.emit(
                "Metavision SDK nicht installiert. DVS-Kamera nicht verfügbar."
            )

    def run(self):
        """Hauptschleife für die DVS-Kamera-Aufnahme"""
        try:
            # Thread als laufend markieren
            self.running = True

            if not HAS_METAVISION:
                # Wenn Metavision nicht verfügbar ist, nur Dummy-Frames senden
                while self.running:
                    self._send_dummy_frame()
                    time.sleep(0.04)  # ca. 25 FPS
                return

            # DVS-Kamera öffnen - DIREKTE IMPLEMENTIERUNG WIE IM BEISPIELCODE
            try:
                # Direkte Initialisierung des Geräts - wie im Recorder-Beispiel
                self.device = initiate_device("")
                if not self.device:
                    raise Exception("Konnte kein DVS-Gerät initialisieren")

                # Events iterator vom Gerät erstellen
                self.mv_iterator = EventsIterator.from_device(device=self.device)
                if not self.mv_iterator:
                    raise Exception("Konnte keinen EventsIterator vom Gerät erstellen")

                # Kamera-Geometrie auslesen
                self.height, self.width = self.mv_iterator.get_size()

                print(
                    f"DVS-Kamera erfolgreich geöffnet mit Auflösung {self.width}x{self.height}"
                )

                # Event Frame Generator - Exakt wie im Beispielcode
                self.event_frame_gen = PeriodicFrameGenerationAlgorithm(
                    sensor_width=self.width,
                    sensor_height=self.height,
                    fps=self.fps,
                    palette=ColorPalette.Dark,
                )

                # Callback für neue Frames setzen - Exakt wie im Beispielcode
                self.event_frame_gen.set_output_callback(self._on_cd_frame_cb)

                # Aufnahmeschleife - Exakt wie im Beispielcode
                for evs in self.mv_iterator:
                    if not self.running:
                        break

                    # Ereignisse verarbeiten - Wichtig: Keine Mutex-Sperre hier
                    self.event_frame_gen.process_events(evs)

                    # Kurze Pause für UI-Updates
                    QApplication.processEvents()

            except Exception as e:
                self.error_signal.emit(
                    f"Fehler bei der DVS-Kamera-Initialisierung: {e}"
                )
                print(f"Fehler bei der DVS-Kamera-Initialisierung: {e}")
                import traceback

                traceback.print_exc()

                # Bei Fehler nur Dummy-Frames senden
                while self.running:
                    self._send_dummy_frame()
                    time.sleep(0.04)  # ca. 25 FPS

        except Exception as e:
            self.error_signal.emit(f"Kritischer Fehler bei der DVS-Kameraaufnahme: {e}")
            print(f"Kritischer Fehler bei der DVS-Kameraaufnahme: {e}")
            import traceback

            traceback.print_exc()

        finally:
            # Ressourcen aufräumen
            self._cleanup_resources()

    def _on_cd_frame_cb(self, ts, cd_frame):
        """Callback für neue Frames vom Event-Generator - Exakt wie im Beispielcode"""
        try:
            # Wenn das Thread nicht mehr läuft, abbrechen
            if not self.running:
                return

            # DEBUG Ausgabe
            print(f"DVS-Frame erhalten: Größe={cd_frame.shape}, Typ={cd_frame.dtype}")

            # Frame für die GUI konvertieren (BGR zu RGB)
            rgb_frame = cv2.cvtColor(cd_frame, cv2.COLOR_BGR2RGB)

            # QImage erstellen
            h, w = rgb_frame.shape[:2]
            bytes_per_line = 3 * w

            # Sicherstellen, dass die Daten kontinuierlich im Speicher liegen
            if not rgb_frame.flags["C_CONTIGUOUS"]:
                rgb_frame = np.ascontiguousarray(rgb_frame)

            # Deep copy erstellen für thread-sichere Übergabe
            qt_image = QImage(
                rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888
            ).copy()

            # Signal mit dem aktuellen Frame senden
            print("DVS-Frame wird an GUI gesendet")
            self.update_frame.emit(qt_image)

        except Exception as e:
            print(f"Fehler bei der Frame-Konvertierung: {e}")
            import traceback

            traceback.print_exc()
            self._send_dummy_frame()

    def _send_dummy_frame(self):
        """Sendet ein Dummy-Frame, wenn keine echten Daten verfügbar sind"""
        try:
            # Kopie des Dummy-Frames erstellen und ggf. Aufnahmestatus hinzufügen
            frame = self.dummy_frame.copy()

            if self.recording:
                cv2.putText(
                    frame,
                    "● REC",
                    (550, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2,
                )

            # Frame für die GUI konvertieren
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb_frame.shape[:2]
            bytes_per_line = 3 * w
            qt_image = QImage(
                rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888
            ).copy()

            # Signal mit dem aktuellen Frame senden
            self.update_frame.emit(qt_image)

        except Exception as e:
            print(f"Fehler beim Senden des Dummy-Frames: {e}")

    def start_recording(self, save_dir=None, file_name=None):
        """Startet die DVS-Kamera-Aufnahme"""
        if not self.running or self.recording:
            return False

        # Verwende die übergebenen Werte oder behalte die vorhandenen bei
        if save_dir:
            self.save_dir = save_dir
        if file_name:
            self.file_name = file_name

        if not self.save_dir or not self.file_name:
            self.error_signal.emit(
                "Kein Speicherort oder Dateiname für DVS-Aufnahme angegeben!"
            )
            return False

        # Wenn Metavision nicht verfügbar ist, abbrechen
        if not HAS_METAVISION:
            self.error_signal.emit(
                "Metavision SDK nicht installiert. DVS-Aufnahme nicht möglich."
            )
            return False

        try:
            # Prüfen, ob die DVS-Kamera verfügbar ist
            if not self.device or not self.device.get_i_events_stream():
                self.error_signal.emit("Keine DVS-Kamera verfügbar für die Aufnahme!")
                return False

            # Sicherstellen, dass der Speicherordner existiert
            os.makedirs(self.save_dir, exist_ok=True)

            # RAW-Datei für die Aufnahme vorbereiten - GENAU WIE IM BEISPIELCODE
            raw_file_path = os.path.join(self.save_dir, f"{self.file_name}.raw")

            # Aufnahme starten - GENAU WIE IM BEISPIELCODE
            print(f"Starte DVS-Aufnahme nach {raw_file_path}")
            self.device.get_i_events_stream().log_raw_data(raw_file_path)
            self.recording = True
            return True

        except Exception as e:
            self.error_signal.emit(f"Fehler beim Starten der DVS-Aufnahme: {e}")
            print(f"Fehler beim Starten der DVS-Aufnahme: {e}")
            import traceback

            traceback.print_exc()
            return False

    def stop_recording(self):
        """Stoppt die laufende DVS-Aufnahme"""
        try:
            if self.recording and self.device and self.device.get_i_events_stream():
                # Aufnahme stoppen - GENAU WIE IM BEISPIELCODE
                print("Stoppe DVS-Aufnahme")
                self.device.get_i_events_stream().stop_log_raw_data()
                self.recording = False
                return True
        except Exception as e:
            self.error_signal.emit(f"Fehler beim Stoppen der DVS-Aufnahme: {e}")
            print(f"Fehler beim Stoppen der DVS-Aufnahme: {e}")
            import traceback

            traceback.print_exc()

        # Status zurücksetzen, auch wenn ein Fehler aufgetreten ist
        self.recording = False
        return False

    def _cleanup_resources(self):
        """Gibt alle Ressourcen frei"""
        try:
            # Aufnahme stoppen, falls sie läuft
            if self.recording and self.device and self.device.get_i_events_stream():
                try:
                    self.device.get_i_events_stream().stop_log_raw_data()
                except:
                    pass
                self.recording = False

            # Metavision-Ressourcen freigeben
            self.event_frame_gen = None
            self.mv_iterator = None
            self.device = None

        except Exception as e:
            print(f"Fehler beim Freigeben der DVS-Ressourcen: {e}")

    def stop(self):
        """Stoppt den Thread und gibt Ressourcen frei"""
        self.running = False

        # Aufräumen
        self._cleanup_resources()

        # Auf Thread-Ende warten
        self.wait()
