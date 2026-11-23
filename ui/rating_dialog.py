#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dialog zur Bewertung einer medizinischen Untersuchung nach der Aufnahme.
Mit zusätzlichem Feld für Notizen/Kommentare.
"""

import os
import json
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QApplication,
    QTextEdit,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class RatingDialog(QDialog):
    """Dialog zur Bewertung der Untersuchung nach der Aufnahme"""

    # Signal für gespeicherte Bewertung
    rating_saved = pyqtSignal()

    def __init__(self, category, save_dir, file_name, parent=None):
        """
        Initialisiert den Bewertungsdialog.

        Args:
            category: Die Kategorie-Informationen aus EXAMINATION_CATEGORIES
            save_dir: Das Verzeichnis, in dem die Aufnahme gespeichert wurde
            file_name: Der Dateiname der Aufnahme (ohne Erweiterung)
            parent: Das übergeordnete Widget
        """
        super().__init__(parent)
        self.category = category
        self.save_dir = save_dir
        self.file_name = file_name

        # Anfänglicher Wert für die Bewertung
        self.rating = 0

        self.init_ui()

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche"""
        self.setWindowTitle(f"Bewertung: {self.category['title']}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(400)  # Erhöhte Mindesthöhe für das Notizfeld

        # Layout
        layout = QVBoxLayout()

        # Titel
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)

        title_label = QLabel(self.category["title"])
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Beschreibung
        if self.category["description"]:
            desc_label = QLabel(self.category["description"])
            desc_label.setWordWrap(True)
            desc_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(desc_label)

        # Bewertungsbereich
        rating_group = QGroupBox("Bewertung")
        form_layout = QFormLayout()

        # Dropdown für die Punktevergabe
        self.score_combo = QComboBox()

        # Punkte-Labels hinzufügen
        points = self.category.get(
            "points", 3
        )  # Standardmäßig 3 Punkte, falls nicht definiert
        point_labels = self.category.get("pointLabels", [])

        # Wenn keine Labels definiert sind, Standardlabels verwenden (0, 1, 2, ...)
        if not point_labels:
            point_labels = [str(i) for i in range(points)]

        for i in range(points):
            # Label aus der Liste holen oder den Index verwenden, falls nicht genug Labels vorhanden
            label = point_labels[i] if i < len(point_labels) else str(i)
            self.score_combo.addItem(f"{i} - {label}", i)

        form_layout.addRow("Punkte:", self.score_combo)
        rating_group.setLayout(form_layout)
        layout.addWidget(rating_group)

        # Notizbereich hinzufügen
        notes_group = QGroupBox("Kommentar / Notiz")
        notes_layout = QVBoxLayout()

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "Optional: Kommentar oder Notiz zu dieser Bewertung eingeben..."
        )
        self.notes_edit.setMinimumHeight(100)
        notes_layout.addWidget(self.notes_edit)

        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.save_button = QPushButton("Speichern")
        self.save_button.clicked.connect(self.save_rating)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Abbrechen")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_rating(self):
        """Speichert die Bewertung als JSON-Datei"""
        try:
            # Aktuelle Bewertung aus dem Dropdown holen
            selected_point = self.score_combo.currentData()

            # Notiz aus dem Textfeld holen
            note_text = self.notes_edit.toPlainText().strip()

            # JSON-Daten vorbereiten
            rating_data = {
                "title": self.category["title"],
                "description": self.category["description"],
                "numberOfSelectedPoint": selected_point,
                "labelOfSelectedPoint": (
                    self.score_combo.currentText().split(" - ", 1)[1]
                    if " - " in self.score_combo.currentText()
                    else self.score_combo.currentText()
                ),
            }

            # Notiz hinzufügen, wenn vorhanden
            if note_text:
                rating_data["note"] = note_text

            # JSON-Datei speichern
            json_file_path = os.path.join(
                self.save_dir, f"{self.file_name}_rating.json"
            )

            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(rating_data, f, ensure_ascii=False, indent=4)

            print(f"Bewertung gespeichert: {json_file_path}")

            # Signal senden, dass die Bewertung gespeichert wurde
            self.rating_saved.emit()

            # Dialog schließen mit Erfolg
            self.accept()

        except Exception as e:
            print(f"Fehler beim Speichern der Bewertung: {e}")
            import traceback

            traceback.print_exc()

            # Dialog trotzdem schließen
            self.reject()
