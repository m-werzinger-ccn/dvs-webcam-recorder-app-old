#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Aufnahmekarte für die Untersuchungsaufnahme-Anwendung.
"""

import os
import datetime
from PyQt5.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QInputDialog,
    QSizePolicy,
    QComboBox,
    QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ui.camera_view import CameraView
from ui.dual_camera_view import DualCameraView
import config


class RecordingCard(QFrame):
    """Eine Karte für jeden Aufnahmekanal"""

    def __init__(self, card_id, camera_id=0, save_dir=""):
        super().__init__()
        self.card_id = card_id
        self.camera_id = camera_id
        self.save_dir = save_dir
        self.recording = False
        self.audio_enabled = True  # Standard: Audio aktiviert

        # Externes Mikrofon
        self.external_mic_enabled = False
        self.external_mic_id = None

        # Spezifischen Titel und Beschreibung basierend auf Card-ID setzen
        if self.card_id < len(config.EXAMINATION_CATEGORIES):
            self.title = config.EXAMINATION_CATEGORIES[self.card_id]["title"]
            self.description = config.EXAMINATION_CATEGORIES[self.card_id][
                "description"
            ]
        else:
            self.title = f"Aufnahme {self.card_id + 1}"
            self.description = ""

        # Dateiname aus Titel generieren (ohne Sonderzeichen)
        self.file_name = self.title.split(". ")[1] if ". " in self.title else self.title
        self.file_name = "".join(c for c in self.file_name if c.isalnum() or c == "_")

        # Kamera-Modi
        self.WEBCAM_ONLY = 0
        self.DUAL_CAMERA = 1
        # ÄNDERUNG: Standard auf Dual-Kamera setzen
        self.camera_mode = self.DUAL_CAMERA

        # Kamera-Ansichten (werden erst erstellt, wenn angeklickt)
        self.camera_view = None
        self.dual_camera_view = None

        # Flag für abgeschlossene Aufnahmen
        self.completed = False

        self.init_ui()

    def init_ui(self):
        """Initialisiert die UI-Komponenten der Karte"""
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(2)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(120)
        self.setMinimumWidth(config.CARD_MIN_WIDTH)

        # Layout
        layout = QVBoxLayout()
        layout.setSpacing(2)

        # Titel
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)

        self.title_label = QLabel(self.title)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)

        # Beschreibung (mit Scrollbereich für längere Texte)
        if self.description:
            self.description_label = QLabel(self.description)
            self.description_label.setAlignment(Qt.AlignCenter)
            self.description_label.setWordWrap(True)

            # Beschreibung in Scrollbereich einbetten, wenn sie sehr lang ist
            if len(self.description) > 100:
                scroll_area = QScrollArea()
                scroll_area.setWidget(self.description_label)
                scroll_area.setWidgetResizable(True)
                scroll_area.setMaximumHeight(60)
                scroll_area.setFrameStyle(QFrame.NoFrame)
                layout.addWidget(scroll_area)
            else:
                layout.addWidget(self.description_label)

        # Status-Label
        self.status_label = QLabel("Bereit")
        self.status_label.setAlignment(Qt.AlignCenter)

        # Dateiname
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))

        self.name_label = QLabel(self.file_name)
        name_layout.addWidget(self.name_label)

        self.change_name_button = QPushButton("Ändern")
        self.change_name_button.clicked.connect(self.change_file_name)
        name_layout.addWidget(self.change_name_button)

        # Kamera-Modus
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Modus:"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Nur Webcam", self.WEBCAM_ONLY)
        self.mode_combo.addItem("Webcam + DVS", self.DUAL_CAMERA)

        # ÄNDERUNG: Standard auf Dual-Kamera (Index 1) setzen
        self.mode_combo.setCurrentIndex(1)

        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_combo)

        # Öffnen-Button
        self.open_button = QPushButton("Aufnahme starten")
        self.open_button.clicked.connect(self.open_camera_view)

        # Komponenten zum Layout hinzufügen
        layout.addWidget(self.title_label)
        layout.addWidget(self.status_label)
        layout.addLayout(name_layout)
        layout.addLayout(mode_layout)
        layout.addWidget(self.open_button)

        self.setLayout(layout)

    def set_completed(self, completed=True):
        """Setzt den Status der Karte auf abgeschlossen/nicht abgeschlossen"""
        self.completed = completed

        if completed:
            # Banner-Stil für den Status erstellen
            self.status_label.setText("✓ Abgeschlossen")
            self.status_label.setStyleSheet(
                """
                color: white;
                background-color: #198754;
                padding: 5px;
                border-radius: 4px;
                font-weight: bold;
            """
            )

            # Button ändern
            self.open_button.setText("Erneut aufnehmen")

            # Titel-Label farblich markieren
            self.title_label.setStyleSheet("color: #198754; font-weight: bold;")
        else:
            # Auf normalen Zustand zurücksetzen
            self.setStyleSheet("")
            self.status_label.setText("Bereit")
            self.status_label.setStyleSheet("")
            self.open_button.setText("Aufnahme starten")
            self.title_label.setStyleSheet("")

    def check_recording_exists(self):
        """Überprüft, ob eine Aufnahme und Bewertung für diese Karte existiert"""
        try:
            # Verwende den Kategorienamen für das Verzeichnis
            safe_title = self.title.replace(" ", "_").replace(".", "_")
            category_dir = os.path.join(self.save_dir, safe_title)

            # Prüfen, ob Bewertungsdatei existiert (diese zeigt eine abgeschlossene Aufnahme an)
            if os.path.exists(category_dir):
                rating_files = [
                    f for f in os.listdir(category_dir) if f.endswith("_rating.json")
                ]

                if rating_files:
                    # Wenn Bewertungsdateien gefunden wurden, als abgeschlossen markieren
                    self.set_completed(True)
                    return True
            return False
        except (FileNotFoundError, OSError):
            # Verzeichnis existiert nicht oder kann nicht zugegriffen werden
            return False

    def set_camera_id(self, camera_id):
        """Setzt die Kamera-ID"""
        self.camera_id = camera_id
        # Kamera-Ansicht aktualisieren, falls sie bereits geöffnet ist
        if self.camera_view is not None:
            self.camera_view.close()
            self.camera_view = None
        if self.dual_camera_view is not None:
            self.dual_camera_view.close()
            self.dual_camera_view = None

    def set_save_directory(self, directory):
        """Setzt das Speicherverzeichnis"""
        self.save_dir = directory
        # Speicherverzeichnis der Kamera-Ansicht aktualisieren, falls vorhanden
        if self.camera_view is not None:
            self.camera_view.set_save_directory(directory)
        if self.dual_camera_view is not None:
            self.dual_camera_view.set_save_directory(directory)

    def set_audio_enabled(self, enabled):
        """Aktiviert oder deaktiviert die Audioaufnahme"""
        self.audio_enabled = enabled
        # Audio-Einstellung der Kamera-Ansicht aktualisieren, falls vorhanden
        if self.camera_view is not None and hasattr(
            self.camera_view, "set_audio_enabled"
        ):
            self.camera_view.set_audio_enabled(enabled)
        if self.dual_camera_view is not None and hasattr(
            self.dual_camera_view, "set_audio_enabled"
        ):
            self.dual_camera_view.set_audio_enabled(enabled)

    def set_external_mic(self, enabled, mic_id=None):
        """Setzt die externen Mikrofon-Einstellungen"""
        print(f"[Card {self.card_id}] set_external_mic: enabled={enabled}, mic_id={mic_id}")
        self.external_mic_enabled = enabled
        self.external_mic_id = mic_id
        # Externe Mikrofon-Einstellung der Kamera-Ansicht aktualisieren, falls vorhanden
        if self.camera_view is not None and hasattr(
            self.camera_view, "set_external_mic"
        ):
            self.camera_view.set_external_mic(enabled, mic_id)
        if self.dual_camera_view is not None and hasattr(
            self.dual_camera_view, "set_external_mic"
        ):
            self.dual_camera_view.set_external_mic(enabled, mic_id)

    def change_file_name(self):
        """Erlaubt dem Benutzer, den Dateinamen zu ändern"""
        new_name, ok = QInputDialog.getText(
            self,
            "Dateiname ändern",
            "Neuer Dateiname (ohne Erweiterung):",
            text=self.file_name,
        )

        if ok and new_name:
            self.file_name = new_name
            self.name_label.setText(self.file_name)

            # Dateinamen der Kamera-Ansicht aktualisieren, falls vorhanden
            if self.camera_view is not None:
                self.camera_view.set_file_name(new_name)
            if self.dual_camera_view is not None:
                self.dual_camera_view.set_file_name(new_name)

    def on_mode_changed(self, index):
        """Wird aufgerufen, wenn sich der Kamera-Modus ändert"""
        if index >= 0:
            self.camera_mode = self.mode_combo.itemData(index)
            # Bestehende Ansichten schließen
            if self.camera_view is not None:
                self.camera_view.close()
                self.camera_view = None
            if self.dual_camera_view is not None:
                self.dual_camera_view.close()
                self.dual_camera_view = None

    def open_camera_view(self):
        """Öffnet das entsprechende Kameraansichts-Fenster je nach gewähltem Modus"""
        # Erstelle einen kategoriebasierten Speicherpfad
        safe_title = self.title.replace(" ", "_").replace(".", "_")
        category_dir = os.path.join(self.save_dir, safe_title)

        # Stelle sicher, dass der Kategorie-Ordner existiert
        try:
            os.makedirs(category_dir, exist_ok=True)
        except Exception as e:
            print(f"Fehler beim Erstellen des Kategorieordners: {e}")

        # Schließe bestehende Ansichten, bevor neue erstellt werden
        if self.camera_view is not None:
            self.camera_view.close()
            self.camera_view = None
        if self.dual_camera_view is not None:
            self.dual_camera_view.close()
            self.dual_camera_view = None

        if self.camera_mode == self.WEBCAM_ONLY:
            # Einfache Webcam-Ansicht
            self.camera_view = CameraView(
                self.card_id,
                self.camera_id,
                category_dir,  # Hier den kategoriebasierten Pfad übergeben
                self.file_name,
            )
            # Audio-Einstellung setzen
            if hasattr(self.camera_view, "set_audio_enabled"):
                self.camera_view.set_audio_enabled(self.audio_enabled)

            # Externes Mikrofon-Einstellung setzen
            if hasattr(self.camera_view, "set_external_mic"):
                self.camera_view.set_external_mic(
                    self.external_mic_enabled, self.external_mic_id
                )

            self.camera_view.recording_state_changed.connect(
                self.on_recording_state_changed
            )
            # Connect the new signal
            self.camera_view.recording_completed.connect(self.on_recording_completed)

            # Ansicht anzeigen
            self.camera_view.show()
            self.camera_view.raise_()
            self.camera_view.activateWindow()
        else:
            # Duale Kamera-Ansicht
            self.dual_camera_view = DualCameraView(
                self.card_id,
                self.camera_id,
                category_dir,  # Hier den kategoriebasierten Pfad übergeben
                self.file_name,
            )
            # Audio-Einstellung setzen
            if hasattr(self.dual_camera_view, "set_audio_enabled"):
                self.dual_camera_view.set_audio_enabled(self.audio_enabled)

            # Externes Mikrofon-Einstellung setzen
            if hasattr(self.dual_camera_view, "set_external_mic"):
                self.dual_camera_view.set_external_mic(
                    self.external_mic_enabled, self.external_mic_id
                )

            self.dual_camera_view.recording_state_changed.connect(
                self.on_recording_state_changed
            )
            # Connect the new signal
            self.dual_camera_view.recording_completed.connect(
                self.on_recording_completed
            )

            # Ansicht anzeigen
            self.dual_camera_view.show()
            self.dual_camera_view.raise_()
            self.dual_camera_view.activateWindow()

    def on_recording_state_changed(self, card_id, is_recording):
        """Wird aufgerufen, wenn sich der Aufnahmestatus ändert"""
        if card_id == self.card_id:
            self.recording = is_recording

            if is_recording:
                self.status_label.setText("Aufnahme läuft...")
                self.status_label.setStyleSheet("color: red;")
            else:
                if not self.completed:
                    self.status_label.setText("Bereit")
                    self.status_label.setStyleSheet("")

    def on_recording_completed(self, card_id):
        """Wird aufgerufen, wenn eine Aufnahme inklusive Bewertung abgeschlossen wurde"""
        if card_id == self.card_id:
            self.set_completed(True)
