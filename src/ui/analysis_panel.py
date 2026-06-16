from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from typing import Optional, Dict, List
import os
from src.engine.manager import EngineManager
from src.io.fen import board_to_fen
from src.core.pieces import Colour

class AnalysisPanel(QWidget):
    arrows_changed = Signal(list)
    markers_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        ctrl_layout = QHBoxLayout()
        self.engine_label = QLabel("Engine: none")
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.multipv_spin = QComboBox()
        self.multipv_spin.addItems(["1", "2", "3", "4"])
        self.multipv_spin.setCurrentIndex(0)
        ctrl_layout.addWidget(self.engine_label, 1)
        ctrl_layout.addWidget(QLabel("Lines:"))
        ctrl_layout.addWidget(self.multipv_spin)
        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.stop_btn)
        layout.addLayout(ctrl_layout)
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Move", "Score", "Depth", "PV"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.engine: Optional[EngineManager] = None
        self.current_fen: Optional[str] = None
        self.enabled = False
        self._current_pv_lines: List[dict] = []

        self.start_btn.clicked.connect(self.start_analysis)
        self.stop_btn.clicked.connect(self.stop_analysis)

    def set_engine_path(self, path: str):
        if self.engine:
            self.engine.close()
        self.engine = EngineManager(path)
        self.engine.info_received.connect(self._on_info)
        self.engine.error_occurred.connect(self._on_error)
        self.engine_label.setText(f"Engine: {os.path.basename(path)}")
        self.status_label.setText("")

    def start_analysis(self):
        if not self.engine or not self.current_fen:
            return
        self.engine.start()
        self.engine.set_multipv(int(self.multipv_spin.currentText()))

        def on_ready():
            self.engine.engine_ready.disconnect(on_ready)
            self.engine.set_position(self.current_fen, [])
            self.engine.go(infinite=True)
            self.status_label.setText("Thinking...")

        self.engine.engine_ready.connect(on_ready)
        self.enabled = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_analysis(self):
        if self.engine:
            self.engine.stop()
        self.enabled = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("")

    def set_position(self, fen: str):
        self.current_fen = fen
        if self.enabled and self.engine:
            self.engine.set_position(fen, [])
            self.status_label.setText("Thinking...")

    def _on_info(self, info: dict):
        self.status_label.setText("")
        pv_num = info.get("multipv", 1)
        found = False
        for i, line in enumerate(self._current_pv_lines):
            if line.get("multipv") == pv_num:
                self._current_pv_lines[i] = info
                found = True
                break
        if not found:
            self._current_pv_lines.append(info)
        self._current_pv_lines.sort(key=lambda x: x.get("multipv", 999))

        self.table.setRowCount(0)
        arrows = []
        markers = []
        for line in self._current_pv_lines:
            row = self.table.rowCount()
            self.table.insertRow(row)
            pv = line.get("pv", [])
            move_str = pv[0] if pv else "?"
            move_item = QTableWidgetItem(move_str)
            move_item.setFont(QFont("Arial", 10, QFont.Bold))
            if row == 0:
                from src.engine.protocol import uci_to_move
                from src.ui.board_widget import BoardArrow, BoardMarker
                move = uci_to_move(move_str)
                if move:
                    arrows.append(BoardArrow(move.from_r, move.from_c, move.to_r, move.to_c, QColor(0, 255, 0, 120)))
                    markers.append(BoardMarker(move.to_r, move.to_c, QColor(0, 255, 0, 150), corner="center"))
            self.table.setItem(row, 0, move_item)

            score_cp = line.get("score_cp")
            score_mate = line.get("score_mate")
            if score_mate is not None:
                score_str = f"Mate {score_mate}"
            elif score_cp is not None:
                score_str = f"{score_cp/100:.2f}"
            else:
                score_str = "?"
            self.table.setItem(row, 1, QTableWidgetItem(score_str))

            depth = line.get("depth", "?")
            self.table.setItem(row, 2, QTableWidgetItem(str(depth)))

            pv_str = " ".join(pv) if pv else ""
            self.table.setItem(row, 3, QTableWidgetItem(pv_str))

        if arrows:
            self.arrows_changed.emit(arrows)
        if markers:
            self.markers_changed.emit(markers)

    def _on_error(self, err: str):
        self.status_label.setText(f"Error: {err}")
        self.status_label.setStyleSheet("color: red;")

    def closeEvent(self, event):
        self.stop_analysis()
        if self.engine:
            self.engine.close()
        super().closeEvent(event)