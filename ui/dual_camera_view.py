#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dual-Kamera-Ansicht mit digitalem Zoom für die Webcam.
Laptop-freundliche Fenstergrößen mit Zoom-Steuerung für DVS-Kompatibilität.
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
    QSplitter,
    QApplication,
    QGroupBox,
    QGridLayout,
    QProgressBar,
    QSlider,
    QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont

from recorder import DualRecorder, ExternalAudioRecorder
import config
from ui.video_widget import VideoDisplayWidget
from ui.rating_dialog import RatingDialog


class DualCameraView(QDialog):
    """Dialogfenster mit Webcam-Zoom-Steuerung für DVS-Kompatibilität"""

    recording_state_changed = pyqtSignal(int, bool)
    recording_completed = pyqtSignal(int)

    def __init__(self, card_id, camera_id, save_dir, file_name, parent=None):
        super().__init__(parent)
        self.card_id = card_id
        self.camera_id = camera_id
        self.save_dir = save_dir
        self.file_name = file_name
        self.recording = False
        self.processing = False
        self.audio_enabled = True

        # Externes Mikrofon
        self.external_mic_enabled = False
        self.external_mic_id = None
        self.external_audio_recorder = None

        # Untersuchungskategorie
        if self.card_id < len(config.EXAMINATION_CATEGORIES):
            self.category = config.EXAMINATION_CATEGORIES[self.card_id]
        else:
            self.category = {"title": f"Aufnahme {self.card_id + 1}", "description": ""}

        # Recorder
        self.recorder = None

        # Timer für Verarbeitungsüberwachung
        self.processing_check_timer = QTimer()
        self.processing_check_timer.timeout.connect(self.check_processing_completed)
        self.was_processing = False

        # Dummy-Bild mit reduzierter Größe für Laptop
        self.dummy_image = QImage(960, 540, QImage.Format_RGB888)  # 75% von 1280x720
        self.dummy_image.fill(Qt.darkGray)

        self.init_ui()

        # Attribute für sanfte Schließung
        self.is_closing = False

    def init_ui(self):
        """Initialisiert die laptop-freundliche Benutzeroberfläche mit Zoom-Steuerung"""
        self.setWindowTitle(f"{self.category['title']} - Dual-Kamera mit Zoom")

        # REDUZIERTE Fenstergröße für Laptops (statt 2600x850)
        self.setMinimumSize(1600, 720)  # Passt auf die meisten Laptop-Bildschirme

        # Hauptlayout mit Scroll-Bereich
        main_layout = QVBoxLayout()

        # Titel
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)

        self.title_label = QLabel(self.category["title"])
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.title_label)

        # Beschreibung
        if self.category["description"]:
            self.description_label = QLabel(self.category["description"])
            self.description_label.setAlignment(Qt.AlignCenter)
            self.description_label.setWordWrap(True)
            main_layout.addWidget(self.description_label)

        # Scroll-Bereich für die Kamera-Ansichten
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QHBoxLayout(scroll_content)

        # Splitter für die beiden Kamerabilder (REDUZIERTE Größe)
        self.splitter = QSplitter(Qt.Horizontal)

        # Webcam-Container mit Zoom-Steuerung
        webcam_container = QWidget()
        webcam_layout = QVBoxLayout(webcam_container)

        webcam_title = QLabel("Webcam (mit Digital-Zoom)")
        webcam_title.setAlignment(Qt.AlignCenter)
        webcam_title_font = QFont()
        webcam_title_font.setBold(True)
        webcam_title_font.setPointSize(11)
        webcam_title.setFont(webcam_title_font)
        webcam_layout.addWidget(webcam_title)

        # Webcam-Vorschau (REDUZIERTE Größe: 75% von 1280x720)
        self.webcam_label = VideoDisplayWidget()
        self.webcam_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.webcam_label.setMinimumSize(640, 360)  # Mindestgröße
        self.webcam_label.setText("Webcam wird initialisiert...")
        webcam_layout.addWidget(self.webcam_label)

        # Zoom-Steuerung für Webcam
        zoom_group = QGroupBox("Digital-Zoom (für DVS-Anpassung)")
        zoom_layout = QVBoxLayout()

        # Zoom-Info
        zoom_info_layout = QHBoxLayout()
        zoom_info_layout.addWidget(QLabel("Zoom:"))
        self.zoom_value_label = QLabel("1.5x")  # Standard-Zoom
        self.zoom_value_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        zoom_info_layout.addWidget(self.zoom_value_label)
        zoom_info_layout.addStretch()
        zoom_layout.addLayout(zoom_info_layout)

        # Zoom-Slider (1.0x bis 3.0x)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(10)  # 1.0x
        self.zoom_slider.setMaximum(30)  # 3.0x
        self.zoom_slider.setValue(15)  # 1.5x Standard
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)
        self.zoom_slider.setTickInterval(5)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)

        # Zoom-Beschriftungen
        zoom_labels_layout = QHBoxLayout()
        zoom_labels_layout.addWidget(QLabel("1.0x"))
        zoom_labels_layout.addStretch()
        zoom_labels_layout.addWidget(QLabel("1.5x"))
        zoom_labels_layout.addStretch()
        zoom_labels_layout.addWidget(QLabel("2.0x"))
        zoom_labels_layout.addStretch()
        zoom_labels_layout.addWidget(QLabel("2.5x"))
        zoom_labels_layout.addStretch()
        zoom_labels_layout.addWidget(QLabel("3.0x"))
        zoom_layout.addLayout(zoom_labels_layout)

        # Hinweis
        zoom_hint = QLabel(
            "💡 Passen Sie den Zoom an, um den Bildausschnitt der DVS-Kamera zu erreichen"
        )
        zoom_hint.setWordWrap(True)
        zoom_hint.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        zoom_layout.addWidget(zoom_hint)

        zoom_group.setLayout(zoom_layout)
        webcam_layout.addWidget(zoom_group)

        # DVS-Container
        dvs_container = QWidget()
        dvs_layout = QVBoxLayout(dvs_container)

        dvs_title = QLabel("DVS-Kamera (Prophesee IMX636)")
        dvs_title.setAlignment(Qt.AlignCenter)
        dvs_title_font = QFont()
        dvs_title_font.setBold(True)
        dvs_title_font.setPointSize(11)
        dvs_title.setFont(dvs_title_font)
        dvs_layout.addWidget(dvs_title)

        # DVS-Vorschau (REDUZIERTE Größe)
        self.dvs_label = VideoDisplayWidget()
        self.dvs_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.dvs_label.setMinimumSize(640, 360)
        self.dvs_label.setText("DVS-Kamera wird initialisiert...")
        dvs_layout.addWidget(self.dvs_label)

        # Info für DVS
        dvs_info = QLabel("Native Auflösung: 1280x720 | 12mm IR-Linse")
        dvs_info.setAlignment(Qt.AlignCenter)
        dvs_info.setStyleSheet("color: #666; font-size: 10px;")
        dvs_layout.addWidget(dvs_info)

        # Container zum Splitter hinzufügen
        self.splitter.addWidget(webcam_container)
        self.splitter.addWidget(dvs_container)

        scroll_layout.addWidget(self.splitter)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # Fortschrittsbalken
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        main_layout.addWidget(self.progress_bar)

        # Aufnahmeinformationen
        info_group = QGroupBox("Aufnahmeinformationen")
        info_layout = QGridLayout()

        # Status
        self.status_label = QLabel("Bereit")
        self.status_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(QLabel("Status:"), 0, 0)
        info_layout.addWidget(self.status_label, 0, 1)

        # Dateiname
        self.file_label = QLabel(self.file_name)
        info_layout.addWidget(QLabel("Dateiname:"), 0, 2)
        info_layout.addWidget(self.file_label, 0, 3)

        # Audio
        self.audio_label = QLabel("Aktiviert" if self.audio_enabled else "Deaktiviert")
        info_layout.addWidget(QLabel("Webcam-Audio:"), 1, 0)
        info_layout.addWidget(self.audio_label, 1, 1)

        # Externes Mikrofon
        self.external_mic_label = QLabel(
            "Aktiviert" if self.external_mic_enabled else "Deaktiviert"
        )
        info_layout.addWidget(QLabel("Ext. Mikrofon:"), 2, 0)
        info_layout.addWidget(self.external_mic_label, 2, 1)

        # Zeitstempel
        self.timestamp_label = QLabel(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        info_layout.addWidget(QLabel("Aufnahmezeit:"), 2, 2)
        info_layout.addWidget(self.timestamp_label, 2, 3)

        self.timer = self.startTimer(1000)

        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.record_button = QPushButton("Aufnahme starten")
        self.record_button.clicked.connect(self.toggle_recording)
        button_layout.addWidget(self.record_button)

        self.close_button = QPushButton("Schließen")
        self.close_button.clicked.connect(self.safe_close)
        button_layout.addWidget(self.close_button)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def on_zoom_changed(self, value):
        """Wird aufgerufen, wenn der Zoom-Slider bewegt wird"""
        zoom_factor = value / 10.0  # Umrechnung: 10 = 1.0x, 15 = 1.5x, etc.
        self.zoom_value_label.setText(f"{zoom_factor:.1f}x")

        # Zoom im Recorder setzen
        if self.recorder and hasattr(self.recorder, "webcam_recorder"):
            if self.recorder.webcam_recorder:
                self.recorder.webcam_recorder.set_zoom(zoom_factor)

    def set_audio_enabled(self, enabled):
        """Aktiviert oder deaktiviert die Audioaufnahme"""
        self.audio_enabled = enabled
        self.audio_label.setText("Aktiviert" if enabled else "Deaktiviert")

        if self.recorder and hasattr(self.recorder, "webcam_recorder"):
            if self.recorder.webcam_recorder:
                self.recorder.webcam_recorder.has_audio = enabled

    def set_external_mic(self, enabled, mic_id=None):
        """Setzt die externen Mikrofon-Einstellungen"""
        print(f"[DualCameraView] set_external_mic: enabled={enabled}, mic_id={mic_id}")
        self.external_mic_enabled = enabled
        self.external_mic_id = mic_id
        self.external_mic_label.setText("Aktiviert" if enabled else "Deaktiviert")

    def showEvent(self, event):
        """Wird aufgerufen, wenn das Fenster angezeigt wird"""
        super().showEvent(event)
        self.start_recorder()

    def closeEvent(self, event):
        """Wird aufgerufen, wenn das Fenster geschlossen wird"""
        if not self.is_closing:
            self.safe_close()
            event.ignore()
        else:
            super().closeEvent(event)

    def timerEvent(self, event):
        """Aktualisiert die Zeitanzeige"""
        if self.recording:
            self.timestamp_label.setText(
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

    def safe_close(self):
        """Sichere Schließung des Fensters"""
        try:
            self.killTimer(self.timer)
            if hasattr(self, "processing_check_timer"):
                self.processing_check_timer.stop()

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

            if self.recording and self.recorder:
                self.record_button.setEnabled(False)
                self.close_button.setEnabled(False)
                self.status_label.setText("Aufnahme wird gestoppt...")
                QApplication.processEvents()

                # Externes Mikrofon stoppen
                if self.external_audio_recorder is not None:
                    self.external_audio_recorder.stop()
                    self.external_audio_recorder = None

                self.recorder.stop_recording()
                self.recording = False
                self.recording_state_changed.emit(self.card_id, False)

            self.stop_recorder()
            self.is_closing = True
            self.close()

        except Exception as e:
            print(f"Fehler beim sicheren Schließen: {e}")
            self.is_closing = True
            self.close()

    def start_recorder(self):
        """Startet den Dual-Recorder"""
        try:
            self.stop_recorder()

            self.webcam_label.setText("Webcam wird initialisiert...")
            self.dvs_label.setText("DVS-Kamera wird initialisiert...")

            print("Initialisiere DualRecorder...")

            self.recorder = DualRecorder(
                webcam_id=self.camera_id,
                save_dir=self.save_dir,
                file_name=self.file_name,
                audio_enabled=self.audio_enabled,
            )
            self.recorder.error_signal.connect(self.on_recorder_error)
            self.recorder.status_signal.connect(self.on_recorder_status)

            if (
                hasattr(self.recorder, "webcam_recorder")
                and self.recorder.webcam_recorder
            ):
                self.recorder.webcam_recorder.has_audio = self.audio_enabled

            print("Verbinde Recorder-Signale...")

            success = self.recorder.initialize()

            if success:
                if self.recorder.webcam_recorder:
                    print("Verbinde Webcam-Signale")
                    self.recorder.webcam_recorder.update_frame.connect(
                        self.update_webcam_frame
                    )
                    self.recorder.webcam_recorder.processing_status.connect(
                        self.on_processing_status
                    )

                    # NEU: Initial-Zoom setzen
                    initial_zoom = self.zoom_slider.value() / 10.0
                    self.recorder.webcam_recorder.set_zoom(initial_zoom)
                    print(f"Initial-Zoom gesetzt auf {initial_zoom:.1f}x")
                else:
                    print("Kein Webcam-Recorder verfügbar")

                if self.recorder.dvs_recorder:
                    print("Verbinde DVS-Signale")
                    self.recorder.dvs_recorder.update_frame.connect(
                        self.update_dvs_frame
                    )
                else:
                    print("Kein DVS-Recorder verfügbar")
            else:
                self.status_label.setText("Fehler bei der Initialisierung")
                self.record_button.setEnabled(False)

            print(f"Dual-Recorder gestartet: {success}")
        except Exception as e:
            print(f"Fehler beim Starten des Recorders: {e}")
            self.status_label.setText(f"Fehler: {e}")
            self.record_button.setEnabled(False)
            import traceback

            traceback.print_exc()

    def stop_recorder(self):
        """Stoppt den Dual-Recorder"""
        try:
            if self.recorder:
                try:
                    self.recorder.error_signal.disconnect(self.on_recorder_error)
                    self.recorder.status_signal.disconnect(self.on_recorder_status)

                    if self.recorder.webcam_recorder:
                        try:
                            self.recorder.webcam_recorder.update_frame.disconnect(
                                self.update_webcam_frame
                            )
                            self.recorder.webcam_recorder.processing_status.disconnect(
                                self.on_processing_status
                            )
                        except:
                            pass

                    if self.recorder.dvs_recorder:
                        try:
                            self.recorder.dvs_recorder.update_frame.disconnect(
                                self.update_dvs_frame
                            )
                        except:
                            pass
                except:
                    pass

                self.recorder.stop()
                self.recorder = None

                self.webcam_label.setText("Webcam wird gestoppt...")
                self.dvs_label.setText("DVS-Kamera wird gestoppt...")

                print("Dual-Recorder gestoppt")
        except Exception as e:
            print(f"Fehler beim Stoppen des Recorders: {e}")
            import traceback

            traceback.print_exc()

    def update_webcam_frame(self, image):
        """Aktualisiert die Webcam-Vorschau"""
        if self.is_closing:
            return

        try:
            self.webcam_label.setImage(image)
        except Exception as e:
            print(f"Fehler beim Aktualisieren des Webcam-Frames: {e}")

    def update_dvs_frame(self, image):
        """Aktualisiert die DVS-Vorschau"""
        if self.is_closing:
            return

        try:
            self.dvs_label.setImage(image)
        except Exception as e:
            print(f"Fehler beim Aktualisieren des DVS-Frames: {e}")

    def on_recorder_error(self, error_msg):
        """Wird bei Recorder-Fehlern aufgerufen"""
        self.status_label.setText(f"Fehler: {error_msg}")
        print(f"Recorder-Fehler: {error_msg}")

    def on_recorder_status(self, status_msg):
        """Wird bei Statusänderungen aufgerufen"""
        self.status_label.setText(status_msg)
        print(f"Recorder-Status: {status_msg}")

    def on_processing_status(self, status_msg):
        """Wird bei Änderungen des Verarbeitungsstatus aufgerufen"""
        self.status_label.setText(status_msg)
        print(f"Processing Status: {status_msg}")

        if "Verarbeite" in status_msg or "Konvertiere" in status_msg:
            self.processing = True
            self.was_processing = True
            self.progress_bar.setVisible(True)
            self.record_button.setEnabled(False)
            self.zoom_slider.setEnabled(False)  # Zoom während Verarbeitung sperren

            if not self.processing_check_timer.isActive():
                self.processing_check_timer.start(1000)
                print("Starte Timer zur Überwachung der Verarbeitung...")

        elif "erfolgreich" in status_msg or "gespeichert" in status_msg:
            self.processing = False
            self.progress_bar.setVisible(False)
            self.record_button.setEnabled(True)
            self.zoom_slider.setEnabled(True)  # Zoom wieder freigeben

            print("Video erfolgreich gespeichert - zeige Bewertungsdialog")
            QTimer.singleShot(100, self.show_rating_dialog)

    def check_processing_completed(self):
        """Prüft, ob die Verarbeitung abgeschlossen ist"""
        try:
            if not self.processing and self.was_processing:
                print("Timer erkannt: Verarbeitung abgeschlossen")
                self.processing_check_timer.stop()
                self.was_processing = False
        except Exception as e:
            print(f"Fehler bei der Verarbeitungsüberprüfung: {e}")

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
        if not self.recorder:
            QMessageBox.warning(self, "Warnung", "Kameras nicht bereit!")
            return

        if not self.recording:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.file_name == f"recording_{self.card_id}" or not self.file_name:
                category_name = os.path.basename(self.save_dir)
                self.file_name = f"{category_name}_{timestamp}"
                self.file_name = "".join(
                    c for c in self.file_name if c.isalnum() or c in "_-"
                )
                self.file_label.setText(self.file_name)

            os.makedirs(self.save_dir, exist_ok=True)

            # Wenn externes Mikrofon aktiviert ist, internes Audio deaktivieren
            # (ALSA unterstützt nicht mehrere Audio-Streams gleichzeitig)
            if self.external_mic_enabled and self.external_mic_id is not None:
                if self.recorder.webcam_recorder:
                    self.recorder.webcam_recorder.has_audio = False
                    print("[DualCameraView] Internes Audio deaktiviert (externes Mikrofon aktiv)")

            success = self.recorder.start_recording(self.save_dir, self.file_name)
            if success:
                # Externes Mikrofon starten (synchron mit Video)
                print(f"[DualCameraView] toggle_recording: external_mic_enabled={self.external_mic_enabled}, external_mic_id={self.external_mic_id}")
                if self.external_mic_enabled and self.external_mic_id is not None:
                    external_audio_path = os.path.join(
                        self.save_dir, f"{self.file_name}_audio.wav"
                    )
                    self.external_audio_recorder = ExternalAudioRecorder(
                        external_audio_path, self.external_mic_id
                    )
                    # Synchronisation mit Video-Startzeit
                    if (
                        self.recorder.webcam_recorder
                        and self.recorder.webcam_recorder.start_time
                    ):
                        self.external_audio_recorder.set_start_time(
                            self.recorder.webcam_recorder.start_time
                        )
                    self.external_audio_recorder.start()
                    print(f"Externes Mikrofon gestartet: {external_audio_path}")

                self.recording = True
                self.record_button.setText("Aufnahme stoppen")
                self.status_label.setText("Aufnahme läuft...")
                self.zoom_slider.setEnabled(False)  # Zoom während Aufnahme sperren
                self.recording_state_changed.emit(self.card_id, True)
        else:
            self.record_button.setEnabled(False)
            self.status_label.setText("Aufnahme wird gestoppt...")
            QApplication.processEvents()

            # Externes Mikrofon stoppen
            if self.external_audio_recorder is not None:
                print("Stoppe externes Mikrofon...")
                self.external_audio_recorder.stop()
                self.external_audio_recorder = None

            self.recorder.stop_recording()
            self.recording = False
            self.record_button.setText("Aufnahme starten")
            self.recording_state_changed.emit(self.card_id, False)

            self.was_processing = False

    def show_rating_dialog(self):
        """Zeigt den Bewertungsdialog an"""
        try:
            print("=== ZEIGE BEWERTUNGSDIALOG ===")

            if hasattr(self, "_showing_dialog") and self._showing_dialog:
                print("Dialog wird bereits angezeigt")
                return

            self._showing_dialog = True

            dialog = RatingDialog(
                category=self.category,
                save_dir=self.save_dir,
                file_name=self.file_name,
                parent=self,
            )

            dialog.rating_saved.connect(
                lambda: self.recording_completed.emit(self.card_id)
            )

            result = dialog.exec_()

            if result == QDialog.Accepted:
                print(f"Bewertung wurde gespeichert")
                self.status_label.setText(
                    "Bewertung gespeichert - Segment abgeschlossen"
                )
            else:
                print(f"Bewertung wurde abgebrochen")
                self.status_label.setText("Bewertung abgebrochen")

            self._showing_dialog = False

        except Exception as e:
            print(f"FEHLER beim Anzeigen des Bewertungsdialogs: {e}")
            import traceback

            traceback.print_exc()
            self._showing_dialog = False
