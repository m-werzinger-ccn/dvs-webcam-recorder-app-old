#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Webcam-Zoom und Aufnahme-Applikation
-----------------------------------
Funktionen:
- Echtzeit-Vorschau der Webcam
- Zoom auf einen ausgewählten Bereich
- Aufnahme des normalen und des gezoomten Bildes (falls gewünscht)
- Aufnahme mit Ton in MP4-Format
"""

import os
import sys
import cv2
import time
import datetime
import threading
import numpy as np
import pyaudio
import wave
import subprocess
import tempfile
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QMessageBox,
    QFrame,
    QSizePolicy,
)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect


class AudioRecorder(threading.Thread):
    """Thread für die Audioaufnahme parallel zum Video"""

    def __init__(self, audio_file_path, channels=1, rate=44100, chunk=1024):
        super().__init__()
        self.audio_file_path = audio_file_path
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.recording = False
        self.frames = []

        # PyAudio Initialisierung
        self.pyaudio = None
        self.stream = None

    def run(self):
        """Startet die Audioaufnahme im eigenen Thread"""
        try:
            self.pyaudio = pyaudio.PyAudio()
            self.recording = True

            # Audiostream öffnen
            self.stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )

            print("Audioaufnahme gestartet...")
            self.frames = []

            # Aufnahmeschleife
            while self.recording:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames.append(data)

            # Aufnahme beenden und in Datei speichern
            self.save_audio()

        except Exception as e:
            print(f"Fehler bei der Audioaufnahme: {e}")
        finally:
            # Ressourcen freigeben
            self.cleanup()

    def stop(self):
        """Stoppt die Audioaufnahme"""
        self.recording = False
        self.join()  # Warten, bis Thread beendet ist

    def save_audio(self):
        """Speichert die aufgenommenen Audiodaten in eine WAV-Datei"""
        try:
            # Sicherstellen, dass das Verzeichnis existiert
            os.makedirs(os.path.dirname(self.audio_file_path), exist_ok=True)

            # WAV-Datei speichern
            wf = wave.open(self.audio_file_path, "wb")
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.pyaudio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.rate)
            wf.writeframes(b"".join(self.frames))
            wf.close()
            print(f"Audiodatei gespeichert: {self.audio_file_path}")
        except Exception as e:
            print(f"Fehler beim Speichern der Audiodatei: {e}")

    def cleanup(self):
        """Gibt alle Ressourcen frei"""
        try:
            if self.stream is not None:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

            if self.pyaudio is not None:
                self.pyaudio.terminate()
                self.pyaudio = None
        except Exception as e:
            print(f"Fehler beim Freigeben der Audio-Ressourcen: {e}")


class WebcamDisplay(QLabel):
    """Benutzerdefiniertes Label für die Anzeige des Webcam-Bildes mit Zoom-Funktionalität"""

    zoomAreaSelected = pyqtSignal(tuple)

    def __init__(self, parent=None):
        super(WebcamDisplay, self).__init__(parent)
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.setAlignment(Qt.AlignCenter)

        # Rechteck-Auswahl Variablen
        self.selecting = False
        self.selection_start = None
        self.selection_end = None
        self.selection_active = False
        self.zoom_area = None

        # Bild-Variablen
        self.frame = None

    def setFrame(self, frame):
        """Aktualisiert das angezeigte Frame"""
        self.frame = frame

        # Wenn eine Auswahl aktiv ist, Rechteck zeichnen
        if (
            self.frame is not None
            and self.zoom_area is not None
            and not self.selection_active
        ):
            x1, y1, x2, y2 = self.zoom_area
            # Rechteck auf dem Bild zeichnen
            cv2.rectangle(self.frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        # Frame in QImage und dann in QPixmap umwandeln
        if self.frame is not None:
            h, w, ch = self.frame.shape
            bytes_per_line = ch * w
            q_img = QImage(self.frame.data, w, h, bytes_per_line, QImage.Format_BGR888)

            # Pixmap skalieren, um in das Label zu passen (Seitenverhältnis beibehalten)
            pixmap = QPixmap.fromImage(q_img)
            self.setPixmap(
                pixmap.scaled(
                    self.width(),
                    self.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

    def activateSelection(self):
        """Aktiviert den Auswahlmodus für das Zoom-Rechteck"""
        self.selection_active = True
        self.selecting = False
        self.selection_start = None
        self.selection_end = None
        self.setCursor(Qt.CrossCursor)

    def deactivateSelection(self):
        """Deaktiviert den Auswahlmodus"""
        self.selection_active = False
        self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, event):
        """Wird aufgerufen, wenn die Maus gedrückt wird"""
        if self.selection_active and event.button() == Qt.LeftButton:
            self.selecting = True
            # Von Frame-Koordinaten zu Pixmap-Koordinaten umrechnen
            if self.pixmap() and not self.pixmap().isNull():
                # Originales Frame
                if self.frame is not None:
                    frame_height, frame_width = self.frame.shape[:2]
                else:
                    return

                # Angezeigtes Pixmap
                pixmap = self.pixmap()
                pixmap_width = pixmap.width()
                pixmap_height = pixmap.height()

                # Position im Label
                pos_x = event.pos().x()
                pos_y = event.pos().y()

                # Skalierung berechnen
                label_width = self.width()
                label_height = self.height()

                # Position des Pixmaps im Label berechnen (zentriert)
                pixmap_pos_x = (label_width - pixmap_width) // 2
                pixmap_pos_y = (label_height - pixmap_height) // 2

                # Position relativ zum Pixmap
                rel_x = pos_x - pixmap_pos_x
                rel_y = pos_y - pixmap_pos_y

                # Prüfen, ob die Position im Pixmap liegt
                if 0 <= rel_x < pixmap_width and 0 <= rel_y < pixmap_height:
                    # Position im Original-Frame berechnen
                    original_x = int(rel_x * (frame_width / pixmap_width))
                    original_y = int(rel_y * (frame_height / pixmap_height))

                    self.selection_start = (original_x, original_y)
                    self.selection_end = self.selection_start

    def mouseMoveEvent(self, event):
        """Wird aufgerufen, wenn die Maus bewegt wird"""
        if self.selecting and self.selection_active:
            # Wie oben: Von Frame-Koordinaten zu Pixmap-Koordinaten umrechnen
            if self.pixmap() and not self.pixmap().isNull():
                # Originales Frame
                if self.frame is not None:
                    frame_height, frame_width = self.frame.shape[:2]
                else:
                    return

                # Angezeigtes Pixmap
                pixmap = self.pixmap()
                pixmap_width = pixmap.width()
                pixmap_height = pixmap.height()

                # Position im Label
                pos_x = event.pos().x()
                pos_y = event.pos().y()

                # Skalierung berechnen
                label_width = self.width()
                label_height = self.height()

                # Position des Pixmaps im Label berechnen (zentriert)
                pixmap_pos_x = (label_width - pixmap_width) // 2
                pixmap_pos_y = (label_height - pixmap_height) // 2

                # Position relativ zum Pixmap
                rel_x = pos_x - pixmap_pos_x
                rel_y = pos_y - pixmap_pos_y

                # Auf Pixmap-Größe beschränken
                rel_x = max(0, min(rel_x, pixmap_width - 1))
                rel_y = max(0, min(rel_y, pixmap_height - 1))

                # Position im Original-Frame berechnen
                original_x = int(rel_x * (frame_width / pixmap_width))
                original_y = int(rel_y * (frame_height / pixmap_height))

                self.selection_end = (original_x, original_y)

                # Frame kopieren und Rechteck zeichnen
                if self.frame is not None:
                    frame_copy = self.frame.copy()
                    start_x, start_y = self.selection_start
                    end_x, end_y = self.selection_end
                    cv2.rectangle(
                        frame_copy, (start_x, start_y), (end_x, end_y), (0, 255, 0), 2
                    )

                    # Frame anzeigen
                    h, w, ch = frame_copy.shape
                    bytes_per_line = ch * w
                    q_img = QImage(
                        frame_copy.data, w, h, bytes_per_line, QImage.Format_BGR888
                    )

                    pixmap = QPixmap.fromImage(q_img)
                    self.setPixmap(
                        pixmap.scaled(
                            self.width(),
                            self.height(),
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        )
                    )

    def mouseReleaseEvent(self, event):
        """Wird aufgerufen, wenn die Maustaste losgelassen wird"""
        if self.selecting and self.selection_active and event.button() == Qt.LeftButton:
            self.selecting = False

            if self.selection_start and self.selection_end:
                # Koordinaten normalisieren (linke obere Ecke und rechte untere Ecke)
                x1 = min(self.selection_start[0], self.selection_end[0])
                y1 = min(self.selection_start[1], self.selection_end[1])
                x2 = max(self.selection_start[0], self.selection_end[0])
                y2 = max(self.selection_start[1], self.selection_end[1])

                # Prüfen, ob das Rechteck groß genug ist
                if (x2 - x1) > 10 and (y2 - y1) > 10:
                    self.zoom_area = (x1, y1, x2, y2)
                    self.deactivateSelection()
                    self.zoomAreaSelected.emit(self.zoom_area)
                else:
                    # Rechteck zu klein, Auswahl zurücksetzen
                    self.selection_start = None
                    self.selection_end = None


class WebcamZoomApp(QMainWindow):
    """Hauptfenster der Webcam-Zoom-Anwendung"""

    def __init__(self):
        super(WebcamZoomApp, self).__init__()

        # Anwendungsvariablen
        self.cap = None
        self.current_frame = None
        self.zoomed_frame = None
        self.zoom_area = None
        self.zoom_mode = False
        self.recording = False

        # Aufnahmevariablen
        self.video_writer = None
        self.zoomed_video_writer = None
        self.audio_recorder = None
        self.temp_video_path = ""
        self.temp_zoomed_video_path = ""
        self.temp_audio_path = ""
        self.final_output_path = ""
        self.final_zoomed_output_path = ""
        self.recording_timer = None
        self.recording_start_time = None

        # Threading-Variablen
        self.frame_lock = threading.Lock()
        self.running = True
        self.capture_thread = None

        # UI initialisieren
        self.init_ui()

        # Webcam starten
        self.init_webcam()

        # Timer für die Bildaktualisierung
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_frame)
        self.update_timer.start(33)  # ~30 FPS

        # Thread für die Frame-Erfassung starten
        self.capture_thread = threading.Thread(target=self.capture_frames)
        self.capture_thread.daemon = True
        self.capture_thread.start()

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche"""
        self.setWindowTitle("Webcam Zoom und Aufnahme")
        self.setMinimumSize(800, 600)

        # Zentrales Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Hauptlayout
        main_layout = QVBoxLayout(central_widget)

        # Webcam-Anzeige
        self.webcam_display = WebcamDisplay()
        self.webcam_display.zoomAreaSelected.connect(self.on_zoom_area_selected)
        main_layout.addWidget(self.webcam_display)

        # Status-Frame
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        status_layout = QVBoxLayout(status_frame)

        # Status-Label
        self.status_label = QLabel("Bereit")
        self.status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.status_label)

        # Aufnahmezeit-Label
        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        status_layout.addWidget(self.time_label)

        main_layout.addWidget(status_frame)

        # Button-Layout
        button_layout = QHBoxLayout()

        # Zoom-Bereich-Button
        self.select_zoom_button = QPushButton("Zoom-Bereich auswählen")
        self.select_zoom_button.clicked.connect(self.toggle_selection)
        button_layout.addWidget(self.select_zoom_button)

        # Zoom-Toggle-Button
        self.zoom_button = QPushButton("Zoom aktivieren")
        self.zoom_button.setEnabled(False)
        self.zoom_button.clicked.connect(self.toggle_zoom)
        button_layout.addWidget(self.zoom_button)

        # Aufnahme-Button
        self.record_button = QPushButton("Aufnahme starten")
        self.record_button.clicked.connect(self.toggle_recording)
        button_layout.addWidget(self.record_button)

        main_layout.addLayout(button_layout)

    def init_webcam(self):
        """Initialisiert die Webcam"""
        try:
            if self.cap is not None:
                self.cap.release()

            self.cap = cv2.VideoCapture(0)

            if not self.cap.isOpened():
                QMessageBox.critical(self, "Fehler", "Konnte keine Webcam öffnen!")
                sys.exit(1)

            # Höhere Frame-Rate einstellen (falls unterstützt)
            self.cap.set(cv2.CAP_PROP_FPS, 30)

            # Aktuelle Frame-Rate anzeigen
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            print(f"Webcam geöffnet mit {fps} FPS")

        except Exception as e:
            QMessageBox.critical(
                self, "Fehler", f"Fehler beim Initialisieren der Webcam: {e}"
            )
            sys.exit(1)

    def capture_frames(self):
        """Thread-Funktion zum kontinuierlichen Erfassen von Frames"""
        while self.running:
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self.frame_lock:
                        self.current_frame = frame

                        # Wenn ein Zoom-Bereich gesetzt ist, auch den gezoomten Frame berechnen
                        if self.zoom_area is not None:
                            x1, y1, x2, y2 = self.zoom_area
                            zoomed = frame[y1:y2, x1:x2]

                            # Auf die Größe des Original-Frames skalieren
                            h, w = frame.shape[:2]
                            self.zoomed_frame = cv2.resize(
                                zoomed, (w, h), interpolation=cv2.INTER_LINEAR
                            )

                        # Wenn Aufnahme aktiv, zum Video hinzufügen
                        if self.recording and self.video_writer is not None:
                            self.video_writer.write(frame)

                            # Wenn Zoom-Bereich gesetzt und Zoomed-Writer existiert, gezoomten Frame speichern
                            if (
                                self.zoom_area is not None
                                and self.zoomed_video_writer is not None
                            ):
                                self.zoomed_video_writer.write(self.zoomed_frame)

            # Kleine Pause für CPU-Entlastung
            time.sleep(0.01)

    def update_frame(self):
        """Aktualisiert die Anzeige mit dem aktuellen Frame"""
        with self.frame_lock:
            # Je nach Zoom-Modus das entsprechende Bild anzeigen
            if self.zoom_mode and self.zoomed_frame is not None:
                frame_to_display = self.zoomed_frame.copy()
            elif self.current_frame is not None:
                frame_to_display = self.current_frame.copy()
            else:
                return

            # Wenn Aufnahme läuft, roter Punkt anzeigen
            if self.recording:
                cv2.circle(
                    frame_to_display,
                    (frame_to_display.shape[1] - 30, 30),
                    15,
                    (0, 0, 255),
                    -1,
                )

                # Aufnahmezeit aktualisieren
                if self.recording_start_time:
                    elapsed = time.time() - self.recording_start_time
                    hours, remainder = divmod(int(elapsed), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    self.time_label.setText(f"{hours:02}:{minutes:02}:{seconds:02}")

            # Frame in der Anzeige aktualisieren
            self.webcam_display.setFrame(frame_to_display)

    def toggle_selection(self):
        """Aktiviert oder deaktiviert den Auswahlmodus für das Zoom-Rechteck"""
        if not self.webcam_display.selection_active:
            self.webcam_display.activateSelection()
            self.select_zoom_button.setText("Auswahl abbrechen")
            self.status_label.setText("Rechteck ziehen, um Zoom-Bereich auszuwählen")
        else:
            self.webcam_display.deactivateSelection()
            self.select_zoom_button.setText("Zoom-Bereich auswählen")
            self.status_label.setText("Bereit")

    def on_zoom_area_selected(self, area):
        """Wird aufgerufen, wenn ein Zoom-Bereich ausgewählt wurde"""
        self.zoom_area = area
        self.zoom_button.setEnabled(True)
        self.select_zoom_button.setText("Zoom-Bereich auswählen")
        self.status_label.setText(f"Zoom-Bereich ausgewählt: {area}")

    def toggle_zoom(self):
        """Aktiviert oder deaktiviert den Zoom-Modus"""
        if self.zoom_area is None:
            QMessageBox.warning(
                self, "Warnung", "Bitte zuerst einen Zoom-Bereich auswählen!"
            )
            return

        self.zoom_mode = not self.zoom_mode

        if self.zoom_mode:
            self.zoom_button.setText("Zoom deaktivieren")
            self.status_label.setText("Zoom-Modus aktiv")
        else:
            self.zoom_button.setText("Zoom aktivieren")
            self.status_label.setText("Zoom-Modus deaktiviert")

    def toggle_recording(self):
        """Startet oder stoppt die Aufnahme"""
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Startet die Aufnahme"""
        try:
            # Temporäre Dateinamen für Video und Audio
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_video_path = os.path.join(temp_dir, f"temp_video_{timestamp}.avi")

            # Wenn ein Zoom-Bereich gesetzt ist, erstelle auch einen Pfad für das gezoomte Video
            if self.zoom_area is not None:
                self.temp_zoomed_video_path = os.path.join(
                    temp_dir, f"temp_zoomed_video_{timestamp}.avi"
                )

            self.temp_audio_path = os.path.join(temp_dir, f"temp_audio_{timestamp}.wav")

            # Endgültige Ausgabepfade
            videos_dir = os.path.join(os.path.expanduser("~"), "Videos", "WebcamZoom")
            os.makedirs(videos_dir, exist_ok=True)

            self.final_output_path = os.path.join(videos_dir, f"webcam_{timestamp}.mp4")
            if self.zoom_area is not None:
                self.final_zoomed_output_path = os.path.join(
                    videos_dir, f"webcam_zoomed_{timestamp}.mp4"
                )

            # Frame-Größe abrufen
            with self.frame_lock:
                if self.current_frame is None:
                    QMessageBox.warning(self, "Warnung", "Kein Frame verfügbar!")
                    return
                height, width = self.current_frame.shape[:2]

            frame_size = (width, height)

            # Video-Schreiber initialisieren
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            fps = 30

            self.video_writer = cv2.VideoWriter(
                self.temp_video_path, fourcc, fps, frame_size
            )

            # Wenn ein Zoom-Bereich gesetzt ist, auch einen Schreiber für das gezoomte Video erstellen
            if self.zoom_area is not None:
                self.zoomed_video_writer = cv2.VideoWriter(
                    self.temp_zoomed_video_path, fourcc, fps, frame_size
                )

            # Audio-Recorder starten
            self.audio_recorder = AudioRecorder(self.temp_audio_path)
            self.audio_recorder.start()

            # Aufnahmezeit zurücksetzen
            self.recording_start_time = time.time()
            self.time_label.setText("00:00:00")

            # UI aktualisieren
            self.recording = True
            self.record_button.setText("Aufnahme stoppen")
            self.status_label.setText("Aufnahme läuft...")
            self.record_button.setStyleSheet("background-color: red; color: white;")

            print(f"Aufnahme gestartet. Video: {self.temp_video_path}")
            if self.zoom_area is not None:
                print(f"Gezoomtes Video: {self.temp_zoomed_video_path}")

        except Exception as e:
            QMessageBox.critical(
                self, "Fehler", f"Fehler beim Starten der Aufnahme: {e}"
            )
            import traceback

            traceback.print_exc()
            self.cleanup_recording_resources()

    def stop_recording(self):
        """Stoppt die Aufnahme und kombiniert Video und Audio"""
        try:
            self.status_label.setText("Aufnahme wird gestoppt...")
            QApplication.processEvents()  # UI aktualisieren

            # Aufnahme beenden
            self.recording = False

            # Zeit der Aufnahme zurücksetzen
            self.time_label.setText("00:00:00")

            # Video-Writer schließen
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None

            if self.zoomed_video_writer is not None:
                self.zoomed_video_writer.release()
                self.zoomed_video_writer = None

            # Audio-Aufnahme stoppen
            if self.audio_recorder is not None:
                self.audio_recorder.stop()

            self.status_label.setText("Aufnahme verarbeiten...")
            QApplication.processEvents()  # UI aktualisieren

            # Kombinieren von Video und Audio für das normale Video
            if os.path.exists(self.temp_video_path) and os.path.exists(
                self.temp_audio_path
            ):
                success = self.combine_video_audio(
                    self.temp_video_path, self.temp_audio_path, self.final_output_path
                )
                if success:
                    print(f"Video mit Audio kombiniert: {self.final_output_path}")
                else:
                    print(
                        "Fehler beim Kombinieren von Video und Audio. Bitte ffmpeg installieren."
                    )

            # Kombinieren von Video und Audio für das gezoomte Video (falls vorhanden)
            if (
                self.zoom_area is not None
                and os.path.exists(self.temp_zoomed_video_path)
                and os.path.exists(self.temp_audio_path)
            ):
                # Kopie der Audiodatei erstellen, da wir sie für beide Videos benötigen
                temp_audio_copy = self.temp_audio_path.replace(".wav", "_copy.wav")
                import shutil

                shutil.copy(self.temp_audio_path, temp_audio_copy)

                success = self.combine_video_audio(
                    self.temp_zoomed_video_path,
                    temp_audio_copy,
                    self.final_zoomed_output_path,
                )
                if success:
                    print(
                        f"Gezoomtes Video mit Audio kombiniert: {self.final_zoomed_output_path}"
                    )

                # Temporäre Audiokopie löschen
                if os.path.exists(temp_audio_copy):
                    os.remove(temp_audio_copy)

            # Temporäre Dateien bereinigen
            self.cleanup_temp_files()

            # UI aktualisieren
            self.record_button.setText("Aufnahme starten")
            self.status_label.setText("Aufnahme beendet und gespeichert")
            self.record_button.setStyleSheet("")

            # Erfolgsmeldung
            QMessageBox.information(
                self,
                "Aufnahme gespeichert",
                f"Die Aufnahme wurde erfolgreich unter\n{self.final_output_path}\ngespeichert.",
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Fehler", f"Fehler beim Stoppen der Aufnahme: {e}"
            )
            import traceback

            traceback.print_exc()

        finally:
            self.cleanup_recording_resources()

    def combine_video_audio(self, video_path, audio_path, output_path):
        """Kombiniert Video und Audio mit FFmpeg zu einer MP4-Datei"""
        try:
            # FFmpeg-Befehl
            cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-i",
                audio_path,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "22",
                "-c:a",
                "aac",
                "-strict",
                "experimental",
                "-shortest",
                "-y",
                output_path,
            ]

            # FFmpeg aufrufen
            process = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            if (
                process.returncode == 0
                and os.path.exists(output_path)
                and os.path.getsize(output_path) > 0
            ):
                return True
            else:
                # Alternative Codecs versuchen
                cmd[7] = "medium"  # Andere Preset-Qualität
                process = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

                if (
                    process.returncode == 0
                    and os.path.exists(output_path)
                    and os.path.getsize(output_path) > 0
                ):
                    return True

                # Noch ein Versuch mit mp4v anstelle von libx264
                cmd[6] = "mp4v"
                process = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

                if (
                    process.returncode == 0
                    and os.path.exists(output_path)
                    and os.path.getsize(output_path) > 0
                ):
                    return True

                # Einfaches Kopieren der Codecs
                cmd = [
                    "ffmpeg",
                    "-i",
                    video_path,
                    "-i",
                    audio_path,
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-shortest",
                    "-y",
                    output_path,
                ]
                process = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

                if (
                    process.returncode == 0
                    and os.path.exists(output_path)
                    and os.path.getsize(output_path) > 0
                ):
                    return True

                print("Fehler beim Kombinieren von Video und Audio mit FFmpeg")
                error_msg = process.stderr.decode()
                print(f"FFmpeg-Fehler: {error_msg}")

                return False

        except Exception as e:
            print(f"Fehler beim Kombinieren von Video und Audio: {e}")
            import traceback

            traceback.print_exc()
            return False

    def cleanup_temp_files(self):
        """Löscht temporäre Video- und Audiodateien"""
        try:
            if os.path.exists(self.temp_video_path):
                os.remove(self.temp_video_path)
                print(f"Temporäre Videodatei gelöscht: {self.temp_video_path}")

            if os.path.exists(self.temp_zoomed_video_path):
                os.remove(self.temp_zoomed_video_path)
                print(
                    f"Temporäre gezoomte Videodatei gelöscht: {self.temp_zoomed_video_path}"
                )

            if os.path.exists(self.temp_audio_path):
                os.remove(self.temp_audio_path)
                print(f"Temporäre Audiodatei gelöscht: {self.temp_audio_path}")
        except Exception as e:
            print(f"Fehler beim Löschen der temporären Dateien: {e}")

    def cleanup_recording_resources(self):
        """Gibt alle Aufnahme-Ressourcen frei"""
        try:
            if hasattr(self, "video_writer") and self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None

            if (
                hasattr(self, "zoomed_video_writer")
                and self.zoomed_video_writer is not None
            ):
                self.zoomed_video_writer.release()
                self.zoomed_video_writer = None

            if hasattr(self, "audio_recorder") and self.audio_recorder is not None:
                if self.audio_recorder.is_alive():
                    self.audio_recorder.stop()
                self.audio_recorder = None

            self.recording = False
        except Exception as e:
            print(f"Fehler beim Freigeben der Aufnahme-Ressourcen: {e}")

    def closeEvent(self, event):
        """Wird aufgerufen, wenn das Fenster geschlossen wird"""
        # Aufnahme beenden und Ressourcen freigeben
        self.running = False

        if self.recording:
            self.stop_recording()

        if self.cap is not None:
            self.cap.release()

        if self.capture_thread is not None and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)

        # Timer stoppen
        if self.update_timer is not None:
            self.update_timer.stop()

        # Event weiterleiten
        super().closeEvent(event)


def main():
    """Hauptfunktion"""
    # Prüfen, ob ffmpeg installiert ist
    try:
        process = subprocess.run(
            ["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if process.returncode != 0:
            print(
                "Warnung: ffmpeg ist nicht installiert oder nicht im PATH. Video- und Audio-Kombinierung funktioniert möglicherweise nicht."
            )
    except:
        print(
            "Warnung: ffmpeg scheint nicht installiert zu sein. Video- und Audio-Kombinierung funktioniert möglicherweise nicht."
        )

    # QApplication starten
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Moderne Optik

    # Hauptfenster erstellen und anzeigen
    window = WebcamZoomApp()
    window.show()

    # Anwendung ausführen
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
