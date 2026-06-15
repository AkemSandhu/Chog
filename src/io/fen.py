from typing import Tuple
from src.core.pieces import Colour, PieceType, Piece, PIECE_SYMBOLS
from src.core.board import Board, ROWS, COLS

def board_to_fen(board: Board, turn: Colour, halfmove: int = 0, fullmove: int = 1) -> str:
    rows = []
    for r in range(ROWS - 1, -1, -1):
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
                row_str += piece.symbol()
        if empty > 0:
            row_str += str(empty)
        rows.append(row_str)
    piece_placement = "/".join(rows)
    active = "w" if turn == Colour.WHITE else "b"
    return f"{piece_placement} {active} - - {halfmove} {fullmove}"

def fen_to_board(fen: str) -> Tuple[Board, Colour, int, int]:
    parts = fen.strip().split()
    if len(parts) < 6:
        raise ValueError("FEN string must have 6 fields")
    placement, active, _, _, halfmove, fullmove = parts

    board = Board()
    ranks = placement.split("/")
    if len(ranks) != ROWS:
        raise ValueError(f"FEN must have exactly {ROWS} ranks")

    for rank_idx, rank_str in enumerate(ranks):
        row = ROWS - 1 - rank_idx
        col = 0
        num_buf = ""
        for ch in rank_str:
            if ch.isdigit():
                num_buf += ch
            else:
                if num_buf:
                    col += int(num_buf)
                    num_buf = ""
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