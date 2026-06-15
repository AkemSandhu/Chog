from PySide6.QtCore import QObject, Signal, QTimer
from typing import Optional
from src.engine.manager import EngineManager
from src.engine.training_runner import TrainingGameRunner

class TrainingManager(QObject):
    training_started = Signal()
    game_completed = Signal(int, dict)
    training_finished = Signal(dict)
    status_update = Signal(str)

    def __init__(self,
                 engine1_path: str,
                 engine2_path: str,
                 num_games: int = 100,
                 movetime: int = 5000,
                 save_interval: int = 10,
                 weights_file1: str = "weights_engine1.nn",
                 weights_file2: str = "weights_engine2.nn",
                 learn_enabled: bool = True):
        super().__init__()
        self.engine1_path = engine1_path
        self.engine2_path = engine2_path
        self.num_games = num_games
        self.movetime = movetime
        self.save_interval = save_interval
        self.weights_file1 = weights_file1
        self.weights_file2 = weights_file2
        self.learn_enabled = learn_enabled

        self.engine1: Optional[EngineManager] = None
        self.engine2: Optional[EngineManager] = None
        self.current_game = 0
        self.running = False
        self.results = []

    def start(self):
        self.engine1 = EngineManager(self.engine1_path)
        self.engine2 = EngineManager(self.engine2_path)
        self.engine1.start()
        self.engine2.start()
        QTimer.singleShot(2000, self._run_next_game)

        self.running = True
        self.current_game = 0
        self.results = []
        self.training_started.emit()
        self.status_update.emit("Training started")

    def stop(self):
        self.running = False
        if self.engine1:
            self.engine1.stop()
        if self.engine2:
            self.engine2.stop()

    def _run_next_game(self):
        if not self.running or self.current_game >= self.num_games:
            self._finish_training()
            return

        if self.current_game % 2 == 0:
            white_engine = self.engine1
            black_engine = self.engine2
        else:
            white_engine = self.engine2
            black_engine = self.engine1

        runner = TrainingGameRunner(
            white_engine, black_engine,
            movetime=self.movetime,
            learn_enabled=self.learn_enabled
        )
        runner.game_finished.connect(lambda result, g=self.current_game: self._on_game_finished(g, result))
        runner.status_update.connect(self.status_update.emit)
        self.current_game += 1
        runner.start_game()

    def _on_game_finished(self, game_num: int, result: dict):
        self.results.append(result)
        self.game_completed.emit(game_num, result)
        self.status_update.emit(f"Game {game_num+1}/{self.num_games}: {result['result']} ({result['reason']})")

        if (game_num + 1) % self.save_interval == 0:
            self._save_weights()

        QTimer.singleShot(1000, self._run_next_game)

    def _save_weights(self):
        if self.engine1:
            self.engine1.send_save_weights(self.weights_file1)
        if self.engine2:
            self.engine2.send_save_weights(self.weights_file2)
        self.status_update.emit("Weights saved")

    def _finish_training(self):
        self._save_weights()
        self.stop()
        stats = self._compute_stats()
        self.training_finished.emit(stats)

    def _compute_stats(self) -> dict:
        wins_white = sum(1 for r in self.results if r['winner'] == 'White')
        wins_black = sum(1 for r in self.results if r['winner'] == 'Black')
        draws = sum(1 for r in self.results if r['winner'] == 'Draw')
        return {
            "games": len(self.results),
            "white_wins": wins_white,
            "black_wins": wins_black,
            "draws": draws,
        }