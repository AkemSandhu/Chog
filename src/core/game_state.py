from __future__ import annotations
from typing import List, Dict, Optional, Tuple
from .pieces import Colour, PieceType, Piece, PROMOTABLE_TYPES
from .board import Board
from .movegen import Move
from .rules import legal_moves, has_legal_moves, is_dead_position, material_score

class GameState:
    def __init__(self, board: Optional[Board] = None, turn: Colour = Colour.WHITE):
        self.board = board if board else Board.starting_position()
        self.turn = turn
        self.move_stack: List[MoveRecord] = []
        self.position_history: Dict[str, int] = {}
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self._record_position()

    def _record_position(self):
        key = self._position_key()
        self.position_history[key] = self.position_history.get(key, 0) + 1

    def _position_key(self) -> str:
        rows = []
        for r in range(9, -1, -1):
            row_str = ""
            for c in range(10):
                piece = self.board.get_piece(r, c)
                if piece:
                    row_str += piece.symbol()
                else:
                    row_str += "1"
            rows.append(row_str)
        fen = "/".join(rows)
        return fen + " " + ("w" if self.turn == Colour.WHITE else "b")

    def make_move(self, move: Move) -> bool:
        record = MoveRecord(
            move=move,
            moved_piece=self.board.get_piece(move.from_r, move.from_c),
            captured_piece=self.board.get_piece(move.to_r, move.to_c),
            prev_halfmove_clock=self.halfmove_clock,
        )
        piece = record.moved_piece
        self.board.clear_square(move.from_r, move.from_c)
        self.board.clear_square(move.to_r, move.to_c)
        if move.promotion is not None:
            new_piece = Piece(move.promotion, piece.colour)
        else:
            new_piece = piece
        self.board.set_piece(move.to_r, move.to_c, new_piece)

        self.halfmove_clock += 1
        if piece.ptype == PieceType.PAWN or record.captured_piece is not None:
            self.halfmove_clock = 0
        if self.turn == Colour.BLACK:
            self.fullmove_number += 1

        self.turn = self.turn.opponent()
        self._record_position()
        self.move_stack.append(record)
        return True

    def unmake_move(self):
        if not self.move_stack:
            return
        record = self.move_stack.pop()
        self.board.set_piece(record.move.from_r, record.move.from_c, record.moved_piece)
        if record.captured_piece:
            self.board.set_piece(record.move.to_r, record.move.to_c, record.captured_piece)
        else:
            self.board.clear_square(record.move.to_r, record.move.to_c)
        self.turn = self.turn.opponent()
        self.halfmove_clock = record.prev_halfmove_clock
        if self.turn == Colour.BLACK:
            self.fullmove_number -= 1

class MoveRecord:
    def __init__(self, move: Move, moved_piece: Piece, captured_piece: Optional[Piece],
                 prev_halfmove_clock: int):
        self.move = move
        self.moved_piece = moved_piece
        self.captured_piece = captured_piece
        self.prev_halfmove_clock = prev_halfmove_clock

def game_result(state: GameState) -> Optional[Tuple[str, Optional[int]]]:
    if not has_legal_moves(state.board, state.turn):
        winner = state.turn.opponent()
        return (winner, None)
    if state.position_history.get(state._position_key(), 0) >= 4:
        white_score = material_score(state.board, Colour.WHITE)
        black_score = material_score(state.board, Colour.BLACK)
        return ('draw', white_score - black_score)
    if is_dead_position(state.board):
        white_score = material_score(state.board, Colour.WHITE)
        black_score = material_score(state.board, Colour.BLACK)
        return ('draw', white_score - black_score)
    return None