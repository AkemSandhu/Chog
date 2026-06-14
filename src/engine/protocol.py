from __future__ import annotations
from typing import List, Optional, Dict
from chog.core.movegen import Move
from chog.core.pieces import PieceType, PIECE_SYMBOLS

def move_to_uci(move: Move) -> str:
    """Convert Move to long algebraic string (e.g. e2e3 or e7e8=U)."""
    s = f"{chr(ord('a') + move.from_c)}{move.from_r}{chr(ord('a') + move.to_c)}{move.to_r}"
    if move.promotion is not None:
        s += f"={PIECE_SYMBOLS[move.promotion]}"
    return s

def uci_to_move(uci: str) -> Optional[Move]:
    """Parse a long algebraic move string. Returns None if invalid."""
    uci = uci.strip()
    if not (uci and uci[0].isalpha() and uci[1].isdigit()):
        return None
    from_c = ord(uci[0]) - ord('a')
    from_r = int(uci[1])
    to_c = ord(uci[2]) - ord('a')
    to_r = int(uci[3])
    promo = None
    if len(uci) > 4 and uci[4] == '=':
        promo_symbol = uci[5].upper()
        for pt, sym in PIECE_SYMBOLS.items():
            if sym == promo_symbol:
                promo = pt
                break
    return Move(from_r, from_c, to_r, to_c, promo)

# ---- Command builders ----

def build_go_command(wtime: int = 60000, btime: int = 60000,
                     movetime: Optional[int] = None,
                     depth: Optional[int] = None,
                     infinite: bool = False) -> str:
    """Build the 'go' command string."""
    cmd = "go"
    if infinite:
        return "go infinite"
    if movetime is not None:
        cmd += f" movetime {movetime}"
    else:
        cmd += f" wtime {wtime} btime {btime}"
    if depth is not None:
        cmd += f" depth {depth}"
    return cmd

def build_position_command(moves: List[Move]) -> str:
    """Build 'position startpos moves ...' command."""
    moves_str = " ".join(move_to_uci(m) for m in moves)
    return f"position startpos moves {moves_str}"

def build_learn_command(fen: str, result: str, score: Optional[int] = None) -> str:
    """Tell engine the outcome of a game from a given position."""
    cmd = f"learn {fen} {result}"
    if score is not None:
        cmd += f" {score}"
    return cmd

def build_setoption_command(name: str, value: str) -> str:
    return f"setoption name {name} value {value}"

def build_saveweights_command(filepath: str) -> str:
    return f"saveweights {filepath}"

def build_loadweights_command(filepath: str) -> str:
    return f"loadweights {filepath}"

# ---- Response parsers ----

def parse_info_line(line: str) -> Optional[Dict]:
    """Parse an 'info ...' line into a dictionary. Returns None if not info."""
    if not line.startswith("info "):
        return None
    parts = line[5:].split()
    info = {}
    i = 0
    while i < len(parts):
        token = parts[i]
        if token == "depth":
            i += 1; info["depth"] = int(parts[i])
        elif token == "score":
            i += 1
            if parts[i] == "cp":
                i += 1; info["score_cp"] = int(parts[i])
            elif parts[i] == "mate":
                i += 1; info["score_mate"] = int(parts[i])
        elif token == "pv":
            i += 1
            pv_moves = []
            while i < len(parts) and parts[i] not in ("depth","score","nodes","nps","time"):
                pv_moves.append(parts[i])
                i += 1
            info["pv"] = pv_moves
            continue
        elif token in ("nodes","nps","time","currmove","currmovenumber","hashfull",
                       "tbhits","cpuload","string"):
            i += 1  # skip value
        i += 1
    return info

def parse_bestmove_line(line: str) -> Optional[str]:
    """Extract best move string from 'bestmove ...' line."""
    if not line.startswith("bestmove "):
        return None
    parts = line.split()
    return parts[1] if len(parts) > 1 else None