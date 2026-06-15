from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QMessageBox, QFileDialog, QInputDialog,
    QLabel
)
from PySide6.QtCore import Qt, Signal
from typing import Optional, List

from src.core.opening_book import OpeningBook, LineNode
from src.core.movegen import Move
from src.core.game_state import GameState
from src.engine.protocol import move_to_uci, uci_to_move
from src.books.chog_book import ChogBook
from src.io.fen import board_to_fen
from src.books.book_engine import BookEngineHelper


class BookEditorWidget(QWidget):
    """Tree‑based opening book editor.

    Displays stored lines as a tree. Each node shows the move and can be expanded.
    """

    move_selected = Signal(Move)  # emitted when user clicks a node

    def __init__(self, parent=None):
        super().__init__(parent)
        self.book: Optional[OpeningBook] = None
        self.chog_book: Optional[ChogBook] = None
        self.current_state: Optional[GameState] = None
        self.current_move_history: List[Move] = []
        self.legal_moves: List[Move] = []
        self.engine_helper: Optional[BookEngineHelper] = None
        self.engine_path: Optional[str] = None

        layout = QVBoxLayout(self)

        # --- Toolbar ---
        toolbar = QHBoxLayout()
        self.load_btn = QPushButton("Load Book...")
        self.load_btn.clicked.connect(self._load_book)
        self.save_btn = QPushButton("Save Book As...")
        self.save_btn.clicked.connect(self._save_book)
        self.save_btn.setEnabled(False)
        self.import_btn = QPushButton("Import FPGN...")
        self.import_btn.clicked.connect(self._import_fpgn)
        self.import_btn.setEnabled(False)
        self.export_chb_btn = QPushButton("Export CHB...")
        self.export_chb_btn.clicked.connect(self._export_chb)
        self.export_chb_btn.setEnabled(False)
        self.suggest_btn = QPushButton("Suggest Moves")
        self.suggest_btn.clicked.connect(self._suggest_moves)
        self.suggest_btn.setEnabled(False)
        self.autocomplete_btn = QPushButton("Auto‑complete Line")
        self.autocomplete_btn.clicked.connect(self._autocomplete_line)
        self.autocomplete_btn.setEnabled(False)

        self.title_label = QLabel("No book loaded")
        toolbar.addWidget(self.load_btn)
        toolbar.addWidget(self.save_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.export_chb_btn)
        toolbar.addWidget(self.suggest_btn)
        toolbar.addWidget(self.autocomplete_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.title_label)
        layout.addLayout(toolbar)

        # --- Tree ---
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Move", "Comment"])
        self.tree.setColumnWidth(0, 150)
        self.tree.setSelectionBehavior(QTreeWidget.SelectRows)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        # --- Bottom buttons ---
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Current Line")
        self.add_btn.clicked.connect(self._add_current_line)
        self.add_btn.setEnabled(False)
        self.delete_btn = QPushButton("Delete Selected Line")
        self.delete_btn.clicked.connect(self._delete_selected_line)
        self.delete_btn.setEnabled(False)
        self.rename_btn = QPushButton("Rename Book")
        self.rename_btn.clicked.connect(self._rename_book)
        self.rename_btn.setEnabled(False)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.rename_btn)
        layout.addLayout(btn_layout)

    def set_engine_path(self, path: str):
        self.engine_path = path
        self.suggest_btn.setEnabled(bool(path) and self.current_state is not None)
        self.autocomplete_btn.setEnabled(bool(path) and self.current_state is not None)

    def set_position(self, state: GameState, legal_moves: List[Move], move_history: List[Move] = None):
        self.current_state = state
        self.legal_moves = legal_moves
        self.current_move_history = move_history or []
        self.add_btn.setEnabled(self.book is not None and len(self.current_move_history) > 0)
        self.suggest_btn.setEnabled(self.engine_path is not None and self.book is not None)
        self.autocomplete_btn.setEnabled(self.engine_path is not None and self.book is not None)

    # ---- Book file actions ----
    def _load_book(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Book Database", "",
                                              "Chog Books (*.chb *.db);;All Files (*)")
        if not path:
            return
        self.load_book_path(path)

    def load_book_path(self, path: str):
        """Load a book directly from a file path."""
        if self.book:
            self.book.close()
        if path.endswith('.db'):
            self.book = OpeningBook(path)
        else:
            QMessageBox.information(self, "Binary Book", "Editing of .chb files is not yet supported.")
            return
        self.save_btn.setEnabled(True)
        self.import_btn.setEnabled(True)
        self.export_chb_btn.setEnabled(True)
        self.rename_btn.setEnabled(True)
        self.title_label.setText(self.book.title)
        self._refresh_tree()

    def _save_book(self):
        QMessageBox.information(self, "Book", "Changes are saved automatically.")

    def _rename_book(self):
        if not self.book:
            return
        new_title, ok = QInputDialog.getText(self, "Rename Book", "New title:",
                                              text=self.book.title)
        if ok and new_title:
            self.book.title = new_title
            self.title_label.setText(new_title)

    # ---- Import / Export ----
    def _import_fpgn(self):
        if not self.book:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open FPGN File", "",
                                              "FPGN Files (*.fpgn);;All Files (*)")
        if not path:
            return
        max_depth, ok = QInputDialog.getInt(self, "Max Depth", "Max moves per line:", 100, 1, 1000)
        if not ok:
            return
        count = self.book.import_from_fpgn(path, max_depth)
        QMessageBox.information(self, "Import", f"Imported {count} lines.")
        self._refresh_tree()

    def _export_chb(self):
        if not self.book:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Chog Binary Book", "",
                                              "Chog Book (*.chb);;All Files (*)")
        if not path:
            return
        chb = ChogBook(path)
        from src.core.game_state import GameState
        for xpv in self.book.get_all_lines():
            state = GameState()
            moves = self.book.get_line_moves(xpv)
            for move in moves:
                chb.add_entry(state.board, move, weight=10)
                state.make_move(move)
        QMessageBox.information(self, "Export", "Binary book exported successfully.")

    # ---- Engine suggestions / autocomplete ----
    def _init_engine_helper(self):
        if not self.engine_path:
            QMessageBox.warning(self, "Engine Required", "Please set an engine path first.")
            return None
        if not self.engine_helper:
            self.engine_helper = BookEngineHelper(self.engine_path)
            self.engine_helper.suggestions_ready.connect(self._on_suggestions_ready)
            self.engine_helper.autocomplete_done.connect(self._on_autocomplete_done)
        return self.engine_helper

    def _suggest_moves(self):
        helper = self._init_engine_helper()
        if not helper or not self.current_state:
            return
        self.suggest_btn.setEnabled(False)
        helper.suggest_moves(self.current_state, multipv=3)

    def _autocomplete_line(self):
        helper = self._init_engine_helper()
        if not helper or not self.current_state:
            return
        self.autocomplete_btn.setEnabled(False)
        state_copy = GameState()
        state_copy.board = self.current_state.board.copy()
        state_copy.turn = self.current_state.turn
        helper.autocomplete_line(state_copy, max_depth=20)

    def _on_suggestions_ready(self, moves_weights: list):
        self.suggest_btn.setEnabled(True)
        if not self.book:
            return
        for move, weight in moves_weights:
            self.book.add_line([move])
        self._refresh_tree()
        QMessageBox.information(self, "Suggestions", f"Added {len(moves_weights)} suggested moves.")

    def _on_autocomplete_done(self, moves: List[Move]):
        self.autocomplete_btn.setEnabled(True)
        if not self.book or not moves:
            return
        self.book.add_line(moves)
        self._refresh_tree()
        QMessageBox.information(self, "Autocomplete", f"Added a new line with {len(moves)} moves.")

    # ---- Tree management ----
    def _refresh_tree(self):
        self.tree.clear()
        if not self.book:
            return
        root = self.book.build_tree()
        self._populate_tree(self.tree.invisibleRootItem(), root)

    def _populate_tree(self, parent_item: QTreeWidgetItem, node: LineNode):
        for key, child in node.children.items():
            text = move_to_uci(child.move) if child.move else "start"
            item = QTreeWidgetItem(parent_item, [text, child.comment])
            item.setData(0, Qt.UserRole, key)
            self._populate_tree(item, child)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        move_str = item.data(0, Qt.UserRole)
        if move_str:
            move = uci_to_move(move_str)
            if move:
                self.move_selected.emit(move)

    # ---- Add / delete lines ----
    def _add_current_line(self):
        if not self.book or not self.current_move_history:
            return
        self.book.add_line(self.current_move_history)
        self._refresh_tree()

    def _delete_selected_line(self):
        selected = self.tree.selectedItems()
        if not selected:
            return
        item = selected[0]
        moves = []
        it = item
        while it.parent() is not None:
            key = it.data(0, Qt.UserRole)
            if key:
                move = uci_to_move(key)
                if move:
                    moves.append(move)
            it = it.parent()
        moves.reverse()
        if not moves:
            return
        xpv = " ".join(move_to_uci(m) for m in moves)
        self.book.remove_line_by_xpv(xpv)
        self._refresh_tree()

    def closeEvent(self, event):
        if self.engine_helper:
            self.engine_helper.close()
        if self.book:
            self.book.close()
        super().closeEvent(event)