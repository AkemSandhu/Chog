from PySide6.QtWidgets import (QMessageBox, QDialog, QVBoxLayout, QLabel,
                               QPushButton, QProgressBar, QApplication)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QFont

class WaitingOverlay(QDialog):
    """Semi‑transparent overlay that blocks the parent and shows a message.

    Usage:
        overlay = WaitingOverlay(parent, "Analyzing...")
        overlay.show()
        ...
        overlay.hide()
    or as a context manager:
        with WaitingOverlay(parent, "Working...", cancel_callback=stop) as w:
            ...
    """

    def __init__(self, parent, message: str = "Please wait...",
                 cancel_callback=None, show_progress=False,
                 opacity=0.8):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self.cancel_callback = cancel_callback

        self._parent = parent

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel(message, self)
        self.label.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        if show_progress:
            self.progress = QProgressBar(self)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setTextVisible(False)
            self.progress.setStyleSheet(
                "QProgressBar { background: #333; border: 1px solid #888; }"
                "QProgressBar::chunk { background: #4caf50; }"
            )
            layout.addWidget(self.progress)
        else:
            self.progress = None

        if cancel_callback:
            self.cancel_btn = QPushButton("Cancel", self)
            self.cancel_btn.clicked.connect(self._on_cancel)
            self.cancel_btn.setStyleSheet(
                "QPushButton { background: #d9534f; color: white; border-radius: 4px; }"
            )
            layout.addWidget(self.cancel_btn)

        self.setStyleSheet("background: rgba(0,0,0,180);")
        self._cancelled = False

    def set_message(self, text: str):
        self.label.setText(text)
        QApplication.processEvents()

    def set_progress(self, value: int):
        if self.progress:
            self.progress.setValue(value)
            QApplication.processEvents()

    def _on_cancel(self):
        self._cancelled = True
        if self.cancel_callback:
            self.cancel_callback()

    def is_cancelled(self) -> bool:
        return self._cancelled

    def showEvent(self, event):
        super().showEvent(event)
        if self._parent:
            self.setGeometry(self._parent.geometry())

    def __enter__(self):
        self.show()
        QApplication.processEvents()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.hide()
        self.close()


def info_message(parent, title: str, text: str):
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.exec()


def error_message(parent, title: str, text: str):
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.exec()


def question_dialog(parent, title: str, text: str, yes_text="Yes", no_text="No") -> bool:
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle(title)
    msg.setText(text)
    yes_btn = msg.addButton(yes_text, QMessageBox.YesRole)
    no_btn = msg.addButton(no_text, QMessageBox.NoRole)
    msg.exec()
    return msg.clickedButton() == yes_btn


def temporary_message(parent, text: str, duration_ms: int = 2000):
    """Show a small temporary popup at the top‑right of the parent."""
    label = QLabel(text, parent)
    label.setWindowFlags(Qt.FramelessWindowHint | Qt.ToolTip)
    label.setStyleSheet(
        "background: #333; color: white; padding: 8px 16px; border-radius: 6px; font-size: 14px;"
    )
    label.adjustSize()
    if parent:
        p_geom = parent.geometry()
        x = p_geom.right() - label.width() - 20
        y = p_geom.top() + 20
        label.move(parent.mapToGlobal(QPoint(x, y)))
    label.show()
    QTimer.singleShot(duration_ms, label.close)