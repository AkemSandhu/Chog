# io/fen.py
from typing import Tuple
from pieces import Colour, PieceType, Piece, PIECE_SYMBOLS
from board import Board, ROWS, COLS

def board_to_fen(board: Board, turn: Colour, halfmove: int = 0, fullmove: int = 1) -> str:
    """Convert a board position to FEN string."""
    rows = []
    for r in range(ROWS - 1, -1, -1):  # from row 9 down to 0
        empty = 0
        row_str = ""
        for c in range(COLS):
            piece = board.get_piece(r, c)
            if piece is None:
                empty += 1
            else:
                if empty > 0:
                    row_str += str(empty)
                    empty = 0
                row_str += piece.symbol()  # uppercase white, lowercase black
        if empty > 0:
            row_str += str(empty)
        rows.append(row_str)
    piece_placement = "/".join(rows)
    active = "w" if turn == Colour.WHITE else "b"
    # No castling or en passant in this variant
    return f"{piece_placement} {active} - - {halfmove} {fullmove}"


def fen_to_board(fen: str) -> Tuple[Board, Colour, int, int]:
    """Parse a FEN string and return (Board, turn, halfmove, fullmove)."""
    parts = fen.strip().split()
    if len(parts) < 6:
        raise ValueError("FEN string must have 6 fields")
    placement, active, _, _, halfmove, fullmove = parts

    board = Board()
    ranks = placement.split("/")
    if len(ranks) != ROWS:
        raise ValueError(f"FEN must have exactly {ROWS} ranks")

    for rank_idx, rank_str in enumerate(ranks):
        row = ROWS - 1 - rank_idx  # rank 9 first in FEN, row 9 in board
        col = 0
        for ch in rank_str:
            if ch.isdigit():
                # could be multi‑digit number like "10"
                # We'll parse the whole number by collecting consecutive digits
                # But we're iterating char by char; easier: use a regex or just step through.
                # Since we iterate per character, a number like "10" would be split into '1' then '0'.
                # To handle this, we'll rebuild the number from consecutive digits.
                # We'll implement by collecting digits.
                pass  # will be handled below
        # Proper parsing: handle multi‑digit empties
        # We'll use a loop with a separate function.
        col = 0
        num_buf = ""
        for ch in rank_str:
            if ch.isdigit():
                num_buf += ch
            else:
                if num_buf:
                    empty = int(num_buf)
                    col += empty
                    num_buf = ""
                # piece symbol
                # Determine colour: uppercase white, lowercase black
                is_white = ch.isupper()
                symbol = ch.upper()
                ptype = None
                for pt, sym in PIECE_SYMBOLS.items():
                    if sym == symbol:
                        ptype = pt
                        break
                if ptype is None:
                    raise ValueError(f"Unknown piece symbol '{ch}'")
                colour = Colour.WHITE if is_white else Colour.BLACK
                board.set_piece(row, col, Piece(ptype, colour))
                col += 1
        if num_buf:
            col += int(num_buf)
        if col != COLS:
            raise ValueError(f"Rank {rank_idx+1} length mismatch (expected {COLS}, got {col})")

    active = Colour.WHITE if active == "w" else Colour.BLACK
    halfmove = int(halfmove)
    fullmove = int(fullmove)
    return board, active, halfmove, fullmove