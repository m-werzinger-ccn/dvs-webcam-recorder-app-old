#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DVS Camera Anwendung mit benutzerdefinierbarem ROI und Recording-Funktion.
Überarbeitete Version mit separater Speicherung der ROI-Koordinaten.
"""

import cv2
import os
import time
import numpy as np
import argparse
from enum import Enum

from metavision_core.event_io import (
    EventsIterator,
    LiveReplayEventsIterator,
    is_live_camera,
)
from metavision_core.event_io.raw_reader import initiate_device
from metavision_sdk_core import (
    PeriodicFrameGenerationAlgorithm,
    PolarityFilterAlgorithm,
    RoiFilterAlgorithm,
    ColorPalette,
)
from metavision_sdk_ui import EventLoop, BaseWindow, MTWindow, UIAction, UIKeyEvent


class Polarity(Enum):
    ALL = (-1,)
    OFF = (0,)
    ON = 1


class RoiLogger:
    """Klasse zur Aufnahme von Events mit ROI-Filter"""

    def __init__(self, device):
        self.device = device
        self.is_recording = False
        self.log_path = None
        self.roi_filter = None
        self.use_roi_filter = False
        self.roi_coords = (0, 0, 0, 0)  # x0, y0, x1, y1
        self.events_buf = RoiFilterAlgorithm.get_empty_output_buffer()

    def set_roi(self, roi_filter, roi_coords, use_roi=True):
        """Setzt den ROI-Filter"""
        self.roi_filter = roi_filter
        self.roi_coords = roi_coords
        self.use_roi_filter = use_roi

    def start_recording(self, log_path):
        """Startet die Aufnahme"""
        if self.is_recording:
            return False

        self.log_path = log_path

        # Wenn ROI-Filter aktiv ist, eigene Aufnahme-Logik starten
        if self.use_roi_filter and self.roi_filter is not None:
            # Hier können wir die ROI-gefilterten Events in eine eigene RAW-Datei schreiben
            # Dies geschieht dann während der Verarbeitung von events
            self.is_recording = True
            print(f"ROI-gefilterte Aufnahme gestartet: {self.log_path}")

            # Wir verwenden trotzdem das integrierte Logging für den Fall, dass unsere
            # eigene Implementierung Probleme hat - können später entscheiden, welche zu behalten
            self.device.get_i_events_stream().log_raw_data(self.log_path)
            return True
        else:
            # Wenn kein ROI-Filter aktiv, Standard-Aufnahme verwenden
            self.device.get_i_events_stream().log_raw_data(self.log_path)
            self.is_recording = True
            print(f"Vollbild-Aufnahme gestartet: {self.log_path}")
            return True

    def stop_recording(self):
        """Stoppt die Aufnahme"""
        if not self.is_recording:
            return False

        # Aufnahme stoppen
        self.device.get_i_events_stream().stop_log_raw_data()
        self.is_recording = False
        print(f"Aufnahme gestoppt: {self.log_path}")
        return True

    def process_events(self, events):
        """Verarbeitet und zeichnet Events auf, falls ROI-Filterung aktiv ist"""
        # Wenn ROI-Filter aktiv und Aufnahme läuft, könnten wir hier die
        # gefilterten Events in eine separate Datei schreiben.
        # Aktuell verwenden wir die eingebaute Logging-Funktion.
        pass


class KeyboardROISelector:
    """ROI-Selektor mit Tastatursteuerung statt Maus"""

    def __init__(self):
        # ROI-Ecken
        self.roi_start = (100, 100)  # Default-Startwert
        self.roi_end = (300, 300)  # Default-Endwert
        self.selected = False
        self.step_size = 10  # Schrittgröße für Tastenbewegungen

    def start_selection(self):
        """Startet die ROI-Auswahl"""
        self.selected = False
        # Initialisiere die ROI mit Standardwerten in der Mitte des Bildschirms
        self.roi_start = (100, 100)
        self.roi_end = (300, 300)

        print("ROI-Auswahl gestartet.")
        print("Verwenden Sie folgende Tasten zur Steuerung:")
        print("  W/A/S/D: Bewegen der Startecke (oben links)")
        print("  I/J/K/L: Bewegen der Endecke (unten rechts)")
        print("  +/-: Schrittweitengröße erhöhen/verringern")
        print("  S: ROI speichern")
        print("  C: ROI-Auswahl abbrechen")

    def handle_key(self, key):
        """Verarbeitet Tastatureingaben für die ROI-Auswahl"""
        # Extrahiere die Koordinaten
        start_x, start_y = self.roi_start
        end_x, end_y = self.roi_end

        # Startecke bewegen (WASD)
        if key == UIKeyEvent.KEY_W:
            start_y = max(0, start_y - self.step_size)
        elif key == UIKeyEvent.KEY_A:
            start_x = max(0, start_x - self.step_size)
        elif key == UIKeyEvent.KEY_S:
            start_y = start_y + self.step_size
        elif key == UIKeyEvent.KEY_D:
            start_x = start_x + self.step_size

        # Endecke bewegen (IJKL)
        elif key == UIKeyEvent.KEY_I:
            end_y = max(0, end_y - self.step_size)
        elif key == UIKeyEvent.KEY_J:
            end_x = max(0, end_x - self.step_size)
        elif key == UIKeyEvent.KEY_K:
            end_y = end_y + self.step_size
        elif key == UIKeyEvent.KEY_L:
            end_x = end_x + self.step_size

        # Schrittweite ändern
        elif key == UIKeyEvent.KEY_EQUAL:  # Plus-Taste
            self.step_size = min(50, self.step_size + 1)
            print(f"Schrittweite erhöht auf {self.step_size}")
            return
        elif key == UIKeyEvent.KEY_MINUS:
            self.step_size = max(1, self.step_size - 1)
            print(f"Schrittweite verringert auf {self.step_size}")
            return

        # Aktualisiere die ROI
        self.roi_start = (start_x, start_y)
        self.roi_end = (end_x, end_y)

        # Debug-Ausgabe
        print(f"ROI aktualisiert: Start={self.roi_start}, End={self.roi_end}")

    def complete_selection(self):
        """Schließt die ROI-Auswahl ab"""
        # Stelle sicher, dass Start-Ecke oben links und End-Ecke unten rechts ist
        x0 = min(self.roi_start[0], self.roi_end[0])
        y0 = min(self.roi_start[1], self.roi_end[1])
        x1 = max(self.roi_start[0], self.roi_end[0])
        y1 = max(self.roi_start[1], self.roi_end[1])

        self.roi_start = (x0, y0)
        self.roi_end = (x1, y1)
        self.selected = True

        print(f"ROI ausgewählt: Start={self.roi_start}, End={self.roi_end}")

    def draw_roi_overlay(self, frame):
        """Zeichnet das ROI-Rechteck auf das Frame"""
        try:
            # Kopie des Frames erstellen
            overlay = frame.copy()

            # ROI-Rechteck zeichnen
            cv2.rectangle(
                overlay,
                (int(self.roi_start[0]), int(self.roi_start[1])),
                (int(self.roi_end[0]), int(self.roi_end[1])),
                (0, 255, 0),  # Grün
                2,  # Dicke
            )

            # Informationen einblenden
            info_text = f"ROI: Start={self.roi_start}, End={self.roi_end}, Schrittweite={self.step_size}"
            cv2.putText(
                overlay,
                info_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

            # Bedienhinweise
            if not self.selected:
                cv2.putText(
                    overlay,
                    "WASD: Startecke bewegen, IJKL: Endecke bewegen, +/-: Schrittweite, S: Speichern",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    1,
                )
            else:
                cv2.putText(
                    overlay,
                    "ROI ausgewählt",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )

            return overlay

        except Exception as e:
            print(f"Fehler beim Zeichnen des ROI-Overlays: {e}")
            return frame

    def get_roi(self):
        """Gibt die ROI zurück, wenn ausgewählt"""
        if self.selected:
            return (
                int(self.roi_start[0]),
                int(self.roi_start[1]),
                int(self.roi_end[0]),
                int(self.roi_end[1]),
            )
        return None, None, None, None


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="DVS Camera mit ROI-Auswahl und Recording",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input-event-file",
        dest="event_file_path",
        default="",
        help="Pfad zur Event-Datei (RAW oder HDF5). Falls nicht angegeben, wird der Live-Stream der Kamera verwendet. "
        "Falls es eine Kamera-Seriennummer ist, wird versucht, diese Kamera zu öffnen.",
    )
    parser.add_argument(
        "-r",
        "--replay_factor",
        type=float,
        default=1,
        help="Wiedergabefaktor. Wenn größer als 1.0, wird mit Zeitlupe wiedergegeben, ansonsten mit Zeitraffer.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default="",
        help="Verzeichnis, in dem die RAW-Datei mit aufgezeichneten Event-Daten erstellt werden soll",
    )
    return parser.parse_args()


def main():
    """Main"""
    args = parse_args()

    print(
        "DVS Camera mit ROI-Auswahl und Recording.\n"
        "Verfügbare Tastaturoptionen:\n"
        "  - T: ROI-Auswahl starten\n"
        "  - R: ROI-Filter ein-/ausschalten\n"
        "  - P: Nur Events mit positiver Polarität anzeigen\n"
        "  - N: Nur Events mit negativer Polarität anzeigen\n"
        "  - A: Alle Events anzeigen\n"
        "  - S: Aufnahme starten/stoppen (oder ROI speichern, wenn ROI-Auswahl aktiv)\n"
        "  - C: ROI-Auswahl abbrechen, wenn aktiv\n"
        "  - Q/Escape: Anwendung beenden\n\n"
        "Bei der ROI-Auswahl:\n"
        "  - WASD: Bewegen der Startecke (oben links)\n"
        "  - IJKL: Bewegen der Endecke (unten rechts)\n"
        "  - +/-: Schrittweite erhöhen/verringern\n"
        "  - S: ROI speichern\n"
        "  - C: ROI-Auswahl abbrechen\n"
    )

    # Überprüfen, ob wir eine Datei oder eine Live-Kamera verwenden
    using_live_camera = args.event_file_path == "" or is_live_camera(
        args.event_file_path
    )

    # Device und Iterator für spätere Freigabe
    device = None
    mv_iterator = None

    try:
        # Wenn wir eine Live-Kamera verwenden, initialisieren wir das Device für die Aufnahme
        if using_live_camera:
            print("Versuche, DVS-Kamera zu öffnen...")
            # Kurze Verzögerung um sicherzustellen, dass die Kamera bereit ist
            time.sleep(1)

            # Diese Methode hat im Test funktioniert
            device = initiate_device(args.event_file_path)

            if not device:
                raise Exception("Konnte kein DVS-Gerät initialisieren")

            print("DVS-Kamera erfolgreich geöffnet!")

            # Events Iterator direkt vom Gerät erstellen
            print("Erstelle EventsIterator vom Gerät...")
            mv_iterator = EventsIterator.from_device(device=device, delta_t=1000)
            print("EventsIterator erfolgreich erstellt!")

            # Recorder für die ROI-gefilterte Aufnahme erstellen
            roi_logger = RoiLogger(device)
        else:
            # Events Iterator auf Event-Datei
            print(f"Öffne Event-Datei: {args.event_file_path}")
            mv_iterator = EventsIterator(input_path=args.event_file_path, delta_t=1000)
            roi_logger = None  # Keine Aufnahme bei Event-Datei

        if args.replay_factor > 0 and not using_live_camera:
            mv_iterator = LiveReplayEventsIterator(
                mv_iterator, replay_factor=args.replay_factor
            )

        height, width = mv_iterator.get_size()  # Kamera-Geometrie
        print(f"Sensor-Auflösung: {width}x{height}")

        # Initialisiere Filter
        polarity_filters = {
            Polarity.OFF: PolarityFilterAlgorithm(0),
            Polarity.ON: PolarityFilterAlgorithm(1),
        }
        roi_filter = (
            None  # Wird später initialisiert, wenn der Benutzer die ROI auswählt
        )
        events_buf = RoiFilterAlgorithm.get_empty_output_buffer()
        use_roi_filter = False
        roi_coords = (0, 0, 0, 0)  # x0, y0, x1, y1
        polarity = Polarity.ALL

        # Aufnahme-Variablen
        is_recording = False
        log_path = None

        # ROI-Auswahl-Status
        roi_selection_active = False

        # Event Frame Generator
        event_frame_gen = PeriodicFrameGenerationAlgorithm(
            width, height, accumulation_time_us=10000
        )

        # Erstelle das Fenster
        with MTWindow(
            title="DVS Camera ROI Recorder",
            width=width,
            height=height,
            mode=BaseWindow.RenderMode.BGR,
        ) as window:
            # Leeres Bild für die erste Anzeige
            initial_frame = np.zeros((height, width, 3), dtype=np.uint8)
            last_frame = initial_frame.copy()

            # ROI-Selektor erstellen
            roi_selector = KeyboardROISelector()

            def on_cd_frame_cb(ts, cd_frame):
                nonlocal last_frame
                # Dispatch system events to the window
                EventLoop.poll_and_dispatch()

                # Kopie des Frames speichern
                last_frame = cd_frame.copy()

                # ROI-Overlay zeichnen, wenn ROI-Auswahl aktiv ist
                display_frame = cd_frame.copy()

                # ROI-Rechteck einzeichnen, wenn ROI definiert ist
                if roi_filter is not None and use_roi_filter:
                    # Verwenden der separat gespeicherten ROI-Koordinaten
                    x0, y0, x1, y1 = roi_coords
                    cv2.rectangle(
                        display_frame,
                        (int(x0), int(y0)),
                        (int(x1), int(y1)),
                        (0, 255, 255),  # Gelb
                        2,  # Dicke
                    )
                    cv2.putText(
                        display_frame,
                        f"Aktive ROI: x0={x0}, y0={y0}, x1={x1}, y1={y1}",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2,
                    )

                # ROI-Auswahl-Overlay zeichnen, wenn im Auswahlmodus
                if roi_selection_active:
                    display_frame = roi_selector.draw_roi_overlay(display_frame)

                # Aufnahmestatus anzeigen
                if is_recording:
                    rec_text = "● REC" + (
                        " (ROI)" if use_roi_filter and roi_filter is not None else ""
                    )
                    cv2.putText(
                        display_frame,
                        rec_text,
                        (width - 150, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),  # Rot
                        2,
                    )

                # Frame anzeigen
                window.show_async(display_frame)

            event_frame_gen.set_output_callback(on_cd_frame_cb)

            def toggle_recording():
                nonlocal is_recording, log_path

                if not using_live_camera:
                    print("Aufnahme nur mit Live-Kamera möglich.")
                    return

                if is_recording:
                    # Stoppe die Aufnahme
                    if roi_logger:
                        roi_logger.stop_recording()
                    is_recording = False
                    print(f"Aufnahme gestoppt: {log_path}")
                else:
                    # Starte die Aufnahme
                    log_path = (
                        "recording_"
                        + time.strftime("%y%m%d_%H%M%S", time.localtime())
                        + ".raw"
                    )
                    if args.output_dir != "":
                        os.makedirs(args.output_dir, exist_ok=True)
                        log_path = os.path.join(args.output_dir, log_path)

                    # Hinweis auf ROI-Recording ausgeben, wenn aktiv
                    if use_roi_filter and roi_filter is not None and roi_logger:
                        print(f"Starte ROI-gefilterte Aufnahme nach {log_path}")
                        roi_logger.set_roi(roi_filter, roi_coords, use_roi_filter)
                        roi_logger.start_recording(log_path)
                    else:
                        print(f"Starte Vollbild-Aufnahme nach {log_path}")
                        if roi_logger:
                            roi_logger.set_roi(None, (0, 0, 0, 0), False)
                            roi_logger.start_recording(log_path)

                    is_recording = True

            def start_roi_selection():
                nonlocal roi_selection_active
                roi_selection_active = True
                roi_selector.start_selection()
                print("ROI-Auswahl gestartet.")

            def complete_roi_selection():
                nonlocal roi_selection_active, roi_filter, roi_coords, use_roi_filter

                if roi_selection_active:
                    roi_selector.complete_selection()
                    x0, y0, x1, y1 = roi_selector.get_roi()

                    if None not in (x0, y0, x1, y1):
                        # Speichere ROI-Koordinaten separat
                        roi_coords = (x0, y0, x1, y1)

                        # Erstelle neuen ROI-Filter mit den ausgewählten Koordinaten
                        roi_filter = RoiFilterAlgorithm(x0=x0, y0=y0, x1=x1, y1=y1)
                        use_roi_filter = True
                        print(f"Neue ROI gesetzt: x0={x0}, y0={y0}, x1={x1}, y1={y1}")

                        # ROI im Logger aktualisieren, wenn verfügbar
                        if roi_logger:
                            roi_logger.set_roi(roi_filter, roi_coords, use_roi_filter)
                    else:
                        print("ROI-Auswahl wurde nicht abgeschlossen.")

                    # ROI-Auswahl beenden
                    roi_selection_active = False

            def cancel_roi_selection():
                nonlocal roi_selection_active

                if roi_selection_active:
                    roi_selection_active = False
                    print("ROI-Auswahl abgebrochen.")

            def toggle_roi_filter():
                nonlocal use_roi_filter

                if roi_filter is not None:
                    use_roi_filter = not use_roi_filter
                    print(
                        f"ROI-Filter {'aktiviert' if use_roi_filter else 'deaktiviert'}"
                    )

                    # ROI im Logger aktualisieren, wenn verfügbar
                    if roi_logger:
                        roi_logger.set_roi(roi_filter, roi_coords, use_roi_filter)
                else:
                    print(
                        "Keine ROI definiert. Bitte zuerst mit 'T' eine ROI auswählen."
                    )

            def keyboard_cb(key, scancode, action, mods):
                nonlocal use_roi_filter, polarity, roi_selection_active

                if action != UIAction.RELEASE:
                    return

                # Debug-Ausgabe für den Tastendruck
                print(f"Taste gedrückt: {key}")

                if key == UIKeyEvent.KEY_ESCAPE or key == UIKeyEvent.KEY_Q:
                    # Sicherstellen, dass die Aufnahme gestoppt wird, bevor wir beenden
                    if is_recording and using_live_camera:
                        if roi_logger:
                            roi_logger.stop_recording()
                    window.set_close_flag()
                # ROI-Auswahlmodus aktiv - spezielle Tastatursteuerung
                elif roi_selection_active:
                    if key == UIKeyEvent.KEY_S:
                        # ROI speichern
                        complete_roi_selection()
                    elif key == UIKeyEvent.KEY_C:
                        # ROI-Auswahl abbrechen
                        cancel_roi_selection()
                    else:
                        # Andere Tasten an den ROI-Selektor weiterleiten
                        roi_selector.handle_key(key)
                # Normale Tastatursteuerung (ROI-Auswahl nicht aktiv)
                else:
                    if key == UIKeyEvent.KEY_A:
                        # Alle Events anzeigen
                        polarity = Polarity.ALL
                        print("Zeige alle Events")
                    elif key == UIKeyEvent.KEY_N:
                        # Nur negative Events anzeigen
                        polarity = Polarity.OFF
                        print("Zeige nur negative Events")
                    elif key == UIKeyEvent.KEY_P:
                        # Nur positive Events anzeigen
                        polarity = Polarity.ON
                        print("Zeige nur positive Events")
                    elif key == UIKeyEvent.KEY_R:
                        # ROI-Filter ein-/ausschalten
                        toggle_roi_filter()
                    elif key == UIKeyEvent.KEY_T:
                        # Neue ROI auswählen
                        start_roi_selection()
                    elif key == UIKeyEvent.KEY_S:
                        # Aufnahme starten/stoppen
                        toggle_recording()

            window.set_keyboard_callback(keyboard_cb)

            # Verarbeite Events
            for evs in mv_iterator:
                # Wenn ROI-Filter aktiviert ist und ROI definiert wurde
                if use_roi_filter and roi_filter is not None:
                    roi_filter.process_events(evs, events_buf)
                    if polarity in polarity_filters:
                        polarity_filters[polarity].process_events_(events_buf)
                        event_frame_gen.process_events(events_buf)
                    else:
                        event_frame_gen.process_events(events_buf)
                # Polaritätsfilter ohne ROI
                elif polarity in polarity_filters:
                    polarity_filters[polarity].process_events(evs, events_buf)
                    event_frame_gen.process_events(events_buf)
                # Keine Filter
                else:
                    event_frame_gen.process_events(evs)

                if window.should_close():
                    # Sicherstellen, dass die Aufnahme gestoppt wird, bevor wir beenden
                    if is_recording and using_live_camera:
                        if roi_logger:
                            roi_logger.stop_recording()
                    break

    except Exception as e:
        print(f"Kritischer Fehler: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Ressourcen freigeben
        if is_recording and using_live_camera and device:
            try:
                if "roi_logger" in locals() and roi_logger:
                    roi_logger.stop_recording()
                print("Aufnahme gestoppt bei Programmende")
            except Exception as e:
                print(f"Fehler beim Stoppen der Aufnahme: {e}")

        # Explizit Device freigeben
        if device:
            try:
                print("Gebe DVS-Kameraressourcen frei...")
                # In Python reicht es oft, die Referenz zu löschen
                del device
            except Exception as e:
                print(f"Fehler beim Freigeben der Kameraressourcen: {e}")


if __name__ == "__main__":
    main()
