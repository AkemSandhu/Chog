from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QMenuBar, QStatusBar, QLabel,
    QMessageBox, QFileDialog, QInputDialog,
    QSystemTrayIcon, QMenu
)
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtCore import Qt
from typing import Optional
import json

from src.ui.board_widget import BoardWidget
from src.ui.move_list import MoveListWidget
from src.ui.clock_widget import ClockWidget
from src.ui.analysis_panel import AnalysisPanel
from src.ui.analysis_graph import AnalysisGraph
from src.ui.match_dialog import MatchSetupDialog
from src.ui.book_editor import BookEditorWidget
from src.ui.training_dialog import TrainingDialog
from src.ui.engine_config_dialog import EngineConfigDialog
from src.ui.game_database_widget import GameDatabaseWidget
from src.ui.config_dialog import ConfigDialog
from src.ui.dynamic_toolbar import DynamicToolbar
from src.game_controller import GameController
from src.engine.match_manager import EngineMatchManager
from src.engine.batch_analysis import BatchAnalysis
from src.core.game_state import GameState
from src.io.fen import board_to_fen
from src.io.fpgn import FPGNReader
from src.ui.sound_manager import SoundManager
from src.ui.messages import WaitingOverlay, info_message, error_message, question_dialog, temporary_message
from src.ui.navigation_toolbar import NavigationToolbar
from src.ui.menus.base_menu import Option, SubMenu
from src.ui.menus.app_menus import (
    FileMenu, ViewMenu, ReviewMenu, EngineMenu,
    AnalysisMenu, MatchMenu, BookMenu, TrainingMenu, HelpMenu
)
from src.ui.menus.tools_menu import ToolsMenu
from src.ui.shortcuts_manager import ShortcutsManager, ShortcutsDialog
from src.ui import icons


class MainWindow(QMainWindow):
    def __init__(self, white_engine_path: Optional[str] = None,
                 black_engine_path: Optional[str] = None):
        super().__init__()
        self.setWindowTitle("Chog – Universal Chess‑Shogi Hybrid")
        self.resize(1200, 900)
        self.setWindowIcon(icons.icon_about())

        self.sound_manager = SoundManager("sounds")
        self.shortcuts_manager = ShortcutsManager()

        self.board_widget = BoardWidget()
        self.setCentralWidget(self.board_widget)

        # Navigation toolbar + Move list
        self.nav_toolbar = NavigationToolbar()
        self.move_list = MoveListWidget()
        move_container = QWidget()
        move_layout = QVBoxLayout(move_container)
        move_layout.addWidget(self.nav_toolbar)
        move_layout.addWidget(self.move_list)
        move_dock = QDockWidget("Moves", self)
        move_dock.setWidget(move_container)
        self.addDockWidget(Qt.RightDockWidgetArea, move_dock)

        self.nav_toolbar.go_start.connect(lambda: self.controller._goto_ply(0))
        self.nav_toolbar.go_back.connect(self._nav_go_back)
        self.nav_toolbar.go_forward.connect(self._nav_go_forward)
        self.nav_toolbar.go_end.connect(
            lambda: self.controller._goto_ply(len(self.controller.move_history) - 1)
        )

        # Clocks
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

        # Analysis
        self.analysis_panel = AnalysisPanel()
        analysis_dock = QDockWidget("Analysis", self)
        analysis_dock.setWidget(self.analysis_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, analysis_dock)
        self.analysis_panel.arrows_changed.connect(self.board_widget.set_arrows)
        self.analysis_panel.markers_changed.connect(self.board_widget.set_markers)

        # Graph
        self.analysis_graph = AnalysisGraph()
        graph_dock = QDockWidget("Eval Graph", self)
        graph_dock.setWidget(self.analysis_graph)
        self.addDockWidget(Qt.BottomDockWidgetArea, graph_dock)

        # Opening Book
        self.book_editor = BookEditorWidget()
        book_dock = QDockWidget("Opening Book", self)
        book_dock.setWidget(self.book_editor)
        self.addDockWidget(Qt.RightDockWidgetArea, book_dock)

        # Game Database
        self.game_database = GameDatabaseWidget()
        db_dock = QDockWidget("Game Database", self)
        db_dock.setWidget(self.game_database)
        self.addDockWidget(Qt.RightDockWidgetArea, db_dock)

        # Dynamic toolbar
        self.dynamic_toolbar = DynamicToolbar(self)
        self.addToolBar(Qt.TopToolBarArea, self.dynamic_toolbar)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Controller
        self.controller = GameController(
            self.board_widget, self.move_list,
            self.white_clock, self.black_clock,
            white_engine_path, black_engine_path,
            time_control_seconds=600, increment_seconds=2,
            animation_enabled=True,
            sound_manager=self.sound_manager
        )
        try:
            with open("config/settings.json", "r") as f:
                settings = json.load(f)
        except FileNotFoundError:
            settings = {}
        self.controller.clock_auto_start = settings.get("clock/auto_start", False)

        self.controller.status_update.connect(self.status_label.setText)
        self.controller.game_ended.connect(self._on_game_ended)
        self.controller.position_changed.connect(self._on_position_changed)
        self.controller.game_mode_changed.connect(self._update_toolbar)
        self.controller.position_changed.connect(self._update_nav_buttons)

        self.match_manager: Optional[EngineMatchManager] = None
        self.batch_analysis: Optional[BatchAnalysis] = None
        self.game_database.game_load_requested.connect(self.controller.load_game_from_fpgn)

        self.tray_icon = None

        self._create_menus()

        for dock in (move_dock, clock_dock, analysis_dock, graph_dock, book_dock, db_dock):
            dock.topLevelChanged.connect(lambda floating: self.shrink())

        self.controller.start_new_game()

    def shrink(self):
        self.resize(self.minimumSizeHint())

    def showEvent(self, event):
        super().showEvent(event)
        self.shrink()

    # ---- Navigation helpers ----
    def _nav_go_back(self):
        ply = self.controller.current_ply
        if ply > 0:
            self.controller._goto_ply(ply - 1)

    def _nav_go_forward(self):
        ply = self.controller.current_ply
        history = self.controller.move_history
        if ply < len(history) - 1:
            self.controller._goto_ply(ply + 1)

    def _update_nav_buttons(self):
        ply = self.controller.current_ply
        total = len(self.controller.move_history)
        self.nav_toolbar.set_enabled(ply <= 0, ply >= total - 1)

    # ---- Toolbar ----
    def _update_toolbar(self, mode: str):
        if mode == "playing":
            actions = [
                ("new_game", "New Game", icons.icon_new_game(), self.controller.start_new_game),
                ("flip", "Flip", icons.icon_flip_board(), self.board_widget.flip_board),
            ]
        else:
            actions = [
                ("prev_game", "Previous", icons.icon_prev_game(), self.controller.previous_game),
                ("next_game", "Next", icons.icon_next_game(), self.controller.next_game),
                ("takeback", "Takeback", icons.icon_exit(), lambda: self.controller.takeback()),
            ]
        self.dynamic_toolbar.set_actions(actions)

    # ---- Menu creation ----
    def _create_menus(self):
        self.menu_instances = [
            FileMenu(self), ViewMenu(self), ReviewMenu(self),
            EngineMenu(self), AnalysisMenu(self), MatchMenu(self),
            BookMenu(self), TrainingMenu(self), ToolsMenu(self), HelpMenu(self)
        ]
        self._all_menu_actions = {}
        for menu in self.menu_instances:
            menu.build()
            qmenu = self.menuBar().addMenu(menu.title)
            self._populate_qmenu(qmenu, menu.children)

        # Options menu
        options_menu = self.menuBar().addMenu("&Options")
        config_action = QAction("General Configuration...", self)
        config_action.setIcon(icons.icon_engine_config())
        config_action.triggered.connect(self._open_config_dialog)
        options_menu.addAction(config_action)

        for (key, _), action in self._all_menu_actions.items():
            shortcut = self.shortcuts_manager.get(key)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))

        self.prev_game_action = self._find_action("prev_game")
        self.next_game_action = self._find_action("next_game")

    def _find_action(self, key: str) -> QAction:
        for (k, _), act in self._all_menu_actions.items():
            if k == key:
                return act
        return QAction(self)

    def _populate_qmenu(self, qmenu, items):
        for item in items:
            if isinstance(item, SubMenu):
                sub_qmenu = qmenu.addMenu(item.label)
                if item.icon:
                    sub_qmenu.setIcon(item.icon)
                sub_qmenu.setEnabled(item.enabled)
                self._populate_qmenu(sub_qmenu, item.children)
            elif isinstance(item, Option):
                if item.separator_before:
                    qmenu.addSeparator()
                action = QAction(item.label, self)
                if item.icon:
                    action.setIcon(item.icon)
                if item.shortcut:
                    action.setShortcut(item.shortcut)
                action.setEnabled(item.enabled)
                action.setCheckable(item.checkable)
                action.setChecked(item.checked)
                action.triggered.connect(lambda checked, opt=item: opt.menu.execute(opt.key))
                qmenu.addAction(action)
                self._all_menu_actions[(item.key, id(action))] = action

    # ---- Tray icon ----
    def toggle_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            temporary_message(self, "System tray not available.", 2000)
            return
        if not self.tray_icon:
            restore_action = QAction("Show", self)
            restore_action.triggered.connect(self.restore_from_tray)
            quit_action = QAction("Quit", self)
            quit_action.triggered.connect(self.close)
            tray_menu = QMenu(self)
            tray_menu.addAction(restore_action)
            tray_menu.addSeparator()
            tray_menu.addAction(quit_action)

            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.setIcon(self.windowIcon())
            self.tray_icon.activated.connect(self.on_tray_activated)

        if self.tray_icon.isVisible():
            self.tray_icon.hide()
        else:
            self.tray_icon.show()
            self.hide()

    def restore_from_tray(self):
        self.tray_icon.hide()
        self.showNormal()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.restore_from_tray()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ---- Config / shortcuts dialogs ----
    def _open_config_dialog(self):
        dlg = ConfigDialog(self)
        if dlg.exec():
            temporary_message(self, "Settings saved. Some changes may require restart.", 2500)

    def _open_shortcuts_dialog(self):
        dlg = ShortcutsDialog(self.shortcuts_manager, self)
        if dlg.exec():
            for (key, _), action in self._all_menu_actions.items():
                shortcut = self.shortcuts_manager.get(key)
                action.setShortcut(QKeySequence(shortcut) if shortcut else QKeySequence())

    # -----------------------------------------------------------------
    # Slots
    # -----------------------------------------------------------------
    def _on_position_changed(self):
        fen = board_to_fen(self.controller.state.board, self.controller.state.turn,
                           self.controller.state.halfmove_clock,
                           self.controller.state.fullmove_number)
        self.analysis_panel.set_position(fen)
        legal_moves = self.controller.get_legal_moves()
        move_history = self.controller.move_history
        self.book_editor.set_position(self.controller.state, legal_moves, move_history)

    def _on_game_ended(self, message: str):
        info_message(self, "Game Over", message)
        self.controller.start_new_game()

    def _open_engine_config(self):
        dlg = EngineConfigDialog(self)
        if dlg.exec():
            temporary_message(self, "Engine configuration saved.")

    def _set_analysis_engine(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Analysis Engine", "",
                                              "Executable Files (*);;All Files (*)")
        if path:
            self.analysis_panel.set_engine_path(path)
            self.game_database.set_engine_path(path)
            self.status_label.setText(f"Analysis engine set: {path}")
            self.book_editor.set_engine_path(path)
            temporary_message(self, "Analysis engine set.", 1500)

    def _load_game(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open FPGN File", "games/",
                                              "FPGN Files (*.fpgn);;All Files (*)")
        if not path:
            return
        self.controller.load_games_from_fpgn(path)
        self._update_game_navigation_buttons()

    def _update_game_navigation_buttons(self):
        has_games = len(self.controller.loaded_games) > 1
        if self.prev_game_action:
            self.prev_game_action.setEnabled(has_games and self.controller.current_game_index > 0)
        if self.next_game_action:
            self.next_game_action.setEnabled(has_games and self.controller.current_game_index < len(self.controller.loaded_games) - 1)

    def _batch_analyze_game(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open FPGN File", "games/",
                                              "FPGN Files (*.fpgn);;All Files (*)")
        if not path:
            return
        games = FPGNReader.read_file(path)
        if not games:
            error_message(self, "Error", "No games found in file.")
            return
        headers, moves = games[0]
        state = GameState()
        move_history = moves

        engine_path = self.analysis_panel.engine.path_exe if self.analysis_panel.engine else None
        if not engine_path:
            engine_path, _ = QFileDialog.getOpenFileName(self, "Select Engine for Batch Analysis", "",
                                                         "Executable Files (*);;All Files (*)")
            if not engine_path:
                error_message(self, "No Engine", "An engine is required for batch analysis.")
                return

        movetime, ok = QInputDialog.getInt(self, "Move Time", "Milliseconds per move:", 5000, 100, 60000, 100)
        if not ok:
            return

        self.batch_analysis = BatchAnalysis(engine_path, movetime)
        self.batch_analysis.progress.connect(lambda cur, tot: self.status_label.setText(f"Analyzing move {cur}/{tot}"))
        self.batch_analysis.analysis_complete.connect(
            lambda: info_message(self, "Done", "Batch analysis complete."))
        self.batch_analysis.analyze_game(state, move_history)

    def _start_match(self):
        dlg = MatchSetupDialog(self)
        if dlg.exec() == MatchSetupDialog.Accepted:
            settings = dlg.get_settings()
            if not settings["engine1"] or not settings["engine2"]:
                error_message(self, "Missing Engine", "Both paths are required.")
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
            info_message(self, "Match Finished", summary)
            self.match_manager = None

    def _load_book(self):
        self.book_editor._load_book()

    def _save_book(self):
        self.book_editor._save_book()

    def _start_training(self):
        dlg = TrainingDialog(self)
        dlg.exec()

    def _about(self):
        info_message(self, "About Chog",
                     "Chog – A Universal Chess‑Shogi Hybrid.\n"
                     "10x10 board, custom pieces, pure strategy.\n"
                     "Powered by CUEP (Chog Universal Engine Protocol).")