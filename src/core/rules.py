from __future__ import annotations
from typing import List, Optional
from .pieces import Piece, PieceType, Colour, PROMOTABLE_TYPES
from .board import Board, ROWS, COLS
from .movegen import pseudo_legal_moves, Move, _is_promotion_zone

def _piece_can_move_from(board: Board, row: int, col: int, ptype: PieceType, colour: Colour) -> bool:
    return _piece_can_move_check(board, row, col, ptype, colour)

def _piece_can_move_check(board: Board, r: int, c: int, ptype: PieceType, colour: Colour) -> bool:
    forward = 1 if colour == Colour.WHITE else -1
    def valid_target(nr, nc):
        if not (0 <= nr < ROWS and 0 <= nc < COLS):
            return False
        target = board.get_piece(nr, nc)
        return target is None or target.colour != colour

    if ptype == PieceType.PAWN:
        if _in_bounds(r+forward, c) and board.is_empty(r+forward, c):
            return True
        for dc in (-1, 1):
            nr, nc = r+forward, c+dc
            if _in_bounds(nr, nc):
                target = board.get_piece(nr, nc)
                if target and target.colour != colour:
                    return True
    elif ptype == PieceType.LANCE:
        nr = r + forward
        while 0 <= nr < ROWS:
            if board.is_empty(nr, c):
                return True
            target = board.get_piece(nr, c)
            if target and target.colour != colour:
                return True
            break
    elif ptype == PieceType.HORSE:
        nr = r + 2*forward
        for dc in (-1, 1):
            if _in_bounds(nr, c+dc):
                target = board.get_piece(nr, c+dc)
                if target is None or target.colour != colour:
                    return True
    elif ptype == PieceType.EAGLE:
        for dc in (1, -1):
            nr, nc = r+forward, c+dc
            while _in_bounds(nr, nc):
                target = board.get_piece(nr, nc)
                if target is None or target.colour != colour:
                    return True
                if target is not None:
                    break
                nr += forward; nc += dc
    return False

def _in_bounds(r, c): return 0 <= r < ROWS and 0 <= c < COLS

def is_check(board: Board, colour: Colour) -> bool:
    king_pos = board.find_king(colour)
    if not king_pos:
        return False
    kr, kc = king_pos
    opponent = colour.opponent()
    for move in pseudo_legal_moves(board, opponent):
        if move.to_r == kr and move.to_c == kc:
            return True
    return False

def legal_moves(board: Board, colour: Colour) -> List[Move]:
    moves = []
    for move in pseudo_legal_moves(board, colour):
        new_board = board.copy()
        _apply_move_to_board(new_board, move)
        if is_check(new_board, colour):
            continue
        piece = board.get_piece(move.from_r, move.from_c)
        if piece and piece.ptype in PROMOTABLE_TYPES and move.promotion is None:
            if _is_promotion_zone(move.to_r, colour):
                if not _piece_can_move_from(new_board, move.to_r, move.to_c, piece.ptype, colour):
                    continue
        moves.append(move)
    return moves

def has_legal_moves(board: Board, colour: Colour) -> bool:
    return len(legal_moves(board, colour)) > 0

def _apply_move_to_board(board: Board, move: Move):
    piece = board.get_piece(move.from_r, move.from_c)
    board.clear_square(move.from_r, move.from_c)
    if move.promotion is not None:
        piece = Piece(move.promotion, piece.colour)
    board.set_piece(move.to_r, move.to_c, piece)

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