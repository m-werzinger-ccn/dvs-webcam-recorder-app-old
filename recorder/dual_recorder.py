#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DualRecorder-Klasse für die gleichzeitige Aufnahme von Webcam und DVS-Kamera.
Mit Signalweiterleitung für Verarbeitungsstatus.
"""

import os
import time
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

from recorder import VideoRecorder, DVSRecorder


class DualRecorder(QObject):
    """Klasse zur Verwaltung und Steuerung beider Kameratypen"""

    error_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    processing_status = pyqtSignal(str)  # Signal für Verarbeitungsstatus
    video_processing_completed = (
        pyqtSignal()
    )  # Signal für abgeschlossene Video-Verarbeitung

    def __init__(self, webcam_id=0, save_dir="", file_name="", audio_enabled=True):
        super().__init__()
        self.webcam_id = webcam_id
        self.save_dir = save_dir
        self.file_name = file_name
        self.recording = False
        self.audio_enabled = audio_enabled

        # Recorder-Instanzen
        self.webcam_recorder = None
        self.dvs_recorder = None

        # Status-Flags
        self.webcam_available = False
        self.dvs_available = False

    def initialize(self):
        """Initialisiert beide Recorder"""
        try:
            print("DualRecorder: Initialisiere Recorder...")

            # Webcam-Recorder initialisieren
            try:
                self.webcam_recorder = VideoRecorder(
                    camera_id=self.webcam_id,
                    save_dir=self.save_dir,
                    file_name=self.file_name,
                    audio_enabled=self.audio_enabled,
                )
                self.webcam_recorder.error_signal.connect(self._on_webcam_error)
                # Signale für Verarbeitungsstatus weiterleiten
                self.webcam_recorder.processing_status.connect(
                    self.processing_status.emit
                )
                self.webcam_recorder.video_processing_completed.connect(
                    self.video_processing_completed.emit
                )
                self.webcam_recorder.start()
                self.webcam_available = True
                print("DualRecorder: Webcam-Recorder erfolgreich initialisiert")
            except Exception as e:
                print(
                    f"DualRecorder: Fehler bei der Initialisierung des Webcam-Recorders: {e}"
                )
                self.error_signal.emit(f"Webcam-Fehler: {e}")
                self.webcam_available = False

            # DVS-Recorder initialisieren
            try:
                self.dvs_recorder = DVSRecorder(
                    save_dir=self.save_dir, file_name=self.file_name
                )
                self.dvs_recorder.error_signal.connect(self._on_dvs_error)
                self.dvs_recorder.start()
                self.dvs_available = True
                print("DualRecorder: DVS-Recorder erfolgreich initialisiert")
            except Exception as e:
                print(
                    f"DualRecorder: Fehler bei der Initialisierung des DVS-Recorders: {e}"
                )
                self.error_signal.emit(f"DVS-Fehler: {e}")
                self.dvs_available = False

            # Erfolg zurückgeben, wenn mindestens eine Kamera verfügbar ist
            return self.webcam_available or self.dvs_available

        except Exception as e:
            self.error_signal.emit(f"Fehler bei der Initialisierung der Recorder: {e}")
            print(f"Fehler bei der Initialisierung der Recorder: {e}")
            import traceback

            traceback.print_exc()
            return False

    def set_audio_enabled(self, enabled):
        """Aktiviert oder deaktiviert die Audioaufnahme"""
        self.audio_enabled = enabled
        if self.webcam_recorder and hasattr(self.webcam_recorder, "has_audio"):
            self.webcam_recorder.has_audio = enabled

    def start_recording(self, save_dir=None, file_name=None):
        """Startet die Aufnahme beider Kameras"""
        if self.recording:
            return False

        # Verwende die übergebenen Werte oder behalte die vorhandenen bei
        if save_dir:
            self.save_dir = save_dir
        if file_name:
            self.file_name = file_name

        if not self.save_dir or not self.file_name:
            self.error_signal.emit("Kein Speicherort oder Dateiname angegeben!")
            return False

        # Prüfen, ob mindestens eine Kamera verfügbar ist
        if not self.webcam_available and not self.dvs_available:
            self.error_signal.emit("Keine Kameras verfügbar für die Aufnahme!")
            return False

        try:
            print("DualRecorder: Starte Aufnahme...")

            # Sicherstellen, dass der Speicherordner existiert
            os.makedirs(self.save_dir, exist_ok=True)

            # Erfolgsstatus
            success = False

            # Webcam-Aufnahme starten
            if self.webcam_available and self.webcam_recorder:
                try:
                    print("DualRecorder: Starte Webcam-Aufnahme...")
                    self.webcam_recorder.start_recording(self.save_dir, self.file_name)
                    success = True
                    self.status_signal.emit("Webcam-Aufnahme gestartet")
                except Exception as e:
                    print(f"DualRecorder: Fehler beim Starten der Webcam-Aufnahme: {e}")
                    self.error_signal.emit(f"Webcam-Fehler: {e}")

            # DVS-Aufnahme starten
            if self.dvs_available and self.dvs_recorder:
                try:
                    print("DualRecorder: Starte DVS-Aufnahme...")
                    dvs_success = self.dvs_recorder.start_recording(
                        self.save_dir, self.file_name
                    )
                    if dvs_success:
                        success = True
                        self.status_signal.emit("DVS-Aufnahme gestartet")
                    else:
                        print(
                            "DualRecorder: DVS-Aufnahme konnte nicht gestartet werden"
                        )
                except Exception as e:
                    print(f"DualRecorder: Fehler beim Starten der DVS-Aufnahme: {e}")
                    self.error_signal.emit(f"DVS-Fehler: {e}")

            # Status setzen
            self.recording = success

            if success:
                print("DualRecorder: Aufnahme erfolgreich gestartet")
                self.status_signal.emit("Aufnahme gestartet")
            else:
                print("DualRecorder: Aufnahme konnte nicht gestartet werden")
                self.error_signal.emit("Aufnahme konnte nicht gestartet werden")

            return success

        except Exception as e:
            self.error_signal.emit(f"Fehler beim Starten der Aufnahme: {e}")
            print(f"Fehler beim Starten der Aufnahme: {e}")
            import traceback

            traceback.print_exc()
            return False

    def stop_recording(self):
        """Stoppt die laufende Aufnahme beider Kameras"""
        if not self.recording:
            return False

        try:
            print("DualRecorder: Stoppe Aufnahme...")

            # Webcam-Aufnahme stoppen
            if self.webcam_available and self.webcam_recorder:
                try:
                    print("DualRecorder: Stoppe Webcam-Aufnahme...")
                    if hasattr(self.webcam_recorder, "stop_recording"):
                        self.webcam_recorder.stop_recording()
                        self.status_signal.emit("Webcam-Aufnahme gestoppt")
                    else:
                        print(
                            "DualRecorder: Warnung - stop_recording ist nicht verfügbar"
                        )
                        if hasattr(self.webcam_recorder, "recording"):
                            self.webcam_recorder.recording = False
                            self.status_signal.emit("Webcam-Aufnahme manuell gestoppt")
                except Exception as e:
                    print(f"DualRecorder: Fehler beim Stoppen der Webcam-Aufnahme: {e}")
                    self.error_signal.emit(f"Webcam-Fehler: {e}")

            # DVS-Aufnahme stoppen
            if self.dvs_available and self.dvs_recorder:
                try:
                    print("DualRecorder: Stoppe DVS-Aufnahme...")
                    if hasattr(self.dvs_recorder, "stop_recording"):
                        self.dvs_recorder.stop_recording()
                        self.status_signal.emit("DVS-Aufnahme gestoppt")
                    else:
                        print(
                            "DualRecorder: Warnung - stop_recording ist nicht verfügbar"
                        )
                        if hasattr(self.dvs_recorder, "recording"):
                            self.dvs_recorder.recording = False
                            self.status_signal.emit("DVS-Aufnahme manuell gestoppt")
                except Exception as e:
                    print(f"DualRecorder: Fehler beim Stoppen der DVS-Aufnahme: {e}")
                    self.error_signal.emit(f"DVS-Fehler: {e}")

            # Status zurücksetzen
            self.recording = False
            self.status_signal.emit("Aufnahme gestoppt")

            return True

        except Exception as e:
            self.error_signal.emit(f"Fehler beim Stoppen der Aufnahme: {e}")
            print(f"Fehler beim Stoppen der Aufnahme: {e}")
            import traceback

            traceback.print_exc()
            self.recording = False  # Status trotzdem zurücksetzen
            return False

    def stop(self):
        """Stoppt beide Recorder"""
        try:
            print("DualRecorder: Stoppe Recorder...")

            # Aufnahme stoppen, falls sie läuft
            if self.recording:
                print("DualRecorder: Stoppe laufende Aufnahme")
                self.stop_recording()

            # Webcam-Recorder stoppen
            if self.webcam_recorder:
                try:
                    print("DualRecorder: Stoppe Webcam-Recorder...")
                    if hasattr(self.webcam_recorder, "stop"):
                        self.webcam_recorder.stop()
                    self.webcam_recorder = None
                except Exception as e:
                    print(
                        f"DualRecorder: Fehler beim Stoppen des Webcam-Recorders: {e}"
                    )

            # DVS-Recorder stoppen
            if self.dvs_recorder:
                try:
                    print("DualRecorder: Stoppe DVS-Recorder...")
                    if hasattr(self.dvs_recorder, "stop"):
                        self.dvs_recorder.stop()
                    self.dvs_recorder = None
                except Exception as e:
                    print(f"DualRecorder: Fehler beim Stoppen des DVS-Recorders: {e}")

            return True

        except Exception as e:
            print(f"Fehler beim Stoppen der Recorder: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _on_webcam_error(self, error_msg):
        """Behandelt Fehler vom Webcam-Recorder"""
        print(f"Webcam-Fehler: {error_msg}")
        self.error_signal.emit(f"Webcam: {error_msg}")
        if "Keine Kamera verfügbar" in error_msg:
            self.webcam_available = False

    def _on_dvs_error(self, error_msg):
        """Behandelt Fehler vom DVS-Recorder"""
        print(f"DVS-Fehler: {error_msg}")
        self.error_signal.emit(f"DVS: {error_msg}")
        if "nicht verfügbar" in error_msg or "konnte nicht geöffnet" in error_msg:
            self.dvs_available = False
