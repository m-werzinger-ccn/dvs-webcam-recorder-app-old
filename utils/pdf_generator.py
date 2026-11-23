#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF-Generator für die Zusammenfassung der Untersuchung.
Erstellt ein PDF mit den Bewertungen aller Segmente.
"""

import os
import json
import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm


def generate_examination_report(
    patient_name,
    examination_datetime,
    save_directory,
    examination_categories,
    examiner_name="",
):
    """
    Generiert einen PDF-Bericht über die Untersuchungsergebnisse.

    Args:
        patient_name: Name des Patienten
        examination_datetime: Zeitpunkt der Untersuchung
        save_directory: Verzeichnis, in dem die Bewertungen gespeichert sind
        examination_categories: Liste der Untersuchungskategorien
        examiner_name: Name des Untersuchers (optional)

    Returns:
        String: Pfad zur erstellten PDF-Datei oder None bei Fehler
    """
    try:
        # Formatierte Datum-Zeit für den Dateinamen
        timestamp = examination_datetime.strftime("%Y%m%d_%H%M%S")
        timestamp_display = examination_datetime.strftime("%d.%m.%Y %H:%M")

        # PDF-Datei erstellen
        pdf_filename = os.path.join(
            save_directory, f"Untersuchungsbericht_{patient_name}_{timestamp}.pdf"
        )
        doc = SimpleDocTemplate(
            pdf_filename,
            pagesize=A4,
            rightMargin=1 * cm,
            leftMargin=1 * cm,
            topMargin=1 * cm,
            bottomMargin=1 * cm,
        )

        # Stile für die Texte
        styles = getSampleStyleSheet()
        title_style = styles["Heading1"]
        subtitle_style = styles["Heading2"]
        normal_style = styles["Normal"]

        # Benutzerdefinierter Stil für Notizen
        note_style = ParagraphStyle(
            "NoteStyle",
            parent=normal_style,
            fontName="Helvetica-Oblique",
            fontSize=9,
            leftIndent=10,
            rightIndent=10,
        )

        # Benutzerdefinierter Stil für Punkte
        points_style = ParagraphStyle(
            "PointsStyle",
            parent=normal_style,
            alignment=1,  # 0=links, 1=mitte, 2=rechts
            fontSize=10,
        )

        # Liste für Elemente im PDF
        elements = []

        # Titel
        title = Paragraph(f"Untersuchungsbericht: {patient_name}", title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.5 * cm))

        # Untersuchungsdatum
        date_text = Paragraph(f"Untersuchung am: {timestamp_display}", subtitle_style)
        elements.append(date_text)
        elements.append(Spacer(1, 0.5 * cm))

        # Gesamtpunktzahl initialisieren
        total_points = 0
        segments_evaluated = 0

        # Jede Kategorie auflisten
        for category in examination_categories:
            category_title = category["title"]
            max_points = category.get("points", 0) - 1  # 0-basiert (0 bis n-1)

            # Formatierter Titel
            cat_title = Paragraph(f"{category_title}", subtitle_style)
            elements.append(cat_title)

            # Verzeichnis für diese Kategorie
            safe_title = category_title.replace(" ", "_").replace(".", "_")
            category_dir = os.path.join(save_directory, safe_title)

            # Punktelabels
            point_labels = category.get("pointLabels", [])

            # Prüfen, ob Bewertungsdateien existieren
            rating_data = None
            if os.path.exists(category_dir):
                rating_files = [
                    f for f in os.listdir(category_dir) if f.endswith("_rating.json")
                ]
                if rating_files:
                    # Nehmen wir die erste Bewertungsdatei (falls mehrere existieren)
                    rating_file_path = os.path.join(category_dir, rating_files[0])
                    with open(rating_file_path, "r", encoding="utf-8") as f:
                        rating_data = json.load(f)

            # Tabelle für die Punkteoptionen erstellen
            table_data = []

            # Ausgewählter Punkt
            selected_point = -1
            if rating_data:
                selected_point = rating_data.get("numberOfSelectedPoint", -1)
                segments_evaluated += 1
                total_points += selected_point

            # Punkte hinzufügen
            for i in range(len(point_labels)):
                row = [
                    Paragraph(f"{point_labels[i]}", normal_style),
                    Paragraph(f"{i}", points_style),
                ]
                table_data.append(row)

            # Wenn keine Bewertung gefunden wurde
            if not rating_data:
                table_data.append(
                    [Paragraph("Keine Bewertung vorhanden", normal_style), ""]
                )

            # Tabelle erstellen und formatieren
            if table_data:
                table = Table(table_data, colWidths=[400, 50])
                table_style = [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]

                # Farbige Hinterlegung für die ausgewählte Zeile hinzufügen
                if selected_point >= 0 and selected_point < len(table_data):
                    table_style.append(
                        (
                            "BACKGROUND",
                            (0, selected_point),
                            (-1, selected_point),
                            colors.lightblue,
                        )
                    )

                table.setStyle(TableStyle(table_style))
                elements.append(table)

            # Notiz hinzufügen, wenn vorhanden
            if rating_data and "note" in rating_data and rating_data["note"]:
                elements.append(Spacer(1, 0.3 * cm))
                note_heading = Paragraph(
                    "Notiz:",
                    ParagraphStyle(
                        "NoteHeading",
                        parent=normal_style,
                        fontName="Helvetica-Bold",
                        fontSize=10,
                    ),
                )
                elements.append(note_heading)
                note_text = Paragraph(rating_data["note"], note_style)
                elements.append(note_text)

            elements.append(Spacer(1, 0.5 * cm))

        # Gesamtpunktzahl am Ende
        elements.append(Spacer(1, 0.5 * cm))
        if segments_evaluated > 0:
            total_text = Paragraph(
                f"Gesamtpunktzahl: {total_points}",
                subtitle_style,
            )
            elements.append(total_text)
        else:
            elements.append(
                Paragraph("Keine Segmente wurden bewertet!", subtitle_style)
            )

        # Untersucher am Ende anzeigen, wenn angegeben
        if examiner_name:
            elements.append(Spacer(1, 1 * cm))
            examiner_style = ParagraphStyle(
                "ExaminerStyle",
                parent=normal_style,
                alignment=2,  # Rechtsbündig
                fontSize=10,
            )
            examiner_text = Paragraph(f"Untersucher: {examiner_name}", examiner_style)
            elements.append(examiner_text)

        # PDF erstellen
        doc.build(elements)
        return pdf_filename

    except Exception as e:
        print(f"Fehler bei der PDF-Generierung: {e}")
        import traceback

        traceback.print_exc()
        return None
