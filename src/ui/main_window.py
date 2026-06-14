from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QMenuBar, QStatusBar, QLabel, QAction,
    QMessageBox, QFileDialog, QInputDialog
)
from PySide6.QtCore import Qt
from typing import Optional

from chog.ui.board_widget import BoardWidget
from chog.ui.move_list import MoveListWidget
from chog.ui.clock_widget import ClockWidget
from chog.ui.analysis_panel import AnalysisPanel
from chog.ui.match_dialog import MatchSetupDialog
from chog.ui.book_editor import BookEditorWidget
from chog.ui.training_dialog import TrainingDialog
from chog.game_controller import GameController
from chog.engine.match_manager import EngineMatchManager
from chog.io.fen import board_to_fen
from chog.io.fpgn import FPGNReader


class MainWindow(QMainWindow):
    def __init__(self, white_engine_path: Optional[str] = None,
                 black_engine_path: Optional[str] = None):
        super().__init__()
        self.setWindowTitle("Fusion Chess")
        self.resize(1200, 900)

        # ---- Central board ----
        self.board_widget = BoardWidget()
        self.setCentralWidget(self.board_widget)

        # ---- Move list dock (right) ----
        self.move_list = MoveListWidget()
        move_dock = QDockWidget("Moves", self)
        move_dock.setWidget(self.move_list)
        self.addDockWidget(Qt.RightDockWidgetArea, move_dock)

        # ---- Clock dock (bottom) ----
        self.white_clock = ClockWidget()
        self.white_clock.label.setText("White")
        self.black_clock = ClockWidget()
        self.black_clock.label.setText("Black")
        clock_widget = QWidget()
        clock_layout = QHBoxLayout(clock_widget)
        clock_layout.addWidget(self.white_clock)
        clock_layout.addWidget(self.black_clock)
        clock_dock = QDockWidget("Clocks", self)
        clock_dock.setWidget(clock_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, clock_dock)

        # ---- Analysis panel dock (left) ----
        self.analysis_panel = AnalysisPanel()
        analysis_dock = QDockWidget("Analysis", self)
        analysis_dock.setWidget(self.analysis_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, analysis_dock)

        # ---- Opening Book dock (right) ----
        self.book_editor = BookEditorWidget()
        book_dock = QDockWidget("Opening Book", self)
        book_dock.setWidget(self.book_editor)
        self.addDockWidget(Qt.RightDockWidgetArea, book_dock)

        # ---- Status bar ----
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # ---- Game controller ----
        self.controller = GameController(
            self.board_widget, self.move_list,
            self.white_clock, self.black_clock,
            white_engine_path, black_engine_path,
            time_control_seconds=600, increment_seconds=2
        )
        self.controller.status_update.connect(self.status_label.setText)
        self.controller.game_ended.connect(self._on_game_ended)
        self.controller.position_changed.connect(self._on_position_changed)

        # ---- Menus ----
        self._create_menus()

        # ---- Match manager (on demand) ----
        self.match_manager: Optional[EngineMatchManager] = None

        # ---- Start first game ----
        self.controller.start_new_game()

    def _create_menus(self):
        menu = self.menuBar()

        # File
        file_menu = menu.addMenu("&File")
        file_menu.addAction("&New Game", self.controller.start_new_game, "Ctrl+N")
        file_menu.addAction("&Load Game...", self._load_game)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close, "Ctrl+Q")

        # Analysis
        analysis_menu = menu.addMenu("&Analysis")
        analysis_menu.addAction("Set Analysis Engine...", self._set_analysis_engine)

        # Match
        match_menu = menu.addMenu("&Match")
        match_menu.addAction("New Engine Match...", self._start_match)
        match_menu.addAction("Stop Match", self._stop_match)

        # Book
        book_menu = menu.addMenu("&Book")
        book_menu.addAction("Load Book...", self._load_book)
        book_menu.addAction("Save Book As...", self._save_book)

        # Training
        training_menu = menu.addMenu("&Training")
        training_menu.addAction("New Training Session...", self._start_training)

        # Help
        help_menu = menu.addMenu("&Help")
        help_menu.addAction("About Fusion Chess", self._about)

    # -----------------------------------------------------------------
    # Slots
    # -----------------------------------------------------------------
    def _on_position_changed(self):
        fen = board_to_fen(self.controller.state.board, self.controller.state.turn,
                           self.controller.state.halfmove_clock,
                           self.controller.state.fullmove_number)
        self.analysis_panel.set_position(fen)
        legal_moves = self.controller.get_legal_moves()
        self.book_editor.set_position(self.controller.state, legal_moves)

    def _on_game_ended(self, message: str):
        QMessageBox.information(self, "Game Over", message)
        self.controller.start_new_game()

    def _set_analysis_engine(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Analysis Engine", "",
                                              "Executable Files (*);;All Files (*)")
        if path:
            self.analysis_panel.set_engine(path)
            self.status_label.setText(f"Analysis engine set: {path}")

    def _load_game(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open FPGN File", "games/",
                                              "FPGN Files (*.fpgn);;All Files (*)")
        if not path:
            return
        games = FPGNReader.read_file(path)
        if not games:
            QMessageBox.information(self, "Load Game", "No games found in file.")
            return
        if len(games) == 1:
            self.controller.load_game_from_fpgn(path, 0)
        else:
            items = [f"Game {i+1}: {h.get('White','?')} vs {h.get('Black','?')}" for i, (h,_) in enumerate(games)]
            item, ok = QInputDialog.getItem(self, "Select Game", "Choose game:", items, 0, False)
            if ok:
                index = items.index(item)
                self.controller.load_game_from_fpgn(path, index)

    def _start_match(self):
        dlg = MatchSetupDialog(self)
        if dlg.exec() == MatchSetupDialog.Accepted:
            settings = dlg.get_settings()
            if not settings["engine1"] or not settings["engine2"]:
                QMessageBox.warning(self, "Missing Engine", "Both paths are required.")
                return
            self.match_manager = EngineMatchManager(
                settings["engine1"], settings["engine2"],
                settings["time_control"], settings["games"],
                settings["save_games"]
            )
            self.match_manager.match_finished.connect(self._on_match_finished)
            self.match_manager.status_update.connect(self.status_label.setText)
            self.match_manager.start_match()

    def _stop_match(self):
        if self.match_manager:
            self.match_manager.stop_match()
            self.status_label.setText("Match stopped")

    def _on_match_finished(self, results):
        if self.match_manager:
            summary = self.match_manager.get_match_summary()
            QMessageBox.information(self, "Match Finished", summary)
            self.match_manager = None

    def _load_book(self):
        self.book_editor._load_book()

    def _save_book(self):
        self.book_editor._save_book()

    def _start_training(self):
        dlg = TrainingDialog(self)
        dlg.exec()

    def _about(self):
        QMessageBox.about(self, "About Fusion Chess",
                          "Fusion Chess – A hybrid of Chess and Shogi.\n"
                          "10x10 board, custom pieces, pure strategy.")