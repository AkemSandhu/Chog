from PySide6.QtCore import QObject, Signal, QTimer
from typing import Optional
import os

from src.game_controller import GameController
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

        # Dummy widgets (not shown, but required by GameController)
        self._dummy_board = BoardWidget()
        self._dummy_move_list = MoveListWidget()
        self._dummy_white_clock = ClockWidget()
        self._dummy_black_clock = ClockWidget()

        # Watchdog per game – if a game doesn't end in 2 minutes, kill it
        self._game_watchdog = QTimer(self)
        self._game_watchdog.setSingleShot(True)
        self._game_watchdog.timeout.connect(self._on_game_timeout)

    def start_match(self):
        self.current_game = 0
        self.results = {
            "engine1": {"wins": 0, "losses": 0, "draws": 0},
            "engine2": {"wins": 0, "losses": 0, "draws": 0},
            "games": []
        }
        self.match_started.emit()
        self.status_update.emit("Match started")
        QTimer.singleShot(0, self._run_next_game)

    def stop_match(self):
        self._game_watchdog.stop()
        if self.current_controller:
            self.current_controller._stop_engines()
            self.current_controller = None
        self.status_update.emit("Match stopped")

    def _run_next_game(self):
        self._game_watchdog.stop()
        if self.current_game >= self.num_games:
            self.match_finished.emit(self.results)
            return

        # Alternate colours
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
        controller.status_update.connect(self.status_update)

        # Handle fatal engine errors
        def on_engine_error(err_msg: str):
            self.status_update.emit(f"Fatal engine error: {err_msg}")
            self._handle_fatal_error(err_msg)
        if controller.white_engine:
            controller.white_engine.error_occurred.connect(on_engine_error)
        if controller.black_engine:
            controller.black_engine.error_occurred.connect(on_engine_error)

        controller.game_ended.connect(self._on_game_ended)
        controller.start_new_game()

        # Arm the game watchdog (2 minutes)
        self._game_watchdog.start(120_000)

    def _on_game_ended(self, result_description: str):
        self._game_watchdog.stop()
        if not self.current_controller:
            return

        # Determine winner in engine‑1/engine‑2 terms
        from src.core.game_state import game_result
        state = self.current_controller.state
        res = game_result(state)
        game_num = self.current_game + 1
        white_is_engine1 = (game_num % 2 == 1)

        if res is None:
            self.current_controller._stop_engines()
            self.current_controller = None
            self.current_game += 1
            QTimer.singleShot(500, self._run_next_game)
            return

        winner_str, score_diff = res
        if winner_str == 'draw':
            if score_diff > 0:
                engine_winner = 1 if white_is_engine1 else 2
            elif score_diff < 0:
                engine_winner = 2 if white_is_engine1 else 1
            else:
                engine_winner = 0
        else:
            if winner_str == 'white':
                eng = 1 if white_is_engine1 else 2
            else:
                eng = 2 if white_is_engine1 else 1
            engine_winner = eng

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
        QTimer.singleShot(500, self._run_next_game)

    def _on_game_timeout(self):
        self.status_update.emit("Game timed out – aborting.")
        if self.current_controller:
            self.current_controller._stop_engines()
            self._on_game_ended("timeout")

    def _handle_fatal_error(self, msg: str):
        self._game_watchdog.stop()
        self.status_update.emit(f"Match aborted: {msg}")
        if self.current_controller:
            self.current_controller._stop_engines()
            self.current_controller = None
        self.match_finished.emit(self.results)
        self.stop_match()

    def get_match_summary(self) -> str:
        r = self.results
        return (f"Match results:\n"
                f"Engine 1: {r['engine1']['wins']}W {r['engine1']['losses']}L {r['engine1']['draws']}D\n"
                f"Engine 2: {r['engine2']['wins']}W {r['engine2']['losses']}L {r['engine2']['draws']}D")