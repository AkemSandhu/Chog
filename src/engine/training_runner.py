from PySide6.QtCore import QObject, Signal, QTimer
from typing import Optional, List, Tuple
from src.core.game_state import GameState, game_result
from src.core.movegen import Move
from src.core.rules import legal_moves
from src.core.pieces import Colour
from src.core.rules import material_score
from src.engine.manager import EngineManager
from src.engine.protocol import uci_to_move
from src.io.fen import board_to_fen

class TrainingGameRunner(QObject):
    """
    Runs a single self-play game between two engines for training.
    Stores all positions and the final result, and can send learning commands.
    """
    game_finished = Signal(dict)            # result info dict
    status_update = Signal(str)

    def __init__(self,
                 engine1: EngineManager,
                 engine2: EngineManager,
                 movetime: int = 5000,      # milliseconds per move
                 learn_enabled: bool = True):
        super().__init__()
        self.engine1 = engine1   # plays white
        self.engine2 = engine2   # plays black
        self.movetime = movetime
        self.learn_enabled = learn_enabled

        self.state = GameState()
        self.move_history: List[Move] = []
        self.position_fens: List[str] = []   # FEN after each move (for learning)
        self.game_over = False

        # Connect engine signals
        self.engine1.bestmove_received.connect(self._on_white_move)
        self.engine2.bestmove_received.connect(self._on_black_move)

    def start_game(self):
        """Begin a new game. Engine1 is white, engine2 is black."""
        self.state = GameState()
        self.move_history = []
        self.position_fens = [board_to_fen(self.state.board, self.state.turn)]
        self.game_over = False

        # Send initial position to white engine
        self.engine1.send_position([])
        self.engine1.send_go(movetime=self.movetime)
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
        """Process a move from an engine."""
        if uci == "0000":
            # Engine resigns
            winner = Colour.BLACK if side == Colour.WHITE else Colour.WHITE
            self._end_game(winner, "resignation")
            return

        move = uci_to_move(uci)
        if move is None:
            # Illegal move – forfeit
            winner = Colour.BLACK if side == Colour.WHITE else Colour.WHITE
            self._end_game(winner, "illegal move")
            return

        # Validate move
        if not any(m.from_r == move.from_r and m.from_c == move.from_c and
                   m.to_r == move.to_r and m.to_c == move.to_c and
                   m.promotion == move.promotion for m in legal_moves(self.state.board, self.state.turn)):
            winner = Colour.BLACK if side == Colour.WHITE else Colour.WHITE
            self._end_game(winner, "illegal move")
            return

        # Apply move
        self.state.make_move(move)
        self.move_history.append(move)
        self.position_fens.append(board_to_fen(self.state.board, self.state.turn))

        # Check game end
        result = game_result(self.state)
        if result is not None:
            # Determine winner
            if result[0] == 'draw':
                score_diff = result[1]
                if score_diff > 0:
                    winner = Colour.WHITE
                elif score_diff < 0:
                    winner = Colour.BLACK
                else:
                    winner = None  # true draw
            else:
                winner = Colour.WHITE if result[0] == 'white' else Colour.BLACK
            self._end_game(winner, "checkmate/stalemate")
        else:
            # Continue – send position to the other engine
            next_engine = self.engine2 if side == Colour.WHITE else self.engine1
            next_engine.send_position(self.move_history)
            next_engine.send_go(movetime=self.movetime)

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

        # Send learning data to both engines
        if self.learn_enabled:
            for fen in self.position_fens:
                self.engine1.send_learn(fen, result_str, score)
                self.engine2.send_learn(fen, result_str, score)

        self.game_finished.emit({
            "winner": winner_name,
            "result": result_str,
            "reason": reason,
            "score": score,
            "moves": len(self.move_history)
        })