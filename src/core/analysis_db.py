import sqlite3
import os
from typing import List, Optional, Tuple
from src.engine.multi_response import MultiEngineResponse, EngineResponse
from src.io.fen import board_to_fen
from src.core.game_state import GameState

class AnalysisDB:
    """Stores engine analyses per position (keyed by FEN or PV)."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)  # ensure directory exists
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                fen TEXT NOT NULL,
                pv TEXT NOT NULL,               -- PV of the position leading to this FEN? We'll use FEN as primary.
                name TEXT DEFAULT '',
                movetime INTEGER DEFAULT 0,
                depth INTEGER DEFAULT 0,
                multipv INTEGER DEFAULT 1,
                data TEXT NOT NULL,              -- serialized MultiEngineResponse (pickle json)
                PRIMARY KEY (fen, pv, name)
            )
        """)
        self.conn.commit()

    def save_analysis(self, state: GameState, pv: str, mrm: MultiEngineResponse,
                      movetime: int = 0, depth: int = 0, multipv: int = 1):
        """Save an analysis for a position. `pv` is the move sequence leading to this position."""
        fen = board_to_fen(state.board, state.turn)
        import json, pickle, base64
        # Serialize mrm to base64
        data = base64.b64encode(pickle.dumps(mrm)).decode('ascii')
        self.conn.execute(
            "INSERT OR REPLACE INTO analyses(fen, pv, name, movetime, depth, multipv, data) "
            "VALUES(?, ?, ?, ?, ?, ?, ?)",
            (fen, pv, mrm.name, movetime, depth, multipv, data)
        )
        self.conn.commit()

    def load_analysis(self, state: GameState, pv: str, name: str = "") -> Optional[MultiEngineResponse]:
        fen = board_to_fen(state.board, state.turn)
        row = self.conn.execute(
            "SELECT data FROM analyses WHERE fen=? AND pv=? AND name=?",
            (fen, pv, name)
        ).fetchone()
        if row:
            import pickle, base64
            return pickle.loads(base64.b64decode(row[0]))
        return None

    def list_analyses_for_position(self, state: GameState) -> List[Tuple[str, str, int]]:
        """Return list of (pv, name, movetime) for the current position."""
        fen = board_to_fen(state.board, state.turn)
        rows = self.conn.execute(
            "SELECT pv, name, movetime FROM analyses WHERE fen=?",
            (fen,)
        ).fetchall()
        return rows

    def remove_analysis(self, state: GameState, pv: str, name: str):
        fen = board_to_fen(state.board, state.turn)
        self.conn.execute(
            "DELETE FROM analyses WHERE fen=? AND pv=? AND name=?",
            (fen, pv, name)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()