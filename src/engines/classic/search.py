import time
from typing import List, Tuple, Optional
from src.core.board import Board, ROWS, COLS
from src.core.pieces import Colour, PieceType, Piece
from src.core.movegen import pseudo_legal_moves_raw, Move, raw_to_move, _in_bounds
from src.core.rules import is_check
from src.core.evaluate import evaluate
from src.engines.classic.move_order import MovePicker, update_quiet_stats, update_capture_stats, stat_bonus
from src.engines.classic.transposition import TranspositionTable, compute_zobrist

INF = 99999999
MATE_SCORE = 100000

def mate_in(ply): return MATE_SCORE - ply
def mated_in(ply): return -MATE_SCORE + ply

def _value_to_tt(v, ply):
    if v >= MATE_SCORE - 100: return v + ply
    if v <= -MATE_SCORE + 100: return v - ply
    return v

def _value_from_tt(v, ply):
    if v >= MATE_SCORE - 100: return v - ply
    if v <= -MATE_SCORE + 100: return v + ply
    return v

class ScratchBoard:
    """Reusable board for make/unmake during search."""
    __slots__ = ('grid', 'zobrist', 'history')
    def __init__(self):
        self.grid = [0] * (ROWS * COLS)
        self.zobrist = 0
        self.history = []  # stack of (from_idx, to_idx, old_to, moved_ptype, moved_col, promo_ptype)

    def load(self, board: Board):
        self.grid[:] = board.grid
        self.zobrist = board.zobrist

    def make_move(self, raw):
        fr, fc, tr, tc, promo = raw
        from_idx = fr * COLS + fc
        to_idx = tr * COLS + tc
        moved = self.grid[from_idx]
        if moved == 0: return
        ptype = PieceType(moved >> 1)
        col = Colour(moved & 1)
        captured = self.grid[to_idx]
        # record for undo
        self.history.append((from_idx, to_idx, captured, moved, ptype, promo))
        # remove from source
        self.zobrist ^= ZOBRIST_TABLE[ptype.value][col.value][from_idx]
        self.grid[from_idx] = 0
        # remove captured
        if captured:
            cap_pt = PieceType(captured >> 1)
            cap_col = Colour(captured & 1)
            self.zobrist ^= ZOBRIST_TABLE[cap_pt.value][cap_col.value][to_idx]
        # place piece
        if promo != -1:
            new_pt = PieceType(promo)
            new_packed = (new_pt.value << 1) | col.value
            self.grid[to_idx] = new_packed
            self.zobrist ^= ZOBRIST_TABLE[new_pt.value][col.value][to_idx]
        else:
            self.grid[to_idx] = moved
            self.zobrist ^= ZOBRIST_TABLE[ptype.value][col.value][to_idx]

    def undo_move(self):
        from_idx, to_idx, captured, moved, ptype, promo = self.history.pop()
        col = Colour(moved & 1)
        # remove piece from to_square
        to_piece = self.grid[to_idx]
        if promo != -1:
            new_pt = PieceType(promo)
            self.zobrist ^= ZOBRIST_TABLE[new_pt.value][col.value][to_idx]
        else:
            self.zobrist ^= ZOBRIST_TABLE[ptype.value][col.value][to_idx]
        self.grid[to_idx] = captured
        if captured:
            cap_pt = PieceType(captured >> 1)
            cap_col = Colour(captured & 1)
            self.zobrist ^= ZOBRIST_TABLE[cap_pt.value][cap_col.value][to_idx]
        # restore source
        self.grid[from_idx] = moved
        self.zobrist ^= ZOBRIST_TABLE[ptype.value][col.value][from_idx]

    def is_king_attacked(self, colour):
        opp = colour.opponent()
        king_idx = None
        for i, v in enumerate(self.grid):
            if v != 0:
                pt = PieceType(v >> 1)
                col = Colour(v & 1)
                if pt == PieceType.KING and col == colour:
                    king_idx = i
                    break
        if king_idx is None: return False
        kr, kc = divmod(king_idx, COLS)
        # check opponent attacks
        for i, v in enumerate(self.grid):
            if v == 0: continue
            col = Colour(v & 1)
            if col != opp: continue
            r, c = divmod(i, COLS)
            if _sq_attacks_king(self.grid, r, c, opp, kr, kc):
                return True
        return False

def _sq_attacks_king(grid, r, c, colour, kr, kc):
    """Simplified fast attack test for a single piece against king."""
    v = grid[r * COLS + c]
    if v == 0: return False
    pt = PieceType(v >> 1)
    # For sliding pieces, check line of sight
    dr = kr - r
    dc = kc - c
    if pt in (PieceType.ROOK, PieceType.QUEEN):
        if dr == 0 and dc != 0:
            step = 1 if dc > 0 else -1
            for cc in range(c + step, kc, step):
                if grid[r * COLS + cc] != 0: return False
            return True
        if dc == 0 and dr != 0:
            step = 1 if dr > 0 else -1
            for rr in range(r + step, kr, step):
                if grid[rr * COLS + c] != 0: return False
            return True
    if pt in (PieceType.BISHOP, PieceType.QUEEN):
        if abs(dr) == abs(dc) and dr != 0:
            step_r = 1 if dr > 0 else -1
            step_c = 1 if dc > 0 else -1
            rr, cc = r + step_r, c + step_c
            while rr != kr:
                if grid[rr * COLS + cc] != 0: return False
                rr += step_r; cc += step_c
            return True
    # Non-sliding: check if (kr,kc) in pre-defined attack table (omitted for brevity, but can be added)
    return False

# Keep the search class but modify _alpha_beta to use ScratchBoard
class Search:
    def __init__(self):
        self.tt = TranspositionTable()
        self.last_score = 0
        self.nodes = 0
        self.stop_flag = False
        self.start_time = 0.0
        self.max_time_ms = 0
        self.root_pv: List[Move] = []
        self.scratch = ScratchBoard()

    def set_time_limit(self, movetime_ms):
        self.max_time_ms = movetime_ms
        self.start_time = time.time()
        self.stop_flag = False

    def check_time(self):
        if self.nodes % 2048 == 0:
            if (time.time() - self.start_time) * 1000 >= self.max_time_ms * 0.8:
                self.stop_flag = True

    def search_depth(self, board: Board, turn: Colour, depth: int) -> Optional[Move]:
        self.tt.new_search()
        self.scratch.load(board)
        best_move = None
        best_score = -INF
        alpha = -INF
        beta = INF
        raw_moves = pseudo_legal_moves_raw(board, turn)
        moves = []
        for raw in raw_moves:
            self.scratch.make_move(raw)
            if not self.scratch.is_king_attacked(turn):
                moves.append(raw)
            self.scratch.undo_move()
        # Order moves simply (captures first)
        moves.sort(key=lambda m: _capture_value(board, m), reverse=True)
        for raw in moves:
            if self.stop_flag: break
            self.scratch.make_move(raw)
            score, child_pv = self._alpha_beta(turn.opponent(), depth - 1, -beta, -alpha, 1)
            score = -score
            self.scratch.undo_move()
            if score > best_score:
                best_score = score
                best_move = raw_to_move(raw)
                self.root_pv = [best_move] + child_pv
            alpha = max(alpha, score)
        self.last_score = best_score
        return best_move

    def _alpha_beta(self, turn: Colour, depth, alpha, beta, ply):
        self.nodes += 1
        self.check_time()
        if self.stop_flag: return 0, []
        # Mate distance pruning
        alpha = max(alpha, mated_in(ply))
        beta = min(beta, mate_in(ply + 1))
        if alpha >= beta: return alpha, []
        # Check for game end
        in_check = self.scratch.is_king_attacked(turn)
        if in_check:
            raw_moves = pseudo_legal_moves_raw_scratch(self.scratch, turn)
            if not raw_moves:
                return mated_in(ply), []
        # Staged move picker (simplified for now)
        raw_moves = pseudo_legal_moves_raw_scratch(self.scratch, turn)
        legal = []
        for raw in raw_moves:
            self.scratch.make_move(raw)
            if not self.scratch.is_king_attacked(turn):
                legal.append(raw)
            self.scratch.undo_move()
        if not legal:
            return (mated_in(ply) if in_check else 0), []
        # Order
        legal.sort(key=lambda m: _capture_value_scratch(self.scratch, m), reverse=True)
        best_score = -INF
        best_pv = []
        for i, raw in enumerate(legal):
            self.scratch.make_move(raw)
            if i == 0:
                score, child_pv = self._alpha_beta(turn.opponent(), depth - 1, -beta, -alpha, ply + 1)
                score = -score
            else:
                # PVS + LMR (simplified)
                r = 0
                if depth >= 3 and i > 3:
                    r = int(0.5 + 2.5 * (depth - 3) * (i - 3) / 20)
                    r = min(r, depth - 1)
                reduced = max(1, depth - 1 - r)
                score, _ = self._alpha_beta(turn.opponent(), reduced, -alpha - 1, -alpha, ply + 1)
                score = -score
                if score > alpha and r > 0:
                    score, child_pv = self._alpha_beta(turn.opponent(), depth - 1, -beta, -alpha, ply + 1)
                    score = -score
                else:
                    child_pv = []
                if score > alpha:
                    score, child_pv = self._alpha_beta(turn.opponent(), depth - 1, -beta, -alpha, ply + 1)
                    score = -score
            self.scratch.undo_move()
            if score > best_score:
                best_score = score
                best_move = raw_to_move(raw)
                best_pv = [best_move] + child_pv
                if score > alpha:
                    alpha = score
                if alpha >= beta:
                    break
        # TT store omitted for brevity but can be added
        return best_score, best_pv

def _capture_value(board, raw):
    fr, fc, tr, tc, _ = raw
    victim = board.get_piece(tr, tc)
    return _piece_value(victim.ptype) if victim else 0

def _piece_value(ptype):
    vals = {PieceType.PAWN:1, PieceType.LANCE:2, PieceType.HORSE:3, PieceType.ELEPHANT:3, PieceType.GENERAL:4, PieceType.WAZIR:1, PieceType.FERZ:1, PieceType.EAGLE:3, PieceType.BISHOP:4, PieceType.ROOK:5, PieceType.QUEEN:9, PieceType.KING:99, PieceType.KNIGHT:3, PieceType.BERS:6, PieceType.DRAGON:6, PieceType.GOLD:7, PieceType.HUNTER:6}
    return vals.get(ptype, 0)