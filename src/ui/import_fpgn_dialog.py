from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QCheckBox, QGroupBox, QFileDialog, QMessageBox,
    QComboBox, QProgressBar
)
from PySide6.QtCore import Qt
from src.core.game_database import GameDatabase
from src.io.fpgn import FPGNReader
import os

class ImportFPGNDialog(QDialog):
    def __init__(self, parent=None, target_folder: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Import FPGN Files")
        self.target_folder = target_folder
        self.files = []
        self.filter_func = None

        layout = QVBoxLayout(self)

        # Source
        src_group = QGroupBox("Source")
        src_layout = QHBoxLayout(src_group)
        self.files_label = QLabel("No files selected")
        btn_select = QPushButton("Select Files...")
        btn_select.clicked.connect(self._select_files)
        src_layout.addWidget(btn_select)
        src_layout.addWidget(self.files_label, 1)
        layout.addWidget(src_group)

        # Filter options
        flt_group = QGroupBox("Filter (optional)")
        flt_layout = QVBoxLayout(flt_group)
        self.white_edit = QLineEdit()
        self.white_edit.setPlaceholderText("White contains...")
        self.black_edit = QLineEdit()
        self.black_edit.setPlaceholderText("Black contains...")
        self.result_combo = QComboBox()
        self.result_combo.addItems(["Any", "1-0", "0-1", "1/2-1/2", "*"])
        flt_layout.addWidget(QLabel("White:"))
        flt_layout.addWidget(self.white_edit)
        flt_layout.addWidget(QLabel("Black:"))
        flt_layout.addWidget(self.black_edit)
        flt_layout.addWidget(QLabel("Result:"))
        flt_layout.addWidget(self.result_combo)
        layout.addWidget(flt_group)

        # Remove options
        rem_group = QGroupBox("Remove elements")
        rem_layout = QVBoxLayout(rem_group)
        self.rem_variations = QCheckBox("Variations")
        self.rem_comments = QCheckBox("Comments")
        self.rem_nags = QCheckBox("NAGs")
        self.rem_analysis = QCheckBox("Engine analysis")
        rem_layout.addWidget(self.rem_variations)
        rem_layout.addWidget(self.rem_comments)
        rem_layout.addWidget(self.rem_nags)
        rem_layout.addWidget(self.rem_analysis)
        layout.addWidget(rem_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_import = QPushButton("Import")
        btn_import.clicked.connect(self._do_import)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_import)
        layout.addLayout(btn_layout)

    def _select_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select FPGN Files", "",
                                                "FPGN Files (*.fpgn);;All Files (*)")
        if files:
            self.files = files
            self.files_label.setText(f"{len(files)} file(s) selected")

    def _do_import(self):
        if not self.files:
            QMessageBox.warning(self, "No Files", "Select files to import.")
            return
        # Build filter function
        white = self.white_edit.text().strip()
        black = self.black_edit.text().strip()
        result = self.result_combo.currentText() if self.result_combo.currentText() != "Any" else ""

        def filter_func(headers):
            if white and white.lower() not in headers.get("White", "").lower():
                return False
            if black and black.lower() not in headers.get("Black", "").lower():
                return False
            if result and headers.get("Result", "*") != result:
                return False
            return True

        # Import into target folder (simplified: copy files)
        if self.target_folder:
            os.makedirs(self.target_folder, exist_ok=True)
            import shutil
            for f in self.files:
                dest = os.path.join(self.target_folder, os.path.basename(f))
                shutil.copy(f, dest)
        QMessageBox.information(self, "Done", f"Imported {len(self.files)} file(s).")
        self.accept()