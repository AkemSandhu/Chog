import json
import time
from PySide6.QtCore import QObject, Signal, QTimer
from src.core.game_state import GameState
from src.core.movegen import Move
from src.core.pieces import Colour
from src.engine.manager import EngineManager
from src.engine.protocol import uci_to_move, move_to_uci
from src.io.fen import board_to_fen

class BatchAnalysis(QObject):
    progress = Signal(int, int)          # current, total moves
    move_analyzed = Signal(int, str)    # move index, bestmove string
    analysis_complete = Signal()
    error_occurred = Signal(str)

    def __init__(self, engine_path: str, movetime: int = 5000, depth: int = None):
        super().__init__()
        self.engine = EngineManager(engine_path)
        self.movetime = movetime
        self.depth = depth
        self.move_results = []

    def analyze_game(self, game_state: GameState, move_history: List[Move]):
        """Analyze all moves in a game, starting from initial position.
        game_state must be at the beginning of the game.
        We'll replay each move and analyze the position before the move.
        """
        self.engine.start()
        # Wait for engine ready
        self.engine.engine_ready.connect(lambda: self._begin_analysis(game_state, move_history))

    def _begin_analysis(self, game_state, move_history):
        # Reset game to start
        state = GameState()  # fresh from starting position
        total = len(move_history)
        for i, move in enumerate(move_history):
            if self.engine._state != EngineManager.READY:
                break
            self.progress.emit(i + 1, total)
            # Analyze position before move
            fen = board_to_fen(state.board, state.turn)
            self.engine.set_position(fen, [])
            self.engine.go(movetime=self.movetime, depth=self.depth)
            # Wait for bestmove
            loop = self._wait_for_bestmove()
            if not loop:
                self.error_occurred.emit("Engine did not respond")
                break
            best = self.engine._current_bestmove
            self.move_analyzed.emit(i, best)
            # Apply the move to advance state
            state.make_move(move)
        self.engine.close()
        self.analysis_complete.emit()

    def _wait_for_bestmove(self):
        """Block until engine sends bestmove or timeout."""
        timer = QTimer()
        timer.setSingleShot(True)
        loop = None
        # Simple event loop
        from PySide6.QtCore import QEventLoop
        loop = QEventLoop()
        self.engine.bestmove_received.connect(loop.quit)
        timer.timeout.connect(loop.quit)
        timer.start(self.movetime + 5000)
        loop.exec()
        timer.stop()
        return True if self.engine._current_bestmove else False