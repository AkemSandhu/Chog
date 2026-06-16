"""
MasterLion – Classic Alpha‑Beta engine for Chog.
Run with: python -m src.engines.classic.main
"""
import sys
import time

# ---- CRITICAL: Unbuffer stdout so GUI sees output immediately ----
sys.stdout.reconfigure(line_buffering=True)   # Python 3.7+

from src.core.board import Board
from src.core.pieces import Colour, PieceType, Piece
from src.core.movegen import Move
from src.core.rules import legal_moves
from src.engine.protocol import (
    uci_to_move, move_to_uci,
    build_go_command, build_position_command_fen, build_position_command_from_moves
)
from src.engines.classic.search import Search


class MasterLion:
    def __init__(self):
        self.board = Board.starting_position()
        self.turn = Colour.WHITE
        self.search = Search()

    def set_position_fen(self, fen: str):
        from src.io.fen import fen_to_board
        self.board, self.turn, _, _ = fen_to_board(fen)

    def apply_moves(self, moves: list):
        for uci in moves:
            move = uci_to_move(uci)
            if move:
                self.make_move(move)

    def make_move(self, move: Move):
        piece = self.board.get_piece(move.from_r, move.from_c)
        self.board.clear_square(move.from_r, move.from_c)
        if move.promotion:
            piece = Piece(move.promotion, piece.colour)
        self.board.set_piece(move.to_r, move.to_c, piece)
        self.turn = Colour.BLACK if self.turn == Colour.WHITE else Colour.WHITE

    def choose_move(self, movetime: int = None, depth: int = None,
                    wtime: int = None, btime: int = None) -> str:
        self.search.stop_flag = False

        if wtime is not None and btime is not None:
            my_time = wtime if self.turn == Colour.WHITE else btime
            alloc = max(100, min(my_time // 30, 5000))
        elif movetime and movetime < 900000:   # not infinite
            alloc = movetime
        else:
            alloc = 5000  # default 5 seconds

        self.search.set_time_limit(alloc)

        # Heartbeat – let the GUI know the engine is alive
        sys.stdout.write("info string MasterLion started thinking\n")
        sys.stdout.flush()

        best_move = None
        if depth:
            best_move = self.search.search_depth(self.board, self.turn, depth)
        else:
            for d in range(1, 100):
                if self.search.stop_flag:
                    break
                result = self.search.search_depth(self.board, self.turn, d)
                if result:
                    best_move = result
                    score = self.search.last_score
                    elapsed = int((time.time() - self.search.start_time) * 1000)
                    sys.stdout.write(f"info depth {d} score cp {score} time {elapsed}\n")
                    sys.stdout.flush()

        if best_move is None:
            moves = legal_moves(self.board, self.turn)
            if moves:
                best_move = moves[0]
            else:
                return "0000"

        return move_to_uci(best_move)

    def stop(self):
        self.search.stop_flag = True


def main():
    # Unbuffer stdout at startup
    sys.stdout.reconfigure(line_buffering=True)
    engine = MasterLion()
    while True:
        try:
            line = sys.stdin.readline()
        except EOFError:
            break
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        if line == "chog":
            sys.stdout.write("chogok\n")
            sys.stdout.flush()
        elif line == "isready":
            sys.stdout.write("readyok\n")
            sys.stdout.flush()
        elif line == "quit":
            break
        elif line.startswith("position"):
            parts = line.split()
            if parts[1] == "startpos":
                engine.board = Board.starting_position()
                engine.turn = Colour.WHITE
                if len(parts) > 2 and parts[2] == "moves":
                    engine.apply_moves(parts[3:])
            elif parts[1] == "fen":
                fen = " ".join(parts[2:])
                engine.set_position_fen(fen)
        elif line.startswith("go"):
            movetime = None
            depth = None
            wtime = None
            btime = None
            parts = line.split()
            i = 1
            while i < len(parts):
                if parts[i] == "movetime" and i + 1 < len(parts):
                    movetime = int(parts[i + 1])
                    i += 2
                elif parts[i] == "depth" and i + 1 < len(parts):
                    depth = int(parts[i + 1])
                    i += 2
                elif parts[i] == "wtime" and i + 1 < len(parts):
                    wtime = int(parts[i + 1])
                    i += 2
                elif parts[i] == "btime" and i + 1 < len(parts):
                    btime = int(parts[i + 1])
                    i += 2
                elif parts[i] == "infinite":
                    movetime = 999999
                    i += 1
                else:
                    i += 1
            best = engine.choose_move(movetime=movetime, depth=depth,
                                      wtime=wtime, btime=btime)
            sys.stdout.write(f"bestmove {best}\n")
            sys.stdout.flush()
        elif line == "stop":
            engine.stop()


if __name__ == "__main__":
    main()