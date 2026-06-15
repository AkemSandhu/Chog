from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class ImportProgressDialog(QDialog):
    def __init__(self, parent, title="Importing", show_errors=True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self._cancelled = False
        self._paused = False

        layout = QVBoxLayout(self)
        font = QFont()
        font.setPointSize(10)

        self.lb_read = QLabel("Games read: 0")
        self.lb_read.setFont(font)
        layout.addWidget(self.lb_read)

        if show_errors:
            self.lb_errors = QLabel("Erroneous: 0")
            self.lb_errors.setFont(font)
            layout.addWidget(self.lb_errors)

        self.lb_duplicates = QLabel("Duplicated: 0")
        self.lb_duplicates.setFont(font)
        layout.addWidget(self.lb_duplicates)

        self.lb_imported = QLabel("Imported: 0")
        self.lb_imported.setFont(font)
        layout.addWidget(self.lb_imported)

        self.lb_work = QLabel("Work done: 0%")
        self.lb_work.setFont(font)
        layout.addWidget(self.lb_work)

        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_continue = QPushButton("Continue")
        self.btn_continue.clicked.connect(self.accept)
        self.btn_continue.setVisible(False)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_continue)
        layout.addLayout(btn_layout)

    def update_stats(self, read: int, errors: int, duplicates: int, imported: int, work_pct: float = 0):
        self.lb_read.setText(f"Games read: {read}")
        if hasattr(self, 'lb_errors'):
            self.lb_errors.setText(f"Erroneous: {errors}")
        self.lb_duplicates.setText(f"Duplicated: {duplicates}")
        self.lb_imported.setText(f"Imported: {imported}")
        self.lb_work.setText(f"Work done: {work_pct:.0f}%")

    def finish(self):
        self.btn_cancel.setVisible(False)
        self.btn_continue.setVisible(True)

    def _cancel(self):
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled