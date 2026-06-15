import json
import os
from PySide6.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QSpinBox, QCheckBox, QComboBox, QLineEdit, QLabel,
    QFileDialog, QColorDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("General Configuration")
        self.resize(500, 400)
        self.config = self.load_config()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._setup_board_tab()
        self._setup_sound_tab()
        self._setup_appearance_tab()
        self._setup_time_tab()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_config(self):
        default = {
            "board/light_color": "#F0D9B5",
            "board/dark_color": "#B58863",
            "board/piece_set": "default",
            "sound/enabled": True,
            "animation/speed": 200,
            "appearance/font_size": 12,
            "time/default_minutes": 10,
            "time/default_increment": 0,
        }
        try:
            with open("config/settings.json", "r") as f:
                loaded = json.load(f)
                default.update(loaded)
        except FileNotFoundError:
            pass
        return default

    def save_config(self):
        os.makedirs("config", exist_ok=True)
        with open("config/settings.json", "w") as f:
            json.dump(self.config, f, indent=2)

    def _setup_board_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.light_color_btn = QPushButton()
        self.light_color_btn.setStyleSheet(f"background: {self.config['board/light_color']}")
        self.light_color_btn.clicked.connect(lambda: self._pick_color('board/light_color', self.light_color_btn))
        layout.addRow("Light squares:", self.light_color_btn)

        self.dark_color_btn = QPushButton()
        self.dark_color_btn.setStyleSheet(f"background: {self.config['board/dark_color']}")
        self.dark_color_btn.clicked.connect(lambda: self._pick_color('board/dark_color', self.dark_color_btn))
        layout.addRow("Dark squares:", self.dark_color_btn)

        self.piece_combo = QComboBox()
        self.piece_combo.addItems(["default", "merida", "alpha"])
        self.piece_combo.setCurrentText(self.config.get("board/piece_set", "default"))
        self.piece_combo.currentTextChanged.connect(lambda t: self.config.update({"board/piece_set": t}))
        layout.addRow("Piece set:", self.piece_combo)

        self.tabs.addTab(tab, "Board")

    def _pick_color(self, key, btn):
        color = QColorDialog.getColor(QColor(self.config[key]), self, "Choose Color")
        if color.isValid():
            self.config[key] = color.name()
            btn.setStyleSheet(f"background: {color.name()}")

    def _setup_sound_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.sound_enabled = QCheckBox()
        self.sound_enabled.setChecked(self.config.get("sound/enabled", True))
        self.sound_enabled.toggled.connect(lambda v: self.config.update({"sound/enabled": v}))
        layout.addRow("Enable sounds:", self.sound_enabled)
        self.tabs.addTab(tab, "Sound")

    def _setup_appearance_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 24)
        self.font_spin.setValue(self.config.get("appearance/font_size", 12))
        self.font_spin.valueChanged.connect(lambda v: self.config.update({"appearance/font_size": v}))
        layout.addRow("Font size:", self.font_spin)
        self.tabs.addTab(tab, "Appearance")

    def _setup_time_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 120)
        self.minutes_spin.setValue(self.config.get("time/default_minutes", 10))
        self.minutes_spin.valueChanged.connect(lambda v: self.config.update({"time/default_minutes": v}))
        layout.addRow("Default minutes:", self.minutes_spin)

        self.increment_spin = QSpinBox()
        self.increment_spin.setRange(0, 60)
        self.increment_spin.setValue(self.config.get("time/default_increment", 0))
        self.increment_spin.valueChanged.connect(lambda v: self.config.update({"time/default_increment": v}))
        layout.addRow("Default increment (sec):", self.increment_spin)
        self.tabs.addTab(tab, "Time")

    def save_and_accept(self):
        self.save_config()
        self.accept()