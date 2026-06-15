from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QSpinBox, QCheckBox, QPushButton, QFormLayout, QDialogButtonBox)
from PySide6.QtCore import Qt

class MatchSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Engine Match Setup")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.engine1_edit = QLineEdit()
        self.engine1_edit.setPlaceholderText("Path to engine 1")
        form.addRow("Engine 1:", self.engine1_edit)

        self.engine2_edit = QLineEdit()
        self.engine2_edit.setPlaceholderText("Path to engine 2")
        form.addRow("Engine 2:", self.engine2_edit)

        self.time_spin = QSpinBox()
        self.time_spin.setRange(1, 3600)
        self.time_spin.setValue(600)
        self.time_spin.setSuffix(" seconds per player")
        form.addRow("Time Control:", self.time_spin)

        self.games_spin = QSpinBox()
        self.games_spin.setRange(1, 100)
        self.games_spin.setValue(2)
        form.addRow("Number of games:", self.games_spin)

        self.save_check = QCheckBox("Save games")
        self.save_check.setChecked(True)
        form.addRow(self.save_check)

        layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_settings(self):
        return {
            "engine1": self.engine1_edit.text(),
            "engine2": self.engine2_edit.text(),
            "time_control": self.time_spin.value(),
            "games": self.games_spin.value(),
            "save_games": self.save_check.isChecked()
        }