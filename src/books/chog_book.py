import struct
import os
from typing import List, Optional, Tuple
from src.core.movegen import Move
from src.core.pieces import Piece, Colour, PieceType, PIECE_SYMBOLS
from src.core.board import Board, ROWS, COLS

# ----------------------------------------------------------------------
# Zobrist table generation (deterministic)
# ----------------------------------------------------------------------
import random
rng = random.Random(0x9E3779B97F4A7C15)  # good seed
ZOBRIST_TABLE = {}
for colour in Colour:
    for ptype in PieceType:
        for sq in range(ROWS * COLS):
            ZOBRIST_TABLE[(ptype, colour, sq)] = rng.getrandbits(64)
ZOBRIST_SIDE = rng.getrandbits(64)

def compute_zobrist(board: Board) -> int:
    h = 0
    for r in range(ROWS):
        for c in range(COLS):
            piece = board.get_piece(r, c)
            if piece:
                sq = r * COLS + c
                h ^= ZOBRIST_TABLE[(piece.ptype, piece.colour, sq)]
    # Side to move is not included in Polyglot; we can ignore to match behaviour.
    return h

# ----------------------------------------------------------------------
# Move encoding / decoding (for binary book)
# ----------------------------------------------------------------------
def encode_move(move: Move) -> int:
    """Pack from(0-99), to(0-99), promotion(0-17 or 63 for none) into a 24-bit int."""
    promo_code = move.promotion.value if move.promotion else 63
    return (move.from_r * COLS + move.from_c) << 17 | (move.to_r * COLS + move.to_c) << 10 | promo_code

def decode_move(encoded: int) -> Move:
    promo_code = encoded & 0x3F   # 6 bits
    to_sq = (encoded >> 10) & 0x7F   # 7 bits
    from_sq = (encoded >> 17) & 0x7F
    from_r, from_c = divmod(from_sq, COLS)
    to_r, to_c = divmod(to_sq, COLS)
    promotion = PieceType(promo_code) if promo_code < len(PieceType) else None
    return Move(from_r, from_c, to_r, to_c, promotion)

# ----------------------------------------------------------------------
# Book reader/writer
# ----------------------------------------------------------------------
class ChogBook:
    def __init__(self, path: str):
        self.path = path
        if not os.path.exists(path):
            # create empty file
            with open(path, 'wb') as f:
                pass

    def lookup(self, board: Board) -> List[Tuple[Move, int]]:
        """Return list of (move, weight) for the given board position."""
        key = compute_zobrist(board)
        entries = []
        with open(self.path, 'rb') as f:
            while True:
                data = f.read(24)
                if len(data) < 24:
                    break
                ekey, emove, weight, learn = struct.unpack('>Q I H I', data)
                # The key in file is big-endian? Polyglot uses big-endian for key but little for others.
                # We'll use big-endian for key, little for rest.
                # Actually standard Polyglot: key big-endian, move big-endian, weight big-endian, learn big-endian.
                # Simpler: everything big-endian.
                if ekey == key:
                    move = decode_move(emove)
                    entries.append((move, weight))
        return entries

    def add_entry(self, board: Board, move: Move, weight: int = 1):
        """Add or increment a move entry."""
        key = compute_zobrist(board)
        emove = encode_move(move)
        # Read existing entries, update or append
        entries = []
        found = False
        if os.path.getsize(self.path) > 0:
            with open(self.path, 'rb') as f:
                while True:
                    data = f.read(24)
                    if len(data) < 24:
                        break
                    ekey, em, w, l = struct.unpack('>Q I H I', data)
                    if ekey == key and em == emove:
                        w += weight
                        found = True
                    entries.append((ekey, em, w, l))
        if not found:
            entries.append((key, emove, weight, 0))
        # Sort by key for faster binary search? Not necessary for small files.
        with open(self.path, 'wb') as f:
            for k, m, w, l in entries:
                f.write(struct.pack('>Q I H I', k, m, w, l))

    def remove_entry(self, board: Board, move: Move):
        """Remove all entries for a given board/move."""
        key = compute_zobrist(board)
        emove = encode_move(move)
        entries = []
        with open(self.path, 'rb') as f:
            while True:
                data = f.read(24)
                if len(data) < 24:
                    break
                ekey, em, w, l = struct.unpack('>Q I H I', data)
                if ekey != key or em != emove:
                    entries.append((ekey, em, w, l))
        with open(self.path, 'wb') as f:
            for k, m, w, l in entries:
                f.write(struct.pack('>Q I H I', k, m, w, l))