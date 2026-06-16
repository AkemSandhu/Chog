import time
from src.core.board import Board
from src.core.pieces import Colour, PieceType, Piece
from src.core.movegen import Move
from src.core.rules import legal_moves, is_check
from src.core.evaluate import evaluate
from src.engines.classic.move_order import order_moves
from src.engines.classic.transposition import TranspositionTable

INF = 999999
MATE_SCORE = 100000

class Search:
    def __init__(self):
        self.tt = TranspositionTable()
        self.last_score = 0
        self.nodes = 0
        self.stop_flag = False
        self.start_time = 0.0
        self.max_time_ms = 0

    def set_time_limit(self, movetime_ms: int):
        self.max_time_ms = movetime_ms
        self.start_time = time.time()
        self.stop_flag = False

    def check_time(self):
        if self.nodes % 2048 == 0:
            elapsed = (time.time() - self.start_time) * 1000
            if elapsed >= self.max_time_ms * 0.8:   # stop at 80% of budget
                self.stop_flag = True

    def search_depth(self, board: Board, turn: Colour, depth: int) -> Move | None:
        """Iterative deepening entry point. Returns best move."""
        best_move = None
        best_score = -INF
        alpha = -INF
        beta = INF
        moves = legal_moves(board, turn)
        if not moves:
            return None
        moves = order_moves(board, moves, None, turn)

        for move in moves:
            if self.stop_flag:
                break
            new_board = board.copy()
            self._make_move(new_board, move)
            score = -self._alpha_beta(new_board, turn.opponent(), depth-1, -beta, -alpha)
            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)

        self.last_score = best_score
        return best_move

    def _alpha_beta(self, board: Board, turn: Colour, depth: int, alpha: int, beta: int) -> int:
        self.nodes += 1
        self.check_time()
        if self.stop_flag:
            return 0

        # Transposition table lookup
        tt_entry = self.tt.probe(board)
        if tt_entry and tt_entry.depth >= depth:
            if tt_entry.flag == 'exact':
                return tt_entry.score
            elif tt_entry.flag == 'lower':
                alpha = max(alpha, tt_entry.score)
            elif tt_entry.flag == 'upper':
                beta = min(beta, tt_entry.score)
            if alpha >= beta:
                return tt_entry.score

        # Null‑move pruning
        if depth >= 3 and not is_check(board, turn):
            R = 3 if depth >= 6 else 2
            new_board = board.copy()
            # Null move: just swap turn, no move
            score = -self._alpha_beta(new_board, turn.opponent(), depth - 1 - R, -beta, -beta + 1)
            if score >= beta:
                return beta

        if depth <= 0:
            return self._quiescence(board, turn, alpha, beta)

        moves = legal_moves(board, turn)
        if not moves:
            if is_check(board, turn):
                return -MATE_SCORE + (20 - depth)
            return 0

        moves = order_moves(board, moves, None, turn)

        best_score = -INF
        for move in moves:
            if self.stop_flag:
                break
            new_board = board.copy()
            self._make_move(new_board, move)
            score = -self._alpha_beta(new_board, turn.opponent(), depth-1, -beta, -alpha)
            if score > best_score:
                best_score = score
            alpha = max(alpha, score)
            if alpha >= beta:
                # Store killer move
                # self.killer_moves[ply] = move
                break

        flag = 'exact'
        if best_score <= alpha:
            flag = 'upper'
        elif best_score >= beta:
            flag = 'lower'
        self.tt.store(board, depth, best_score, flag)
        return best_score

    def _quiescence(self, board: Board, turn: Colour, alpha: int, beta: int) -> int:
        self.check_time()
        if self.stop_flag:
            return 0
        stand_pat = evaluate(board)
        if turn == Colour.BLACK:
            stand_pat = -stand_pat

        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        moves = legal_moves(board, turn)
        captures = [m for m in moves if board.get_piece(m.to_r, m.to_c) is not None]
        captures = order_moves(board, captures, None, turn)

        for move in captures:
            if self.stop_flag:
                break
            new_board = board.copy()
            self._make_move(new_board, move)
            score = -self._quiescence(new_board, turn.opponent(), -beta, -alpha)
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    @staticmethod
    def _make_move(board: Board, move: Move):
        piece = board.get_piece(move.from_r, move.from_c)
        board.clear_square(move.from_r, move.from_c)
        if move.promotion:
            piece = Piece(move.promotion, piece.colour)
        board.set_piece(move.to_r, move.to_c, piece)