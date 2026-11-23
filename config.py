#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Konfigurationsdatei für die medizinische Untersuchungsaufnahme-Anwendung.
"""

# Anwendungskonfiguration
APP_NAME = "Medizinische Untersuchung Recorder"
APP_VERSION = "1.1.0"
APP_ICON = "medical-cross"  # Name des Systemsymbols

# Standardwerte für Video-Codec und Erweiterung
# Diese können später dynamisch überschrieben werden
DEFAULT_VIDEO_CODEC = "mp4v"  # Standard-Codec für MP4
DEFAULT_VIDEO_EXTENSION = ".mp4"  # Standard-Erweiterung

# Aufnahme-Einstellungen
DEFAULT_FPS = 30.0  # Höhere Framerate für medizinische Aufnahmen

# UI-Konfiguration
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 900
CARD_MIN_WIDTH = 380
CARD_MIN_HEIGHT = 200

# Medizinische Untersuchungs-Kategorien
EXAMINATION_CATEGORIES = [
    {
        "title": "1a. Bewusstsein",
        "description": "wach, benommen, soporös, komatös",
        "points": 4,
        "pointLabels": [
            "wach (Augen geöffnet, unmittelbar antwortend)",
            "benommen (Augen öffnen auf Ansprache)",
            "soporös (Augen öffnen auf Schmerzreiz oder wiederholte Stimulation)",
            "komatös (keine motorische Antwort, Streck- Beugesynergismen)",
        ],
    },
    {
        "title": "1b. Orientierung",
        "description": "Fragen nach aktuellem Monat und Alter, bei erstem Versuch richtig",
        "points": 3,
        "pointLabels": [
            "beide richtig",
            "eine richtig, schwer dysarthrisch oder intubiert",
            "keine richtig, aphasisch oder komatös",
        ],
    },
    {
        "title": "1c. Aufforderungen",
        "description": "Augen öffnen, Faust machen",
        "points": 3,
        "pointLabels": ["beide richtig", "eine richtig", "keine richtig oder komatös"],
    },
    {
        "title": "2. Blickbewegungen",
        "description": "Blick folgt dem Finger des Untersuchers",
        "points": 3,
        "pointLabels": [
            "normal",
            "partielle Blickparese oder isolierte periphere/nukleäre Paresen (Nn, III, IV, VI)",
            "komplette Blichparese oder fixierte Blickdeviation",
        ],
    },
    {
        "title": "3. Gesichtsfeld",
        "description": "fingerperimetisch, alle Quadranten",
        "points": 4,
        "pointLabels": [
            "keine Einschränkung",
            "partielle Hemianopsie, Auslöschung bei simultaner Prüfung",
            "komplette Hemianopsie, bei Koma nur einseitige Schreckreaktion",
            "(kortikale) Blindheit, bei Koma keine Schreckreaktion",
        ],
    },
    {
        "title": "4. Facialisparese",
        "description": "Zähne zeigen, Stirn runzeln, Augen schließen",
        "points": 4,
        "pointLabels": [
            "normal",
            "geringe Parese (faziale Mundastschwäche)",
            "partielle Parese (deutliche zentrale Parese)",
            "vollständige Parese (beidseitig zentral, einseitig peripher oder Koma)",
        ],
    },
    {
        "title": "5a. Armvorhalten links",
        "description": "",
        "points": 5,
        "pointLabels": [
            "10 sec. normal gehalten oder Amputation",
            "langsames unvollständiges Absinken",
            "schnelles vollständiges Absinken oder Anheben gegen Schwerkraft",
            "Bewegung auf dr Unterlage, kein Anheben",
            "keine Bewegung oder Koma",
        ],
    },
    {
        "title": "5b. Armvorhalten rechts",
        "description": "",
        "points": 5,
        "pointLabels": [
            "10 sec. normal gehalten oder Amputation",
            "langsames unvollständiges Absinken",
            "schnelles vollständiges Absinken oder Anheben gegen Schwerkraft",
            "Bewegung auf dr Unterlage, kein Anheben",
            "keine Bewegung oder Koma",
        ],
    },
    {
        "title": "6a. Beinvorhalten links",
        "description": "",
        "points": 5,
        "pointLabels": [
            "5 sec. normal gehalten (stets im Ligen prüfen)",
            "langsames unvollständiges Absinken",
            "schnelles vollständiges Absinken oder Anheben gegen Schwerkraft",
            "Bewegung auf der Unterlage, kein Anheben",
            "keine Bewegung oder Koma",
        ],
    },
    {
        "title": "6b. Beinvorhalten rechts",
        "description": "",
        "points": 4,
        "pointLabels": [
            "5 sec. normal gehalten (stets im Ligen prüfen)",
            "langsames unvollständiges Absinken",
            "schnelles vollständiges Absinken oder Anheben gegen Schwerkraft",
            "Bewegung auf der Unterlage, kein Anheben",
            "keine Bewegung oder Koma",
        ],
    },
    {
        "title": "7. Ataxie",
        "description": "Finger-Nase-Versuch, Knie-Hacke-Versuch, offene Augen",
        "points": 3,
        "pointLabels": [
            "keine Ataxie, Patient versteht Übung nicht, bei Parase oder Koma",
            "eine Extremität ataktisch",
            "mindestens zwei Extremitäten ataktisch",
        ],
    },
    {
        "title": "8. Sensibilität",
        "description": "nur Defizite durch Stroke, Hände und Füße nicht prüfen",
        "points": 3,
        "pointLabels": [
            "normal",
            "Hemihpästhesie, Seitendifferenz auf Schmerzreiz",
            "Hemianästhesie, Hypästhesie beidseits, keine Schmerzreaktion beidseits oder Koma",
        ],
    },
    {
        "title": "9. Sprache",
        "description": "Spontansprache beurteilen, Gegenstände benennen, nachsprechen lassen",
        "points": 4,
        "pointLabels": [
            "normal",
            "Wortfindungsstörungen, leichte Aphasie",
            "Deutlich gestörte Konversation",
            "globale Aphasie, keine Aufforderung befolgt, stumm oder komatös",
        ],
    },
    {
        "title": "10. Dysarthrie",
        "description": '"Stuhl, Fünfzehn, Siebenhunderteinundzwanzig" nachsprechen lassen',
        "points": 3,
        "pointLabels": [
            "normal oder Intubation",
            "Dysarthisch, aber noch verständlich",
            "kaum veständlich, keine Sprachproduktion, stumm, Koma",
        ],
    },
    {
        "title": "11. Auslöschung/Nichtbeachtung",
        "description": "visuell und sensibel",
        "points": 3,
        "pointLabels": [
            "nicht vorhanden, Aphasie oder Verständigungsschwierigkeiten",
            "eine Sinnesmodalität betroffen, Anosognie oder andere Neglectphänomene",
            "beide Modalitäten betroffen oder Koma",
        ],
    },
]
