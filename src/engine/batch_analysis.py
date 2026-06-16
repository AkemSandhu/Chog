import json
import time
from PySide6.QtCore import QObject, Signal, QTimer, QEventLoop
from src.core.game_state import GameState
from src.core.movegen import Move
from src.core.pieces import Colour
from src.engine.manager import EngineManager, EngineState
from src.engine.protocol import uci_to_move, move_to_uci
from src.io.fen import board_to_fen

class BatchAnalysis(QObject):
    progress = Signal(int, int)
    move_analyzed = Signal(int, str)
    analysis_complete = Signal()
    error_occurred = Signal(str)

    def __init__(self, engine_path: str, movetime: int = 5000, depth: int = None):
        super().__init__()
        self.engine = EngineManager(engine_path)
        self.movetime = movetime
        self.depth = depth
        self.move_results = []

    def analyze_game(self, game_state: GameState, move_history: List[Move]):
        self.engine.start()
        self.engine.engine_ready.connect(lambda: self._begin_analysis(game_state, move_history))

    def _begin_analysis(self, game_state, move_history):
        state = GameState()
        total = len(move_history)
        for i, move in enumerate(move_history):
            if self.engine.state != EngineState.READY:
                break
            self.progress.emit(i + 1, total)
            fen = board_to_fen(state.board, state.turn)
            self.engine.set_position(fen, [])
            self.engine.go(movetime=self.movetime, depth=self.depth)
            loop = self._wait_for_bestmove()
            if not loop:
                self.error_occurred.emit("Engine did not respond")
                break
            best = self.engine.current_bestmove          # <-- property
            self.move_analyzed.emit(i, best)
            state.make_move(move)
        self.engine.close()
        self.analysis_complete.emit()

    def _wait_for_bestmove(self):
        loop = QEventLoop()
        self.engine.bestmove_received.connect(loop.quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(self.movetime + 5000)
        loop.exec()
        timer.stop()
        return True if self.engine.current_bestmove else False   # <-- property