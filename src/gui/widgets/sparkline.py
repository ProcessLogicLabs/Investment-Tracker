"""Sparkline mini-chart widget using QPainter."""

from typing import List, Optional
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath
from ..theme import theme


class SparklineWidget(QWidget):
    """A tiny inline chart showing a value trend."""

    def __init__(self, parent=None, width=120, height=40):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._data: List[float] = []
        default_color = theme().palette.accent
        self._line_color = QColor(default_color)
        self._fill_color = QColor(default_color)
        self._fill_color.setAlpha(50)

    def set_data(self, data: List[float], color: Optional[str] = None):
        """Set sparkline data points and optional color."""
        self._data = data if data else []
        if color:
            self._line_color = QColor(color)
            self._fill_color = QColor(color)
            self._fill_color.setAlpha(50)
        self.update()

    def paintEvent(self, event):
        """Draw the sparkline."""
        if len(self._data) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 2

        data = self._data
        min_val = min(data)
        max_val = max(data)
        val_range = max_val - min_val if max_val != min_val else 1.0

        # Build point list
        points = []
        for i, val in enumerate(data):
            x = margin + (i / (len(data) - 1)) * (w - 2 * margin)
            y = h - margin - ((val - min_val) / val_range) * (h - 2 * margin)
            points.append(QPointF(x, y))

        # Draw filled area under curve
        path = QPainterPath()
        path.moveTo(points[0].x(), h)
        for p in points:
            path.lineTo(p)
        path.lineTo(points[-1].x(), h)
        path.closeSubpath()
        painter.fillPath(path, self._fill_color)

        # Draw line
        pen = QPen(self._line_color, 1.5)
        painter.setPen(pen)
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])

        # Draw endpoint dot
        painter.setBrush(self._line_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(points[-1], 2, 2)

        painter.end()
