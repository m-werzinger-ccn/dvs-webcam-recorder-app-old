#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hauptfenster für die medizinische Untersuchungsaufnahme-Anwendung.
"""

import os
import sys
import datetime
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGridLayout,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QScrollArea,
    QStatusBar,
    QFrame,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ui.card import RecordingCard
from ui.patient_dialog import PatientDialog
from utils import get_available_cameras
from config import WINDOW_WIDTH, WINDOW_HEIGHT, EXAMINATION_CATEGORIES

# Der Import von pdf_generator erfolgt dynamisch in der generate_report Methode


class MainWindow(QMainWindow):
    """Hauptfenster der Anwendung"""

    def __init__(self):
        super().__init__()
        self.cards = []
        self.save_directory = ""
        self.available_cameras = []
        self.selected_camera_id = 0

        # Patientendaten
        self.patient_name = ""
        self.examiner_name = ""  # Neu: Name des Untersuchers
        self.examination_timestamp = ""
        self.audio_enabled = True
        self.examination_datetime = None

        # Externes Mikrofon
        self.external_mic_enabled = False
        self.external_mic_id = None

        # Verfügbare Kameras abrufen
        self.scan_cameras()

        # Zeige zuerst den Patienten-Dialog
        self.show_patient_dialog()

        # UI erst nach dem Patienten-Dialog initialisieren
        if self.save_directory:  # Nur fortfahren, wenn ein Speicherort angegeben wurde
            self.init_ui()

    def show_patient_dialog(self):
        """Zeigt den Dialog zur Eingabe von Patientendaten an"""
        dialog = PatientDialog(self)

        # Dialog modal anzeigen (blockiert, bis der Dialog geschlossen wird)
        result = dialog.exec_()

        if result == PatientDialog.Accepted:
            # Daten aus dem Dialog übernehmen
            data = dialog.get_data()
            self.patient_name = data["patient_name"]
            self.examiner_name = data[
                "examiner_name"
            ]  # Neu: Name des Untersuchers übernehmen
            self.examination_timestamp = data["timestamp"]
            self.save_directory = data["save_directory"]
            self.audio_enabled = data["audio_enabled"]
            self.examination_datetime = data["examination_datetime"]

            # Externes Mikrofon
            self.external_mic_enabled = data.get("external_mic_enabled", False)
            self.external_mic_id = data.get("external_mic_id", None)
            print(f"[MainWindow] Externes Mikrofon: enabled={self.external_mic_enabled}, mic_id={self.external_mic_id}")

            # Verzeichnis für den Patienten erstellen
            patient_dir = os.path.join(self.save_directory, self.patient_name)
            try:
                os.makedirs(patient_dir, exist_ok=True)
                self.save_directory = (
                    patient_dir  # Setze das Verzeichnis auf das Patientenverzeichnis
                )
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Warnung",
                    f"Fehler beim Erstellen des Patientenverzeichnisses: {e}",
                )
        else:
            # Benutzer hat abgebrochen, Anwendung beenden
            QMessageBox.information(
                self,
                "Information",
                "Die Anwendung wird beendet, da keine Untersuchung angelegt wurde.",
            )
            # Anwendung beenden
            import sys

            sys.exit(0)

    def scan_cameras(self):
        """Sucht nach verfügbaren Kameras"""
        self.available_cameras = get_available_cameras()

        if not self.available_cameras:
            QMessageBox.warning(
                self,
                "Warnung",
                "Keine Kamera gefunden! Die Anwendung wird starten, aber es können keine Aufnahmen gemacht werden.",
            )
            print("Keine Kamera gefunden!")
        else:
            print(f"Gefundene Kameras: {self.available_cameras}")
            # ÄNDERUNG: Erste verfügbare Kamera als Standard auswählen
            # (get_available_cameras() sortiert UGREEN-Kameras bereits an den Anfang)
            self.selected_camera_id = self.available_cameras[0][0]

            # Info-Ausgabe, welche Kamera als Standard gewählt wurde
            selected_camera_name = self.available_cameras[0][1]
            if "ugreen" in selected_camera_name.lower():
                print(
                    f"UGREEN-Kamera automatisch als Standard ausgewählt: {selected_camera_name}"
                )
            else:
                print(f"Standard-Kamera ausgewählt: {selected_camera_name}")

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche"""
        self.setWindowTitle(f"Medizinische Untersuchung - {self.patient_name}")
        self.setMinimumSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # Hauptwidget und Layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Patienteninformationen anzeigen
        patient_frame = QFrame()
        patient_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        patient_layout = QVBoxLayout()

        # Titel für Patienteninformationen
        patient_title_font = QFont()
        patient_title_font.setBold(True)
        patient_title_font.setPointSize(14)

        patient_title = QLabel("Untersuchungsinformationen")
        patient_title.setFont(patient_title_font)
        patient_title.setAlignment(Qt.AlignCenter)
        patient_layout.addWidget(patient_title)

        # Patientendaten anzeigen
        patient_info_layout = QHBoxLayout()

        # Name und Zeitpunkt
        info_left = QVBoxLayout()
        name_label = QLabel(f"<b>Patient:</b> {self.patient_name}")
        examiner_label = QLabel(
            f"<b>Untersucher:</b> {self.examiner_name}"
        )  # Neu: Anzeige des Untersuchers
        date_label = QLabel(
            f"<b>Datum:</b> {self.examination_datetime.strftime('%d.%m.%Y %H:%M')}"
        )
        audio_label = QLabel(
            f"<b>Webcam-Audio:</b> {'Aktiviert' if self.audio_enabled else 'Deaktiviert'}"
        )
        external_mic_label = QLabel(
            f"<b>Externes Mikrofon:</b> {'Aktiviert' if self.external_mic_enabled else 'Deaktiviert'}"
        )
        info_left.addWidget(name_label)
        info_left.addWidget(examiner_label)  # Neu: Untersucher anzeigen
        info_left.addWidget(date_label)
        info_left.addWidget(audio_label)
        info_left.addWidget(external_mic_label)

        # Speicherort
        info_right = QVBoxLayout()
        dir_label = QLabel(f"<b>Speicherort:</b> {self.save_directory}")
        dir_label.setWordWrap(True)
        info_right.addWidget(dir_label)

        # Zusammenführen
        patient_info_layout.addLayout(info_left)
        patient_info_layout.addLayout(info_right)

        patient_layout.addLayout(patient_info_layout)
        patient_frame.setLayout(patient_layout)

        main_layout.addWidget(patient_frame)

        # Kamera-Auswahl
        camera_layout = QHBoxLayout()
        camera_layout.addWidget(QLabel("Kamera:"))

        self.camera_combo = QComboBox()
        # Kamera-Liste füllen
        for cam_id, cam_name in self.available_cameras:
            self.camera_combo.addItem(cam_name, cam_id)

        # Falls keine Kameras gefunden wurden, deaktivieren und leeren Eintrag hinzufügen
        if not self.available_cameras:
            self.camera_combo.addItem("Keine Kamera gefunden", -1)
            self.camera_combo.setEnabled(False)
        else:
            # ÄNDERUNG: Standardmäßig die erste Kamera auswählen (UGREEN steht bereits an erster Stelle)
            self.camera_combo.setCurrentIndex(0)

        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)
        camera_layout.addWidget(self.camera_combo)

        # Aktualisieren-Button
        self.refresh_button = QPushButton("Kameras aktualisieren")
        self.refresh_button.clicked.connect(self.refresh_cameras)
        camera_layout.addWidget(self.refresh_button)

        # Bericht erstellen Button
        self.report_button = QPushButton("Bericht erstellen")
        self.report_button.clicked.connect(self.generate_report)
        camera_layout.addWidget(self.report_button)

        main_layout.addLayout(camera_layout)

        # Scrollbereich für die Karten erstellen
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Grid für die Aufnahmekarten
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(8)  # Mehr Abstand zwischen den Karten

        # Anzahl der Karten aus Konfiguration holen
        num_cards = len(EXAMINATION_CATEGORIES)

        # Karten erstellen (3x5 Grid oder ähnlich, je nach Anzahl)
        cols = 3  # Anzahl der Spalten im Grid
        for i in range(num_cards):
            row = i // cols
            col = i % cols

            card = RecordingCard(i, self.selected_camera_id, self.save_directory)

            # Audio-Einstellung an die Karten weitergeben
            if hasattr(card, "set_audio_enabled"):
                card.set_audio_enabled(self.audio_enabled)

            # Externe Mikrofon-Einstellung an die Karten weitergeben
            if hasattr(card, "set_external_mic"):
                card.set_external_mic(self.external_mic_enabled, self.external_mic_id)

            # Prüfen, ob bereits Aufnahmen für diese Karte existieren
            card.check_recording_exists()

            self.cards.append(card)
            self.grid_layout.addWidget(card, row, col)

        scroll_layout.addLayout(self.grid_layout)
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)

        main_layout.addWidget(scroll_area)

        # Statusleiste hinzufügen
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage(
            f"Bereit | Patient: {self.patient_name} | Untersucher: {self.examiner_name} | Datum: {self.examination_datetime.strftime('%d.%m.%Y %H:%M')}"
        )

        # Widget setzen
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # "Neue Untersuchung" Button in der Werkzeugleiste hinzufügen
        toolbar = self.addToolBar("Hauptwerkzeuge")
        new_exam_action = toolbar.addAction("Neue Untersuchung")
        new_exam_action.triggered.connect(self.new_examination)

    def generate_report(self):
        """Generiert einen PDF-Bericht mit den Bewertungen aller Segmente"""
        try:
            # Installieren von reportlab prüfen/durchführen
            if not self.check_reportlab_installation():
                return

            # Anzeigen, dass der Bericht erstellt wird
            self.statusBar.showMessage("Erstelle Bericht...")

            # Direktes Importieren des PDF-Generators mit vollständigem Pfad
            pdf_generator_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "utils",
                "pdf_generator.py",
            )

            if not os.path.exists(pdf_generator_path):
                QMessageBox.critical(
                    self,
                    "Fehler",
                    f"PDF-Generator-Datei nicht gefunden unter: {pdf_generator_path}",
                )
                return

            # Dynamisches Laden des PDF-Generator-Moduls
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "pdf_generator", pdf_generator_path
            )
            pdf_generator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(pdf_generator)

            # PDF generieren - Untersucher-Namen mit übergeben
            pdf_path = pdf_generator.generate_examination_report(
                self.patient_name,
                self.examination_datetime,
                self.save_directory,
                EXAMINATION_CATEGORIES,
                self.examiner_name,  # Neu: Untersucher-Namen übergeben
            )

            if pdf_path and os.path.exists(pdf_path):
                # Erfolgsmeldung
                QMessageBox.information(
                    self,
                    "Bericht erstellt",
                    f"Der Bericht wurde erfolgreich erstellt und unter\n{pdf_path}\ngespeichert.",
                )
                self.statusBar.showMessage(f"Bericht erstellt: {pdf_path}")

                # Datei öffnen (plattformunabhängig)
                self.open_file(pdf_path)
            else:
                QMessageBox.warning(
                    self,
                    "Fehler",
                    "Beim Erstellen des Berichts ist ein Fehler aufgetreten.",
                )
                self.statusBar.showMessage("Fehler beim Erstellen des Berichts")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Kritischer Fehler",
                f"Beim Erstellen des Berichts ist ein kritischer Fehler aufgetreten:\n{str(e)}",
            )
            self.statusBar.showMessage("Kritischer Fehler beim Erstellen des Berichts")
            import traceback

            traceback.print_exc()

    def check_reportlab_installation(self):
        """Prüft, ob reportlab installiert ist und installiert es bei Bedarf"""
        try:
            import reportlab

            return True
        except ImportError:
            reply = QMessageBox.question(
                self,
                "Bibliothek fehlt",
                "Die Bibliothek 'reportlab' für die PDF-Erstellung fehlt. Möchten Sie sie jetzt installieren?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if reply == QMessageBox.Yes:
                try:
                    import sys
                    import subprocess

                    self.statusBar.showMessage("Installiere reportlab...")

                    # pip verwenden, um reportlab zu installieren
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "reportlab"]
                    )

                    self.statusBar.showMessage("reportlab wurde installiert")
                    return True
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Fehler bei der Installation",
                        f"Fehler beim Installieren von reportlab: {str(e)}\n\n"
                        "Bitte installieren Sie reportlab manuell mit:\n"
                        "pip install reportlab",
                    )
                    return False
            else:
                return False

    def open_file(self, file_path):
        """Öffnet eine Datei mit dem Standardprogramm (plattformunabhängig)"""
        try:
            import platform
            import subprocess

            system = platform.system()

            if system == "Windows":
                os.startfile(file_path)
            elif system == "Darwin":  # macOS
                subprocess.call(["open", file_path])
            else:  # Linux und andere
                subprocess.call(["xdg-open", file_path])
        except Exception as e:
            print(f"Fehler beim Öffnen der Datei: {e}")

    def new_examination(self):
        """Startet eine neue Untersuchung"""
        # Bestätigung vom Benutzer einholen
        reply = QMessageBox.question(
            self,
            "Neue Untersuchung",
            "Möchten Sie eine neue Untersuchung starten? Die aktuelle Untersuchung wird geschlossen.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # Alle Kamera-Ansichten schließen
            for card in self.cards:
                if hasattr(card, "camera_view") and card.camera_view is not None:
                    card.camera_view.close()
                if (
                    hasattr(card, "dual_camera_view")
                    and card.dual_camera_view is not None
                ):
                    card.dual_camera_view.close()

            # Aktuelles Fenster schließen
            self.close()

            # Programm neu starten
            python = sys.executable
            os.execl(python, python, *sys.argv)

    def on_camera_changed(self, index):
        """Wird aufgerufen, wenn eine andere Kamera ausgewählt wird"""
        if index >= 0 and index < len(self.available_cameras):
            self.selected_camera_id = self.available_cameras[index][0]
            print(
                f"Kamera gewechselt zu: {self.available_cameras[index][1]} (ID: {self.selected_camera_id})"
            )

            # Kamera-ID in allen Karten aktualisieren
            for card in self.cards:
                card.set_camera_id(self.selected_camera_id)

    def refresh_cameras(self):
        """Aktualisiert die Liste der verfügbaren Kameras"""
        previous_camera_id = self.selected_camera_id

        # Liste der verfügbaren Kameras aktualisieren
        self.available_cameras = get_available_cameras()

        # ComboBox aktualisieren
        self.camera_combo.clear()

        if not self.available_cameras:
            self.camera_combo.addItem("Keine Kamera gefunden", -1)
            self.camera_combo.setEnabled(False)
            QMessageBox.warning(self, "Warnung", "Keine Kamera gefunden!")
        else:
            self.camera_combo.setEnabled(True)

            # ComboBox mit Kameras füllen
            selected_index = 0
            for i, (cam_id, cam_name) in enumerate(self.available_cameras):
                self.camera_combo.addItem(cam_name, cam_id)

                # Vorherige Kamera wiederfinden
                if cam_id == previous_camera_id:
                    selected_index = i

            # ÄNDERUNG: Prüfen, ob UGREEN-Kamera verfügbar ist und diese bevorzugen
            # (get_available_cameras() sortiert UGREEN bereits an den Anfang)
            if self.available_cameras:
                first_camera_name = self.available_cameras[0][1]
                if "ugreen" in first_camera_name.lower():
                    selected_index = 0  # UGREEN-Kamera steht bereits an erster Stelle
                    print(f"UGREEN-Kamera automatisch ausgewählt: {first_camera_name}")

            # Kamera auswählen
            self.camera_combo.setCurrentIndex(selected_index)
            self.selected_camera_id = self.available_cameras[selected_index][0]

    def closeEvent(self, event):
        """Wird aufgerufen, wenn das Fenster geschlossen wird"""
        # Alle Kamera-Ansichten schließen
        for card in self.cards:
            if hasattr(card, "camera_view") and card.camera_view is not None:
                card.camera_view.close()
            if hasattr(card, "dual_camera_view") and card.dual_camera_view is not None:
                card.dual_camera_view.close()

        # Event weiterleiten
        super().closeEvent(event)
