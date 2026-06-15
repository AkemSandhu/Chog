from PySide6.QtWidgets import QToolBar
from PySide6.QtCore import QSize
from PySide6.QtGui import QAction

class DynamicToolbar(QToolBar):
    def __init__(self, parent=None):
        super().__init__("Main", parent)
        self.setIconSize(QSize(24, 24))
        self.setMovable(False)

    def set_actions(self, action_defs):
        """Replace all actions. `action_defs` is a list of tuples:
        (key, label, icon_path_or_None, callback).
        """
        self.clear()
        for key, label, icon, callback in action_defs:
            action = QAction(label, self)
            if icon:
                action.setIcon(icon)
            action.triggered.connect(callback)
            action.setData(key)
            self.addAction(action)

    def enable_action(self, key: str, enabled: bool):
        for action in self.actions():
            if action.data() == key:
                action.setEnabled(enabled)
                break