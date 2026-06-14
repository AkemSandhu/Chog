from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PySide6.QtCore import Signal

class MoveListWidget(QTableWidget):
    move_selected = Signal(int)   # ply index (0-based)

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["#", "White", "Black"])
        self.setColumnWidth(0, 40)
        self.setColumnWidth(1, 120)
        self.setColumnWidth(2, 120)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.cellClicked.connect(self._on_cell_clicked)
        self._moves = []   # list of (move_str, is_white)

    def add_move(self, move_str: str, is_white: bool):
        self._moves.append((move_str, is_white))
        if is_white:
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.setItem(row, 1, QTableWidgetItem(move_str))
        else:
            row = self.rowCount() - 1
            self.setItem(row, 2, QTableWidgetItem(move_str))
        self.scrollToBottom()

    def clear_moves(self):
        self.setRowCount(0)
        self._moves.clear()

    def set_current_ply(self, ply: int):
        """Highlight the row containing the given ply (0‑based)."""
        row = ply // 2
        if ply % 2 == 0:
            self.setCurrentCell(row, 1)
        else:
            self.setCurrentCell(row, 2)
        self.scrollToItem(self.currentItem())

    def _on_cell_clicked(self, row: int, col: int):
        if col == 1:
            ply = row * 2
        elif col == 2:
            ply = row * 2 + 1
        else:
            return
        if ply < len(self._moves):
            self.move_selected.emit(ply)