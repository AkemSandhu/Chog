"""
Pawn structure evaluation helpers for Chog.
Adapted from Stockfish's pawns.cpp.
"""
from src.core.pieces import PieceType, Colour
from src.core.board import Board, ROWS, COLS

# Pawn penalties / bonuses (centipawns)
DOUBLED_PENALTY      = 15
ISOLATED_PENALTY     = 10
BACKWARD_PENALTY     = 20
CONNECTED_BONUS      = [0, 5, 8, 12, 20, 30, 40, 55, 70, 85]  # by rank (0-9)
PASSED_BONUS         = [0, 5, 10, 20, 35, 55, 85, 130, 200, 0]  # rank 9 = promoted
SUPPORT_BONUS        = 15

def _forward(colour: Colour) -> int:
    """Direction 'up' for pawns: +1 for White, -1 for Black."""
    return 1 if colour == Colour.WHITE else -1

def pawn_structure_score(board: Board, colour: Colour) -> int:
    """Return a score (positive = good) for the pawn structure of `colour`."""
    forward = _forward(colour)
    pawns = []
    for r in range(ROWS):
        for c in range(COLS):
            p = board.get_piece(r, c)
            if p and p.ptype == PieceType.PAWN and p.colour == colour:
                pawns.append((r, c))

    score = 0
    # Build set of pawn squares for fast lookup
    our_pawn_squares = {(r, c) for r, c in pawns}
    # Opponent pawns
    opp = colour.opponent()
    opp_pawn_squares = set()
    for r in range(ROWS):
        for c in range(COLS):
            p = board.get_piece(r, c)
            if p and p.ptype == PieceType.PAWN and p.colour == opp:
                opp_pawn_squares.add((r, c))

    for r, c in pawns:
        # Doubled pawns
        if (r - forward, c) in our_pawn_squares:
            score -= DOUBLED_PENALTY

        # Isolated: no friendly pawn on adjacent files
        left_col  = c - 1
        right_col = c + 1
        isolated = True
        for rr in range(ROWS):
            if (left_col >= 0 and (rr, left_col) in our_pawn_squares) or \
               (right_col < COLS and (rr, right_col) in our_pawn_squares):
                isolated = False
                break
        if isolated:
            score -= ISOLATED_PENALTY

        # Backward: pawn behind all friendly pawns on adjacent files and can't safely advance
        backward = True
        for rr in range(r + forward, ROWS if forward > 0 else -1, forward):
            if (left_col >= 0 and (rr, left_col) in our_pawn_squares) or \
               (right_col < COLS and (rr, right_col) in our_pawn_squares):
                backward = False
                break
        # Also backward if the square in front is blocked by an enemy pawn
        front_sq = (r + forward, c)
        if front_sq in opp_pawn_squares:
            backward = True
        if backward and not isolated:
            score -= BACKWARD_PENALTY

        # Connected / supported pawns
        if (r - forward, c) in our_pawn_squares:
            score += SUPPORT_BONUS
        # Phalanx: friendly pawn on same rank, adjacent file
        if (left_col >= 0 and (r, left_col) in our_pawn_squares) or \
           (right_col < COLS and (r, right_col) in our_pawn_squares):
            score += CONNECTED_BONUS[r]

    return score


def passed_pawn_score(board: Board, colour: Colour) -> int:
    """Bonus for passed pawns of `colour`."""
    forward = _forward(colour)
    opp = colour.opponent()
    score = 0
    for r in range(ROWS):
        for c in range(COLS):
            p = board.get_piece(r, c)
            if p and p.ptype == PieceType.PAWN and p.colour == colour:
                # Check if no opponent pawns block the path
                passed = True
                start = r + forward
                end = ROWS if forward > 0 else -1
                step = forward
                for rr in range(start, end, step):
                    if board.get_piece(rr, c) is not None and \
                       board.get_piece(rr, c).colour == opp and \
                       board.get_piece(rr, c).ptype == PieceType.PAWN:
                        passed = False
                        break
                    # Also check adjacent files for opponent pawns that could capture
                    for dc in (-1, 1):
                        cc = c + dc
                        if 0 <= cc < COLS:
                            enemy = board.get_piece(rr, cc)
                            if enemy and enemy.ptype == PieceType.PAWN and enemy.colour == opp:
                                passed = False
                                break
                    if not passed:
                        break
                if passed:
                    score += PASSED_BONUS[r]
    return score