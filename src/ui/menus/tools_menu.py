# src/ui/menus/tools_menu.py
import os
from PySide6.QtGui import QIcon
from src.ui.menus.base_menu import RootMenu, SubMenu
from src.ui import icons

class ToolsMenu(RootMenu):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.title = "&Tools"

    def build(self):
        # Databases submenu
        db_sub = self.submenu("Databases", icons.icon_database())
        self._populate_db_submenu(db_sub, "games")

        # Openings submenu
        book_sub = self.submenu("Opening Books", icons.icon_opening())
        self._populate_book_submenu(book_sub, "config")

        # Shortcuts
        self.option("shortcuts", "Configure Shortcuts...", icons.icon_shortcuts())

    def _populate_db_submenu(self, submenu: SubMenu, folder: str):
        if not os.path.isdir(folder):
            return
        # List .fpgn files
        for file in sorted(os.listdir(folder)):
            if file.endswith(".fpgn"):
                full_path = os.path.join(folder, file)
                submenu.option(f"open_db_{full_path}", file, icons.icon_database())

    def _populate_book_submenu(self, submenu: SubMenu, folder: str):
        if not os.path.isdir(folder):
            return
        for file in sorted(os.listdir(folder)):
            if file.endswith(".db") or file.endswith(".chb"):
                full_path = os.path.join(folder, file)
                submenu.option(f"open_book_{full_path}", file, icons.icon_opening())

    def execute(self, key: str):
        if key == "shortcuts":
            self.main_window._open_shortcuts_dialog()
        elif key.startswith("open_db_"):
            db_path = key[len("open_db_"):]
            self.main_window.controller.load_games_from_fpgn(db_path)
        elif key.startswith("open_book_"):
            book_path = key[len("open_book_"):]
            self.main_window.book_editor._load_book(book_path)  # need a method to load specific path