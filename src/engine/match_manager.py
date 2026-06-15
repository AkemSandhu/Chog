from PySide6.QtCore import QObject, Signal, QTimer
from typing import Optional, List, Dict
from datetime import datetime
import os

from src.game_controller import GameController
from src.core.pieces import Colour
from src.ui.board_widget import BoardWidget
from src.ui.move_list import MoveListWidget
from src.ui.clock_widget import ClockWidget

class EngineMatchManager(QObject):
    match_started = Signal()
    game_completed = Signal(int, str, str)
    match_finished = Signal(dict)
    status_update = Signal(str)

    def __init__(self,
                 engine1_path: str,
                 engine2_path: str,
                 time_control: int = 600,
                 games: int = 2,
                 save_games: bool = True):
        super().__init__()
        self.engine1_path = engine1_path
        self.engine2_path = engine2_path
        self.time_control = time_control
        self.num_games = games
        self.save_games = save_games

        self.results = {
            "engine1": {"wins": 0, "losses": 0, "draws": 0},
            "engine2": {"wins": 0, "losses": 0, "draws": 0},
            "games": []
        }
        self.current_game = 0
        self.current_controller: Optional[GameController] = None

        self._dummy_board = BoardWidget()
        self._dummy_move_list = MoveListWidget()
        self._dummy_white_clock = ClockWidget()
        self._dummy_black_clock = ClockWidget()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._run_next_game)

    def start_match(self):
        self.current_game = 0
        self.results = {
            "engine1": {"wins": 0, "losses": 0, "draws": 0},
            "engine2": {"wins": 0, "losses": 0, "draws": 0},
            "games": []
        }
        self.match_started.emit()
        self.status_update.emit("Match started")
        self.timer.singleShot(0, self._run_next_game)

    def stop_match(self):
        if self.current_controller:
            self.current_controller._stop_engines()
        self.timer.stop()
        self.status_update.emit("Match stopped")

    def _run_next_game(self):
        if self.current_game >= self.num_games:
            self.match_finished.emit(self.results)
            return

        if self.current_game % 2 == 0:
            white_engine = self.engine1_path
            black_engine = self.engine2_path
        else:
            white_engine = self.engine2_path
            black_engine = self.engine1_path

        self.status_update.emit(f"Starting game {self.current_game+1}/{self.num_games}")

        controller = GameController(
            self._dummy_board,
            self._dummy_move_list,
            self._dummy_white_clock,
            self._dummy_black_clock,
            white_engine_path=white_engine,
            black_engine_path=black_engine,
            time_control_seconds=self.time_control,
            increment_seconds=0,
            animation_enabled=False,
            sound_manager=None
        )
        self.current_controller = controller
        controller.game_ended.connect(self._on_game_ended)
        controller.start_new_game()

    def _on_game_ended(self, result_description: str):
        if not self.current_controller:
            return
        state = self.current_controller.state
        from src.core.game_state import game_result
        result = game_result(state)

        game_num = self.current_game + 1
        if result[0] == 'draw':
            score_diff = result[1]
            if score_diff > 0:
                winner = 'Engine 1' if (game_num % 2 == 1) else 'Engine 2'
            elif score_diff < 0:
                winner = 'Engine 2' if (game_num % 2 == 1) else 'Engine 1'
            else:
                winner = 'Draw'
        else:
            winner_str = result[0]
            if winner_str == 'white':
                winner = 'White'
            else:
                winner = 'Black'

        white_is_engine1 = (game_num % 2 == 1)
        if winner == 'White':
            engine_winner = 1 if white_is_engine1 else 2
        elif winner == 'Black':
            engine_winner = 2 if white_is_engine1 else 1
        else:
            engine_winner = 0

        if engine_winner == 1:
            self.results["engine1"]["wins"] += 1
            self.results["engine2"]["losses"] += 1
            outcome = "1-0" if white_is_engine1 else "0-1"
        elif engine_winner == 2:
            self.results["engine2"]["wins"] += 1
            self.results["engine1"]["losses"] += 1
            outcome = "0-1" if white_is_engine1 else "1-0"
        else:
            self.results["engine1"]["draws"] += 1
            self.results["engine2"]["draws"] += 1
            outcome = "1/2-1/2"

        self.results["games"].append({
            "game": game_num,
            "white": "Engine 1" if white_is_engine1 else "Engine 2",
            "black": "Engine 2" if white_is_engine1 else "Engine 1",
            "outcome": outcome,
            "description": result_description
        })

        self.game_completed.emit(game_num, outcome, result_description)
        self.status_update.emit(f"Game {game_num} finished: {outcome} ({result_description})")

        self.current_controller._stop_engines()
        self.current_controller = None
        self.current_game += 1
        self.timer.singleShot(500, self._run_next_game)

    def get_match_summary(self) -> str:
        r = self.results
        summary = "Match results:\n"
        summary += f"Engine 1: {r['engine1']['wins']} wins, {r['engine1']['losses']} losses, {r['engine1']['draws']} draws\n"
        summary += f"Engine 2: {r['engine2']['wins']} wins, {r['engine2']['losses']} losses, {r['engine2']['draws']} draws\n"
        return summary