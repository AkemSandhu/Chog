from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel
from src.core.pieces import PieceType, Colour, PROMOTION_TARGETS

class PromotionDialog(QDialog):
    def __init__(self, piece_type: PieceType, colour: Colour, forced: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Promotion")
        self.chosen_piece: PieceType = None
        self.declined = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Promote {piece_type.name}?"))

        if piece_type == PieceType.PAWN:
            self.gold_btn = QPushButton("Gold (O)")
            self.hunter_btn = QPushButton("Hunter (U)")
            self.gold_btn.clicked.connect(lambda: self.done_with(PieceType.GOLD))
            self.hunter_btn.clicked.connect(lambda: self.done_with(PieceType.HUNTER))
            layout.addWidget(self.gold_btn)
            layout.addWidget(self.hunter_btn)
            if not forced:
                self.decline_btn = QPushButton("Don't Promote")
                self.decline_btn.clicked.connect(self.decline)
                layout.addWidget(self.decline_btn)
        else:
            target = PROMOTION_TARGETS[piece_type][0]
            self.promote_btn = QPushButton(f"Promote to {target.name}")
            self.promote_btn.clicked.connect(lambda: self.done_with(target))
            layout.addWidget(self.promote_btn)
            if not forced:
                self.decline_btn = QPushButton("Don't Promote")
                self.decline_btn.clicked.connect(self.decline)
                layout.addWidget(self.decline_btn)

    def done_with(self, ptype):
        self.chosen_piece = ptype
        self.accept()

    def decline(self):
        self.declined = True
        self.reject()