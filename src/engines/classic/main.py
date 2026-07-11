"""
MasterLion – Classic Alpha‑Beta engine for Chog.
Run with: python -m src.engines.classic.main
"""
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

from src.core.board import Board
from src.core.pieces import Colour, PieceType, Piece
from src.core.movegen import Move
from src.core.rules import legal_moves
from src.engine.protocol import (
    uci_to_move, move_to_uci,
    build_go_command, build_position_command_fen, build_position_command_from_moves
)
from src.engines.classic.search import Search
from src.engines.classic.timeman import TimeManager
from src.engines.classic.options import Options


class MasterLion:
    def __init__(self):
        self.board = Board.starting_position()
        self.turn = Colour.WHITE
        self.search = Search()
        self.ply = 0
        self.options = Options()

    def set_position_fen(self, fen: str):
        from src.io.fen import fen_to_board
        self.board, self.turn, _, _ = fen_to_board(fen)
        self.ply = 0

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
        self.ply += 1

    def choose_move(self, movetime: int = None, depth: int = None,
                    wtime: int = None, btime: int = None,
                    winc: int = 0, binc: int = 0, movestogo: int = None) -> str:
        try:
            return self._choose_move_impl(movetime, depth, wtime, btime, winc, binc, movestogo)
        except Exception as e:
            sys.stderr.write(f"Engine crash: {e}\n")
            sys.stderr.flush()
            return "0000"

    def _choose_move_impl(self, movetime, depth, wtime, btime, winc, binc, movestogo):
        self.search.stop_flag = False

        time_mgr = TimeManager(self.options)

        # ----------  Fixed time allocation  ----------
        if movetime is not None and movetime > 0:
            if movetime >= 900_000:          # "go infinite" or huge movetime
                # Allocate a very long time – will be stopped by GUI later
                time_mgr.optimum_time = 3_600_000   # 1 hour
                time_mgr.maximum_time = 3_600_000
                time_mgr.start_time = time.time()
            else:
                time_mgr.optimum_time = movetime
                time_mgr.maximum_time = movetime
                time_mgr.start_time = time.time()
        elif wtime is not None and btime is not None:
            time_mgr.init(self.turn, wtime, btime, winc or 0, binc or 0,
                          movestogo, self.ply)
        else:
            # No time information – safe default
            time_mgr.optimum_time = 5000
            time_mgr.maximum_time = 5000
            time_mgr.start_time = time.time()
        # -------------------------------------------------

        self.search.set_time_limit(time_mgr.maximum_time)

        sys.stdout.write("info string MasterLion started thinking\n")
        sys.stdout.flush()

        best_move = None

        if depth:
            best_move = self.search.search_depth(self.board, self.turn, depth)
            if best_move:
                pv_str = " ".join(move_to_uci(m) for m in self.search.root_pv)
                sys.stdout.write(
                    f"info depth {depth} score cp {self.search.last_score} pv {pv_str}\n")
                sys.stdout.flush()
        else:
            for d in range(1, 200):               # up to depth 200
                if self.search.stop_flag:
                    break
                result = self.search.search_depth(self.board, self.turn, d)
                if result:
                    best_move = result
                    score = self.search.last_score
                    pv_str = " ".join(move_to_uci(m) for m in self.search.root_pv)
                    elapsed = time_mgr.elapsed()
                    sys.stdout.write(
                        f"info depth {d} score cp {score} time {elapsed} pv {pv_str}\n")
                    sys.stdout.flush()
                # Stop if we exceeded the soft limit
                if time_mgr.elapsed() >= time_mgr.optimum_time:
                    self.search.stop_flag = True

        if best_move is None:
            moves = legal_moves(self.board, self.turn)
            if moves:
                best_move = moves[0]
            else:
                return "0000"

        return move_to_uci(best_move)

    def stop(self):
        self.search.stop_flag = True

    def set_option(self, name: str, value: str):
        self.options.set_option(name, value)
        if name == "Hash":
            self.search.tt.resize(int(value))
        elif name == "Clear Hash":
            self.search.tt.clear()

    def uci_info(self) -> str:
        return (
            "id name MasterLion\n"
            "id author DeepSeek\n" +
            self.options.print_options() +
            "\nuciok"
        )


def main():
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
        elif line == "uci":
            sys.stdout.write(engine.uci_info() + "\n")
            sys.stdout.flush()
        elif line == "isready":
            sys.stdout.write("readyok\n")
            sys.stdout.flush()
        elif line == "quit":
            break
        elif line.startswith("setoption"):
            parts = line.split()
            try:
                idx_name = parts.index("name")
                idx_value = parts.index("value")
                name = " ".join(parts[idx_name+1:idx_value])
                value = " ".join(parts[idx_value+1:])
                engine.set_option(name, value)
            except (ValueError, IndexError):
                pass
        elif line.startswith("position"):
            parts = line.split()
            if parts[1] == "startpos":
                engine.board = Board.starting_position()
                engine.turn = Colour.WHITE
                engine.ply = 0
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
            winc = 0
            binc = 0
            movestogo = None
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
                elif parts[i] == "winc" and i + 1 < len(parts):
                    winc = int(parts[i + 1])
                    i += 2
                elif parts[i] == "binc" and i + 1 < len(parts):
                    binc = int(parts[i + 1])
                    i += 2
                elif parts[i] == "movestogo" and i + 1 < len(parts):
                    movestogo = int(parts[i + 1])
                    i += 2
                elif parts[i] == "infinite":
                    movetime = 999999
                    i += 1
                else:
                    i += 1
            best = engine.choose_move(movetime=movetime, depth=depth,
                                      wtime=wtime, btime=btime,
                                      winc=winc, binc=binc,
                                      movestogo=movestogo)
            sys.stdout.write(f"bestmove {best}\n")
            sys.stdout.flush()
        elif line == "stop":
            engine.stop()


if __name__ == "__main__":
    main()