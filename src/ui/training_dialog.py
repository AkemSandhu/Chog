from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QCheckBox, QPushButton, QPlainTextEdit, QFormLayout, QDialogButtonBox
)
from PySide6.QtCore import Qt, QTimer
from src.engine.training_manager import TrainingManager

class TrainingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Self‑Learning Training")
        self.training_manager: TrainingManager = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.engine1_edit = QLineEdit()
        self.engine1_edit.setPlaceholderText("Path to white/engine1")
        form.addRow("Engine 1:", self.engine1_edit)

        self.engine2_edit = QLineEdit()
        self.engine2_edit.setPlaceholderText("Path to black/engine2 (can be same)")
        form.addRow("Engine 2:", self.engine2_edit)

        self.games_spin = QSpinBox()
        self.games_spin.setRange(1, 100000)
        self.games_spin.setValue(100)
        form.addRow("Number of games:", self.games_spin)

        self.movetime_spin = QSpinBox()
        self.movetime_spin.setRange(100, 60000)
        self.movetime_spin.setValue(5000)
        self.movetime_spin.setSuffix(" ms")
        form.addRow("Move time:", self.movetime_spin)

        self.save_interval_spin = QSpinBox()
        self.save_interval_spin.setRange(1, 1000)
        self.save_interval_spin.setValue(10)
        form.addRow("Save weights every N games:", self.save_interval_spin)

        self.weights1_edit = QLineEdit("weights_engine1.nn")
        form.addRow("Weights file engine 1:", self.weights1_edit)

        self.weights2_edit = QLineEdit("weights_engine2.nn")
        form.addRow("Weights file engine 2:", self.weights2_edit)

        self.learn_check = QCheckBox("Enable learning")
        self.learn_check.setChecked(True)
        form.addRow(self.learn_check)

        layout.addLayout(form)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Training")
        self.start_btn.clicked.connect(self.start_training)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_training)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

    def start_training(self):
        path1 = self.engine1_edit.text().strip()
        path2 = self.engine2_edit.text().strip()
        if not path1 or not path2:
            self.log.appendPlainText("Both engine paths are required.")
            return

        self.training_manager = TrainingManager(
            engine1_path=path1,
            engine2_path=path2,
            num_games=self.games_spin.value(),
            movetime=self.movetime_spin.value(),
            save_interval=self.save_interval_spin.value(),
            weights_file1=self.weights1_edit.text(),
            weights_file2=self.weights2_edit.text(),
            learn_enabled=self.learn_check.isChecked()
        )
        self.training_manager.status_update.connect(self.log.appendPlainText)
        self.training_manager.game_completed.connect(self._on_game_done)
        self.training_manager.training_finished.connect(self._on_finished)
        self.training_manager.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_training(self):
        if self.training_manager:
            self.training_manager.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_game_done(self, game_num, result):
        self.log.appendPlainText(f"Game {game_num+1}: {result['result']} ({result['reason']})")

    def _on_finished(self, stats):
        self.log.appendPlainText(f"Training finished. Summary: {stats}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)