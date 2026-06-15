from PySide6.QtGui import QIcon
from src.ui.menus.base_menu import RootMenu
from src.ui import icons

class FileMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&File"

    def build(self):
        sm = self.main_window.shortcuts_manager
        self.option("new_game", "&New Game", icons.icon_new_game(), shortcut=sm.get("new_game"))
        self.option("load_game", "&Load Game...", icons.icon_load_game(), shortcut=sm.get("load_game"))
        self.option("exit", "E&xit", icons.icon_exit(), shortcut=sm.get("exit"), sep_before=True)

    def execute(self, key):
        if key == "new_game": self.controller.start_new_game()
        elif key == "load_game": self.main_window._load_game()
        elif key == "exit": self.main_window.close()

class ViewMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&View"

    def build(self):
        sm = self.main_window.shortcuts_manager
        self.option("flip_board", "Flip Board", icons.icon_flip_board(), shortcut=sm.get("flip_board"))
        self.option("fullscreen", "Fullscreen", icons.icon_fullscreen(), shortcut=sm.get("fullscreen"))
        self.option("tray", "Minimize to Tray", icons.icon_tray(), shortcut=sm.get("tray"))

    def execute(self, key):
        if key == "flip_board": self.main_window.board_widget.flip_board()
        elif key == "fullscreen": self.main_window.toggle_fullscreen()
        elif key == "tray": self.main_window.toggle_tray_icon()

class ReviewMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&Review"

    def build(self):
        sm = self.main_window.shortcuts_manager
        self.option("prev_game", "Previous Game", icons.icon_prev_game(), shortcut=sm.get("prev_game"))
        self.option("next_game", "Next Game", icons.icon_next_game(), shortcut=sm.get("next_game"))

    def execute(self, key):
        if key == "prev_game": self.controller.previous_game()
        elif key == "next_game": self.controller.next_game()

class EngineMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&Engine"

    def build(self):
        self.option("engine_config", "Configure Engines...", icons.icon_engine_config())

    def execute(self, key):
        if key == "engine_config": self.main_window._open_engine_config()

class AnalysisMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&Analysis"

    def build(self):
        self.option("set_analysis_engine", "Set Analysis Engine...", icons.icon_analysis())
        self.option("batch_analyze", "Batch Analyze Game...", icons.icon_batch_analyze(), sep_before=True)

    def execute(self, key):
        if key == "set_analysis_engine": self.main_window._set_analysis_engine()
        elif key == "batch_analyze": self.main_window._batch_analyze_game()

class MatchMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&Match"

    def build(self):
        self.option("start_match", "New Engine Match...", icons.icon_match())
        self.option("stop_match", "Stop Match", icons.icon_stop_match())

    def execute(self, key):
        if key == "start_match": self.main_window._start_match()
        elif key == "stop_match": self.main_window._stop_match()

class BookMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&Book"

    def build(self):
        self.option("load_book", "Load Book...", icons.icon_book_load())
        self.option("save_book", "Save Book As...", icons.icon_book_save())

    def execute(self, key):
        if key == "load_book": self.main_window._load_book()
        elif key == "save_book": self.main_window._save_book()

class TrainingMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&Training"

    def build(self):
        self.option("start_training", "New Training Session...", icons.icon_training())

    def execute(self, key):
        if key == "start_training": self.main_window._start_training()

class HelpMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&Help"

    def build(self):
        self.option("about", "About Chog", icons.icon_about())

    def execute(self, key):
        if key == "about": self.main_window._about()