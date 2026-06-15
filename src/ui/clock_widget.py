from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLCDNumber
from PySide6.QtCore import QTimer, Signal

class ClockWidget(QWidget):
    timeout = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.label = QLabel("Player")
        self.lcd = QLCDNumber()
        self.lcd.setDigitCount(5)
        self.lcd.display("10:00")
        layout.addWidget(self.label)
        layout.addWidget(self.lcd)

        # Captured pieces display
        self.captured_label = QLabel("")
        self.captured_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.captured_label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.time_left_ms = 600_000
        self.increment_ms = 0
        self.running = False
        self._update_display()

    def set_time(self, seconds: int, increment: int = 0):
        self.time_left_ms = seconds * 1000
        self.increment_ms = increment * 1000
        self._update_display()

    def start(self):
        if not self.running and self.time_left_ms > 0:
            self.timer.start(100)
            self.running = True

    def stop(self):
        self.timer.stop()
        self.running = False

    def add_increment(self):
        self.time_left_ms += self.increment_ms
        self._update_display()

    def reset(self):
        self.stop()
        self._update_display()

    def set_captured(self, text: str):
        self.captured_label.setText(text)

    def _tick(self):
        if self.time_left_ms > 0:
            self.time_left_ms -= 100
            self._update_display()
        if self.time_left_ms <= 0:
            self.time_left_ms = 0
            self._update_display()
            self.stop()
            self.timeout.emit()

    def _update_display(self):
        total_seconds = self.time_left_ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        self.lcd.display(f"{minutes:02}:{seconds:02}")