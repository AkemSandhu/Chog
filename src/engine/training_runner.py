from PySide6.QtCore import QObject, Signal, QTimer
from typing import Optional, List, Tuple
from src.core.game_state import GameState, game_result
from src.core.movegen import Move
from src.core.rules import legal_moves, material_score
from src.core.pieces import Colour
from src.engine.manager import EngineManager
from src.engine.protocol import uci_to_move
from src.io.fen import board_to_fen

class TrainingGameRunner(QObject):
    game_finished = Signal(dict)
    status_update = Signal(str)

    def __init__(self,
                 engine1: EngineManager,
                 engine2: EngineManager,
                 movetime: int = 5000,
                 learn_enabled: bool = True):
        super().__init__()
        self.engine1 = engine1
        self.engine2 = engine2
        self.movetime = movetime
        self.learn_enabled = learn_enabled

        self.state = GameState()
        self.move_history: List[Move] = []
        self.position_fens: List[str] = []
        self.game_over = False

        self.engine1.bestmove_received.connect(self._on_white_move)
        self.engine2.bestmove_received.connect(self._on_black_move)

    def start_game(self):
        self.state = GameState()
        self.move_history = []
        self.position_fens = [board_to_fen(self.state.board, self.state.turn)]
        self.game_over = False
        self.engine1.set_position([])
        self.engine1.go(movetime=self.movetime)
        self.status_update.emit("Training game started: White (Engine1) vs Black (Engine2)")

    def _on_white_move(self, uci: str):
        if self.game_over or self.state.turn != Colour.WHITE:
            return
        self._handle_move(uci, Colour.WHITE)

    def _on_black_move(self, uci: str):
        if self.game_over or self.state.turn != Colour.BLACK:
            return
        self._handle_move(uci, Colour.BLACK)

    def _handle_move(self, uci: str, side: Colour):
        if uci == "0000":
            winner = Colour.BLACK if side == Colour.WHITE else Colour.WHITE
            self._end_game(winner, "resignation")
            return
        move = uci_to_move(uci)
        if move is None:
            winner = Colour.BLACK if side == Colour.WHITE else Colour.WHITE
            self._end_game(winner, "illegal move")
            return
        if not any(m.from_r == move.from_r and m.from_c == move.from_c and
                   m.to_r == move.to_r and m.to_c == move.to_c and
                   m.promotion == move.promotion for m in legal_moves(self.state.board, self.state.turn)):
            winner = Colour.BLACK if side == Colour.WHITE else Colour.WHITE
            self._end_game(winner, "illegal move")
            return
        self.state.make_move(move)
        self.move_history.append(move)
        self.position_fens.append(board_to_fen(self.state.board, self.state.turn))
        result = game_result(self.state)
        if result is not None:
            if result[0] == 'draw':
                score_diff = result[1]
                if score_diff > 0:
                    winner = Colour.WHITE
                elif score_diff < 0:
                    winner = Colour.BLACK
                else:
                    winner = None
            else:
                winner = Colour.WHITE if result[0] == 'white' else Colour.BLACK
            self._end_game(winner, "checkmate/stalemate")
        else:
            next_engine = self.engine2 if side == Colour.WHITE else self.engine1
            next_engine.set_position(self.move_history)
            next_engine.go(movetime=self.movetime)

    def _end_game(self, winner: Optional[Colour], reason: str):
        self.game_over = True
        white_score = material_score(self.state.board, Colour.WHITE)
        black_score = material_score(self.state.board, Colour.BLACK)
        if winner is None:
            result_str = "1/2-1/2"
            winner_name = "Draw"
            score = white_score - black_score
        elif winner == Colour.WHITE:
            result_str = "1-0"
            winner_name = "White"
            score = white_score - black_score
        else:
            result_str = "0-1"
            winner_name = "Black"
            score = black_score - white_score
        if self.learn_enabled:
            for fen in self.position_fens:
                # EngineManager doesn't have send_learn; it's a stub. Use send_command with build_learn_command if needed.
                # For now we just pass; training is not fully implemented.
                pass
        self.game_finished.emit({
            "winner": winner_name,
            "result": result_str,
            "reason": reason,
            "score": score,
            "moves": len(self.move_history)
        })