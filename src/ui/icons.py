from PySide6.QtGui import QIcon, QPixmap, QColor
import os

_ICON_DIR = os.path.join(os.path.dirname(__file__), "..", "resources", "icons")

def _load_icon(name: str) -> QIcon:
    """Load icon from resources/icons/<name>.png, or create a simple pixmap."""
    path = os.path.join(_ICON_DIR, f"{name}.png")
    if os.path.exists(path):
        return QIcon(path)
    # Fallback: create a small colored square
    pm = QPixmap(32, 32)
    pm.fill(QColor(128, 128, 128))
    return QIcon(pm)

def icon_new_game():       return _load_icon("new_game")
def icon_load_game():      return _load_icon("load")
def icon_exit():           return _load_icon("exit")
def icon_flip_board():     return _load_icon("flip")
def icon_fullscreen():     return _load_icon("fullscreen")
def icon_tray():           return _load_icon("tray")
def icon_prev_game():      return _load_icon("prev")
def icon_next_game():      return _load_icon("next")
def icon_engine_config():  return _load_icon("engine_config")
def icon_analysis():       return _load_icon("analysis")
def icon_batch_analyze():  return _load_icon("batch")
def icon_match():          return _load_icon("match")
def icon_stop_match():     return _load_icon("stop")
def icon_book_load():      return _load_icon("book_load")
def icon_book_save():      return _load_icon("book_save")
def icon_training():       return _load_icon("training")
def icon_about():          return _load_icon("about")
def icon_database():       return _load_icon("database")
def icon_opening():        return _load_icon("opening")
def icon_shortcuts():      return _load_icon("shortcuts")