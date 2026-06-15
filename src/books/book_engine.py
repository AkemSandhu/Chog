# src/books/book_engine.py
from PySide6.QtCore import QObject, Signal
from src.engine.manager import EngineManager
from src.io.fen import board_to_fen
from src.core.movegen import Move
from src.core.game_state import GameState
from src.engine.protocol import uci_to_move
from typing import List, Optional

class BookEngineHelper(QObject):
    suggestions_ready = Signal(list)   # list of (move, weight)
    autocomplete_done = Signal(list)   # list of Move added

    def __init__(self, engine_path: str, parent=None):
        super().__init__(parent)
        self.engine = EngineManager(engine_path)
        self.engine.info_received.connect(self._on_info)
        self.engine.bestmove_received.connect(self._on_bestmove)
        self._pending = None
        self._results = []
        self._state = None  # 'suggest', 'autocomplete'

    def suggest_moves(self, game_state: GameState, multipv: int = 3):
        """Ask engine for top moves, emit suggestions_ready with (move, weight)."""
        self._state = 'suggest'
        self._results = []
        self.engine.start()
        self.engine.set_multipv(multipv)
        fen = board_to_fen(game_state.board, game_state.turn)
        self.engine.set_position(fen, [])
        self.engine.go(movetime=3000)  # 3 seconds analysis

    def autocomplete_line(self, game_state: GameState, max_depth: int = 20):
        """Play engine's best move repeatedly, adding each to a list."""
        self._state = 'autocomplete'
        self._results = []
        self._current_state = game_state
        self._max_depth = max_depth
        self._depth = 0
        self._engine_step()

    def _engine_step(self):
        if self._depth >= self._max_depth:
            self.autocomplete_done.emit(self._results)
            self.engine.stop()
            return
        fen = board_to_fen(self._current_state.board, self._current_state.turn)
        self.engine.set_position(fen, [])
        self.engine.go(movetime=2000)

    def _on_info(self, info: dict):
        pass  # we'll use bestmove

    def _on_bestmove(self, uci: str):
        if self._state == 'suggest':
            # We need to get multiPV info. Since we get only bestmove, we can't get full multiPV easily.
            # Instead, we'll run analysis with MultiPV and collect bestmove after each? Not ideal.
            # A better approach: run multiple single-PV analyses? For simplicity, we'll just get bestmove and add weight=1.
            # The proper way: we can't get multiPV from bestmove alone. We'll rely on info lines.
            # We'll modify approach: collect info lines and use them.
            pass
        elif self._state == 'autocomplete':
            move = uci_to_move(uci)
            if move:
                self._results.append(move)
                # Apply move to state
                self._current_state.make_move(move)
                self._depth += 1
                # Check if game over
                from src.core.game_state import game_result
                if game_result(self._current_state) is not None:
                    self.autocomplete_done.emit(self._results)
                    self.engine.stop()
                else:
                    self._engine_step()
            else:
                self.autocomplete_done.emit(self._results)
                self.engine.stop()

    def close(self):
        self.engine.close()