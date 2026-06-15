from PySide6.QtWidgets import (
    QTableView, QAbstractItemView, QHeaderView, QMenu, QMessageBox, QInputDialog,
    QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Signal, Qt, QAbstractTableModel, QModelIndex, QSize
from PySide6.QtGui import QAction, QColor, QFont
from typing import List, Tuple, Optional

class MoveModel(QAbstractTableModel):
    COL_NUMBER, COL_WHITE, COL_BLACK = range(3)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._moves: List[Tuple[str, bool, str, str, str]] = []  # (move_str, is_white, comment, score, indicators)

    def add_move(self, move_str: str, is_white: bool, comment: str = "",
                 score: str = "", indicators: str = ""):
        self._moves.append((move_str, is_white, comment, score, indicators))
        row = (len(self._moves) - 1) // 2
        if is_white:
            self.beginInsertRows(QModelIndex(), row, row)
            self.endInsertRows()
        else:
            self.dataChanged.emit(
                self.index(row, self.COL_BLACK),
                self.index(row, self.COL_BLACK)
            )

    def clear(self):
        self.beginResetModel()
        self._moves.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if not self._moves:
            return 0
        return (len(self._moves) + 1) // 2

    def columnCount(self, parent=QModelIndex()):
        return 3

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        ply = row * 2 + (1 if col == self.COL_BLACK else 0)
        if col == self.COL_NUMBER:
            if role == Qt.DisplayRole:
                return str(row + 1)
            return None
        if ply >= len(self._moves):
            return None
        move_str, is_white, comment, score, indicators = self._moves[ply]
        if col == self.COL_WHITE and not is_white:
            return None
        if col == self.COL_BLACK and is_white:
            return None
        if role == Qt.DisplayRole:
            return move_str
        if role == Qt.ToolTipRole:
            return comment if comment else ""
        if role == Qt.UserRole + 1:
            return score
        if role == Qt.UserRole + 2:
            return indicators
        return None

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ["#", "White", "Black"][section]
        return None

    def get_ply(self, row: int, col: int) -> int:
        if col == self.COL_NUMBER:
            return -1
        return row * 2 + (1 if col == self.COL_BLACK else 0)


class MoveDelegate(QStyledItemDelegate):
    """Custom delegate for painting move cells with optional score and indicators."""
    def paint(self, painter, option, index):
        painter.save()
        # Selection background
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor("#3399ff"))
        else:
            painter.fillRect(option.rect, option.palette.base())

        move_str = index.data(Qt.DisplayRole)
        score = index.data(Qt.UserRole + 1)
        indicators = index.data(Qt.UserRole + 2)

        rect = option.rect.adjusted(4, 2, -4, -2)
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)

        # Draw move text
        if move_str:
            painter.setPen(Qt.black)
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, move_str)

        # Draw score on right side
        if score:
            painter.setPen(QColor("#555555"))
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, score)

        # Draw indicators (icons not implemented, just text)
        if indicators:
            painter.setPen(QColor("#888888"))
            font.setPointSize(7)
            painter.setFont(font)
            indicator_rect = rect.adjusted(0, rect.height()//2, 0, 0)
            painter.drawText(indicator_rect, Qt.AlignLeft | Qt.AlignBottom, indicators)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(120, 24)


class MoveListWidget(QTableView):
    move_selected = Signal(int)           # ply index (0-based)
    takeback_requested = Signal()
    delete_move_requested = Signal(int)
    new_variation_requested = Signal()
    switch_variation_requested = Signal(object)
    promote_variation_requested = Signal(object)
    save_analysis_requested = Signal(str, object, int, int)
    load_analysis_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = MoveModel(self)
        self.setModel(self._model)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.setColumnWidth(0, 40)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setItemDelegate(MoveDelegate(self))
        self.clicked.connect(self._on_cell_clicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._moves_count = 0

    def add_move(self, move_str: str, is_white: bool, comment: str = "",
                 score: str = "", indicators: str = ""):
        self._model.add_move(move_str, is_white, comment, score, indicators)
        self._moves_count += 1
        self.scrollToBottom()

    def clear_moves(self):
        self._model.clear()
        self._moves_count = 0

    def set_current_ply(self, ply: int):
        row = ply // 2
        col = MoveModel.COL_WHITE if ply % 2 == 0 else MoveModel.COL_BLACK
        index = self._model.index(row, col)
        self.setCurrentIndex(index)
        self.scrollTo(index)

    def _on_cell_clicked(self, index):
        ply = self._model.get_ply(index.row(), index.column())
        if ply >= 0 and ply < self._moves_count:
            self.move_selected.emit(ply)

    def _show_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return
        ply = self._model.get_ply(index.row(), index.column())
        if ply < 0 or ply >= self._moves_count:
            return
        menu = QMenu(self)
        takeback_action = QAction("Takeback from here", self)
        takeback_action.triggered.connect(lambda: self.delete_move_requested.emit(ply))
        menu.addAction(takeback_action)
        delete_action = QAction("Delete this move", self)
        delete_action.triggered.connect(lambda: self.delete_move_requested.emit(ply))
        menu.addAction(delete_action)
        if ply == self._moves_count - 1:
            undo_last_action = QAction("Undo last move", self)
            undo_last_action.triggered.connect(self.takeback_requested.emit)
            menu.addAction(undo_last_action)
        menu.addSeparator()
        new_var_action = QAction("New variation from here", self)
        new_var_action.triggered.connect(self.new_variation_requested.emit)
        menu.addAction(new_var_action)
        menu.addSeparator()
        analysis_menu = menu.addMenu("Analysis")
        save_action = QAction("Save current engine analysis...", self)
        save_action.triggered.connect(lambda: self.save_analysis_requested.emit("", None, 0, 0))
        analysis_menu.addAction(save_action)
        load_action = QAction("Load analysis...", self)
        load_action.triggered.connect(lambda: self.load_analysis_requested.emit("", ""))
        analysis_menu.addAction(load_action)
        menu.exec(self.viewport().mapToGlobal(pos))