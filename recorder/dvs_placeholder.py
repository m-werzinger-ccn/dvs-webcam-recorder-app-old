#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Platzhalter für die DVS-Kamera-Integration.
Diese Datei würde später durch tatsächliche Metavision-Integration ersetzt werden.
"""

import os
import cv2
import time
import datetime
import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QMessageBox
from config import DEFAULT_VIDEO_EXTENSION


class DVSRecorder(QThread):
    """Thread für die DVS-Kamera-Aufnahme (Platzhalter)"""
    update_frame = pyqtSignal(QImage)
    error_signal = pyqtSignal(str)
    
    def __init__(self, save_dir="", file_name=""):
        super().__init__()
        self.save_dir = save_dir
        self.file_name = file_name
        self.running = False
        self.recording = False
        self.frame_count = 0
        
        # Dummy-Bild für simulierte DVS-Kamera
        self.frame_size = (640, 480)
        self.frame = np.zeros((self.frame_size[1], self.frame_size[0], 3), dtype=np.uint8)
        
        # Für MP4-Videoaufnahme (für Demonstrationszwecke)
        self.video_writer = None
    
    def run(self):
        """Hauptschleife für die simulierte DVS-Kamera"""
        try:
            self.running = True
            self.error_signal.emit("DVS-Kamera ist nur ein Platzhalter - nur simulierte Aufnahme möglich")
            
            while self.running:
                # Simuliertes DVS-Bild erstellen (schwarz mit zufälligen weißen Punkten)
                self.frame_count += 1
                frame = self.frame.copy()
                
                # Zufällige "Ereignisse" generieren (typisch für DVS-Kameras)
                for _ in range(100):
                    x = np.random.randint(0, self.frame_size[0])
                    y = np.random.randint(0, self.frame_size[1])
                    # Positive Events (weiß) und negative Events (grün)
                    color = (255, 255, 255) if np.random.rand() > 0.5 else (0, 255, 0)
                    cv2.circle(frame, (x, y), 1, color, -1)
                
                # Text und Timestamp hinzufügen
                cv2.putText(frame, "DVS-Kamera Simulation", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                          1, (255, 255, 255), 2)
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                cv2.putText(frame, timestamp, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 
                          0.5, (255, 255, 255), 1)
                
                # Aufnahmestatus anzeigen
                if self.recording:
                    cv2.putText(frame, "● REC", (550, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                              1, (0, 0, 255), 2)
                    
                    # Tatsächliches Video speichern (inklusive Visualisierung für Demonstrationszwecke)
                    if self.video_writer is not None:
                        self.video_writer.write(frame)
                
                # Frame für die GUI konvertieren
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                # Signal mit dem aktuellen Frame senden
                self.update_frame.emit(qt_image)
                
                # Kurze Pause für bessere Performance
                time.sleep(0.033)  # ~30 FPS
                
        except Exception as e:
            self.error_signal.emit(f"Fehler bei der DVS-Kamera-Simulation: {e}")
            print(f"Fehler bei der DVS-Kamera-Simulation: {e}")
    
    def start_recording(self, save_dir=None, file_name=None):
        """Startet die simulierte DVS-Aufnahme"""
        if not self.running or self.recording:
            return False
        
        # Verwende die übergebenen Werte oder behalte die vorhandenen bei
        if save_dir:
            self.save_dir = save_dir
        if file_name:
            self.file_name = file_name
            
        if not self.save_dir or not self.file_name:
            QMessageBox.warning(None, "Warnung", "Kein Speicherort oder Dateiname angegeben!")
            return False
        
        # Sicherstellen, dass der Speicherordner existiert
        os.makedirs(self.save_dir, exist_ok=True)
        
        # Vollständigen Pfad erstellen
        raw_file_path = os.path.join(self.save_dir, f"{self.file_name}.raw")
        video_file_path = os.path.join(self.save_dir, f"{self.file_name}_vis{DEFAULT_VIDEO_EXTENSION}")
        
        # In einem echten Szenario würde hier die DVS-Kamera mit der Metavision-API initialisiert
        print(f"Simulierte DVS-Aufnahme gestartet. Würde RAW-Daten in {raw_file_path} speichern.")
        
        # Video-Schreiber für die Visualisierung initialisieren
        try:
            # Für MP4 verwenden wir H.264-Codec
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(video_file_path, fourcc, 30.0, self.frame_size)
            
            # Fallback auf andere Codecs, falls mp4v nicht funktioniert
            if not self.video_writer.isOpened():
                fourcc = cv2.VideoWriter_fourcc(*'X264')
                self.video_writer = cv2.VideoWriter(video_file_path, fourcc, 30.0, self.frame_size)
                
                if not self.video_writer.isOpened():
                    video_file_path = video_file_path.replace(".mp4", ".avi")
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    self.video_writer = cv2.VideoWriter(video_file_path, fourcc, 30.0, self.frame_size)
                    print("Warnung: MP4-Codec nicht verfügbar, verwende AVI mit XVID-Codec")
            
            self.recording = True
            return True
            
        except Exception as e:
            print(f"Fehler beim Erstellen des VideoWriters für DVS-Visualisierung: {e}")
            self.video_writer = None
            return False
    
    def stop_recording(self):
        """Stoppt die simulierte DVS-Aufnahme"""
        if self.recording:
            self.recording = False
            print("Simulierte DVS-Aufnahme gestoppt.")
            
            # Video-Writer schließen
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
            
            return True
        return False
    
    def stop(self):
        """Stoppt den Thread"""
        self.running = False
        if self.recording:
            self.stop_recording()
        
        self.wait()