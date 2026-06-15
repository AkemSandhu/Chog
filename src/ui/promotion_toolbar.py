from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QApplication
from PySide6.QtCore import Signal, Qt, QPoint
from src.core.pieces import PieceType, PROMOTION_TARGETS

class PromotionToolbar(QWidget):
    """A floating toolbar for selecting a promotion piece."""
    promotion_selected = Signal(PieceType)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._buttons = {}
        self._decline_btn = None
        self._forced = False

    def show_for_piece(self, piece_type: PieceType, forced: bool):
        # Remove old buttons
        for btn in self._buttons.values():
            btn.deleteLater()
        self._buttons.clear()
        if self._decline_btn:
            self._decline_btn.deleteLater()
            self._decline_btn = None

        layout = self.layout()
        targets = PROMOTION_TARGETS.get(piece_type, [])
        for target in targets:
            name = target.name.capitalize()
            btn = QPushButton(name)
            btn.setStyleSheet("QPushButton { background: #eee; border: 1px solid #888; padding: 6px 12px; }")
            btn.clicked.connect(lambda checked, t=target: self.promotion_selected.emit(t))
            layout.addWidget(btn)
            self._buttons[target] = btn

        if not forced:
            decline = QPushButton("Decline")
            decline.setStyleSheet("QPushButton { background: #eee; border: 1px solid #888; padding: 6px 12px; }")
            decline.clicked.connect(self.cancelled.emit)
            layout.addWidget(decline)
            self._decline_btn = decline

        self.adjustSize()
        self.show()

    def hide_toolbar(self):
        self.hide()