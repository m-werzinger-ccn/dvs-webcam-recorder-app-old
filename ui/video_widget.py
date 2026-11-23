#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Benutzerdefiniertes Widget für die Videoanzeige, das die Frames direkt zeichnet.
Dieses Widget kann als Ersatz für QLabel verwendet werden.
"""

from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPainter, QImage, QPixmap


class VideoDisplayWidget(QWidget):
    """Widget zur direkten Anzeige von Videoframes"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.setMinimumSize(640, 480)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent)  # Für bessere Performance

    def setImage(self, image):
        """Setzt das anzuzeigende Bild (QImage)"""
        if image.isNull():
            return

        # Konvertieren zu QPixmap für schnelleres Zeichnen
        self.pixmap = QPixmap.fromImage(image)

        # Widget neu zeichnen
        self.update()

    def setPixmap(self, pixmap):
        """Setzt das anzuzeigende Bild (QPixmap)"""
        if pixmap.isNull():
            return

        self.pixmap = pixmap
        self.update()

    def clear(self):
        """Löscht das angezeigte Bild"""
        self.pixmap = None
        self.update()

    def setText(self, text):
        """Kompatibilitätsmethode für QLabel - Text wird ignoriert"""
        # Leeres Bild mit Text erstellen
        pixmap = QPixmap(self.width(), self.height())
        pixmap.fill(Qt.black)
        painter = QPainter(pixmap)
        painter.setPen(Qt.white)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
        painter.end()
        self.setPixmap(pixmap)

    def paintEvent(self, event):
        """Zeichenereignis-Handler"""
        if self.pixmap is None:
            # Wenn kein Bild vorhanden, einen schwarzen Hintergrund zeichnen
            painter = QPainter(self)
            painter.fillRect(self.rect(), Qt.black)
            return

        # Bild skalieren, um in das Widget zu passen (Aspektverhältnis beibehalten)
        scaled_pixmap = self.pixmap.scaled(
            self.width(), self.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        # Position berechnen, um das Bild zu zentrieren
        x = (self.width() - scaled_pixmap.width()) / 2
        y = (self.height() - scaled_pixmap.height()) / 2

        # Bild zeichnen
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)  # Hintergrund schwarz machen
        painter.drawPixmap(int(x), int(y), scaled_pixmap)

    def sizeHint(self):
        """Bevorzugte Größe des Widgets"""
        return QSize(1280, 720)

    def minimumSizeHint(self):
        """Minimale Größe des Widgets"""
        return QSize(320, 180)
