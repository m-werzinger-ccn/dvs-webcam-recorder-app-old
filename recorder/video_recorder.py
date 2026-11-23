#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
VideoRecorder mit digitalem Zoom für DVS-Kompatibilität.
Ermöglicht Software-Zoom der Webcam, um den Bildausschnitt der DVS-Kamera anzupassen.
"""

import os
import cv2
import time
import datetime
import threading
import numpy as np
import wave
import subprocess
import tempfile
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QMessageBox
import config

# PyAudio optional importieren
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("PyAudio nicht verfügbar - Audio-Aufnahme deaktiviert")


class AudioRecorder(QThread):
    """Thread für die Audioaufnahme mit präzisem Timing"""

    def __init__(self, audio_file_path, channels=1, rate=44100, chunk=1024):
        super().__init__()
        self.audio_file_path = audio_file_path
        self.channels = channels
        self.rate = rate
        self.chunk = chunk
        self.recording = False
        self.frames = []
        self.start_time = None

        self.pyaudio = None
        self.stream = None

    def set_start_time(self, start_time):
        """Setzt den gemeinsamen Startzeitpunkt"""
        self.start_time = start_time

    def run(self):
        """Startet die Audioaufnahme im eigenen Thread"""
        if not PYAUDIO_AVAILABLE:
            print("PyAudio nicht verfügbar - Audio-Aufnahme übersprungen")
            return

        try:
            self.pyaudio = pyaudio.PyAudio()

            self.stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )

            while self.start_time is None and not self.recording:
                time.sleep(0.001)

            self.recording = True
            print("Audioaufnahme gestartet...")
            self.frames = []

            while self.recording:
                try:
                    data = self.stream.read(self.chunk, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception as e:
                    print(f"Fehler beim Audio-Frame-Lesen: {e}")

            self.save_audio()

        except Exception as e:
            print(f"Fehler bei der Audioaufnahme: {e}")
        finally:
            self.cleanup()

    def stop(self):
        """Stoppt die Audioaufnahme"""
        self.recording = False
        self.wait()

    def save_audio(self):
        """Speichert die aufgenommenen Audiodaten"""
        if not PYAUDIO_AVAILABLE or self.pyaudio is None:
            return

        try:
            os.makedirs(os.path.dirname(self.audio_file_path), exist_ok=True)

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


class ExternalAudioRecorder(QThread):
    """Thread für die Audioaufnahme über ein externes USB-Mikrofon"""

    recording_finished = pyqtSignal(bool, str)  # Erfolg, Pfad/Fehlermeldung

    def __init__(self, audio_file_path, device_index, channels=None, rate=None, chunk=1024):
        super().__init__()
        self.audio_file_path = audio_file_path
        self.device_index = device_index  # Spezifisches USB-Mikrofon
        self.channels = channels  # None = automatisch vom Gerät ermitteln
        self.rate = rate  # None = automatisch vom Gerät ermitteln
        self.chunk = chunk
        self.recording = False
        self.frames = []
        self.start_time = None

        self.pyaudio = None
        self.stream = None

    def set_start_time(self, start_time):
        """Setzt den gemeinsamen Startzeitpunkt für Synchronisation"""
        self.start_time = start_time

    def run(self):
        """Startet die Audioaufnahme im eigenen Thread"""
        if not PYAUDIO_AVAILABLE:
            print("PyAudio nicht verfügbar - Externe Audio-Aufnahme übersprungen")
            self.recording_finished.emit(False, "PyAudio nicht installiert")
            return

        try:
            self.pyaudio = pyaudio.PyAudio()

            # Geräteinformationen abrufen und native Einstellungen verwenden
            try:
                device_info = self.pyaudio.get_device_info_by_index(self.device_index)
                device_name = device_info.get('name', 'Unbekannt')

                # Kanäle vom Gerät übernehmen wenn nicht explizit angegeben
                if self.channels is None:
                    self.channels = int(device_info.get('maxInputChannels', 2))

                if self.rate is None:
                    self.rate = 41100  # Native Rate für die meisten USB-Mikrofone

                print(f"Externes Mikrofon: {device_name}")
                print(f"  Kanäle: {self.channels}, Sample-Rate: {self.rate} Hz")

            except Exception as e:
                print(f"Fehler beim Abrufen der Geräteinformationen: {e}")
                self.recording_finished.emit(False, f"Mikrofon nicht verfügbar: {e}")
                return

            # Stream mit spezifischem Gerät und korrekten Parametern öffnen
            # Versuche zuerst höhere Raten (Yeti unterstützt bis 96 kHz)
            rates_to_try = [96000, 48000, 44100, 32000, 22050, 16000]
            stream_opened = False

            for rate in rates_to_try:
                try:
                    self.stream = self.pyaudio.open(
                        format=pyaudio.paInt16,
                        channels=self.channels,
                        rate=rate,
                        input=True,
                        input_device_index=self.device_index,
                        frames_per_buffer=self.chunk,
                    )
                    self.rate = rate  # Tatsächlich verwendete Rate speichern
                    stream_opened = True
                    print(f"  Stream geöffnet mit {rate} Hz")
                    break
                except Exception as e:
                    print(f"  Rate {rate} Hz fehlgeschlagen")
                    continue

            if not stream_opened:
                raise Exception("Keine unterstützte Sample-Rate gefunden")

            # Warten auf start_time (Synchronisation mit Video)
            while self.start_time is None and not self.recording:
                time.sleep(0.001)

            self.recording = True
            print(f"Externe Audioaufnahme gestartet (Gerät {self.device_index})...")
            self.frames = []

            while self.recording:
                try:
                    data = self.stream.read(self.chunk, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception as e:
                    print(f"Fehler beim Audio-Frame-Lesen (extern): {e}")

            self.save_audio()

        except Exception as e:
            print(f"Fehler bei der externen Audioaufnahme: {e}")
            self.recording_finished.emit(False, str(e))
        finally:
            self.cleanup()

    def stop(self):
        """Stoppt die Audioaufnahme"""
        self.recording = False
        self.wait()

    def save_audio(self):
        """Speichert die aufgenommenen Audiodaten als WAV"""
        if not PYAUDIO_AVAILABLE or self.pyaudio is None:
            return

        try:
            os.makedirs(os.path.dirname(self.audio_file_path), exist_ok=True)

            # Diagnose: Berechne die tatsächliche Dauer
            total_bytes = sum(len(f) for f in self.frames)
            bytes_per_sample = 2  # 16-bit = 2 bytes
            total_samples = total_bytes // (bytes_per_sample * self.channels)
            calculated_duration = total_samples / self.rate
            print(f"  Audio-Diagnose:")
            print(f"    Frames: {len(self.frames)}, Total Bytes: {total_bytes}")
            print(f"    Kanäle: {self.channels}, Rate: {self.rate} Hz")
            print(f"    Samples: {total_samples}, Berechnete Dauer: {calculated_duration:.2f}s")

            wf = wave.open(self.audio_file_path, "wb")
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.pyaudio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.rate)
            wf.writeframes(b"".join(self.frames))
            wf.close()

            print(f"Externe Audiodatei gespeichert: {self.audio_file_path}")
            self.recording_finished.emit(True, self.audio_file_path)

        except Exception as e:
            print(f"Fehler beim Speichern der externen Audiodatei: {e}")
            self.recording_finished.emit(False, str(e))

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
            print(f"Fehler beim Freigeben der externen Audio-Ressourcen: {e}")


class VideoProcessingWorker(QObject):
    """Worker-Klasse für die Video-/Audio-Verarbeitung"""

    processing_finished = pyqtSignal(bool, str)
    processing_progress = pyqtSignal(str)
    processing_completed = pyqtSignal()

    def __init__(
        self,
        temp_video_path,
        temp_audio_path,
        final_output_path,
        has_audio,
        actual_fps=None,
    ):
        super().__init__()
        self.temp_video_path = temp_video_path
        self.temp_audio_path = temp_audio_path
        self.final_output_path = final_output_path
        self.has_audio = has_audio
        self.actual_fps = actual_fps

    def process_video(self):
        """Verarbeitet Video und Audio in einem separaten Thread"""
        try:
            self.processing_progress.emit("Verarbeite Video und Audio...")

            if (
                self.has_audio
                and os.path.exists(self.temp_video_path)
                and os.path.exists(self.temp_audio_path)
            ):
                success = self.combine_video_audio()
                if success:
                    self.processing_progress.emit(
                        "Video mit Audio erfolgreich kombiniert"
                    )
                    self.processing_finished.emit(
                        True,
                        f"Video mit Audio erfolgreich kombiniert: {self.final_output_path}",
                    )
                    self.processing_completed.emit()
                else:
                    self.processing_progress.emit(
                        "Fehler beim Kombinieren - kopiere nur Video"
                    )
                    self.convert_video_only()
                    self.processing_finished.emit(
                        True, f"Nur Video konvertiert: {self.final_output_path}"
                    )
                    self.processing_completed.emit()
            else:
                if os.path.exists(self.temp_video_path):
                    self.processing_progress.emit("Konvertiere Video...")
                    self.convert_video_only()
                    self.processing_finished.emit(
                        True, f"Video konvertiert: {self.final_output_path}"
                    )
                    self.processing_completed.emit()
                else:
                    self.processing_finished.emit(False, "Keine Videodatei gefunden")

            self.cleanup_temp_files()

        except Exception as e:
            self.processing_finished.emit(False, f"Fehler bei der Verarbeitung: {e}")
            import traceback

            traceback.print_exc()

    def convert_video_only(self):
        """Konvertiert nur das Video ohne Audio"""
        try:
            try:
                subprocess.run(
                    ["ffmpeg", "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            except:
                print("FFmpeg nicht gefunden. Versuche direkte Kopie...")
                import shutil

                shutil.copy(self.temp_video_path, self.final_output_path)
                return

            fps = self.actual_fps if self.actual_fps else config.DEFAULT_FPS

            codecs_to_try = ["libx264", "mp4v", "h264"]

            for codec in codecs_to_try:
                try:
                    print(f"Versuche Konvertierung mit Codec {codec}, FPS: {fps}...")
                    cmd = [
                        "ffmpeg",
                        "-r",
                        str(fps),
                        "-i",
                        self.temp_video_path,
                        "-c:v",
                        codec,
                        "-r",
                        str(fps),
                        "-vf",
                        "format=yuv420p",
                        "-y",
                        self.final_output_path,
                    ]

                    process = subprocess.run(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )

                    if (
                        process.returncode == 0
                        and os.path.exists(self.final_output_path)
                        and os.path.getsize(self.final_output_path) > 0
                    ):
                        print(f"Video erfolgreich mit {codec} konvertiert")
                        return
                except Exception as e:
                    print(f"Fehler bei der Konvertierung mit {codec}: {e}")

            # Fallback
            try:
                import shutil

                self.final_output_path = os.path.join(
                    os.path.dirname(self.final_output_path),
                    os.path.splitext(os.path.basename(self.final_output_path))[0]
                    + ".avi",
                )
                shutil.copy(self.temp_video_path, self.final_output_path)
            except Exception as e:
                print(f"Fehler beim Kopieren: {e}")

        except Exception as e:
            print(f"Fehler bei der Video-Konvertierung: {e}")

    def combine_video_audio(self):
        """Kombiniert Video und Audio mit verbesserter Synchronisation"""
        try:
            try:
                subprocess.run(
                    ["ffmpeg", "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            except:
                print("FFmpeg nicht gefunden")
                return False

            fps = self.actual_fps if self.actual_fps else config.DEFAULT_FPS

            configs = [
                [
                    "ffmpeg",
                    "-r",
                    str(fps),
                    "-i",
                    self.temp_video_path,
                    "-i",
                    self.temp_audio_path,
                    "-c:v",
                    "libx264",
                    "-r",
                    str(fps),
                    "-vf",
                    "format=yuv420p",
                    "-c:a",
                    "aac",
                    "-strict",
                    "experimental",
                    "-async",
                    "1",
                    "-vsync",
                    "cfr",
                    "-y",
                    self.final_output_path,
                ],
                [
                    "ffmpeg",
                    "-r",
                    str(fps),
                    "-i",
                    self.temp_video_path,
                    "-i",
                    self.temp_audio_path,
                    "-c:v",
                    "libx264",
                    "-r",
                    str(fps),
                    "-vf",
                    "format=yuv420p,setpts=PTS-STARTPTS",
                    "-c:a",
                    "aac",
                    "-af",
                    "asetpts=PTS-STARTPTS",
                    "-strict",
                    "experimental",
                    "-y",
                    self.final_output_path,
                ],
            ]

            for i, cmd in enumerate(configs):
                print(f"Versuche FFmpeg-Methode {i+1}...")
                process = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

                if (
                    process.returncode == 0
                    and os.path.exists(self.final_output_path)
                    and os.path.getsize(self.final_output_path) > 0
                ):
                    print(f"Video und Audio erfolgreich kombiniert (Methode {i+1})")
                    return True
                else:
                    error_msg = process.stderr.decode()
                    print(f"FFmpeg-Fehler (Methode {i+1}): {error_msg}")

            return False

        except Exception as e:
            print(f"Fehler beim Kombinieren von Video und Audio: {e}")
            return False

    def cleanup_temp_files(self):
        """Löscht temporäre Dateien"""
        try:
            if os.path.exists(self.temp_video_path):
                os.remove(self.temp_video_path)
                print(f"Temporäre Videodatei gelöscht")

            if os.path.exists(self.temp_audio_path):
                os.remove(self.temp_audio_path)
                print(f"Temporäre Audiodatei gelöscht")
        except Exception as e:
            print(f"Fehler beim Löschen der temporären Dateien: {e}")


class VideoRecorder(QThread):
    """Thread für die Videoaufnahme mit digitalem Zoom"""

    update_frame = pyqtSignal(QImage)
    error_signal = pyqtSignal(str)
    processing_status = pyqtSignal(str)
    video_processing_completed = pyqtSignal()
    zoom_changed = pyqtSignal(float)  # NEU: Signal für Zoom-Änderungen

    def __init__(self, camera_id=0, save_dir="", file_name="", audio_enabled=True):
        super().__init__()
        self.camera_id = camera_id
        self.save_dir = save_dir
        self.file_name = file_name
        self.running = False
        self.recording = False
        self.video_writer = None
        self.cap = None

        # Audio-Recorder
        self.audio_recorder = None
        self.has_audio = audio_enabled
        self.temp_video_path = ""
        self.temp_audio_path = ""
        self.final_output_path = ""

        # Timing-Variablen
        self.start_time = None
        self.frame_count = 0
        self.target_fps = config.DEFAULT_FPS
        self.actual_fps = None

        # NEU: Zoom-Parameter
        self.zoom_factor = 1.5  # Standard-Zoom (1.0 = kein Zoom, 2.0 = 2x Zoom)
        self.zoom_enabled = True  # Zoom standardmäßig aktiviert

        # Mutex
        self.mutex = threading.Lock()

        # Worker Thread
        self.processing_thread = None
        self.processing_worker = None

        # Dummy-Frame mit DVS-Auflösung
        self.dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.putText(
            self.dummy_frame,
            "Keine Kamera verfügbar",
            (400, 360),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (255, 255, 255),
            2,
        )

    def set_zoom(self, zoom_factor):
        """Setzt den Zoom-Faktor (1.0 = kein Zoom, 2.0 = 2x Zoom)"""
        with self.mutex:
            self.zoom_factor = max(1.0, min(3.0, zoom_factor))  # Begrenzt auf 1.0-3.0
            print(f"Zoom-Faktor gesetzt auf: {self.zoom_factor:.2f}x")
            self.zoom_changed.emit(self.zoom_factor)

    def set_zoom_enabled(self, enabled):
        """Aktiviert oder deaktiviert den Zoom"""
        with self.mutex:
            self.zoom_enabled = enabled
            print(f"Zoom {'aktiviert' if enabled else 'deaktiviert'}")

    def apply_zoom(self, frame):
        """Wendet digitalen Zoom auf ein Frame an"""
        if not self.zoom_enabled or self.zoom_factor <= 1.0:
            return frame

        h, w = frame.shape[:2]

        # Berechne den neuen Bildausschnitt (zentriert)
        new_w = int(w / self.zoom_factor)
        new_h = int(h / self.zoom_factor)

        # Zentrierter Ausschnitt
        x = (w - new_w) // 2
        y = (h - new_h) // 2

        # Bild ausschneiden
        cropped = frame[y : y + new_h, x : x + new_w]

        # Auf Original-Größe hochskalieren
        zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

        return zoomed

    def run(self):
        """Hauptschleife mit präzisem Timing und Zoom"""
        try:
            self.running = True
            self.open_camera()

            frame_interval = 1.0 / self.target_fps
            next_frame_time = time.perf_counter()

            while self.running:
                try:
                    current_time = time.perf_counter()

                    if current_time >= next_frame_time:
                        # Frame abrufen
                        if self.cap is not None and self.cap.isOpened():
                            ret, frame = self.cap.read()
                        else:
                            ret = False

                        if not ret:
                            frame = self.dummy_frame.copy()
                            if (
                                not hasattr(self, "last_reconnect")
                                or time.time() - self.last_reconnect > 5.0
                            ):
                                self.last_reconnect = time.time()
                                self.reopen_camera()
                        else:
                            # NEU: Zoom anwenden
                            frame = self.apply_zoom(frame)

                        # Frame aufnehmen wenn Recording aktiv
                        with self.mutex:
                            if self.recording and self.video_writer is not None and ret:
                                self.video_writer.write(frame)
                                self.frame_count += 1

                        # Frame für GUI
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb_frame.shape
                        bytes_per_line = ch * w
                        qt_image = QImage(
                            rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888
                        )
                        self.update_frame.emit(qt_image)

                        next_frame_time += frame_interval

                        if current_time > next_frame_time + frame_interval:
                            next_frame_time = current_time + frame_interval

                    else:
                        time.sleep(0.001)

                except Exception as e:
                    print(f"Fehler in der Videoschleife: {e}")
                    rgb_frame = cv2.cvtColor(self.dummy_frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_frame.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(
                        rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888
                    )
                    self.update_frame.emit(qt_image)
                    time.sleep(0.033)

        except Exception as e:
            self.error_signal.emit(f"Kritischer Fehler: {e}")
            print(f"Kritischer Fehler: {e}")
        finally:
            self.cleanup_resources()

    def start_recording(self, save_dir=None, file_name=None):
        """Startet die Videoaufnahme"""
        if not self.running:
            return False

        with self.mutex:
            if self.recording:
                return False

        if save_dir:
            self.save_dir = save_dir
        if file_name:
            self.file_name = file_name

        if not self.save_dir or not self.file_name:
            self.error_signal.emit("Kein Speicherort oder Dateiname angegeben!")
            return False

        if self.cap is None or not self.cap.isOpened():
            self.error_signal.emit("Keine Kamera verfügbar!")
            return False

        try:
            os.makedirs(self.save_dir, exist_ok=True)

            temp_dir = tempfile.gettempdir()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_video_path = os.path.join(temp_dir, f"temp_video_{timestamp}.avi")
            self.temp_audio_path = os.path.join(temp_dir, f"temp_audio_{timestamp}.wav")
            self.final_output_path = os.path.join(
                self.save_dir, f"{self.file_name}{config.DEFAULT_VIDEO_EXTENSION}"
            )

            # Frame-Größe (nach Zoom!)
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if width <= 0 or height <= 0:
                print(
                    "Warnung: Ungültige Frame-Größe, verwende DVS-Standard (1280x720)"
                )
                width, height = 1280, 720

            frame_size = (width, height)

            fourcc = cv2.VideoWriter_fourcc(*"MJPG")

            try:
                with self.mutex:
                    self.video_writer = cv2.VideoWriter(
                        self.temp_video_path, fourcc, self.target_fps, frame_size
                    )

                    if not self.video_writer.isOpened():
                        raise Exception("Video Writer konnte nicht geöffnet werden")

                    self.start_time = time.perf_counter()
                    self.frame_count = 0

                    if self.has_audio:
                        self.audio_recorder = AudioRecorder(self.temp_audio_path)
                        self.audio_recorder.set_start_time(self.start_time)
                        self.audio_recorder.start()
                        print(f"Audio aktiviert")

                    self.recording = True
                    print(f"Aufnahme gestartet mit Zoom {self.zoom_factor:.2f}x")
                    return True

            except Exception as e:
                print(f"Fehler beim Starten: {e}")
                self.error_signal.emit(f"Fehler: {e}")
                with self.mutex:
                    if self.video_writer is not None:
                        self.video_writer.release()
                        self.video_writer = None
                    if self.audio_recorder is not None:
                        self.audio_recorder.stop()
                        self.audio_recorder = None
                return False

        except Exception as e:
            self.error_signal.emit(f"Fehler: {e}")
            return False

    def stop_recording(self):
        """Stoppt die Aufnahme"""
        try:
            with self.mutex:
                if not self.recording:
                    return False

                self.recording = False

                if self.start_time and self.frame_count > 0:
                    duration = time.perf_counter() - self.start_time
                    self.actual_fps = self.frame_count / duration
                    print(
                        f"Aufnahme: {self.frame_count} Frames in {duration:.2f}s = {self.actual_fps:.2f} FPS"
                    )
                else:
                    self.actual_fps = self.target_fps

                if self.video_writer is not None:
                    self.video_writer.release()
                    self.video_writer = None

                if self.has_audio and self.audio_recorder is not None:
                    self.audio_recorder.stop()

                self.start_video_processing()
                return True

        except Exception as e:
            self.error_signal.emit(f"Fehler beim Stoppen: {e}")
            self.recording = False
            return False

    def start_video_processing(self):
        """Startet die Verarbeitung"""
        try:
            self.processing_worker = VideoProcessingWorker(
                self.temp_video_path,
                self.temp_audio_path,
                self.final_output_path,
                self.has_audio,
                self.actual_fps,
            )

            self.processing_thread = QThread()
            self.processing_worker.moveToThread(self.processing_thread)

            self.processing_worker.processing_progress.connect(
                self.processing_status.emit
            )
            self.processing_worker.processing_finished.connect(
                self.on_processing_finished
            )
            self.processing_worker.processing_completed.connect(
                self.video_processing_completed.emit
            )
            self.processing_thread.started.connect(self.processing_worker.process_video)

            self.processing_thread.start()
            print("Video-Verarbeitung gestartet")

        except Exception as e:
            print(f"Fehler beim Starten der Verarbeitung: {e}")
            self.error_signal.emit(f"Fehler: {e}")

    def on_processing_finished(self, success, message):
        """Wird nach Verarbeitung aufgerufen"""
        try:
            if success:
                print(f"Verarbeitung erfolgreich: {message}")
                self.processing_status.emit("Video erfolgreich gespeichert")
            else:
                print(f"Verarbeitung fehlgeschlagen: {message}")
                self.error_signal.emit(f"Verarbeitung fehlgeschlagen: {message}")

            if self.processing_thread:
                self.processing_thread.quit()
                self.processing_thread.wait()
                self.processing_thread = None

            self.processing_worker = None

        except Exception as e:
            print(f"Fehler beim Abschließen: {e}")

    def open_camera(self):
        """Öffnet die Kamera mit DVS-kompatibler Auflösung"""
        try:
            if self.cap is not None:
                self.cap.release()
                self.cap = None

            # V4L2 Backend explizit verwenden um GStreamer-Konflikte zu vermeiden
            self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_V4L2)

            if not self.cap.isOpened():
                # Fallback: ohne spezifisches Backend versuchen
                print(f"V4L2-Backend fehlgeschlagen, versuche Standard-Backend...")
                self.cap = cv2.VideoCapture(self.camera_id)

            if not self.cap.isOpened():
                self.error_signal.emit(
                    f"Kamera {self.camera_id} konnte nicht geöffnet werden!"
                )
                return False

            # Auflösung auf DVS-Format setzen
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)

            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

            print(f"Kamera {self.camera_id} geöffnet:")
            print(f"  Auflösung: {actual_width}x{actual_height}")
            print(f"  FPS: {actual_fps}")
            print(f"  Zoom: {self.zoom_factor:.2f}x")

            if actual_width != 1280 or actual_height != 720:
                print(
                    f"  HINWEIS: Kamera unterstützt 1280x720 nicht, verwende {actual_width}x{actual_height}"
                )

            return True

        except Exception as e:
            self.error_signal.emit(f"Fehler beim Öffnen der Kamera: {e}")
            return False

    def reopen_camera(self):
        """Versucht Kamera neu zu öffnen"""
        return self.open_camera()

    def set_audio_enabled(self, enabled):
        """Audio aktivieren/deaktivieren"""
        self.has_audio = enabled

    def stop(self):
        """Stoppt den Thread"""
        self.running = False
        if self.recording:
            self.stop_recording()
        self.wait()
        self.cleanup_resources()

    def cleanup_resources(self):
        """Gibt Ressourcen frei"""
        try:
            if hasattr(self, "video_writer") and self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None

            if hasattr(self, "audio_recorder") and self.audio_recorder is not None:
                self.audio_recorder.stop()
                self.audio_recorder = None

            if hasattr(self, "cap") and self.cap is not None:
                self.cap.release()
                self.cap = None

            if (
                hasattr(self, "processing_thread")
                and self.processing_thread is not None
            ):
                self.processing_thread.quit()
                self.processing_thread.wait()
                self.processing_thread = None

        except Exception as e:
            print(f"Fehler beim Freigeben der Ressourcen: {e}")
