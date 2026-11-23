#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hilfsfunktionen für die Webcam-Aufnahme-Anwendung.
"""

import os
import sys
import cv2
import time
import subprocess
import shutil
import numpy as np

# Import von config-Werten ohne zirkulären Import
from config import APP_NAME, APP_ICON

# PyAudio für Mikrofon-Erkennung
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("PyAudio nicht verfügbar - Mikrofon-Erkennung deaktiviert")


def create_desktop_shortcut():
    """Erstellt eine Desktop-Verknüpfung für die Anwendung"""
    # Unterstützung für verschiedene Desktop-Namen (Englisch und Deutsch)
    potential_desktop_paths = [
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "Schreibtisch"),
    ]

    desktop_path = None
    for path in potential_desktop_paths:
        if os.path.exists(path) and os.path.isdir(path):
            desktop_path = path
            break

    if desktop_path is None:
        print("Desktop-Verzeichnis konnte nicht gefunden werden.")
        desktop_path = os.path.expanduser("~")  # Fallback auf Home-Verzeichnis

    shortcut_path = os.path.join(desktop_path, "WebcamRecorder.desktop")

    # Aktuellen Pfad der Anwendung
    app_path = os.path.abspath(sys.argv[0])

    with open(shortcut_path, "w") as f:
        f.write(
            f"""[Desktop Entry]
Version=1.0
Type=Application
Name={APP_NAME}
Comment=Aufnahme von Webcam-Videos
Exec=python3 {app_path}
Icon={APP_ICON}
Terminal=false
Categories=Video;AudioVideo;
"""
        )

    # Ausführbar machen
    os.chmod(shortcut_path, 0o755)
    return shortcut_path


def get_available_cameras():
    """Ermittelt verfügbare Kameras und gibt eine Liste mit IDs und tatsächlichen Namen zurück"""
    available_cameras = []
    ugreen_camera = None  # Variable für UGREEN-Kamera

    try:
        # Kameranamen über v4l2 ermitteln (Linux-spezifisch)
        camera_names = get_v4l2_camera_names()

        # Verfügbare Videogeräte finden
        cameras_from_sys = list_video_devices_from_system()

        # Wenn wir Geräte über das System gefunden haben, testen wir diese
        if cameras_from_sys:
            for idx in cameras_from_sys:
                try:
                    cap = cv2.VideoCapture(idx)
                    # Kurz warten, damit die Kamera Zeit hat sich zu initialisieren
                    time.sleep(0.1)

                    if cap.isOpened():
                        # Ein Frame lesen, um sicherzustellen, dass die Kamera funktioniert
                        ret, _ = cap.read()
                        if ret:
                            # Kameranamen aus v4l2 verwenden, falls verfügbar
                            if idx in camera_names:
                                camera_info = (idx, camera_names[idx])
                                # ÄNDERUNG: Prüfen, ob es eine UGREEN-Kamera ist
                                if "ugreen" in camera_names[idx].lower():
                                    ugreen_camera = camera_info
                                else:
                                    available_cameras.append(camera_info)
                            else:
                                # Fallback zum generischen Namen
                                camera_info = (idx, f"Kamera {idx}")
                                available_cameras.append(camera_info)
                        cap.release()
                except Exception as e:
                    print(f"Fehler beim Testen von Kamera {idx}: {e}")

        # Wenn wir keine Kameras gefunden haben, versuchen wir einen alternativen Ansatz
        if not available_cameras and not ugreen_camera:
            # Testen von einigen üblichen Indizes (0-9)
            for idx in range(10):
                try:
                    if idx not in [
                        cam[0] for cam in available_cameras
                    ]:  # Vermeiden von Duplikaten
                        cap = cv2.VideoCapture(idx)
                        time.sleep(0.1)  # Kurz warten

                        if cap.isOpened():
                            ret, _ = cap.read()
                            if ret:
                                if idx in camera_names:
                                    camera_info = (idx, camera_names[idx])
                                    # ÄNDERUNG: Prüfen, ob es eine UGREEN-Kamera ist
                                    if "ugreen" in camera_names[idx].lower():
                                        ugreen_camera = camera_info
                                    else:
                                        available_cameras.append(camera_info)
                                else:
                                    camera_info = (idx, f"Kamera {idx}")
                                    available_cameras.append(camera_info)
                            cap.release()
                except Exception as e:
                    print(f"Fehler beim Testen von Kamera {idx}: {e}")

    except Exception as e:
        print(f"Fehler bei der Kameraerkennung: {e}")

    # ÄNDERUNG: UGREEN-Kamera an den Anfang der Liste setzen, falls gefunden
    final_cameras = []
    if ugreen_camera:
        final_cameras.append(ugreen_camera)
        print(f"UGREEN-Kamera gefunden und als Standard gesetzt: {ugreen_camera[1]}")

    # Alle anderen Kameras hinzufügen
    final_cameras.extend(available_cameras)

    return final_cameras


def get_v4l2_camera_names():
    """Ermittelt die tatsächlichen Namen der Kameras über v4l2-ctl (Linux-spezifisch)"""
    camera_names = {}

    try:
        # Prüfen, ob wir unter Linux arbeiten
        if not os.path.exists("/dev/video0"):
            return camera_names

        # Versuchen, v4l2-ctl zu nutzen
        import subprocess

        # Liste aller Videodeivces abrufen
        result = subprocess.run(
            ["v4l2-ctl", "--list-devices"], capture_output=True, text=True, check=False
        )

        if result.returncode == 0:
            # Ausgabe parsen
            current_name = None
            lines = result.stdout.strip().split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if not line.startswith("/dev/video"):
                    # Das ist ein Kameraname
                    current_name = line
                elif current_name and line.startswith("/dev/video"):
                    # Das ist ein Gerätepfad
                    try:
                        # Extrahiere die Nummer aus dem Pfad
                        dev_idx = int(line.replace("/dev/video", ""))
                        camera_names[dev_idx] = current_name
                    except ValueError:
                        pass
        else:
            # Alternativer Ansatz: Direkt aus dem Dateisystem lesen
            for device in os.listdir("/dev"):
                if device.startswith("video"):
                    try:
                        idx = int(
                            device[5:]
                        )  # Extrahiere Nummer aus 'video0', 'video1', etc.

                        # Versuche, den Namen aus /sys/class/video4linux zu lesen
                        name_path = f"/sys/class/video4linux/{device}/name"
                        if os.path.exists(name_path):
                            with open(name_path, "r") as f:
                                name = f.read().strip()
                                if name:
                                    camera_names[idx] = name
                    except (ValueError, IOError) as e:
                        print(f"Fehler beim Lesen des Kamernamens für {device}: {e}")

    except Exception as e:
        print(f"Fehler beim Abrufen der Kameranamen via v4l2: {e}")

    return camera_names


def list_video_devices_from_system():
    """Ermittelt verfügbare Videogeräte über das Betriebssystem"""
    video_devices = []

    try:
        # Prüfen auf Linux-System
        if os.path.exists("/dev"):
            # Suche nach Videogeräten in /dev
            for device in os.listdir("/dev"):
                if device.startswith("video"):
                    try:
                        # Extrahiere die Nummer aus "video0", "video1", etc.
                        idx = int(device[5:])
                        video_devices.append(idx)
                    except ValueError:
                        continue
    except Exception as e:
        print(f"Fehler beim Auflisten der Videogeräte: {e}")

    return video_devices


def check_available_codecs():
    """Überprüft, welche Videocodecs auf dem System verfügbar sind"""
    available_codecs = []

    # Liste der zu testenden Codecs
    codecs_to_test = [
        ("mp4v", "MP4 (H.264)"),
        ("avc1", "MP4 (H.264 alternative)"),
        ("X264", "MP4 (X264)"),
        ("XVID", "AVI (XVID)"),
        ("MJPG", "AVI (Motion JPEG)"),
        ("DIVX", "AVI (DivX)"),
    ]

    # Temporäre Datei für Tests
    temp_dir = os.path.join(os.path.expanduser("~"), ".webcam_recorder_temp")
    os.makedirs(temp_dir, exist_ok=True)

    # Testbild erstellen (einfarbig)
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    for codec_id, codec_name in codecs_to_test:
        try:
            # Dateierweiterung basierend auf Codec bestimmen
            if codec_id in ["mp4v", "avc1", "X264"]:
                ext = ".mp4"
            else:
                ext = ".avi"

            test_file = os.path.join(temp_dir, f"test_{codec_id}{ext}")

            # VideoWriter mit diesem Codec testen
            fourcc = cv2.VideoWriter_fourcc(*codec_id)
            writer = cv2.VideoWriter(test_file, fourcc, 30.0, (640, 480))

            if writer.isOpened():
                # Ein Frame schreiben und Writer schließen
                writer.write(test_frame)
                writer.release()

                # Prüfen, ob die Datei existiert und größer als 0 Bytes ist
                if os.path.exists(test_file) and os.path.getsize(test_file) > 0:
                    available_codecs.append((codec_id, codec_name, ext))

                # Testdatei löschen
                if os.path.exists(test_file):
                    os.remove(test_file)

        except Exception as e:
            print(f"Codec {codec_id} nicht verfügbar: {e}")

    # Temporäres Verzeichnis aufräumen
    try:
        shutil.rmtree(temp_dir)
    except:
        pass

    return available_codecs


def get_best_codec():
    """Ermittelt den besten verfügbaren Codec für die Videoaufnahme"""
    available_codecs = check_available_codecs()

    # Priorisierte Liste von Codecs
    preferred_order = ["mp4v", "X264", "avc1", "XVID", "MJPG", "DIVX"]

    # Besten verfügbaren Codec basierend auf der Priorität finden
    for codec in preferred_order:
        for available_codec, codec_name, ext in available_codecs:
            if available_codec == codec:
                return available_codec, ext

    # Fallback auf XVID/AVI, wenn kein anderer Codec verfügbar ist
    return "XVID", ".avi"


def get_available_microphones():
    """
    Ermittelt verfügbare Audio-Input-Geräte (Mikrofone) und gibt eine Liste zurück.

    Returns:
        Liste von Tupeln: [(device_index, device_name), ...]
    """
    available_microphones = []

    if not PYAUDIO_AVAILABLE:
        print("PyAudio nicht verfügbar - keine Mikrofone erkannt")
        return available_microphones

    try:
        audio = pyaudio.PyAudio()

        # Alle Audio-Geräte durchgehen
        device_count = audio.get_device_count()
        print(f"Gefundene Audio-Geräte: {device_count}")

        for i in range(device_count):
            try:
                device_info = audio.get_device_info_by_index(i)

                # Nur Input-Geräte (Mikrofone) berücksichtigen
                max_input_channels = device_info.get('maxInputChannels', 0)

                if max_input_channels > 0:
                    device_name = device_info.get('name', f'Mikrofon {i}')

                    # Gerätename bereinigen (manchmal gibt es Encoding-Probleme)
                    try:
                        device_name = device_name.encode('utf-8', errors='ignore').decode('utf-8')
                    except:
                        device_name = f'Mikrofon {i}'

                    available_microphones.append((i, device_name))
                    print(f"  Mikrofon gefunden: [{i}] {device_name} (Kanäle: {max_input_channels})")

            except Exception as e:
                print(f"  Fehler beim Lesen von Gerät {i}: {e}")

        audio.terminate()

    except Exception as e:
        print(f"Fehler bei der Mikrofon-Erkennung: {e}")

    return available_microphones
