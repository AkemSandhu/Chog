from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton
from PySide6.QtCore import Qt, Signal
from typing import Optional, Dict
from chog.engine.manager import EngineManager
from chog.engine.protocol import parse_info_line
from chog.core.game_state import GameState

class AnalysisPanel(QWidget):
    """Shows real-time engine analysis for the current position."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.engine_label = QLabel("Analysis Engine: none")
        layout.addWidget(self.engine_label)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(100)
        layout.addWidget(self.info_text)

        self.start_btn = QPushButton("Start Analysis")
        self.stop_btn = QPushButton("Stop Analysis")
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)

        self.analysis_engine: Optional[EngineManager] = None
        self.current_fen: Optional[str] = None
        self.enabled = False

        self.start_btn.clicked.connect(self.start_analysis)
        self.stop_btn.clicked.connect(self.stop_analysis)

    def set_engine(self, engine_path: str):
        """Set the engine used for analysis (creates a dedicated EngineManager)."""
        if self.analysis_engine:
            self.analysis_engine.stop()
        self.analysis_engine = EngineManager(engine_path)
        self.analysis_engine.info_received.connect(self._on_info)
        self.analysis_engine.error_occurred.connect(self._on_error)
        self.analysis_engine.bestmove_received.connect(self._on_bestmove)
        self.engine_label.setText(f"Analysis Engine: {engine_path}")

    def start_analysis(self):
        if not self.analysis_engine or not self.current_fen:
            return
        self.analysis_engine.start()
        self.analysis_engine.send_command(f"position fen {self.current_fen}")
        self.analysis_engine.send_command("go infinite")
        self.enabled = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def stop_analysis(self):
        if self.analysis_engine:
            self.analysis_engine.send_command("stop")
        self.enabled = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def set_position(self, fen: str):
        """Update the position to analyse."""
        self.current_fen = fen
        if self.enabled and self.analysis_engine:
            self.analysis_engine.send_command(f"position fen {fen}")
            # No need to restart 'go infinite' – engine continues searching from new position

    def _on_info(self, info: dict):
        """Format and display the principal variation."""
        depth = info.get("depth", "?")
        score_cp = info.get("score_cp")
        score_mate = info.get("score_mate")
        pv_moves = info.get("pv", [])

        if score_mate is not None:
            score_str = f"mate {score_mate}"
        elif score_cp is not None:
            score_str = f"{score_cp/100:.2f}"
        else:
            score_str = "?"

        pv_str = " ".join(pv_moves[:10]) if pv_moves else ""
        self.info_text.setText(f"depth {depth}  score {score_str}  pv {pv_str}")

    def _on_bestmove(self, move):
        # Not used in analysis mode
        pass

    def _on_error(self, err: str):
        self.info_text.append(f"Error: {err}")

    def closeEvent(self, event):
        self.stop_analysis()
        super().closeEvent(event)