from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtCore import Qt, QPointF, Signal
from typing import List, Tuple

class AnalysisGraph(QWidget):
    """Simple line graph of evaluation over moves.

    Data: list of (move_number, score_centipawns)
    """
    move_selected = Signal(int)  # move number (0-based)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: List[Tuple[int, float]] = []
        self.setMinimumSize(200, 150)
        self._selected_index = -1
        self.setMouseTracking(True)

    def set_data(self, data: List[Tuple[int, float]]):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        if not self.data:
            return

        # Compute scale
        xs = [p[0] for p in self.data]
        ys = [p[1] for p in self.data]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if max_x == min_x:
            max_x += 1
        if max_y == min_y:
            max_y = min_y + 1
        margin = 20
        scale_x = (w - 2*margin) / (max_x - min_x)
        scale_y = (h - 2*margin) / (max_y - min_y)

        # Draw axes
        painter.setPen(QPen(QColor(100,100,100), 1))
        painter.drawLine(margin, margin, margin, h - margin)
        painter.drawLine(margin, h - margin, w - margin, h - margin)

        # Zero line if within range
        if min_y <= 0 <= max_y:
            y0 = h - margin - (0 - min_y) * scale_y
            painter.setPen(QPen(QColor(200,200,200), 1, Qt.DashLine))
            painter.drawLine(margin, int(y0), w - margin, int(y0))

        # Plot points and lines
        painter.setPen(QPen(QColor(0, 150, 0), 2))
        points = []
        for i, (x, y) in enumerate(self.data):
            px = margin + (x - min_x) * scale_x
            py = h - margin - (y - min_y) * scale_y
            points.append(QPointF(px, py))
            # Draw point
            painter.setBrush(QColor(0,150,0))
            painter.drawEllipse(QPointF(px, py), 3, 3)

        # Connect points
        painter.setPen(QPen(QColor(0,150,0), 1))
        for i in range(len(points)-1):
            painter.drawLine(points[i], points[i+1])

    def mousePressEvent(self, event):
        pos = event.position()
        # Find nearest data point
        if not self.data:
            return
        best_idx = -1
        best_dist = 1e9
        margin = 20
        w = self.width()
        h = self.height()
        xs = [p[0] for p in self.data]
        ys = [p[1] for p in self.data]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        scale_x = (w - 2*margin) / (max_x - min_x) if max_x != min_x else 1
        scale_y = (h - 2*margin) / (max_y - min_y) if max_y != min_y else 1
        for i, (x, y) in enumerate(self.data):
            px = margin + (x - min_x) * scale_x
            py = h - margin - (y - min_y) * scale_y
            dist = ((pos.x() - px)**2 + (pos.y() - py)**2)**0.5
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx >= 0 and best_dist < 20:
            self._selected_index = best_idx
            self.move_selected.emit(best_idx)
            self.update()