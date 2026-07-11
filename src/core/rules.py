from __future__ import annotations
from typing import List, Optional
from .pieces import Piece, PieceType, Colour, PROMOTABLE_TYPES
from .board import Board, ROWS, COLS
from .movegen import pseudo_legal_moves, Move, _is_promotion_zone

def _in_bounds(r, c):
    return 0 <= r < ROWS and 0 <= c < COLS

# -------------------------------------------------------------------
#  Check detection
# -------------------------------------------------------------------
def is_check(board: Board, colour: Colour) -> bool:
    """Return True if `colour`'s king is in check."""
    king_pos = board.find_king(colour)
    if not king_pos:
        return False
    kr, kc = king_pos
    opponent = colour.opponent()
    for move in pseudo_legal_moves(board, opponent):
        if move.to_r == kr and move.to_c == kc:
            return True
    return False

# -------------------------------------------------------------------
#  Apply a move to a board copy (used during legality testing)
# -------------------------------------------------------------------
def _apply_move(board: Board, move: Move):
    piece = board.get_piece(move.from_r, move.from_c)
    board.clear_square(move.from_r, move.from_c)
    # handle captured piece automatically when we overwrite the square
    board.clear_square(move.to_r, move.to_c)   # just in case
    if move.promotion is not None:
        piece = Piece(move.promotion, piece.colour)
    board.set_piece(move.to_r, move.to_c, piece)

# -------------------------------------------------------------------
#  Check if a piece can still move after promoting (pawns etc.)
# -------------------------------------------------------------------
def _piece_can_still_move(board: Board, row: int, col: int, ptype: PieceType, colour: Colour) -> bool:
    """True if a piece of type `ptype` at (row,col) has at least one legal move.
       Used to enforce that forced promotions don't leave a piece immobile."""
    forward = 1 if colour == Colour.WHITE else -1
    if ptype == PieceType.PAWN:
        if _in_bounds(row + forward, col) and board.is_empty(row + forward, col):
            return True
        for dc in (-1, 1):
            nr, nc = row + forward, col + dc
            if _in_bounds(nr, nc):
                target = board.get_piece(nr, nc)
                if target and target.colour != colour:
                    return True
    elif ptype == PieceType.LANCE:
        r = row + forward
        while 0 <= r < ROWS:
            if board.is_empty(r, col):
                return True
            target = board.get_piece(r, col)
            if target and target.colour != colour:
                return True
            break
    elif ptype == PieceType.HORSE:
        nr = row + 2 * forward
        for dc in (-1, 1):
            if _in_bounds(nr, col + dc):
                target = board.get_piece(nr, col + dc)
                if target is None or target.colour != colour:
                    return True
    elif ptype == PieceType.EAGLE:
        for dc in (1, -1):
            r, c = row + forward, col + dc
            while _in_bounds(r, c):
                target = board.get_piece(r, c)
                if target is None or target.colour != colour:
                    return True
                if target is not None:
                    break
                r += forward
                c += dc
    return False

# -------------------------------------------------------------------
#  Legal move generation
# -------------------------------------------------------------------
def legal_moves(board: Board, colour: Colour) -> List[Move]:
    moves = []
    for move in pseudo_legal_moves(board, colour):
        # Make the move on a copy of the board
        new_board = board.copy()
        _apply_move(new_board, move)

        # 1. King safety
        if is_check(new_board, colour):
            continue

        # 2. Forced promotion rule: if a promotable piece moves into the
        #    promotion zone without promoting, it must still be able to move
        #    (otherwise the move is illegal because it would be stuck).
        piece = board.get_piece(move.from_r, move.from_c)
        if piece and piece.ptype in PROMOTABLE_TYPES and move.promotion is None:
            if _is_promotion_zone(move.to_r, colour):
                if not _piece_can_still_move(new_board, move.to_r, move.to_c,
                                             piece.ptype, colour):
                    continue
        moves.append(move)
    return moves

def has_legal_moves(board: Board, colour: Colour) -> bool:
    return len(legal_moves(board, colour)) > 0

# -------------------------------------------------------------------
#  Material count for dead position detection
# -------------------------------------------------------------------
def material_score(board: Board, colour: Colour) -> int:
    score = 0
    for r in range(ROWS):
        for c in range(COLS):
            piece = board.get_piece(r, c)
            if piece and piece.colour == colour:
                ptype = piece.ptype
                if ptype == PieceType.QUEEN:
                    score += 25
                elif ptype in (PieceType.ROOK, PieceType.BISHOP, PieceType.BERS,
                               PieceType.DRAGON, PieceType.GOLD, PieceType.HUNTER):
                    score += 5
                else:
                    score += 1
    return score

def is_dead_position(board: Board) -> bool:
    white_material = False
    black_material = False
    mating_set = {PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP,
                  PieceType.BERS, PieceType.DRAGON, PieceType.GOLD, PieceType.HUNTER,
                  PieceType.PAWN}
    for r in range(ROWS):
        for c in range(COLS):
            piece = board.get_piece(r, c)
            if piece and piece.ptype in mating_set:
                if piece.colour == Colour.WHITE:
                    white_material = True
                else:
                    black_material = True
    return not (white_material and black_material)