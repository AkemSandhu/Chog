from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Generator
from .pieces import Piece, PieceType, Colour, PROMOTABLE_TYPES, PROMOTION_TARGETS
from .board import Board, ROWS, COLS

@dataclass(frozen=True)
class Move:
    from_r: int
    from_c: int
    to_r: int
    to_c: int
    promotion: Optional[PieceType] = None

    def __repr__(self):
        s = f"{chr(ord('a')+self.from_c)}{self.from_r}{chr(ord('a')+self.to_c)}{self.to_r}"
        if self.promotion is not None:
            s += f"={self.promotion.symbol()}"
        return s

def _in_bounds(r, c): return 0 <= r < ROWS and 0 <= c < COLS

def _sliding_moves(board: Board, r: int, c: int, directions: List[Tuple[int,int]], colour: Colour) -> Generator[Tuple[int,int], None, None]:
    for dr, dc in directions:
        nr, nc = r + dr, c + dc
        while _in_bounds(nr, nc):
            target = board.get_piece(nr, nc)
            if target is None:
                yield nr, nc
            else:
                if target.colour != colour:
                    yield nr, nc
                break
            nr += dr
            nc += dc

def _step_moves(board: Board, r: int, c: int, directions: List[Tuple[int,int]], colour: Colour) -> Generator[Tuple[int,int], None, None]:
    for dr, dc in directions:
        nr, nc = r + dr, c + dc
        if not _in_bounds(nr, nc):
            continue
        target = board.get_piece(nr, nc)
        if target is None or target.colour != colour:
            yield nr, nc

def pseudo_legal_moves(board: Board, colour: Colour) -> List[Move]:
    moves: List[Move] = []
    forward = 1 if colour == Colour.WHITE else -1
    pieces = board.all_pieces(colour)
    for r, c, piece in pieces:
        ptype = piece.ptype
        destinations = []
        if ptype == PieceType.PAWN:
            push_r = r + forward
            if _in_bounds(push_r, c) and board.is_empty(push_r, c):
                destinations.append((push_r, c))
            for dc in (-1, 1):
                cap_r, cap_c = r + forward, c + dc
                if _in_bounds(cap_r, cap_c):
                    target = board.get_piece(cap_r, cap_c)
                    if target and target.colour != colour:
                        destinations.append((cap_r, cap_c))
        elif ptype == PieceType.ROOK:
            for dest in _sliding_moves(board, r, c, [(1,0), (-1,0), (0,1), (0,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.EAGLE:
            for dest in _sliding_moves(board, r, c, [(forward,1), (forward,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.BISHOP:
            for dest in _sliding_moves(board, r, c, [(1,1), (1,-1), (-1,1), (-1,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.WAZIR:
            for dest in _step_moves(board, r, c, [(1,0), (-1,0), (0,1), (0,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.FERZ:
            for dest in _step_moves(board, r, c, [(1,1), (1,-1), (-1,1), (-1,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.LANCE:
            for dest in _sliding_moves(board, r, c, [(forward,0)], colour):
                destinations.append(dest)
        elif ptype == PieceType.HORSE:
            nr = r + 2*forward
            if _in_bounds(nr, c-1):
                target = board.get_piece(nr, c-1)
                if target is None or target.colour != colour:
                    destinations.append((nr, c-1))
            if _in_bounds(nr, c+1):
                target = board.get_piece(nr, c+1)
                if target is None or target.colour != colour:
                    destinations.append((nr, c+1))
        elif ptype == PieceType.ELEPHANT:
            dirs = [(1,1),(1,-1),(-1,1),(-1,-1)] + [(forward,0)]
            for dest in _step_moves(board, r, c, dirs, colour):
                destinations.append(dest)
        elif ptype == PieceType.GENERAL:
            dirs = [(1,0),(-1,0),(0,1),(0,-1)] + [(forward,1),(forward,-1)]
            for dest in _step_moves(board, r, c, dirs, colour):
                destinations.append(dest)
        elif ptype == PieceType.KNIGHT:
            jumps = [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]
            for dest in _step_moves(board, r, c, jumps, colour):
                destinations.append(dest)
        elif ptype == PieceType.QUEEN:
            for dest in _sliding_moves(board, r, c, [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.KING:
            for dest in _step_moves(board, r, c, [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.BERS:
            for dest in _sliding_moves(board, r, c, [(1,0),(-1,0),(0,1),(0,-1)], colour):
                destinations.append(dest)
            for dest in _step_moves(board, r, c, [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.DRAGON:
            for dest in _sliding_moves(board, r, c, [(1,1),(1,-1),(-1,1),(-1,-1)], colour):
                destinations.append(dest)
            for dest in _step_moves(board, r, c, [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.GOLD:
            for dest in _sliding_moves(board, r, c, [(1,0),(-1,0),(0,1),(0,-1)], colour):
                destinations.append(dest)
            for dest in _sliding_moves(board, r, c, [(forward,1),(forward,-1)], colour):
                destinations.append(dest)
        elif ptype == PieceType.HUNTER:
            for dest in _sliding_moves(board, r, c, [(1,1),(1,-1),(-1,1),(-1,-1)], colour):
                destinations.append(dest)
            for dest in _sliding_moves(board, r, c, [(forward,0)], colour):
                destinations.append(dest)

        for tr, tc in destinations:
            base_move = Move(r, c, tr, tc)
            if ptype in PROMOTABLE_TYPES and _is_promotion_zone(tr, colour):
                for target_type in PROMOTION_TARGETS[ptype]:
                    moves.append(Move(r, c, tr, tc, promotion=target_type))
                moves.append(base_move)
            else:
                moves.append(base_move)
    return moves

def _is_promotion_zone(row: int, colour: Colour) -> bool:
    if colour == Colour.WHITE:
        return row >= 8
    else:
        return row <= 1