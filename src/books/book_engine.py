from PySide6.QtCore import QObject, Signal, QTimer
from src.engine.manager import EngineManager
from src.io.fen import board_to_fen
from src.core.movegen import Move
from src.core.game_state import GameState
from src.engine.protocol import uci_to_move
from typing import List, Optional

class BookEngineHelper(QObject):
    suggestions_ready = Signal(list)
    autocomplete_done = Signal(list)

    def __init__(self, engine_path: str, parent=None):
        super().__init__(parent)
        self.engine = EngineManager(engine_path)
        self.engine.info_received.connect(self._on_info)
        self.engine.bestmove_received.connect(self._on_bestmove)
        self._state = None
        self._results: List[Move] = []
        self._info_cache: List[dict] = []
        self._suggest_timer = QTimer(self)
        self._suggest_timer.setSingleShot(True)
        self._suggest_timer.timeout.connect(self._finish_suggestions)

    def suggest_moves(self, game_state: GameState, multipv: int = 3):
        self._state = 'suggest'
        self._results = []
        self._info_cache = []
        self.engine.start()
        self.engine.set_multipv(multipv)
        fen = board_to_fen(game_state.board, game_state.turn)
        self.engine.set_position(fen, [])
        self.engine.go(movetime=3000)
        self._suggest_timer.start(3500)

    def autocomplete_line(self, game_state: GameState, max_depth: int = 20):
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
        if self._state == 'suggest':
            self._info_cache.append(info)

    def _on_bestmove(self, uci: str):
        if self._state == 'autocomplete':
            move = uci_to_move(uci)
            if move:
                self._results.append(move)
                self._current_state.make_move(move)
                self._depth += 1
                from src.core.game_state import game_result
                if game_result(self._current_state) is not None:
                    self.autocomplete_done.emit(self._results)
                    self.engine.stop()
                else:
                    self._engine_step()
            else:
                self.autocomplete_done.emit(self._results)
                self.engine.stop()

    def _finish_suggestions(self):
        self.engine.stop()
        moves_weights = []
        seen = set()
        for info in self._info_cache:
            pv = info.get("pv", [])
            if pv:
                move = uci_to_move(pv[0])
                if move and move not in seen:
                    seen.add(move)
                    score_cp = info.get("score_cp", 0)
                    weight = max(1, score_cp // 10) if score_cp else 1
                    moves_weights.append((move, weight))
        self.suggestions_ready.emit(moves_weights)

    def close(self):
        self.engine.close()