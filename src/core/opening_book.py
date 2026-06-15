import sqlite3
import os
from typing import List, Dict, Tuple, Optional
from src.core.movegen import Move
from src.core.game_state import GameState
from src.core.pieces import PieceType, Colour
from src.io.fen import board_to_fen
from src.engine.protocol import move_to_uci, uci_to_move

class LineNode:
    """A node in the opening tree."""
    def __init__(self, move: Optional[Move] = None, parent=None):
        self.move = move          # Move object (None for root)
        self.parent = parent
        self.children: Dict[str, LineNode] = {}   # key = move string (e.g. "e2e3")
        self.comment = ""
        self.annotations = {}     # additional per‑position data

    def add_line(self, moves: List[Move]):
        """Add a sequence of moves to the tree."""
        node = self
        for m in moves:
            key = move_to_uci(m)
            if key not in node.children:
                node.children[key] = LineNode(m, node)
            node = node.children[key]
        return node

    def pgn_line(self) -> str:
        """Return the full move sequence from root to this node as a PGN string."""
        moves = []
        node = self
        while node.parent is not None:
            moves.append(node.move)
            node = node.parent
        moves.reverse()
        # Build a simple PGN line (just moves separated by spaces)
        return " ".join(move_to_uci(m) for m in moves)


class OpeningBook:
    """Manages an opening book with lines, config, and annotations.

    The SQLite database contains three tables:
      - LINES: stores complete variations (XPV compressed move strings)
      - CONFIG: key‑value metadata
      - ANNOTATIONS: per‑FEN comments, evaluations, etc.
    """

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                xpv TEXT NOT NULL UNIQUE   -- compressed move string (space‑separated move codes)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                fen TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                PRIMARY KEY (fen, key)
            )
        """)
        self.conn.commit()

    # -----------------------------------------------------------------
    # Config
    # -----------------------------------------------------------------
    def get_config(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_config(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO config(key, value) VALUES(?, ?)", (key, value)
        )
        self.conn.commit()

    @property
    def title(self):
        return self.get_config("title", os.path.basename(self.db_path))

    @title.setter
    def title(self, value: str):
        self.set_config("title", value)

    # -----------------------------------------------------------------
    # Lines
    # -----------------------------------------------------------------
    def add_line(self, moves: List[Move]):
        """Insert a new variation (list of Move objects). If a shorter
        existing line is a prefix of the new one, it is replaced.
        If a longer existing line starts with this one, we keep both.
        """
        new_xpv = " ".join(move_to_uci(m) for m in moves)
        existing = self.get_all_lines()
        # Check for exact duplicate
        if new_xpv in existing:
            return
        # Remove any line that is a strict prefix of the new one
        to_remove = []
        for xpv in existing:
            if new_xpv.startswith(xpv + " ") or new_xpv == xpv:
                # existing is a prefix of new -> remove existing (new is longer)
                # but only if new is longer (strict prefix) -> xpv < new_xpv
                if len(new_xpv) > len(xpv):
                    to_remove.append(xpv)
            elif xpv.startswith(new_xpv + " ") or xpv == new_xpv:
                # new is a prefix of existing -> keep both? In LucasChess, if new is prefix, it doesn't replace.
                # Actually in the reference: if new starts with existing, existing is removed.
                # But if existing starts with new, we keep both? Let's do: if a line exists that is a prefix of the new one, remove it (new is more precise). If a line exists that is an extension, keep both.
                pass
        for old_xpv in to_remove:
            self.remove_line_by_xpv(old_xpv)
        # Insert new line
        self.conn.execute("INSERT INTO lines(xpv) VALUES(?)", (new_xpv,))
        self.conn.commit()

    def remove_line_by_xpv(self, xpv: str):
        self.conn.execute("DELETE FROM lines WHERE xpv=?", (xpv,))
        self.conn.commit()

    def get_all_lines(self) -> List[str]:
        """Return list of all stored XPV strings."""
        rows = self.conn.execute("SELECT xpv FROM lines ORDER BY xpv").fetchall()
        return [r[0] for r in rows]

    def get_line_moves(self, xpv: str) -> List[Move]:
        """Convert an XPV string back to a list of Move objects."""
        moves = []
        for token in xpv.split():
            m = uci_to_move(token)
            if m:
                moves.append(m)
        return moves

    def get_line_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM lines").fetchone()[0]

    # -----------------------------------------------------------------
    # Annotations
    # -----------------------------------------------------------------
    def get_annotation(self, fen: str, key: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM annotations WHERE fen=? AND key=?", (fen, key)
        ).fetchone()
        return row[0] if row else None

    def set_annotation(self, fen: str, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO annotations(fen, key, value) VALUES(?, ?, ?)",
            (fen, key, value)
        )
        self.conn.commit()

    def remove_annotation(self, fen: str, key: str):
        self.conn.execute(
            "DELETE FROM annotations WHERE fen=? AND key=?", (fen, key)
        )
        self.conn.commit()

    def get_all_annotations_for_fen(self, fen: str) -> Dict[str, str]:
        rows = self.conn.execute(
            "SELECT key, value FROM annotations WHERE fen=?", (fen,)
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    # -----------------------------------------------------------------
    # Tree builder
    # -----------------------------------------------------------------
    def build_tree(self) -> LineNode:
        """Build a tree from all stored lines."""
        root = LineNode()
        for xpv in self.get_all_lines():
            moves = self.get_line_moves(xpv)
            root.add_line(moves)
        return root

    # -----------------------------------------------------------------
    # PGN Import
    # -----------------------------------------------------------------
    def import_from_fpgn(self, filepath: str, max_depth: int = 100,
                         min_moves: int = 0, base_pv: str = ""):
        """Import all variations from an FPGN file.

        Args:
            filepath: Path to .fpgn file.
            max_depth: Maximum number of moves to import per line.
            min_moves: Minimum number of moves a line must have.
            base_pv: If provided, only import lines starting with this PV (space‑separated moves).
        """
        from src.io.fpgn import FPGNReader
        games = FPGNReader.read_file(filepath)
        total_imported = 0
        for headers, moves in games:
            # We'll need to reconstruct the game to get variations? Our FPGN currently only stores main line moves.
            # For variations, we would need to extend the reader. For now, import the main line.
            if not moves:
                continue
            # Filter by base_pv
            line_moves = moves[:max_depth]
            if len(line_moves) < min_moves:
                continue
            # Convert moves to strings
            pv_str = " ".join(move_to_uci(m) for m in line_moves)
            if base_pv and not pv_str.startswith(base_pv):
                continue
            # Insert into book
            self.add_line(line_moves)  # add_line handles deduplication
            total_imported += 1
        return total_imported

    def close(self):
        self.conn.close()