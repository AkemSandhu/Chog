from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QDoubleSpinBox,
    QLineEdit, QDialogButtonBox
)
from typing import List
from chog.core.movegen import Move
from chog.engine.protocol import move_to_uci

class AddMoveDialog(QDialog):
    def __init__(self, legal_moves: List[Move], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Book Move")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Move:"))
        self.move_combo = QComboBox()
        self.move_map = {}
        for move in legal_moves:
            uci = move_to_uci(move)
            self.move_combo.addItem(uci)
            self.move_map[uci] = move
        layout.addWidget(self.move_combo)

        layout.addWidget(QLabel("Weight:"))
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0.0, 1000.0)
        self.weight_spin.setValue(1.0)
        self.weight_spin.setSingleStep(0.1)
        layout.addWidget(self.weight_spin)

        layout.addWidget(QLabel("Comment:"))
        self.comment_edit = QLineEdit()
        layout.addWidget(self.comment_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_move(self) -> Move:
        uci = self.move_combo.currentText()
        return self.move_map[uci]

    def get_weight(self) -> float:
        return self.weight_spin.value()

    def get_comment(self) -> str:
        return self.comment_edit.text().strip()