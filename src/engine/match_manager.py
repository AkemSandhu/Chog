from PySide6.QtCore import QObject, Signal, QTimer
from typing import Optional, List, Dict
from datetime import datetime
import os

from chog.game_controller import GameController
from chog.core.pieces import Colour
from chog.ui.board_widget import BoardWidget
from chog.ui.move_list import MoveListWidget
from chog.ui.clock_widget import ClockWidget

class EngineMatchManager(QObject):
    """
    Runs a match between two engines.

    The match consists of a series of games with alternating colours.
    It uses a headless GameController (without GUI widgets) to simulate moves.
    """

    match_started = Signal()
    game_completed = Signal(int, str, str)          # game_number, result, reason
    match_finished = Signal(dict)                   # final statistics
    status_update = Signal(str)

    def __init__(self,
                 engine1_path: str,
                 engine2_path: str,
                 time_control: int = 600,    # seconds per game per engine
                 games: int = 2,             # number of games
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

        # Create dummy widgets for the controller (it still needs them, but they won't be displayed)
        self._dummy_board = BoardWidget()
        self._dummy_move_list = MoveListWidget()
        self._dummy_white_clock = ClockWidget()
        self._dummy_black_clock = ClockWidget()

        # We'll run games via a timer to avoid blocking the GUI event loop
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
        # Start first game in next event loop iteration
        self.timer.singleShot(0, self._run_next_game)

    def stop_match(self):
        if self.current_controller:
            self.current_controller._stop_engines()
        self.timer.stop()
        self.status_update.emit("Match stopped")

    def _run_next_game(self):
        """Run a single game and schedule the next one when finished."""
        if self.current_game >= self.num_games:
            self.match_finished.emit(self.results)
            return

        # Determine colours
        if self.current_game % 2 == 0:
            white_engine = self.engine1_path
            black_engine = self.engine2_path
            white_name = "Engine 1"
            black_name = "Engine 2"
        else:
            white_engine = self.engine2_path
            black_engine = self.engine1_path
            white_name = "Engine 2"
            black_name = "Engine 1"

        self.status_update.emit(f"Starting game {self.current_game+1}/{self.num_games} ({white_name} vs {black_name})")

        # Create a new controller for this game
        controller = GameController(
            self._dummy_board,
            self._dummy_move_list,
            self._dummy_white_clock,
            self._dummy_black_clock,
            white_engine_path=white_engine,
            black_engine_path=black_engine,
            time_control_seconds=self.time_control,
            increment_seconds=0
        )
        self.current_controller = controller

        # Override certain behaviours to avoid UI interactions
        controller.game_ended.connect(self._on_game_ended)
        # Ensure engines are ready, then start game
        # The controller's start_new_game will launch engines and call _start_turn().
        # In _start_turn() the engine will send "go" and the game will play automatically.
        controller.start_new_game()

    def _on_game_ended(self, result_description: str):
        """Called when the current game finishes."""
        if not self.current_controller:
            return
        # Determine winner
        # We need to know who won from the result string; parse it or check controller state.
        # The result_description contains e.g. "White wins", "Black wins", etc.
        # We'll also check the final board to compute material win in case of draw.
        # A robust way: the controller already set game_active = False and we have the state.
        # But we only have the string. We'll examine the game state from the controller.
        state = self.current_controller.state
        from chog.core.rules import material_score

        # Determine winner based on the game end state.
        # The controller already handled the result; we'll reconstruct from the game state's side to move and material.
        # Simpler: the game controller could have stored the final result in a variable. We'll add a self.last_result in GameController.
        # For now, we'll call game_result from the state again (it should return the same).
        from chog.core.game_state import game_result
        result = game_result(state)

        game_num = self.current_game + 1
        if result[0] == 'draw':
            score_diff = result[1]
            if score_diff > 0:
                winner = 'Engine 1' if (game_num % 2 == 1) else 'Engine 2'  # depends on who was white
            elif score_diff < 0:
                winner = 'Engine 2' if (game_num % 2 == 1) else 'Engine 1'
            else:
                winner = 'Draw'
        else:
            winner_str = result[0]  # 'white' or 'black'
            if winner_str == 'white':
                winner = 'White'
            else:
                winner = 'Black'

        # Map to engine names
        white_is_engine1 = (game_num % 2 == 1)
        if winner == 'White':
            engine_winner = 1 if white_is_engine1 else 2
        elif winner == 'Black':
            engine_winner = 2 if white_is_engine1 else 1
        else:
            engine_winner = 0  # draw

        # Update statistics
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

        # Clean up this controller's engines
        self.current_controller._stop_engines()
        self.current_controller = None

        # Schedule next game
        self.current_game += 1
        self.timer.singleShot(500, self._run_next_game)   # small delay before next game

    def get_match_summary(self) -> str:
        """Return a formatted summary of the match results."""
        r = self.results
        summary = f"Match results:\n"
        summary += f"Engine 1: {r['engine1']['wins']} wins, {r['engine1']['losses']} losses, {r['engine1']['draws']} draws\n"
        summary += f"Engine 2: {r['engine2']['wins']} wins, {r['engine2']['losses']} losses, {r['engine2']['draws']} draws\n"
        return summary