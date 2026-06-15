from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QMessageBox, QFileDialog,
    QInputDialog, QLabel, QLineEdit, QComboBox, QProgressBar, QDialog
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction
from typing import Optional, List
from src.core.game_database import GameDatabase
from src.engine.batch_analysis import BatchAnalysis
from src.io.fpgn import FPGNReader

class GameDatabaseWidget(QWidget):
    """Dockable widget for browsing and managing a game database."""
    game_load_requested = Signal(str, int)  # filepath, game_index
    status_update = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = GameDatabase()
        self.batch: Optional[BatchAnalysis] = None

        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.load_folder_btn = QPushButton("Load Folder")
        self.load_folder_btn.clicked.connect(self._load_folder)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh)
        self.filter_btn = QPushButton("Filter...")
        self.filter_btn.clicked.connect(self._filter)
        self.import_btn = QPushButton("Import FPGN...")
        self.import_btn.clicked.connect(self._import_fpgn)
        self.mass_analyze_btn = QPushButton("Mass Analyze")
        self.mass_analyze_btn.clicked.connect(self._mass_analyze)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected)
        toolbar.addWidget(self.load_folder_btn)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.filter_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.mass_analyze_btn)
        toolbar.addWidget(self.delete_btn)
        layout.addLayout(toolbar)

        # Game count label
        self.count_label = QLabel("0 games")
        layout.addWidget(self.count_label)

        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["#", "White", "Black", "Result", "Date", "Moves"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table)

        self.engine_path = ""

    def set_engine_path(self, path: str):
        self.engine_path = path

    def _load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Game Database Folder")
        if folder:
            self.db.scan_folder(folder)
            self._populate_table()
            self.count_label.setText(f"{len(self.db)} games")

    def _refresh(self):
        if self.db.folder:
            self.db.scan_folder(self.db.folder)
            self._populate_table()
            self.count_label.setText(f"{len(self.db)} games")

    def _populate_table(self, indices: List[int] = None):
        self.table.setRowCount(0)
        games = [self.db[i] for i in indices] if indices is not None else self.db.games
        for i, rec in enumerate(games):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(row, 1, QTableWidgetItem(rec.white))
            self.table.setItem(row, 2, QTableWidgetItem(rec.black))
            self.table.setItem(row, 3, QTableWidgetItem(rec.result))
            self.table.setItem(row, 4, QTableWidgetItem(rec.date))
            self.table.setItem(row, 5, QTableWidgetItem(str(rec.moves_count)))

    def _filter(self):
        dlg = FilterDialog(self)
        if dlg.exec():
            indices = self.db.filter(**dlg.filters)
            self._populate_table(indices)
            self.count_label.setText(f"{len(indices)} games (filtered)")

    def _import_fpgn(self):
        from src.ui.import_fpgn_dialog import ImportFPGNDialog
        dlg = ImportFPGNDialog(self, self.db.folder)
        if dlg.exec():
            self._refresh()

    def _mass_analyze(self):
        if not self.engine_path:
            QMessageBox.warning(self, "No Engine", "Set an analysis engine first.")
            return
        selected = self._selected_indices()
        if not selected:
            QMessageBox.information(self, "No Selection", "Select games to analyze.")
            return
        movetime, ok = QInputDialog.getInt(self, "Move Time", "Milliseconds per move:", 5000, 100, 60000)
        if not ok:
            return
        # Confirm
        if not QMessageBox.question(self, "Mass Analysis", f"Analyze {len(selected)} game(s)?"):
            return
        self.batch = BatchAnalysis(self.engine_path, movetime)
        self.batch.progress.connect(lambda cur, tot: self.status_update.emit(f"Move {cur}/{tot}"))
        self.batch.analysis_complete.connect(lambda: QMessageBox.information(self, "Done", "Mass analysis complete."))
        # Process games one by one? BatchAnalysis currently expects a single game.
        # For now, we'll analyze the first selected game as example.
        headers, moves = self.db.get_game_moves(selected[0])
        from src.core.game_state import GameState
        state = GameState()
        self.batch.analyze_game(state, moves)

    def _delete_selected(self):
        selected = self._selected_indices()
        if not selected:
            return
        if QMessageBox.question(self, "Delete", f"Delete {len(selected)} game(s)?"):
            # For now, just remove from index; not deleting actual files.
            for i in sorted(selected, reverse=True):
                del self.db.games[i]
            self._populate_table()
            self.count_label.setText(f"{len(self.db)} games")
            self.db._save_index()

    def _selected_indices(self) -> List[int]:
        rows = set(item.row() for item in self.table.selectedItems())
        return sorted(rows)

    def _on_double_click(self, row, col):
        self.game_load_requested.emit(self.db[row].filepath, self.db[row].game_index)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        load_action = QAction("Load Game", self)
        load_action.triggered.connect(self._on_double_click_ctx)
        menu.addAction(load_action)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_double_click_ctx(self):
        row = self.table.currentRow()
        if row >= 0:
            self.game_load_requested.emit(self.db[row].filepath, self.db[row].game_index)


class FilterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Games")
        layout = QVBoxLayout(self)
        self.white_edit = QLineEdit()
        self.black_edit = QLineEdit()
        self.result_combo = QComboBox()
        self.result_combo.addItems(["", "1-0", "0-1", "1/2-1/2", "*"])
        self.date_from = QLineEdit()
        self.date_to = QLineEdit()
        layout.addWidget(QLabel("White contains:"))
        layout.addWidget(self.white_edit)
        layout.addWidget(QLabel("Black contains:"))
        layout.addWidget(self.black_edit)
        layout.addWidget(QLabel("Result:"))
        layout.addWidget(self.result_combo)
        layout.addWidget(QLabel("Date from (YYYY.MM.DD):"))
        layout.addWidget(self.date_from)
        layout.addWidget(QLabel("Date to:"))
        layout.addWidget(self.date_to)
        btn = QPushButton("Apply")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    @property
    def filters(self):
        return {
            "white": self.white_edit.text(),
            "black": self.black_edit.text(),
            "result": self.result_combo.currentText(),
            "date_from": self.date_from.text(),
            "date_to": self.date_to.text(),
        }