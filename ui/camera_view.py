#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kamera-Ansicht für die medizinische Untersuchungsaufnahme-Anwendung.
Verbesserte Version mit Timer-basierter Erkennung für abgeschlossene Video-Verarbeitung.
"""

import os
import datetime
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
    QDialog,
    QSizePolicy,
    QGroupBox,
    QGridLayout,
    QProgressBar,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont

from recorder import VideoRecorder, ExternalAudioRecorder
import config
from ui.video_widget import VideoDisplayWidget
from ui.rating_dialog import RatingDialog


class CameraView(QDialog):
    """Dialogfenster mit Live-Vorschau und Aufnahmesteuerung für eine Kamera"""

    recording_state_changed = pyqtSignal(int, bool)  # ID, isRecording
    recording_completed = pyqtSignal(int)  # card_id

    def __init__(self, card_id, camera_id, save_dir, file_name, parent=None):
        super().__init__(parent)
        self.card_id = card_id
        self.camera_id = camera_id
        self.save_dir = save_dir
        self.file_name = file_name
        self.recording = False
        self.processing = False  # Variable für Verarbeitungsstatus
        self.audio_enabled = True

        # Externes Mikrofon
        self.external_mic_enabled = False
        self.external_mic_id = None
        self.external_audio_recorder = None

        # Untersuchungskategorie abrufen
        if self.card_id < len(config.EXAMINATION_CATEGORIES):
            self.category = config.EXAMINATION_CATEGORIES[self.card_id]
        else:
            self.category = {"title": f"Aufnahme {self.card_id + 1}", "description": ""}

        # Recorder initialisieren
        self.recorder = None

        # Timer für Verarbeitungsüberwachung
        self.processing_check_timer = QTimer()
        self.processing_check_timer.timeout.connect(self.check_processing_completed)
        self.was_processing = False

        # Dummy-Bild erstellen
        self.dummy_image = QImage(1280, 720, QImage.Format_RGB888)
        self.dummy_image.fill(Qt.darkGray)

        self.init_ui()

        # Attribute für sanfte Schließung
        self.is_closing = False

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche"""
        self.setWindowTitle(f"{self.category['title']} - Kamera {self.camera_id}")
        self.setMinimumSize(1400, 850)  # Etwas höher für Fortschrittsbalken

        # Layout
        layout = QVBoxLayout()

        # Titel
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)

        self.title_label = QLabel(self.category["title"])
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)

        # Beschreibung, falls vorhanden
        if self.category["description"]:
            self.description_label = QLabel(self.category["description"])
            self.description_label.setAlignment(Qt.AlignCenter)
            self.description_label.setWordWrap(True)
            layout.addWidget(self.description_label)

        # Video-Vorschau
        self.video_label = VideoDisplayWidget()
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setMinimumSize(1280, 720)
        self.video_label.setText("Kamera wird initialisiert...")

        # Fortschrittsbalken für Video-Verarbeitung (zunächst versteckt)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # Unbestimmter Fortschritt

        # Aufnahmeinformationen in einer Gruppenbox
        info_group = QGroupBox("Aufnahmeinformationen")
        info_layout = QGridLayout()

        # Status-Label
        self.status_label = QLabel("Bereit")
        self.status_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(QLabel("Status:"), 0, 0)
        info_layout.addWidget(self.status_label, 0, 1)

        # Dateiname-Anzeige
        self.file_label = QLabel(self.file_name)
        info_layout.addWidget(QLabel("Dateiname:"), 1, 0)
        info_layout.addWidget(self.file_label, 1, 1)

        # Audio-Status anzeigen
        self.audio_label = QLabel("Aktiviert" if self.audio_enabled else "Deaktiviert")
        info_layout.addWidget(QLabel("Webcam-Audio:"), 2, 0)
        info_layout.addWidget(self.audio_label, 2, 1)

        # Externes Mikrofon Status
        self.external_mic_label = QLabel(
            "Aktiviert" if self.external_mic_enabled else "Deaktiviert"
        )
        info_layout.addWidget(QLabel("Ext. Mikrofon:"), 2, 2)
        info_layout.addWidget(self.external_mic_label, 2, 3)

        # Zeitstempel
        self.timestamp_label = QLabel(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        info_layout.addWidget(QLabel("Aufnahmezeit:"), 3, 0)
        info_layout.addWidget(self.timestamp_label, 3, 1)

        # Aufnahmezeit-Timer aktualisieren
        self.timer = self.startTimer(1000)  # Aktualisierung jede Sekunde

        info_group.setLayout(info_layout)

        # Steuerungs-Buttons
        button_layout = QHBoxLayout()

        self.record_button = QPushButton("Aufnahme starten")
        self.record_button.clicked.connect(self.toggle_recording)
        button_layout.addWidget(self.record_button)

        self.close_button = QPushButton("Schließen")
        self.close_button.clicked.connect(self.safe_close)
        button_layout.addWidget(self.close_button)

        # Komponenten zum Layout hinzufügen
        layout.addWidget(self.title_label)
        layout.addWidget(self.video_label)
        layout.addWidget(self.progress_bar)  # Fortschrittsbalken hinzufügen
        layout.addWidget(info_group)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def set_audio_enabled(self, enabled):
        """Aktiviert oder deaktiviert die Audioaufnahme"""
        self.audio_enabled = enabled
        self.audio_label.setText("Aktiviert" if enabled else "Deaktiviert")

        # Wenn der Recorder bereits existiert, auch dort den Status aktualisieren
        if self.recorder:
            self.recorder.has_audio = enabled

    def set_external_mic(self, enabled, mic_id=None):
        """Setzt die externen Mikrofon-Einstellungen"""
        print(f"[CameraView] set_external_mic: enabled={enabled}, mic_id={mic_id}")
        self.external_mic_enabled = enabled
        self.external_mic_id = mic_id
        self.external_mic_label.setText("Aktiviert" if enabled else "Deaktiviert")

    def showEvent(self, event):
        """Wird aufgerufen, wenn das Fenster angezeigt wird"""
        super().showEvent(event)
        # Video-Recorder neu starten, wenn das Fenster geöffnet wird
        self.start_recorder()

    def closeEvent(self, event):
        """Wird aufgerufen, wenn das Fenster geschlossen wird"""
        if not self.is_closing:
            # Benutzer hat versucht, das Fenster direkt zu schließen
            self.safe_close()
            event.ignore()
        else:
            # safe_close hat bereits alles vorbereitet
            super().closeEvent(event)

    def timerEvent(self, event):
        """Aktualisiert die Zeitanzeige"""
        if self.recording:
            self.timestamp_label.setText(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

    def safe_close(self):
        """Sichere Schließung des Fensters mit Ressourcenfreigabe"""
        try:
            # Timer stoppen
            self.killTimer(self.timer)
            if hasattr(self, "processing_check_timer"):
                self.processing_check_timer.stop()

            # Prüfen, ob gerade verarbeitet wird
            if self.processing:
                reply = QMessageBox.question(
                    self,
                    "Video wird verarbeitet",
                    "Das Video wird gerade verarbeitet. Möchten Sie wirklich schließen?\n"
                    "Die Verarbeitung läuft im Hintergrund weiter.",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return

            # Aufnahme stoppen, falls sie läuft
            if self.recording and self.recorder:
                # Button deaktivieren, damit der Benutzer nicht mehrfach klickt
                self.record_button.setEnabled(False)
                self.close_button.setEnabled(False)
                self.status_label.setText("Aufnahme wird gestoppt...")

                from PyQt5.QtWidgets import QApplication

                QApplication.processEvents()

                # Externes Mikrofon stoppen
                if self.external_audio_recorder is not None:
                    self.external_audio_recorder.stop()
                    self.external_audio_recorder = None

                # Aufnahme stoppen
                self.recorder.stop_recording()
                self.recording = False
                self.recording_state_changed.emit(self.card_id, False)

            # Recorder stoppen
            self.stop_recorder()

            # Fenster als schließend markieren und schließen
            self.is_closing = True
            self.close()

        except Exception as e:
            print(f"Fehler beim sicheren Schließen des Fensters: {e}")
            # Im Fehlerfall trotzdem schließen
            self.is_closing = True
            self.close()

    def start_recorder(self):
        """Startet den Video-Recorder-Thread"""
        try:
            # Zuerst sicherstellen, dass ein vorhandener Recorder gestoppt wird
            self.stop_recorder()

            # Video-Label zurücksetzen
            self.video_label.setText("Kamera wird initialisiert...")

            # Neuen Recorder erstellen und starten
            self.recorder = VideoRecorder(
                camera_id=self.camera_id,
                save_dir=self.save_dir,
                file_name=self.file_name,
                audio_enabled=self.audio_enabled,
            )

            # Signale verbinden
            self.recorder.update_frame.connect(self.update_video_frame)
            self.recorder.error_signal.connect(self.on_camera_error)
            self.recorder.processing_status.connect(self.on_processing_status)

            self.recorder.start()

            print(f"Recorder neu gestartet für Kamera {self.camera_id}")
        except Exception as e:
            print(f"Fehler beim Starten des Recorders: {e}")
            self.status_label.setText(f"Fehler: {e}")
            self.record_button.setEnabled(False)
            import traceback

            traceback.print_exc()

    def stop_recorder(self):
        """Stoppt den Video-Recorder-Thread"""
        try:
            if self.recorder and self.recorder.running:
                # Signalverbindungen trennen
                try:
                    self.recorder.update_frame.disconnect(self.update_video_frame)
                    self.recorder.error_signal.disconnect(self.on_camera_error)
                    self.recorder.processing_status.disconnect(
                        self.on_processing_status
                    )
                except:
                    pass  # Fehler ignorieren, falls keine Verbindungen bestehen

                # Recorder-Thread stoppen
                self.recorder.stop()
                self.recorder = None

                # Setze das Bild auf ein "Bitte warten"-Bild zurück
                self.video_label.setText("Kamera wird gestoppt...")
        except Exception as e:
            print(f"Fehler beim Stoppen des Recorders: {e}")
            import traceback

            traceback.print_exc()

    def update_video_frame(self, image):
        """Aktualisiert die Videovorschau mit dem neuesten Frame"""
        if self.is_closing:
            return  # Keine Updates mehr, wenn das Fenster geschlossen wird

        try:
            self.video_label.setImage(image)
        except Exception as e:
            print(f"Fehler beim Aktualisieren des Video-Frames: {e}")
            import traceback

            traceback.print_exc()

    def on_camera_error(self, error_msg):
        """Wird bei Kamera-Fehlern aufgerufen"""
        self.status_label.setText(error_msg)
        if "Keine Kamera verfügbar" in error_msg:
            self.record_button.setEnabled(False)

    def on_processing_status(self, status_msg):
        """Wird bei Änderungen des Verarbeitungsstatus aufgerufen"""
        self.status_label.setText(status_msg)
        print(f"Processing Status: {status_msg}")  # Debug-Ausgabe

        # Prüfen, ob die Verarbeitung startet
        if "Verarbeite" in status_msg or "Konvertiere" in status_msg:
            self.processing = True
            self.was_processing = True
            self.progress_bar.setVisible(True)
            self.record_button.setEnabled(False)

            # Timer starten, um das Ende der Verarbeitung zu überwachen
            if not self.processing_check_timer.isActive():
                self.processing_check_timer.start(1000)  # Prüfe jede Sekunde
                print("Starte Timer zur Überwachung der Verarbeitung...")

        # WICHTIG: Direkt auf "erfolgreich gespeichert" reagieren
        elif "erfolgreich" in status_msg or "gespeichert" in status_msg:
            self.processing = False
            self.progress_bar.setVisible(False)
            self.record_button.setEnabled(True)

            print("Video erfolgreich gespeichert - zeige Bewertungsdialog SOFORT")
            # Bewertungsdialog SOFORT anzeigen, nicht warten
            QTimer.singleShot(100, self.show_rating_dialog)

    def check_processing_completed(self):
        """Prüft, ob die Video-Verarbeitung abgeschlossen ist"""
        try:
            print(
                f"Timer-Check: processing={self.processing}, was_processing={self.was_processing}"
            )

            # Wenn wir eine "erfolgreich gespeichert" Meldung hatten, Timer stoppen
            if not self.processing and self.was_processing:
                print("Timer erkannt: Verarbeitung abgeschlossen - stoppe Timer")
                self.processing_check_timer.stop()
                self.was_processing = False

        except Exception as e:
            print(f"Fehler bei der Verarbeitungsüberprüfung: {e}")

    def _is_processing_thread_active(self):
        """Prüft, ob der Processing-Thread noch aktiv ist"""
        try:
            if (
                hasattr(self.recorder, "processing_thread")
                and self.recorder.processing_thread is not None
            ):
                return self.recorder.processing_thread.isRunning()
            return False
        except:
            return False

    def set_file_name(self, file_name):
        """Setzt den Dateinamen"""
        self.file_name = file_name
        self.file_label.setText(file_name)
        if self.recorder:
            self.recorder.file_name = file_name

    def set_save_directory(self, directory):
        """Setzt das Speicherverzeichnis"""
        self.save_dir = directory
        if self.recorder:
            self.recorder.save_dir = directory

    def toggle_recording(self):
        """Startet oder stoppt die Aufnahme"""
        if not self.recorder or not self.recorder.running:
            QMessageBox.warning(self, "Warnung", "Kamera nicht bereit für Aufnahme!")
            return

        if not self.recording:
            # Aufnahme starten
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.file_name == f"recording_{self.card_id}" or not self.file_name:
                # Verwende den Kategorienamen für den Dateinamen
                category_name = os.path.basename(self.save_dir)
                self.file_name = f"{category_name}_{timestamp}"
                self.file_name = "".join(
                    c for c in self.file_name if c.isalnum() or c in "_-"
                )
                self.file_label.setText(self.file_name)

            # Sicherstellen, dass der Speicherordner existiert
            os.makedirs(self.save_dir, exist_ok=True)

            # Wenn externes Mikrofon aktiviert ist, internes Audio deaktivieren
            # (ALSA unterstützt nicht mehrere Audio-Streams gleichzeitig)
            if self.external_mic_enabled and self.external_mic_id is not None:
                self.recorder.has_audio = False
                print("[CameraView] Internes Audio deaktiviert (externes Mikrofon aktiv)")

            self.recorder.start_recording(self.save_dir, self.file_name)

            # Externes Mikrofon starten (synchron mit Video)
            print(f"[CameraView] toggle_recording: external_mic_enabled={self.external_mic_enabled}, external_mic_id={self.external_mic_id}")
            if self.external_mic_enabled and self.external_mic_id is not None:
                external_audio_path = os.path.join(
                    self.save_dir, f"{self.file_name}_audio.wav"
                )
                self.external_audio_recorder = ExternalAudioRecorder(
                    external_audio_path, self.external_mic_id
                )
                # Synchronisation mit Video-Startzeit
                if self.recorder.start_time:
                    self.external_audio_recorder.set_start_time(self.recorder.start_time)
                self.external_audio_recorder.start()
                print(f"Externes Mikrofon gestartet: {external_audio_path}")

            self.recording = True
            self.record_button.setText("Aufnahme stoppen")
            self.status_label.setText("Aufnahme läuft...")
            self.recording_state_changed.emit(self.card_id, True)
        else:
            # Aufnahme stoppen
            # Button deaktivieren, während die Aufnahme gestoppt wird
            self.record_button.setEnabled(False)
            self.status_label.setText("Aufnahme wird gestoppt...")
            from PyQt5.QtWidgets import QApplication

            QApplication.processEvents()  # GUI aktualisieren

            # Externes Mikrofon stoppen
            if self.external_audio_recorder is not None:
                print("Stoppe externes Mikrofon...")
                self.external_audio_recorder.stop()
                self.external_audio_recorder = None

            # Aufnahme stoppen - die Verarbeitung läuft jetzt automatisch im Hintergrund
            self.recorder.stop_recording()
            self.recording = False
            self.record_button.setText("Aufnahme starten")
            self.recording_state_changed.emit(self.card_id, False)

            # Verarbeitungsüberwachung vorbereiten
            self.was_processing = False

    def show_rating_dialog(self):
        """Zeigt den Bewertungsdialog an"""
        try:
            print("=== ZEIGE BEWERTUNGSDIALOG ===")

            # Sicherstellen, dass wir nicht bereits dabei sind, einen Dialog zu zeigen
            if hasattr(self, "_showing_dialog") and self._showing_dialog:
                print("Dialog wird bereits angezeigt - überspringe")
                return

            self._showing_dialog = True

            # Bewertungsdialog erstellen und anzeigen
            dialog = RatingDialog(
                category=self.category,
                save_dir=self.save_dir,
                file_name=self.file_name,
                parent=self,
            )

            print(f"Dialog erstellt für Kategorie: {self.category['title']}")

            # Verbinde das "rating_saved"-Signal
            dialog.rating_saved.connect(
                lambda: self.recording_completed.emit(self.card_id)
            )

            # Dialog modal anzeigen (blockiert, bis der Dialog geschlossen wird)
            print("Zeige Dialog modal...")
            result = dialog.exec_()

            if result == QDialog.Accepted:
                print(f"Bewertung wurde gespeichert.")
                self.status_label.setText(
                    "Bewertung gespeichert - Segment abgeschlossen"
                )
            else:
                print(f"Bewertung wurde abgebrochen.")
                self.status_label.setText("Bewertung abgebrochen")

            self._showing_dialog = False

        except Exception as e:
            print(f"FEHLER beim Anzeigen des Bewertungsdialogs: {e}")
            import traceback

            traceback.print_exc()
            self._showing_dialog = False
