from __future__ import annotations
from typing import List, Optional, Dict
from src.core.movegen import Move
from src.core.pieces import PieceType, PIECE_SYMBOLS

# ----------------------------------------------------------------------
#  Move ↔ string converters
# ----------------------------------------------------------------------
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

# ----------------------------------------------------------------------
#  Command builders (CUEP)
# ----------------------------------------------------------------------
def build_chog_handshake() -> str:
    """Initiate CUEP handshake."""
    return "chog"

def build_isready() -> str:
    return "isready"

def build_quit() -> str:
    return "quit"

def build_go_command(wtime: int = None, btime: int = None,
                     movetime: Optional[int] = None,
                     depth: Optional[int] = None,
                     nodes: Optional[int] = None,
                     infinite: bool = False,
                     ponder: bool = False,
                     winc: Optional[int] = None,
                     binc: Optional[int] = None) -> str:
    """Build the 'go' command for CUEP (identical to UCI but with 10x10 squares)."""
    cmd = "go"
    if infinite:
        cmd += " infinite"
    if ponder:
        cmd += " ponder"
    if movetime is not None and movetime > 0:
        cmd += f" movetime {movetime}"
    if depth is not None and depth > 0:
        cmd += f" depth {depth}"
    if nodes is not None and nodes > 0:
        cmd += f" nodes {nodes}"
    if wtime is not None and wtime > 0:
        cmd += f" wtime {wtime} btime {btime or 0}"
        if winc is not None:
            cmd += f" winc {winc}"
        if binc is not None:
            cmd += f" binc {binc}"
    if cmd == "go":
        cmd += " infinite"   # default
    return cmd

def build_position_command_from_moves(moves: List[Move]) -> str:
    """Build 'position startpos moves ...' command."""
    moves_str = " ".join(move_to_uci(m) for m in moves)
    return f"position startpos moves {moves_str}"

def build_position_command_fen(fen: str, moves: List[str] = None) -> str:
    """Build 'position fen ... moves ...' command."""
    cmd = f"position fen {fen}"
    if moves:
        cmd += " moves " + " ".join(moves)
    return cmd

def build_learn_command(fen: str, result: str, score: Optional[int] = None) -> str:
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

# ----------------------------------------------------------------------
#  Response parsers
# ----------------------------------------------------------------------
def parse_info_line(line: str) -> Optional[Dict]:
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
            i += 1
        i += 1
    return info

def parse_bestmove_line(line: str) -> Optional[str]:
    if not line.startswith("bestmove "):
        return None
    parts = line.split()
    return parts[1] if len(parts) > 1 else None

def parse_ponder_move(line: str) -> Optional[str]:
    """Extract ponder move from 'bestmove ... ponder ...' line."""
    if not line.startswith("bestmove "):
        return None
    parts = line.split()
    try:
        idx = parts.index("ponder")
        return parts[idx + 1] if idx + 1 < len(parts) else None
    except ValueError:
        return None