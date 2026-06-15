import os
from typing import List, Tuple, Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import (QPainter, QColor, QFont, QPen, QBrush, QPixmap,
                           QPolygonF, QPainterPath)
from PySide6.QtCore import Qt, QRect, Signal, QSize, QTimer, QPointF, QLineF
from src.core.board import Board
from src.core.pieces import Piece, Colour, PieceType, PIECE_SYMBOLS


class BoardArrow:
    def __init__(self, from_r: int, from_c: int, to_r: int, to_c: int,
                 color: QColor = QColor(255, 255, 0, 180), width: int = 3):
        self.from_r = from_r
        self.from_c = from_c
        self.to_r = to_r
        self.to_c = to_c
        self.color = color
        self.width = width


class BoardMarker:
    def __init__(self, row: int, col: int, color: QColor = QColor(0, 255, 0, 150),
                 radius: int = 12, corner: str = "center"):
        self.row = row
        self.col = col
        self.color = color
        self.radius = radius
        self.corner = corner


class BoardWidget(QWidget):
    square_clicked = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = Board.starting_position()
        self.flipped = False
        self.selected_square: Optional[Tuple[int, int]] = None
        self.legal_destinations: List[Tuple[int, int]] = []
        self.last_move: Optional[Tuple[int, int, int, int]] = None

        self.square_size = 60
        self.margin = 30
        self.setMinimumSize(10 * self.square_size + 2 * self.margin,
                            10 * self.square_size + 2 * self.margin)

        self.piece_pixmaps = self._load_piece_images()

        self.arrows: List[BoardArrow] = []
        self.markers: List[BoardMarker] = []

        self._animating = False
        self._anim_from_r = 0
        self._anim_from_c = 0
        self._anim_to_r = 0
        self._anim_to_c = 0
        self._anim_piece: Optional[Piece] = None
        self._anim_progress = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animation_step)
        self._anim_callback = None
        self._anim_duration_ms = 200
        self._anim_start_time = 0

    def _load_piece_images(self) -> dict:
        pixmaps = {}
        base_dir = os.path.join(os.path.dirname(__file__), "..", "resources", "pieces")
        for colour in Colour:
            colour_name = colour.name.lower()
            for ptype in PieceType:
                ptype_name = ptype.name.lower()
                path = os.path.join(base_dir, f"{colour_name}_{ptype_name}.png")
                if os.path.exists(path):
                    pixmaps[(colour, ptype)] = QPixmap(path)
        return pixmaps

    def set_arrows(self, arrows: List[BoardArrow]):
        self.arrows = arrows
        self.update()

    def set_markers(self, markers: List[BoardMarker]):
        self.markers = markers
        self.update()

    def clear_annotations(self):
        self.arrows.clear()
        self.markers.clear()
        self.update()

    def flip_board(self):
        self.flipped = not self.flipped
        self.update()

    def animate_move(self, from_r: int, from_c: int, to_r: int, to_c: int,
                     piece: Piece, on_finished=None):
        if self._animating:
            return
        self._animating = True
        self._anim_from_r = from_r
        self._anim_from_c = from_c
        self._anim_to_r = to_r
        self._anim_to_c = to_c
        self._anim_piece = piece
        self._anim_progress = 0.0
        self._anim_callback = on_finished
        self._anim_start_time = 0
        self._anim_timer.start(16)
        self.update()

    def set_board(self, board: Board):
        self.board = board
        self.update()

    def set_selected(self, square: Optional[Tuple[int, int]], destinations: List[Tuple[int, int]]):
        self.selected_square = square
        self.legal_destinations = destinations
        self.update()

    def set_last_move(self, move: Optional[Tuple[int, int, int, int]]):
        self.last_move = move
        self.update()

    def sizeHint(self):
        return QSize(10 * self.square_size + 2 * self.margin,
                     10 * self.square_size + 2 * self.margin)

    def _row_col_to_rect(self, row: int, col: int) -> QRect:
        if self.flipped:
            view_row = row
            view_col = 9 - col
        else:
            view_row = 9 - row
            view_col = col
        x = self.margin + view_col * self.square_size
        y = self.margin + view_row * self.square_size
        return QRect(x, y, self.square_size, self.square_size)

    def _pixel_to_square(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        x -= self.margin
        y -= self.margin
        if x < 0 or y < 0:
            return None
        view_col = x // self.square_size
        view_row = y // self.square_size
        if view_col >= 10 or view_row >= 10:
            return None
        if self.flipped:
            col = 9 - view_col
            row = view_row
        else:
            col = view_col
            row = 9 - view_row
        return (row, col)

    def mousePressEvent(self, event):
        pos = event.position()
        square = self._pixel_to_square(pos.x(), pos.y())
        if square is not None:
            self.square_clicked.emit(square[0], square[1])

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw_board(painter)
        self._draw_coordinates(painter)
        self._draw_pieces(painter)
        self._draw_highlights(painter)
        self._draw_last_move(painter)
        self._draw_arrows(painter)
        self._draw_markers(painter)

    def _draw_board(self, painter: QPainter):
        for r in range(10):
            for c in range(10):
                rect = self._row_col_to_rect(r, c)
                if (r + c) % 2 == 0:
                    painter.fillRect(rect, QColor(240, 217, 181))
                else:
                    painter.fillRect(rect, QColor(181, 136, 99))

    def _draw_coordinates(self, painter: QPainter):
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0))
        for c in range(10):
            if self.flipped:
                col_char = chr(ord('a') + (9 - c))
            else:
                col_char = chr(ord('a') + c)
            x = self.margin + c * self.square_size + self.square_size // 2
            y_bottom = self.margin + 10 * self.square_size + 15
            painter.drawText(QRect(x - 10, y_bottom, 20, 20), Qt.AlignCenter, col_char)
            y_top = self.margin - 25
            painter.drawText(QRect(x - 10, y_top, 20, 20), Qt.AlignCenter, col_char)
        for r in range(10):
            if self.flipped:
                rank_num = str(r)
            else:
                rank_num = str(9 - r)
            y = self.margin + r * self.square_size + self.square_size // 2
            x_left = self.margin - 25
            x_right = self.margin + 10 * self.square_size + 5
            painter.drawText(QRect(x_left, y - 10, 20, 20), Qt.AlignCenter, rank_num)
            painter.drawText(QRect(x_right, y - 10, 20, 20), Qt.AlignCenter, rank_num)

    def _draw_pieces(self, painter: QPainter):
        for r in range(10):
            for c in range(10):
                if self._animating and (r, c) == (self._anim_from_r, self._anim_from_c):
                    continue
                piece = self.board.get_piece(r, c)
                if piece is None:
                    continue
                rect = self._row_col_to_rect(r, c)
                pixmap = self.piece_pixmaps.get((piece.colour, piece.ptype))
                if pixmap:
                    painter.drawPixmap(rect, pixmap)
                else:
                    font = QFont("Arial", int(self.square_size * 0.7), QFont.Bold)
                    painter.setFont(font)
                    if piece.colour == Colour.WHITE:
                        painter.setPen(QColor(255, 255, 255))
                        painter.setBrush(QColor(255, 255, 255))
                    else:
                        painter.setPen(QColor(0, 0, 0))
                        painter.setBrush(QColor(0, 0, 0))
                    symbol = PIECE_SYMBOLS[piece.ptype]
                    painter.drawText(rect, Qt.AlignCenter,
                                     symbol if piece.colour == Colour.WHITE else symbol.lower())

        if self._animating and self._anim_piece is not None:
            from_rect = self._row_col_to_rect(self._anim_from_r, self._anim_from_c)
            to_rect = self._row_col_to_rect(self._anim_to_r, self._anim_to_c)
            cx = from_rect.x() + self._anim_progress * (to_rect.x() - from_rect.x())
            cy = from_rect.y() + self._anim_progress * (to_rect.y() - from_rect.y())
            anim_rect = QRect(int(cx), int(cy), self.square_size, self.square_size)
            pixmap = self.piece_pixmaps.get((self._anim_piece.colour, self._anim_piece.ptype))
            if pixmap:
                painter.drawPixmap(anim_rect, pixmap)
            else:
                font = QFont("Arial", int(self.square_size * 0.7), QFont.Bold)
                painter.setFont(font)
                if self._anim_piece.colour == Colour.WHITE:
                    painter.setPen(QColor(255, 255, 255))
                    painter.setBrush(QColor(255, 255, 255))
                else:
                    painter.setPen(QColor(0, 0, 0))
                    painter.setBrush(QColor(0, 0, 0))
                symbol = PIECE_SYMBOLS[self._anim_piece.ptype]
                painter.drawText(anim_rect, Qt.AlignCenter,
                                 symbol if self._anim_piece.colour == Colour.WHITE else symbol.lower())

    def _draw_highlights(self, painter: QPainter):
        if self.selected_square is not None:
            r, c = self.selected_square
            rect = self._row_col_to_rect(r, c)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 0), 3))
            painter.drawRect(rect)
        for r, c in self.legal_destinations:
            rect = self._row_col_to_rect(r, c)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 255, 0, 80))
            painter.drawEllipse(rect.center(), self.square_size // 5, self.square_size // 5)

    def _draw_last_move(self, painter: QPainter):
        if self.last_move is None:
            return
        fr, fc, tr, tc = self.last_move
        for r, c in [(fr, fc), (tr, tc)]:
            rect = self._row_col_to_rect(r, c)
            painter.setPen(QPen(QColor(255, 255, 0, 120), 0))
            painter.setBrush(QColor(255, 255, 0, 80))
            painter.drawRect(rect)

    def _draw_arrows(self, painter: QPainter):
        if not self.arrows:
            return
        for arrow in self.arrows:
            from_rect = self._row_col_to_rect(arrow.from_r, arrow.from_c)
            to_rect = self._row_col_to_rect(arrow.to_r, arrow.to_c)
            p1 = from_rect.center()
            p2 = to_rect.center()
            self._paint_arrow(painter, p1, p2, arrow.color, arrow.width)

    def _paint_arrow(self, painter, p1: QPointF, p2: QPointF, color: QColor, width: int):
        pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(p1, p2)
        arrow_len = 10.0
        line = QLineF(p2, p1)
        if line.length() < 1:
            return
        dx = (p1.x() - p2.x()) / line.length()
        dy = (p1.y() - p2.y()) / line.length()
        head_p1 = QPointF(p2.x() + dx * arrow_len * 0.8, p2.y() + dy * arrow_len * 0.8)
        left = QPointF(head_p1.x() - dx * arrow_len * 0.5 + dy * arrow_len * 0.3,
                       head_p1.y() - dy * arrow_len * 0.5 - dx * arrow_len * 0.3)
        right = QPointF(head_p1.x() - dx * arrow_len * 0.5 - dy * arrow_len * 0.3,
                        head_p1.y() - dy * arrow_len * 0.5 + dx * arrow_len * 0.3)
        arrow_head = QPolygonF([QPointF(p2), left, right, QPointF(p2)])
        painter.setBrush(color)
        painter.drawPolygon(arrow_head)

    def _draw_markers(self, painter: QPainter):
        if not self.markers:
            return
        for marker in self.markers:
            rect = self._row_col_to_rect(marker.row, marker.col)
            offsets = {
                "tl": (0, 0),
                "tr": (self.square_size - marker.radius * 2, 0),
                "bl": (0, self.square_size - marker.radius * 2),
                "br": (self.square_size - marker.radius * 2, self.square_size - marker.radius * 2),
                "center": ((self.square_size - marker.radius * 2) // 2, (self.square_size - marker.radius * 2) // 2)
            }
            ox, oy = offsets.get(marker.corner, offsets["center"])
            x = rect.x() + ox
            y = rect.y() + oy
            painter.setBrush(marker.color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x + marker.radius, y + marker.radius), marker.radius, marker.radius)

    def _animation_step(self):
        import time
        if self._anim_start_time == 0:
            self._anim_start_time = time.monotonic()
        elapsed = (time.monotonic() - self._anim_start_time) * 1000
        self._anim_progress = min(elapsed / self._anim_duration_ms, 1.0)
        self.update()
        if self._anim_progress >= 1.0:
            self._anim_timer.stop()
            self._animating = False
            if self._anim_callback:
                cb = self._anim_callback
                self._anim_callback = None
                cb()