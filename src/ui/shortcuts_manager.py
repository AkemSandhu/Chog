import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QMessageBox, QLabel, QKeySequenceEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence

DEFAULT_SHORTCUTS = {
    "new_game": "Ctrl+N",
    "load_game": "Ctrl+O",
    "exit": "Ctrl+Q",
    "flip_board": "Ctrl+F",
    "fullscreen": "F11",
    "tray": "F12",
    "prev_game": "Ctrl+Left",
    "next_game": "Ctrl+Right",
    "engine_config": "",
    "set_analysis_engine": "",
    "batch_analyze": "",
    "start_match": "",
    "stop_match": "",
    "load_book": "",
    "save_book": "",
    "start_training": "",
    "about": "",
}

class ShortcutsManager:
    def __init__(self, config_path="config/shortcuts.json"):
        self.config_path = config_path
        self.shortcuts = self._load()

    def _load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                return json.load(f)
        return dict(DEFAULT_SHORTCUTS)

    def save(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.shortcuts, f, indent=2)

    def get(self, key: str) -> str:
        return self.shortcuts.get(key, "")

    def set(self, key: str, value: str):
        self.shortcuts[key] = value
        self.save()


class ShortcutsDialog(QDialog):
    def __init__(self, manager: ShortcutsManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(500, 400)
        self.manager = manager

        layout = QVBoxLayout(self)

        self.table = QTableWidget(len(DEFAULT_SHORTCUTS), 2)
        self.table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        # Fill table with current shortcuts
        self._actions_order = list(DEFAULT_SHORTCUTS.keys())
        for row, key in enumerate(self._actions_order):
            label = key.replace("_", " ").title()
            self.table.setItem(row, 0, QTableWidgetItem(label))
            shortcut = manager.get(key)
            item = QTableWidgetItem(shortcut)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row, 1, item)

        layout.addWidget(self.table)

        # Edit button
        btn_layout = QHBoxLayout()
        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self._edit_shortcut)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_shortcut)
        reset_btn = QPushButton("Reset All")
        reset_btn.clicked.connect(self._reset_all)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(reset_btn)
        layout.addLayout(btn_layout)

        # Save/Cancel
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_and_accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(save_btn)
        btn_layout2.addWidget(cancel_btn)
        layout.addLayout(btn_layout2)

    def _edit_shortcut(self):
        row = self.table.currentRow()
        if row < 0:
            return
        key = self._actions_order[row]
        current = self.table.item(row, 1).text()
        # Use QKeySequenceEdit in a small dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Press Shortcut")
        layout = QVBoxLayout(dlg)
        editor = QKeySequenceEdit()
        editor.setKeySequence(QKeySequence(current) if current else QKeySequence())
        layout.addWidget(editor)
        buttons = QHBoxLayout()
        ok = QPushButton("OK")
        ok.clicked.connect(dlg.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dlg.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        if dlg.exec() == QDialog.Accepted:
            seq = editor.keySequence()
            new_shortcut = seq.toString() if seq != QKeySequence() else ""
            # Check for conflicts
            for other_key in self._actions_order:
                if other_key != key and self.table.item(self._actions_order.index(other_key), 1).text() == new_shortcut and new_shortcut:
                    QMessageBox.warning(self, "Conflict", f"Shortcut already used by '{other_key}'.")
                    return
            self.table.item(row, 1).setText(new_shortcut)

    def _clear_shortcut(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.item(row, 1).setText("")

    def _reset_all(self):
        for row, key in enumerate(self._actions_order):
            self.table.item(row, 1).setText(DEFAULT_SHORTCUTS.get(key, ""))

    def _save_and_accept(self):
        for row, key in enumerate(self._actions_order):
            self.manager.set(key, self.table.item(row, 1).text())
        self.accept()