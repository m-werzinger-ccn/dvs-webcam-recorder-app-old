#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Skript zur Erstellung einer Desktop-Verknüpfung mit eigenem Icon für die
medizinische Untersuchungsaufnahme-Anwendung.
"""

import os
import sys
import subprocess
import shutil


def create_application_shortcut(custom_icon_path=None):
    """
    Erstellt eine Desktop-Verknüpfung und einen Eintrag im Anwendungsmenü

    Args:
        custom_icon_path: Pfad zu einer eigenen Icon-Datei (PNG oder SVG)
    """

    # Ermittle den absoluten Pfad der Anwendung
    app_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))

    # Stelle sicher, dass main.py ausführbar ist
    os.chmod(app_path, 0o755)

    # Name der Anwendung
    app_name = "Medizinische Untersuchung Recorder"

    # Icon-Pfad ermitteln
    if custom_icon_path:
        # Absoluten Pfad sicherstellen
        icon_path = os.path.abspath(custom_icon_path)

        # Prüfen, ob das Icon existiert
        if not os.path.exists(icon_path):
            print(f"WARNUNG: Das angegebene Icon '{icon_path}' existiert nicht!")
            print("Verwende Standardsymbol stattdessen.")
            icon_path = "medical-cross"
    else:
        # Standardsymbol verwenden
        icon_path = "medical-cross"

    # Erstelle Desktop-Datei im Anwendungsmenü
    applications_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(applications_dir, exist_ok=True)

    desktop_file_path = os.path.join(
        applications_dir, "medizinische-untersuchung.desktop"
    )

    with open(desktop_file_path, "w") as f:
        f.write(
            f"""[Desktop Entry]
Version=1.0
Type=Application
Name={app_name}
Comment=Medizinische Untersuchungsaufnahme-Anwendung
Exec=python3 "{app_path}"
Icon={icon_path}
Terminal=false
Categories=Medical;Video;
StartupNotify=true
"""
        )

    # Mache die Desktop-Datei ausführbar
    os.chmod(desktop_file_path, 0o755)

    # Erstelle auch eine Verknüpfung auf dem Desktop
    # Unterstützung für verschiedene Desktop-Namen (Englisch und Deutsch)
    potential_desktop_paths = [
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "Schreibtisch"),
    ]

    desktop_shortcut_created = False
    for desktop_path in potential_desktop_paths:
        if os.path.exists(desktop_path) and os.path.isdir(desktop_path):
            desktop_shortcut_path = os.path.join(
                desktop_path, "Medizinische Untersuchung.desktop"
            )
            # Kopiere die Desktop-Datei
            shutil.copy2(desktop_file_path, desktop_shortcut_path)
            # Mache die Kopie ausführbar
            os.chmod(desktop_shortcut_path, 0o755)
            desktop_shortcut_created = True
            print(f"Desktop-Verknüpfung erstellt in: {desktop_path}")
            break

    if not desktop_shortcut_created:
        print("Desktop-Verzeichnis nicht gefunden. Keine Desktop-Verknüpfung erstellt.")

    print(f"Anwendungsverknüpfung erstellt: {desktop_file_path}")
    print(f"Verwendetes Icon: {icon_path}")
    print("Die Anwendung ist jetzt im Anwendungsmenü und auf dem Desktop verfügbar.")

    return True


if __name__ == "__main__":
    # Wenn ein Befehlszeilenargument übergeben wurde, verwende es als Icon-Pfad
    if len(sys.argv) > 1:
        create_application_shortcut(sys.argv[1])
    else:
        # Frage nach einem benutzerdefinierten Icon
        response = input("Möchtest du ein eigenes Icon verwenden? (j/n): ")
        if response.lower() in ["j", "ja", "y", "yes"]:
            icon_path = input("Gib den Pfad zum Icon ein (PNG oder SVG): ")
            create_application_shortcut(icon_path)
        else:
            create_application_shortcut()
