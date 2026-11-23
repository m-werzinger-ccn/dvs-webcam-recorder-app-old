#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Patient-Registrierungsdialog für die medizinische Untersuchungsaufnahme-Anwendung.
Erscheint vor der Hauptoberfläche zur Eingabe von Patientendaten.
"""

import os
import datetime
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QDateTimeEdit,
    QGroupBox,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtGui import QFont

from utils import get_available_microphones


class PatientDialog(QDialog):
    """Dialog zur Erfassung von Patientendaten für eine neue Untersuchung"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.patient_name = ""
        self.examiner_name = ""  # Neu: Name des Untersuchers
        self.examination_timestamp = QDateTime.currentDateTime()
        self.save_directory = ""
        self.audio_enabled = True

        # Externes Mikrofon
        self.external_mic_enabled = False
        self.external_mic_id = None
        self.available_microphones = []

        self.init_ui()

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche"""
        self.setWindowTitle("Neue Untersuchung anlegen")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setModal(True)

        # Layout
        layout = QVBoxLayout()

        # Titel
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)

        title_label = QLabel("Neue Untersuchung anlegen")
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Untersuchungsinformationen
        exam_group = QGroupBox("Untersuchungsdaten")
        form_layout = QFormLayout()

        # Zeitstempel der Untersuchung
        self.timestamp_edit = QDateTimeEdit(self.examination_timestamp)
        self.timestamp_edit.setDisplayFormat("dd.MM.yyyy HH:mm:ss")
        self.timestamp_edit.setCalendarPopup(True)
        form_layout.addRow("Zeitpunkt der Untersuchung:", self.timestamp_edit)

        # Patientenname
        current_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"Patient-{current_timestamp}"

        self.name_edit = QLineEdit(default_name)
        form_layout.addRow("Name des Patienten:", self.name_edit)

        # Neu: Name des Untersuchers
        self.examiner_edit = QLineEdit()
        form_layout.addRow("Name des Untersuchers:", self.examiner_edit)

        # Audio-Aufnahme Option (Webcam-Audio)
        self.audio_checkbox = QCheckBox("Webcam-Audio aufnehmen")
        self.audio_checkbox.setChecked(True)
        form_layout.addRow("", self.audio_checkbox)

        # Externes Mikrofon Option
        self.external_mic_checkbox = QCheckBox("Externes USB-Mikrofon verwenden")
        self.external_mic_checkbox.setChecked(False)
        self.external_mic_checkbox.stateChanged.connect(self.on_external_mic_toggled)
        form_layout.addRow("", self.external_mic_checkbox)

        # Mikrofon-Auswahl (initial versteckt)
        mic_layout = QHBoxLayout()
        self.mic_combo = QComboBox()
        self.mic_combo.setEnabled(False)
        self.mic_combo.setMinimumWidth(300)
        mic_layout.addWidget(self.mic_combo)

        self.refresh_mic_button = QPushButton("Aktualisieren")
        self.refresh_mic_button.setEnabled(False)
        self.refresh_mic_button.clicked.connect(self.refresh_microphones)
        mic_layout.addWidget(self.refresh_mic_button)

        form_layout.addRow("Mikrofon:", mic_layout)

        # Mikrofone initial laden
        self.refresh_microphones()

        # Speicherort
        dir_layout = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        dir_layout.addWidget(self.dir_edit)

        browse_button = QPushButton("Durchsuchen...")
        browse_button.clicked.connect(self.browse_directory)
        dir_layout.addWidget(browse_button)

        form_layout.addRow("Speicherort:", dir_layout)

        exam_group.setLayout(form_layout)
        layout.addWidget(exam_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.create_button = QPushButton("Untersuchung anlegen")
        self.create_button.clicked.connect(self.accept)
        button_layout.addWidget(self.create_button)

        cancel_button = QPushButton("Abbrechen")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        # Layout setzen
        self.setLayout(layout)

    def on_external_mic_toggled(self, state):
        """Wird aufgerufen, wenn die externe Mikrofon-Checkbox geändert wird"""
        enabled = state == Qt.Checked
        self.mic_combo.setEnabled(enabled)
        self.refresh_mic_button.setEnabled(enabled)

        if enabled and self.mic_combo.count() == 0:
            self.refresh_microphones()

    def refresh_microphones(self):
        """Aktualisiert die Liste der verfügbaren Mikrofone"""
        self.mic_combo.clear()
        self.available_microphones = get_available_microphones()

        if not self.available_microphones:
            self.mic_combo.addItem("Kein Mikrofon gefunden", -1)
            self.mic_combo.setEnabled(False)
            self.external_mic_checkbox.setEnabled(False)
        else:
            for mic_id, mic_name in self.available_microphones:
                self.mic_combo.addItem(mic_name, mic_id)
            # Erstes Mikrofon auswählen
            self.mic_combo.setCurrentIndex(0)

    def browse_directory(self):
        """Öffnet einen Dialog zur Auswahl des Speicherverzeichnisses"""
        try:
            # Als Startpunkt den Home-Ordner des Benutzers verwenden
            start_dir = os.path.expanduser("~")

            # Dialog mit Fehlerbehandlung ausführen
            directory = QFileDialog.getExistingDirectory(
                self,
                "Speicherverzeichnis auswählen",
                start_dir,
                QFileDialog.ShowDirsOnly,
            )

            if directory:
                self.save_directory = directory
                self.dir_edit.setText(directory)

        except Exception as e:
            QMessageBox.critical(
                self, "Fehler", f"Fehler beim Öffnen des Dateiauswahldialogs: {e}"
            )
            print(f"Fehler beim Öffnen des Dateiauswahldialogs: {e}")

    def accept(self):
        """Wird aufgerufen, wenn der Dialog bestätigt wird"""
        # Werte erfassen
        self.patient_name = self.name_edit.text()
        self.examiner_name = (
            self.examiner_edit.text()
        )  # Neu: Name des Untersuchers speichern
        self.examination_timestamp = self.timestamp_edit.dateTime()
        self.audio_enabled = self.audio_checkbox.isChecked()

        # Externes Mikrofon
        self.external_mic_enabled = self.external_mic_checkbox.isChecked()
        if self.external_mic_enabled and self.mic_combo.currentIndex() >= 0:
            self.external_mic_id = self.mic_combo.currentData()
        else:
            self.external_mic_id = None
        print(f"[PatientDialog] accept: external_mic_enabled={self.external_mic_enabled}, external_mic_id={self.external_mic_id}, combo_index={self.mic_combo.currentIndex()}")

        # Prüfen, ob ein Speicherort angegeben wurde
        if not self.save_directory:
            QMessageBox.warning(
                self,
                "Warnung",
                "Bitte wählen Sie einen Speicherort für die Untersuchungsaufnahmen aus.",
            )
            return

        # Wenn alles in Ordnung ist, Dialog schließen
        super().accept()

    def get_data(self):
        """Gibt die eingegebenen Daten zurück"""
        timestamp_str = self.examination_timestamp.toString("yyyyMMdd_HHmmss")

        data = {
            "patient_name": self.patient_name,
            "examiner_name": self.examiner_name,  # Neu: Name des Untersuchers zurückgeben
            "timestamp": timestamp_str,
            "save_directory": self.save_directory,
            "audio_enabled": self.audio_enabled,
            "examination_datetime": self.examination_timestamp.toPyDateTime(),
            "external_mic_enabled": self.external_mic_enabled,
            "external_mic_id": self.external_mic_id,
        }
        print(f"[PatientDialog] get_data: external_mic_enabled={data['external_mic_enabled']}, external_mic_id={data['external_mic_id']}")
        return data
