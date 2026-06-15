from enum import IntEnum
from typing import Optional

class Colour(IntEnum):
    WHITE = 0
    BLACK = 1

    def opponent(self) -> 'Colour':
        return Colour.BLACK if self == Colour.WHITE else Colour.WHITE

class PieceType(IntEnum):
    PAWN = 0       # P
    ROOK = 1       # R
    EAGLE = 2      # A
    BISHOP = 3     # B
    WAZIR = 4      # W
    FERZ = 5       # F
    LANCE = 6      # L
    HORSE = 7      # H
    ELEPHANT = 8   # E
    GENERAL = 9    # G
    KNIGHT = 10    # N
    QUEEN = 11     # Q
    KING = 12      # K
    BERS = 13      # S  (promoted Lance)
    DRAGON = 14    # D  (promoted Eagle)
    GOLD = 15      # O  (promoted Pawn choice)
    HUNTER = 16    # U  (promoted Pawn choice)

PROMOTABLE_TYPES = {PieceType.PAWN, PieceType.LANCE, PieceType.HORSE, PieceType.EAGLE}

PROMOTION_TARGETS = {
    PieceType.PAWN: [PieceType.GOLD, PieceType.HUNTER],
    PieceType.LANCE: [PieceType.BERS],
    PieceType.HORSE: [PieceType.KNIGHT],
    PieceType.EAGLE: [PieceType.DRAGON],
}

PIECE_SYMBOLS = {
    PieceType.PAWN: 'P', PieceType.ROOK: 'R', PieceType.EAGLE: 'A',
    PieceType.BISHOP: 'B', PieceType.WAZIR: 'W', PieceType.FERZ: 'F',
    PieceType.LANCE: 'L', PieceType.HORSE: 'H', PieceType.ELEPHANT: 'E',
    PieceType.GENERAL: 'G', PieceType.KNIGHT: 'N', PieceType.QUEEN: 'Q',
    PieceType.KING: 'K', PieceType.BERS: 'S', PieceType.DRAGON: 'D',
    PieceType.GOLD: 'O', PieceType.HUNTER: 'U',
}

class Piece:
    __slots__ = ('ptype', 'colour')
    def __init__(self, ptype: PieceType, colour: Colour):
        self.ptype = ptype
        self.colour = colour

    def symbol(self) -> str:
        s = PIECE_SYMBOLS[self.ptype]
        return s if self.colour == Colour.WHITE else s.lower()

    def __repr__(self) -> str:
        return f"Piece({self.ptype.name}, {self.colour.name})"

    def __eq__(self, other):
        return isinstance(other, Piece) and self.ptype == other.ptype and self.colour == other.colour