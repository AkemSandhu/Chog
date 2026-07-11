"""
Move ordering and staged move generation for Chog.
Adapted from Stockfish's movepick.cpp.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
from src.core.board import Board
from src.core.pieces import Colour, PieceType
from src.core.movegen import Move, pseudo_legal_moves

# ----------------------------------------------------------------------
# History tables
# ----------------------------------------------------------------------
MAX_PLY = 100
SQUARE_NB = 100  # 10x10 board

# Butterfly history: history[colour][from_sq][to_sq]
butterfly_history = [[[0 for _ in range(SQUARE_NB)] for _ in range(SQUARE_NB)] for _ in range(2)]

# Piece-to history: pieceToHistory[piece_type][to_sq]
piece_to_history = [[0 for _ in range(SQUARE_NB)] for _ in range(len(PieceType))]

# Killer moves (two slots per ply)
killer_moves = [[None, None] for _ in range(MAX_PLY)]

# Countermove table: counterMoves[piece_type][to_sq]
counter_moves = [[None for _ in range(SQUARE_NB)] for _ in range(len(PieceType))]

# ----------------------------------------------------------------------
# History update helpers
# ----------------------------------------------------------------------
def stat_bonus(depth: int) -> int:
    """Stockfish-like bonus based on depth."""
    if depth > 15:
        return -8
    return 19 * depth * depth + 155 * depth - 132

def update_quiet_stats(board: Board, move: Move, bonus: int, ply: int):
    """Update history and killer tables for a quiet move that caused a cutoff."""
    piece = board.get_piece(move.from_r, move.from_c)
    if piece is None:
        return
    from_sq = move.from_r * 10 + move.from_c
    to_sq = move.to_r * 10 + move.to_c
    colour = piece.colour.value

    # Update butterfly history
    butterfly_history[colour][from_sq][to_sq] += bonus

    # Update piece-to history
    piece_to_history[piece.ptype][to_sq] += bonus

    # Update killers
    if killer_moves[ply][0] != move:
        killer_moves[ply][1] = killer_moves[ply][0]
        killer_moves[ply][0] = move

    # Update countermoves
    if ply > 0:
        # We need the previous move; that info must be passed or stored.
        # For simplicity, we'll handle countermove updates elsewhere in search.
        pass

def update_capture_stats(board: Board, move: Move, bonus: int):
    """Update history for a capture move."""
    piece = board.get_piece(move.from_r, move.from_c)
    if piece is None:
        return
    to_sq = move.to_r * 10 + move.to_c
    piece_to_history[piece.ptype][to_sq] += bonus

# ----------------------------------------------------------------------
# Move scoring helpers
# ----------------------------------------------------------------------
def _piece_value(ptype: PieceType) -> int:
    values = {
        PieceType.PAWN: 1, PieceType.LANCE: 2, PieceType.HORSE: 3,
        PieceType.ELEPHANT: 3, PieceType.GENERAL: 4, PieceType.WAZIR: 1,
        PieceType.FERZ: 1, PieceType.EAGLE: 3, PieceType.BISHOP: 4,
        PieceType.ROOK: 5, PieceType.QUEEN: 9, PieceType.KING: 99,
        PieceType.KNIGHT: 3, PieceType.BERS: 6, PieceType.DRAGON: 6,
        PieceType.GOLD: 7, PieceType.HUNTER: 6,
    }
    return values.get(ptype, 0)

def _capture_score(board: Board, move: Move) -> int:
    """MVV-LVA + capture history score."""
    victim = board.get_piece(move.to_r, move.to_c)
    attacker = board.get_piece(move.from_r, move.from_c)
    if victim is None or attacker is None:
        return 0
    score = 6 * _piece_value(victim.ptype) - _piece_value(attacker.ptype)
    # Add capture history
    score += piece_to_history[attacker.ptype][move.to_r * 10 + move.to_c] // 64
    return score

def _quiet_score(board: Board, move: Move) -> int:
    """Butterfly history + piece-to history for quiet moves."""
    piece = board.get_piece(move.from_r, move.from_c)
    if piece is None:
        return 0
    from_sq = move.from_r * 10 + move.from_c
    to_sq = move.to_r * 10 + move.to_c
    colour = piece.colour.value
    score = butterfly_history[colour][from_sq][to_sq]
    score += piece_to_history[piece.ptype][to_sq]
    return score

# ----------------------------------------------------------------------
# Staged move picker
# ----------------------------------------------------------------------
class MovePicker:
    """
    Generates and returns moves in order of expected strength.
    Stages: TT_MOVE → CAPTURES → KILLERS → QUIETS → BAD_CAPTURES
    """

    STAGE_TT = 0
    STAGE_CAPTURES = 1
    STAGE_KILLERS = 2
    STAGE_QUIETS = 3
    STAGE_DONE = 4

    def __init__(self, board: Board, turn: Colour, tt_move: Optional[Move],
                 ply: int, depth: int):
        self.board = board
        self.turn = turn
        self.tt_move = tt_move
        self.ply = ply
        self.depth = depth

        self.stage = self.STAGE_TT
        self._captures: List[Move] = []
        self._quiets: List[Move] = []
        self._capture_idx = 0
        self._quiet_idx = 0
        self._killer_idx = 0
        self._killer_moves = [m for m in killer_moves[ply] if m is not None]
        # Add countermove as well if we had it (simplified: not using countermove here)
        self._generated = False

    def _generate(self):
        """Generate all legal moves and partition into captures and quiets."""
        if self._generated:
            return
        moves = pseudo_legal_moves(self.board, self.turn)
        for move in moves:
            # Skip the TT move (already returned)
            if self.tt_move and move == self.tt_move:
                continue
            if self.board.get_piece(move.to_r, move.to_c) is not None:
                self._captures.append(move)
            else:
                self._quiets.append(move)

        # Sort captures by score descending
        self._captures.sort(key=lambda m: _capture_score(self.board, m), reverse=True)
        # Sort quiets by score descending
        self._quiets.sort(key=lambda m: _quiet_score(self.board, m), reverse=True)

        self._generated = True

    def next_move(self) -> Optional[Move]:
        """Return the next best move, or None if no more moves."""
        # Stage 0: TT move
        if self.stage == self.STAGE_TT:
            self.stage = self.STAGE_CAPTURES
            if self.tt_move is not None:
                # Verify it's still legal
                moves = pseudo_legal_moves(self.board, self.turn)
                if any(m == self.tt_move for m in moves):
                    return self.tt_move
            # Fall through to captures if TT move not valid

        # Ensure moves are generated
        self._generate()

        # Stage 1: Good captures (all captures for now)
        if self.stage == self.STAGE_CAPTURES:
            if self._capture_idx < len(self._captures):
                move = self._captures[self._capture_idx]
                self._capture_idx += 1
                return move
            self.stage = self.STAGE_KILLERS

        # Stage 2: Killer moves (if not already returned as capture or TT)
        if self.stage == self.STAGE_KILLERS:
            while self._killer_idx < len(self._killer_moves):
                move = self._killer_moves[self._killer_idx]
                self._killer_idx += 1
                if move is None:
                    continue
                # Make sure it's legal and not already generated
                moves = pseudo_legal_moves(self.board, self.turn)
                if any(m == move for m in moves):
                    # Also ensure it's not already in captures or TT
                    if move != self.tt_move and self.board.get_piece(move.to_r, move.to_c) is None:
                        return move
            self.stage = self.STAGE_QUIETS

        # Stage 3: Remaining quiet moves
        if self.stage == self.STAGE_QUIETS:
            if self._quiet_idx < len(self._quiets):
                move = self._quiets[self._quiet_idx]
                self._quiet_idx += 1
                # Skip if already returned as killer or TT
                if move in self._killer_moves:
                    return self.next_move()
                return move
            self.stage = self.STAGE_DONE

        return None

    def all_moves(self) -> List[Move]:
        """Generate and return all moves in order (for compatibility)."""
        self._generate()
        result = []
        # TT move
        if self.tt_move:
            result.append(self.tt_move)
        # Captures
        result.extend(self._captures)
        # Quiets
        result.extend(self._quiets)
        return result