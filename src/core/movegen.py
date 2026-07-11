"""
Move generation for Chog.
Provides fast raw tuple generation and a standard Move dataclass.
"""
from dataclasses import dataclass
from typing import List, Tuple, Optional as Opt
from src.core.pieces import Piece, PieceType, Colour, PROMOTABLE_TYPES, PROMOTION_TARGETS
from src.core.board import Board, ROWS, COLS

# ----------------------------------------------------------------------
#  Standard Move class (used by GUI, protocol, etc.)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Move:
    from_r: int
    from_c: int
    to_r: int
    to_c: int
    promotion: Opt[PieceType] = None

    def __repr__(self):
        s = f"{chr(ord('a')+self.from_c)}{self.from_r}{chr(ord('a')+self.to_c)}{self.to_r}"
        if self.promotion is not None:
            s += f"={self.promotion.symbol()}"
        return s

def raw_to_move(raw: tuple) -> Move:
    """Convert a raw move tuple to a Move object."""
    fr, fc, tr, tc, p = raw
    promo = PieceType(p) if p != -1 else None
    return Move(fr, fc, tr, tc, promo)

# ----------------------------------------------------------------------
#  Helper functions
# ----------------------------------------------------------------------
def _in_bounds(r: int, c: int) -> bool:
    return 0 <= r < ROWS and 0 <= c < COLS

def _is_promotion_zone(row: int, colour: Colour) -> bool:
    """True if a pawn/piece on this row can promote."""
    return row >= 8 if colour == Colour.WHITE else row <= 1

# ----------------------------------------------------------------------
#  Direction tables
# ----------------------------------------------------------------------
_SLIDE = {
    PieceType.ROOK:   [(1,0), (-1,0), (0,1), (0,-1)],
    PieceType.BISHOP: [(1,1), (1,-1), (-1,1), (-1,-1)],
    PieceType.QUEEN:  [(1,0), (-1,0), (0,1), (0,-1), (1,1), (1,-1), (-1,1), (-1,-1)],
    PieceType.LANCE:  [(1,0)],
    PieceType.EAGLE:  [(1,1), (1,-1)],
    PieceType.BERS:   [(1,0), (-1,0), (0,1), (0,-1)],
    PieceType.DRAGON: [(1,1), (1,-1), (-1,1), (-1,-1)],
    PieceType.GOLD:   [(1,0), (-1,0), (0,1), (0,-1)],
    PieceType.HUNTER: [(1,1), (1,-1), (-1,1), (-1,-1)],
}

_STEP = {
    PieceType.KING:    [(1,0), (-1,0), (0,1), (0,-1), (1,1), (1,-1), (-1,1), (-1,-1)],
    PieceType.KNIGHT:  [(2,1), (2,-1), (-2,1), (-2,-1), (1,2), (1,-2), (-1,2), (-1,-2)],
    PieceType.GENERAL: [(1,0), (-1,0), (0,1), (0,-1), (1,1), (1,-1)],
    PieceType.ELEPHANT:[(1,1), (1,-1), (-1,1), (-1,-1), (1,0)],
    PieceType.WAZIR:   [(1,0), (-1,0), (0,1), (0,-1)],
    PieceType.FERZ:    [(1,1), (1,-1), (-1,1), (-1,-1)],
}

# Piece values for capture ordering
_PIECE_VAL = {
    PieceType.PAWN:1, PieceType.LANCE:2, PieceType.HORSE:3, PieceType.ELEPHANT:3,
    PieceType.GENERAL:4, PieceType.WAZIR:1, PieceType.FERZ:1, PieceType.EAGLE:3,
    PieceType.BISHOP:4, PieceType.ROOK:5, PieceType.QUEEN:9, PieceType.KING:99,
    PieceType.KNIGHT:3, PieceType.BERS:6, PieceType.DRAGON:6, PieceType.GOLD:7,
    PieceType.HUNTER:6,
}

# ----------------------------------------------------------------------
#  Raw move generation (returns tuples, very fast)
# ----------------------------------------------------------------------
def pseudo_legal_moves_raw(board: Board, colour: Colour) -> List[Tuple[int, int, int, int, int]]:
    """
    Return list of raw moves: (from_r, from_c, to_r, to_c, promo_idx).
    promo_idx is -1 (no promotion) or PieceType.value.
    Uses the flat grid for maximum speed.
    """
    forward = 1 if colour == Colour.WHITE else -1
    moves = []
    grid = board.grid
    for idx, val in enumerate(grid):
        if val == 0:
            continue
        ptype = PieceType(val >> 1)
        pcol = Colour(val & 1)
        if pcol != colour:
            continue
        from_r, from_c = divmod(idx, COLS)
        dests = []

        # --- Pawn ---
        if ptype == PieceType.PAWN:
            push = from_r + forward
            if _in_bounds(push, from_c) and grid[push * COLS + from_c] == 0:
                dests.append((push, from_c))
            for dc in (-1, 1):
                tr, tc = from_r + forward, from_c + dc
                if _in_bounds(tr, tc):
                    tgt = grid[tr * COLS + tc]
                    if tgt != 0 and Colour(tgt & 1) != colour:
                        dests.append((tr, tc))

        # --- Lance ---
        elif ptype == PieceType.LANCE:
            r = from_r + forward
            while _in_bounds(r, from_c):
                tgt = grid[r * COLS + from_c]
                if tgt == 0:
                    dests.append((r, from_c))
                else:
                    if Colour(tgt & 1) != colour:
                        dests.append((r, from_c))
                    break
                r += forward

        # --- Horse ---
        elif ptype == PieceType.HORSE:
            nr = from_r + 2 * forward
            for dc in (-1, 1):
                nc = from_c + dc
                if _in_bounds(nr, nc):
                    tgt = grid[nr * COLS + nc]
                    if tgt == 0 or Colour(tgt & 1) != colour:
                        dests.append((nr, nc))

        # --- Eagle (forward diagonals) ---
        elif ptype == PieceType.EAGLE:
            for dc in (1, -1):
                r, c = from_r + forward, from_c + dc
                while _in_bounds(r, c):
                    tgt = grid[r * COLS + c]
                    if tgt == 0:
                        dests.append((r, c))
                    else:
                        if Colour(tgt & 1) != colour:
                            dests.append((r, c))
                        break
                    r += forward; c += dc

        # --- Sliding pieces (Rook, Bishop, Queen) ---
        elif ptype in _SLIDE:
            for dr, dc in _SLIDE[ptype]:
                r, c = from_r + dr, from_c + dc
                while _in_bounds(r, c):
                    tgt = grid[r * COLS + c]
                    if tgt == 0:
                        dests.append((r, c))
                    else:
                        if Colour(tgt & 1) != colour:
                            dests.append((r, c))
                        break
                    r += dr; c += dc

        # --- Stepping pieces ---
        elif ptype in _STEP:
            for dr, dc in _STEP[ptype]:
                tr, tc = from_r + dr, from_c + dc
                if not _in_bounds(tr, tc):
                    continue
                tgt = grid[tr * COLS + tc]
                if tgt == 0 or Colour(tgt & 1) != colour:
                    dests.append((tr, tc))

        # --- Bers (slide orthogonal + step like king) ---
        elif ptype == PieceType.BERS:
            for dr, dc in _SLIDE[PieceType.ROOK]:
                r, c = from_r + dr, from_c + dc
                while _in_bounds(r, c):
                    tgt = grid[r * COLS + c]
                    if tgt == 0:
                        dests.append((r, c))
                    else:
                        if Colour(tgt & 1) != colour:
                            dests.append((r, c))
                        break
                    r += dr; c += dc
            for dr, dc in _STEP[PieceType.KING]:
                tr, tc = from_r + dr, from_c + dc
                if _in_bounds(tr, tc):
                    tgt = grid[tr * COLS + tc]
                    if tgt == 0 or Colour(tgt & 1) != colour:
                        dests.append((tr, tc))

        # --- Dragon (slide diagonal + step like king) ---
        elif ptype == PieceType.DRAGON:
            for dr, dc in _SLIDE[PieceType.BISHOP]:
                r, c = from_r + dr, from_c + dc
                while _in_bounds(r, c):
                    tgt = grid[r * COLS + c]
                    if tgt == 0:
                        dests.append((r, c))
                    else:
                        if Colour(tgt & 1) != colour:
                            dests.append((r, c))
                        break
                    r += dr; c += dc
            for dr, dc in _STEP[PieceType.KING]:
                tr, tc = from_r + dr, from_c + dc
                if _in_bounds(tr, tc):
                    tgt = grid[tr * COLS + tc]
                    if tgt == 0 or Colour(tgt & 1) != colour:
                        dests.append((tr, tc))

        # --- Gold (slide orthogonal + slide forward diagonals) ---
        elif ptype == PieceType.GOLD:
            for dr, dc in _SLIDE[PieceType.ROOK]:
                r, c = from_r + dr, from_c + dc
                while _in_bounds(r, c):
                    tgt = grid[r * COLS + c]
                    if tgt == 0:
                        dests.append((r, c))
                    else:
                        if Colour(tgt & 1) != colour:
                            dests.append((r, c))
                        break
                    r += dr; c += dc
            for dc in (1, -1):
                r, c = from_r + forward, from_c + dc
                while _in_bounds(r, c):
                    tgt = grid[r * COLS + c]
                    if tgt == 0:
                        dests.append((r, c))
                    else:
                        if Colour(tgt & 1) != colour:
                            dests.append((r, c))
                        break
                    r += forward; c += dc

        # --- Hunter (slide diagonal + slide forward) ---
        elif ptype == PieceType.HUNTER:
            for dr, dc in _SLIDE[PieceType.BISHOP]:
                r, c = from_r + dr, from_c + dc
                while _in_bounds(r, c):
                    tgt = grid[r * COLS + c]
                    if tgt == 0:
                        dests.append((r, c))
                    else:
                        if Colour(tgt & 1) != colour:
                            dests.append((r, c))
                        break
                    r += dr; c += dc
            r = from_r + forward
            while _in_bounds(r, from_c):
                tgt = grid[r * COLS + from_c]
                if tgt == 0:
                    dests.append((r, from_c))
                else:
                    if Colour(tgt & 1) != colour:
                        dests.append((r, from_c))
                    break
                r += forward

        # --- Attach promotion suffixes ---
        in_zone = _is_promotion_zone(from_r, colour)
        for tr, tc in dests:
            if ptype in PROMOTABLE_TYPES and (in_zone or _is_promotion_zone(tr, colour)):
                for target in PROMOTION_TARGETS[ptype]:
                    moves.append((from_r, from_c, tr, tc, target.value))
                moves.append((from_r, from_c, tr, tc, -1))  # no promotion
            else:
                moves.append((from_r, from_c, tr, tc, -1))
    return moves


# ----------------------------------------------------------------------
#  Standard move generation (returns Move objects, used by rules etc.)
# ----------------------------------------------------------------------
def pseudo_legal_moves(board: Board, colour: Colour) -> List[Move]:
    """Return list of Move objects. Slightly slower, used for compatibility."""
    return [Move(r, c, tr, tc, PieceType(p) if p != -1 else None)
            for r, c, tr, tc, p in pseudo_legal_moves_raw(board, colour)]