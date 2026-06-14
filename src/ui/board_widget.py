import os
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPixmap
from PySide6.QtCore import Qt, QRect, Signal, QSize
from typing import List, Tuple, Optional

from chog.core.board import Board
from chog.core.pieces import Piece, Colour, PieceType, PIECE_SYMBOLS

class BoardWidget(QWidget):
    square_clicked = Signal(int, int)  # row, col

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

        # Load piece images
        self.piece_pixmaps = self._load_piece_images()

    def _load_piece_images(self) -> dict:
        """Return dict mapping (Colour, PieceType) -> QPixmap."""
        pixmaps = {}
        base_dir = os.path.join(os.path.dirname(__file__), "..", "resources", "pieces")
        for colour in Colour:
            colour_name = colour.name.lower()  # "white" / "black"
            for ptype in PieceType:
                ptype_name = ptype.name.lower()  # "pawn", "rook", …
                path = os.path.join(base_dir, f"{colour_name}_{ptype_name}.png")
                if os.path.exists(path):
                    pixmaps[(colour, ptype)] = QPixmap(path)
        return pixmaps

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

    def _draw_board(self, painter: QPainter):
        for r in range(10):
            for c in range(10):
                rect = self._row_col_to_rect(r, c)
                if (r + c) % 2 == 0:
                    painter.fillRect(rect, QColor(240, 217, 181))  # light
                else:
                    painter.fillRect(rect, QColor(181, 136, 99))   # dark

    def _draw_coordinates(self, painter: QPainter):
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0))
        for c in range(10):
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
                piece = self.board.get_piece(r, c)
                if piece is None:
                    continue
                rect = self._row_col_to_rect(r, c)
                pixmap = self.piece_pixmaps.get((piece.colour, piece.ptype))
                if pixmap:
                    painter.drawPixmap(rect, pixmap)
                else:
                    # Fallback to text
                    font = QFont("Arial", int(self.square_size * 0.7), QFont.Bold)
                    painter.setFont(font)
                    if piece.colour == Colour.WHITE:
                        painter.setPen(QColor(255, 255, 255))
                        painter.setBrush(QColor(255, 255, 255))
                    else:
                        painter.setPen(QColor(0, 0, 0))
                        painter.setBrush(QColor(0, 0, 0))
                    symbol = PIECE_SYMBOLS[piece.ptype]
                    painter.drawText(rect, Qt.AlignCenter, symbol if piece.colour == Colour.WHITE else symbol.lower())

    def _draw_highlights(self, painter: QPainter):
        if self.selected_square is not None:
            r, c = self.selected_square
            rect = self._row_col_to_rect(r, c)
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