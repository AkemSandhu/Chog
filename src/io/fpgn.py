# io/fpgn.py
from __future__ import annotations
import re
from typing import List, Dict, Tuple, Optional, TextIO
from pieces import PieceType, PIECE_SYMBOLS
from movegen import Move

# Column letters mapping: a=0, b=1, ..., j=9
def _col_from_char(c: str) -> int:
    return ord(c) - ord('a')

def _col_to_char(c: int) -> str:
    return chr(ord('a') + c)

def move_to_fpgn(move: Move, moved_piece_type: PieceType) -> str:
    """
    Convert a Move object to FPGN long algebraic notation.
    - Always uses from/to squares (e.g., e2e3).
    - Only pawn promotions add '=' and the promoted piece symbol.
    - Other promotions are ignored.
    """
    base = f"{_col_to_char(move.from_c)}{move.from_r}{_col_to_char(move.to_c)}{move.to_r}"
    if moved_piece_type == PieceType.PAWN and move.promotion is not None:
        base += f"={PIECE_SYMBOLS[move.promotion]}"
    return base

def fpgn_to_move(fpgn_str: str) -> Move:
    """
    Parse a move string like "e2e3" or "e7e8=U".
    Returns a Move with promotion set if the symbol is a valid promotion target (for any piece).
    """
    fpgn_str = fpgn_str.strip()
    # Remove check/mate markers, comments (simple handling)
    fpgn_str = re.sub(r'[+#]', '', fpgn_str)
    # Extract squares and optional promotion
    match = re.match(r'([a-j])(\d)([a-j])(\d)(?:=(\w+))?', fpgn_str)
    if not match:
        raise ValueError(f"Invalid move format: {fpgn_str}")
    fc, fr, tc, tr = match.group(1), match.group(2), match.group(3), match.group(4)
    promo_str = match.group(5)
    from_c = _col_from_char(fc)
    from_r = int(fr)
    to_c = _col_from_char(tc)
    to_r = int(tr)
    promotion = None
    if promo_str:
        # Look up piece type from symbol (uppercase)
        symbol = promo_str.upper()
        for pt, sym in PIECE_SYMBOLS.items():
            if sym == symbol:
                promotion = pt
                break
    return Move(from_r, from_c, to_r, to_c, promotion)


class FPGNReader:
    """Reads .fpgn files containing one or more games."""

    @staticmethod
    def read_file(filepath: str) -> List[Tuple[Dict[str, str], List[Move]]]:
        """
        Returns a list of (headers, moves) for each game in the file.
        headers: dict of tag pairs (e.g., {"Event": "Casual Game", ...})
        moves: list of Move objects
        """
        games = []
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Split into games by blank line(s)
        raw_games = re.split(r'\n\s*\n', content.strip())
        for raw_game in raw_games:
            if not raw_game.strip():
                continue
            headers, move_text = FPGNReader._parse_game(raw_game)
            moves = FPGNReader._parse_moves(move_text)
            games.append((headers, moves))
        return games

    @staticmethod
    def _parse_game(text: str) -> Tuple[Dict[str, str], str]:
        headers = {}
        lines = text.split('\n')
        i = 0
        # Parse header tags
        while i < len(lines) and lines[i].strip().startswith('['):
            line = lines[i].strip()
            match = re.match(r'\[(\w+)\s+"(.*)"\]', line)
            if match:
                headers[match.group(1)] = match.group(2)
            i += 1
        # Remaining lines are move text (possibly with comments)
        move_text = " ".join(lines[i:])
        return headers, move_text

    @staticmethod
    def _parse_moves(move_text: str) -> List[Move]:
        # Remove comments in braces
        move_text = re.sub(r'\{.*?\}', '', move_text)
        # Remove move numbers (e.g., "1." "2...") and game result
        move_text = re.sub(r'\d+\.\.?', '', move_text)
        move_text = re.sub(r'1-0|0-1|1/2-1/2|\*', '', move_text)
        # Split into tokens
        tokens = move_text.split()
        moves = []
        for token in tokens:
            if re.match(r'[a-j]\d[a-j]\d', token):
                moves.append(fpgn_to_move(token))
        return moves


class FPGNWriter:
    """Writes a game incrementally to a .fpgn file."""

    def __init__(self, filepath: str, headers: Dict[str, str]):
        self.file = open(filepath, 'w', encoding='utf-8')
        self.move_number = 1
        self.pending_white = None  # store white's move until black's move is known (for move numbers)
        self._write_headers(headers)

    def _write_headers(self, headers: Dict[str, str]):
        for key, value in headers.items():
            self.file.write(f'[{key} "{value}"]\n')
        self.file.write('\n')  # blank line after headers

    def add_move(self, move: Move, moved_piece_type: PieceType, comment: Optional[str] = None):
        """
        Add a move to the record. Handles move numbering automatically.
        The game alternates white/black; the first call adds white's move,
        the second black's, and so on.
        """
        fpgn_str = move_to_fpgn(move, moved_piece_type)
        if self.pending_white is None:
            # White's move
            self.pending_white = fpgn_str
            if comment:
                self.pending_white += f" {{{comment}}}"
        else:
            # Black's move – write full turn
            white_str = self.pending_white
            black_str = fpgn_str
            if comment:
                black_str += f" {{{comment}}}"
            self.file.write(f"{self.move_number}. {white_str} {black_str} ")
            self.pending_white = None
            self.move_number += 1

    def add_result(self, result: str):
        """Write game result. Result can be '1-0', '0-1', '1/2-1/2', '*'."""
        # If there's a pending white move (game ended after white's move), write it now
        if self.pending_white is not None:
            self.file.write(f"{self.move_number}. {self.pending_white} ")
            self.pending_white = None
        self.file.write(f"{result}\n")

    def close(self):
        """Close the file. Call after writing result."""
        if self.file and not self.file.closed:
            self.file.close()