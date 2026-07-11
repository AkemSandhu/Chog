from __future__ import annotations
from typing import Optional, List, Tuple
from .pieces import Piece, PieceType, Colour
import random

ROWS = 10
COLS = 10

# Packed piece representation: (ptype << 1) | colour
EMPTY = 0

def _pack(ptype: PieceType, colour: Colour) -> int:
    return (ptype.value << 1) | colour.value

def _unpack(v: int) -> Optional[Piece]:
    if v == EMPTY:
        return None
    ptype = PieceType(v >> 1)
    colour = Colour(v & 1)
    return Piece(ptype, colour)

# Zobrist table
rng = random.Random(0x9E3779B97F4A7C15)
ZOBRIST_TABLE = []
for ptype in PieceType:
    colour_table = []
    for col in Colour:
        sq_table = [rng.getrandbits(64) for _ in range(ROWS * COLS)]
        colour_table.append(sq_table)
    ZOBRIST_TABLE.append(colour_table)
ZOBRIST_SIDE = rng.getrandbits(64)

class Board:
    __slots__ = ('grid', 'zobrist', 'piece_counts')
    def __init__(self):
        self.grid = [EMPTY] * (ROWS * COLS)
        self.zobrist = 0
        self.piece_counts = [[0] * len(PieceType) for _ in range(2)]

    @staticmethod
    def starting_position() -> Board:
        board = Board()
        # Black back rank
        row9 = [
            (9, 0, PieceType.LANCE, Colour.BLACK),
            (9, 1, PieceType.HORSE, Colour.BLACK),
            (9, 2, PieceType.ELEPHANT, Colour.BLACK),
            (9, 3, PieceType.GENERAL, Colour.BLACK),
            (9, 4, PieceType.QUEEN, Colour.BLACK),
            (9, 5, PieceType.KING, Colour.BLACK),
            (9, 6, PieceType.GENERAL, Colour.BLACK),
            (9, 7, PieceType.ELEPHANT, Colour.BLACK),
            (9, 8, PieceType.HORSE, Colour.BLACK),
            (9, 9, PieceType.LANCE, Colour.BLACK),
        ]
        row8 = [
            (8, 0, PieceType.ROOK, Colour.BLACK),
            (8, 1, PieceType.EAGLE, Colour.BLACK),
            (8, 2, PieceType.BISHOP, Colour.BLACK),
            (8, 3, PieceType.WAZIR, Colour.BLACK),
            (8, 4, PieceType.FERZ, Colour.BLACK),
            (8, 5, PieceType.FERZ, Colour.BLACK),
            (8, 6, PieceType.WAZIR, Colour.BLACK),
            (8, 7, PieceType.BISHOP, Colour.BLACK),
            (8, 8, PieceType.EAGLE, Colour.BLACK),
            (8, 9, PieceType.ROOK, Colour.BLACK),
        ]
        # Black pawns
        row7 = [(7, c, PieceType.PAWN, Colour.BLACK) for c in range(10)]
        # White pawns (row 2)
        row2 = [(2, c, PieceType.PAWN, Colour.WHITE) for c in range(10)]
        # White pieces (mirror of Black)
        row1 = [(1, c, pt, Colour.WHITE) for (_, c, pt, _) in row8]
        row0 = [(0, c, pt, Colour.WHITE) for (_, c, pt, _) in row9]

        for piece_list in (row9, row8, row7, row2, row1, row0):
            for r, c, pt, col in piece_list:
                board.set_piece(r, c, Piece(pt, col))
        return board

    def _index(self, r: int, c: int) -> int:
        return r * COLS + c

    def get_piece(self, r: int, c: int) -> Optional[Piece]:
        if 0 <= r < ROWS and 0 <= c < COLS:
            return _unpack(self.grid[self._index(r, c)])
        return None

    def set_piece(self, r: int, c: int, piece: Optional[Piece]):
        if not (0 <= r < ROWS and 0 <= c < COLS):
            return
        idx = self._index(r, c)
        old = self.grid[idx]
        # Remove old piece
        if old != EMPTY:
            op = _unpack(old)
            self.zobrist ^= ZOBRIST_TABLE[op.ptype.value][op.colour.value][idx]
            self.piece_counts[op.colour.value][op.ptype.value] -= 1
        # Place new piece
        if piece:
            self.grid[idx] = _pack(piece.ptype, piece.colour)
            self.zobrist ^= ZOBRIST_TABLE[piece.ptype.value][piece.colour.value][idx]
            self.piece_counts[piece.colour.value][piece.ptype.value] += 1
        else:
            self.grid[idx] = EMPTY

    def clear_square(self, r: int, c: int):
        self.set_piece(r, c, None)

    def is_empty(self, r: int, c: int) -> bool:
        return self.grid[self._index(r, c)] == EMPTY

    def all_pieces(self, colour: Colour) -> List[Tuple[int, int, Piece]]:
        pieces = []
        for idx, v in enumerate(self.grid):
            if v != EMPTY:
                p = _unpack(v)
                if p.colour == colour:
                    r, c = divmod(idx, COLS)
                    pieces.append((r, c, p))
        return pieces

    def find_king(self, colour: Colour) -> Optional[Tuple[int, int]]:
        for idx, v in enumerate(self.grid):
            if v != EMPTY:
                p = _unpack(v)
                if p.ptype == PieceType.KING and p.colour == colour:
                    return divmod(idx, COLS)
        return None

    def copy(self) -> Board:
        new_board = Board()
        new_board.grid = self.grid[:]
        new_board.zobrist = self.zobrist
        new_board.piece_counts = [row[:] for row in self.piece_counts]
        return new_board