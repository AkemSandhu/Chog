from __future__ import annotations
from typing import Optional, List, Tuple
from .pieces import Piece, PieceType, Colour

ROWS = 10
COLS = 10

class Board:
    def __init__(self):
        self.grid: List[List[Optional[Piece]]] = [[None for _ in range(COLS)] for _ in range(ROWS)]

    @staticmethod
    def starting_position() -> Board:
        board = Board()
        board.set_row(9, [Piece(PieceType.LANCE, Colour.BLACK),
                          Piece(PieceType.HORSE, Colour.BLACK),
                          Piece(PieceType.ELEPHANT, Colour.BLACK),
                          Piece(PieceType.GENERAL, Colour.BLACK),
                          Piece(PieceType.QUEEN, Colour.BLACK),
                          Piece(PieceType.KING, Colour.BLACK),
                          Piece(PieceType.GENERAL, Colour.BLACK),
                          Piece(PieceType.ELEPHANT, Colour.BLACK),
                          Piece(PieceType.HORSE, Colour.BLACK),
                          Piece(PieceType.LANCE, Colour.BLACK)])
        board.set_row(8, [Piece(PieceType.ROOK, Colour.BLACK),
                          Piece(PieceType.EAGLE, Colour.BLACK),
                          Piece(PieceType.BISHOP, Colour.BLACK),
                          Piece(PieceType.WAZIR, Colour.BLACK),
                          Piece(PieceType.FERZ, Colour.BLACK),
                          Piece(PieceType.FERZ, Colour.BLACK),
                          Piece(PieceType.WAZIR, Colour.BLACK),
                          Piece(PieceType.BISHOP, Colour.BLACK),
                          Piece(PieceType.EAGLE, Colour.BLACK),
                          Piece(PieceType.ROOK, Colour.BLACK)])
        board.set_row(7, [Piece(PieceType.PAWN, Colour.BLACK) for _ in range(COLS)])
        board.set_row(2, [Piece(PieceType.PAWN, Colour.WHITE) for _ in range(COLS)])
        board.set_row(1, [Piece(PieceType.ROOK, Colour.WHITE),
                          Piece(PieceType.EAGLE, Colour.WHITE),
                          Piece(PieceType.BISHOP, Colour.WHITE),
                          Piece(PieceType.WAZIR, Colour.WHITE),
                          Piece(PieceType.FERZ, Colour.WHITE),
                          Piece(PieceType.FERZ, Colour.WHITE),
                          Piece(PieceType.WAZIR, Colour.WHITE),
                          Piece(PieceType.BISHOP, Colour.WHITE),
                          Piece(PieceType.EAGLE, Colour.WHITE),
                          Piece(PieceType.ROOK, Colour.WHITE)])
        board.set_row(0, [Piece(PieceType.LANCE, Colour.WHITE),
                          Piece(PieceType.HORSE, Colour.WHITE),
                          Piece(PieceType.ELEPHANT, Colour.WHITE),
                          Piece(PieceType.GENERAL, Colour.WHITE),
                          Piece(PieceType.QUEEN, Colour.WHITE),
                          Piece(PieceType.KING, Colour.WHITE),
                          Piece(PieceType.GENERAL, Colour.WHITE),
                          Piece(PieceType.ELEPHANT, Colour.WHITE),
                          Piece(PieceType.HORSE, Colour.WHITE),
                          Piece(PieceType.LANCE, Colour.WHITE)])
        return board

    def set_row(self, row: int, pieces: List[Piece]):
        for col, piece in enumerate(pieces):
            self.grid[row][col] = piece

    def get_piece(self, row: int, col: int) -> Optional[Piece]:
        if 0 <= row < ROWS and 0 <= col < COLS:
            return self.grid[row][col]
        return None

    def set_piece(self, row: int, col: int, piece: Optional[Piece]):
        if 0 <= row < ROWS and 0 <= col < COLS:
            self.grid[row][col] = piece

    def clear_square(self, row: int, col: int):
        self.set_piece(row, col, None)

    def is_empty(self, row: int, col: int) -> bool:
        return self.get_piece(row, col) is None

    def copy(self) -> Board:
        new_board = Board()
        for r in range(ROWS):
            for c in range(COLS):
                piece = self.grid[r][c]
                if piece:
                    new_board.grid[r][c] = Piece(piece.ptype, piece.colour)
        return new_board

    def all_pieces(self, colour: Colour) -> List[Tuple[int, int, Piece]]:
        pieces = []
        for r in range(ROWS):
            for c in range(COLS):
                p = self.grid[r][c]
                if p and p.colour == colour:
                    pieces.append((r, c, p))
        return pieces

    def find_king(self, colour: Colour) -> Optional[Tuple[int, int]]:
        for r in range(ROWS):
            for c in range(COLS):
                p = self.grid[r][c]
                if p and p.ptype == PieceType.KING and p.colour == colour:
                    return (r, c)
        return None