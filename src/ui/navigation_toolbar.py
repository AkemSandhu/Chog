from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QStyle
from PySide6.QtCore import Signal

class NavigationToolbar(QWidget):
    """A small toolbar with Start, Back, Forward, End buttons for move navigation."""

    go_start = Signal()
    go_back = Signal()
    go_forward = Signal()
    go_end = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.btn_start = QPushButton("⏮")
        self.btn_start.setToolTip("Start")
        self.btn_back = QPushButton("◀")
        self.btn_back.setToolTip("Back")
        self.btn_forward = QPushButton("▶")
        self.btn_forward.setToolTip("Forward")
        self.btn_end = QPushButton("⏭")
        self.btn_end.setToolTip("End")

        for btn in (self.btn_start, self.btn_back, self.btn_forward, self.btn_end):
            btn.setFixedSize(32, 32)
            btn.setStyleSheet("QPushButton { font-size: 16px; }")
            layout.addWidget(btn)

        self.btn_start.clicked.connect(self.go_start)
        self.btn_back.clicked.connect(self.go_back)
        self.btn_forward.clicked.connect(self.go_forward)
        self.btn_end.clicked.connect(self.go_end)

    def set_enabled(self, at_start: bool, at_end: bool):
        self.btn_start.setEnabled(not at_start)
        self.btn_back.setEnabled(not at_start)
        self.btn_forward.setEnabled(not at_end)
        self.btn_end.setEnabled(not at_end)