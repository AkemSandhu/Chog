import sqlite3
from typing import List, Tuple, Optional
from chog.io.fen import board_to_fen
from chog.core.game_state import GameState
from chog.core.movegen import Move
from chog.engine.protocol import move_to_uci, uci_to_move

class BookDB:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS book (
                position_fen TEXT NOT NULL,
                move_uci TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                comment TEXT DEFAULT '',
                PRIMARY KEY (position_fen, move_uci)
            )
        """)
        self.conn.commit()

    def add_move(self, state: GameState, move: Move, weight: float = 1.0, comment: str = ""):
        fen = board_to_fen(state.board, state.turn)
        uci = move_to_uci(move)
        self.conn.execute(
            "INSERT OR REPLACE INTO book VALUES (?, ?, ?, ?)",
            (fen, uci, weight, comment)
        )
        self.conn.commit()

    def remove_move(self, state: GameState, move: Move):
        fen = board_to_fen(state.board, state.turn)
        uci = move_to_uci(move)
        self.conn.execute("DELETE FROM book WHERE position_fen=? AND move_uci=?", (fen, uci))
        self.conn.commit()

    def get_moves(self, state: GameState) -> List[Tuple[Move, float, str]]:
        """Return list of (Move, weight, comment) for current position."""
        fen = board_to_fen(state.board, state.turn)
        rows = self.conn.execute(
            "SELECT move_uci, weight, comment FROM book WHERE position_fen=?",
            (fen,)
        ).fetchall()
        moves = []
        for uci, weight, comment in rows:
            move = uci_to_move(uci)
            if move:
                moves.append((move, weight, comment))
        return moves

    def update_weight(self, state: GameState, move: Move, weight: float):
        fen = board_to_fen(state.board, state.turn)
        uci = move_to_uci(move)
        self.conn.execute("UPDATE book SET weight=? WHERE position_fen=? AND move_uci=?", (weight, fen, uci))
        self.conn.commit()

    def update_comment(self, state: GameState, move: Move, comment: str):
        fen = board_to_fen(state.board, state.turn)
        uci = move_to_uci(move)
        self.conn.execute("UPDATE book SET comment=? WHERE position_fen=? AND move_uci=?", (comment, fen, uci))
        self.conn.commit()

    def close(self):
        self.conn.close()