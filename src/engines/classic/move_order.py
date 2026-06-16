from src.core.board import Board
from src.core.pieces import Colour, PieceType
from src.core.movegen import Move

# Killer moves (two slots per ply)
killer_moves = [[None, None] for _ in range(100)]
history_table = {}

def order_moves(board: Board, moves: list, hash_move: Move | None, turn: Colour) -> list:
    """Order moves for better alpha‑beta pruning."""
    def score(move: Move):
        if hash_move and move == hash_move:
            return 10000
        # MVV‑LVA for captures
        victim = board.get_piece(move.to_r, move.to_c)
        if victim:
            return 1000 + _piece_value(victim.ptype) - _piece_value(board.get_piece(move.from_r, move.from_c).ptype)
        # Killer moves
        ply = 0  # we don't track ply easily here; simplified
        if move in killer_moves[ply]:
            return 900
        # History heuristic
        return history_table.get(move, 0)

    return sorted(moves, key=score, reverse=True)

def _piece_value(ptype: PieceType) -> int:
    values = {
        PieceType.PAWN: 1, PieceType.LANCE: 2, PieceType.HORSE: 3,
        PieceType.ELEPHANT: 3, PieceType.GENERAL: 4, PieceType.WAZIR: 1,
        PieceType.FERZ: 1, PieceType.EAGLE: 3, PieceType.BISHOP: 4,
        PieceType.ROOK: 5, PieceType.QUEEN: 9, PieceType.KING: 99,
        PieceType.KNIGHT: 3, PieceType.BERS: 6, PieceType.DRAGON: 6,
        PieceType.GOLD: 7, PieceType.HUNTER: 6,
    }
    return values.get(ptype, 0)