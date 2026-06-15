import os
import json
from typing import List, Dict, Optional, Tuple
from src.io.fpgn import FPGNReader
from src.core.movegen import Move

class GameRecord:
    def __init__(self):
        self.filepath = ""
        self.game_index = 0       # index within the file (if multiple games)
        self.white = ""
        self.black = ""
        self.result = "*"
        self.date = ""
        self.moves_count = 0
        self.first_moves = ""      # first few moves as PGN
        self.headers = {}

class GameDatabase:
    def __init__(self, folder: str = ""):
        self.folder = folder
        self.games: List[GameRecord] = []
        self._index_file = "games_index.json"

    def scan_folder(self, folder: str = None) -> int:
        """Scan a folder for .fpgn files and build an index. Returns number of games found."""
        if folder:
            self.folder = folder
        self.games.clear()
        if not self.folder or not os.path.isdir(self.folder):
            return 0
        for root, _, files in os.walk(self.folder):
            for file in files:
                if file.endswith(".fpgn"):
                    full_path = os.path.join(root, file)
                    try:
                        games = FPGNReader.read_file(full_path)
                        for idx, (headers, moves) in enumerate(games):
                            rec = GameRecord()
                            rec.filepath = full_path
                            rec.game_index = idx
                            rec.headers = headers
                            rec.white = headers.get("White", "?")
                            rec.black = headers.get("Black", "?")
                            rec.result = headers.get("Result", "*")
                            rec.date = headers.get("Date", "")
                            rec.moves_count = len(moves)
                            # Build first moves string
                            from src.engine.protocol import move_to_uci
                            pv = " ".join(move_to_uci(m) for m in moves[:8])  # first 8 moves
                            rec.first_moves = pv
                            self.games.append(rec)
                    except Exception:
                        pass
        # Save index
        self._save_index()
        return len(self.games)

    def _save_index(self):
        index_path = os.path.join(self.folder, self._index_file)
        data = []
        for g in self.games:
            data.append({
                "filepath": g.filepath,
                "game_index": g.game_index,
                "white": g.white,
                "black": g.black,
                "result": g.result,
                "date": g.date,
                "moves_count": g.moves_count,
                "first_moves": g.first_moves,
            })
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_index(self, folder: str) -> bool:
        index_path = os.path.join(folder, self._index_file)
        if not os.path.exists(index_path):
            return False
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.games.clear()
        for d in data:
            rec = GameRecord()
            rec.filepath = d["filepath"]
            rec.game_index = d["game_index"]
            rec.white = d["white"]
            rec.black = d["black"]
            rec.result = d["result"]
            rec.date = d["date"]
            rec.moves_count = d["moves_count"]
            rec.first_moves = d["first_moves"]
            self.games.append(rec)
        self.folder = folder
        return True

    def get_game_moves(self, index: int) -> Tuple[Dict, List[Move]]:
        """Return (headers, moves) for the game at the given index."""
        rec = self.games[index]
        all_games = FPGNReader.read_file(rec.filepath)
        if rec.game_index < len(all_games):
            return all_games[rec.game_index]
        return {}, []

    def filter(self, white: str = "", black: str = "", result: str = "", date_from: str = "", date_to: str = "",
               min_moves: int = 0) -> List[int]:
        """Return indices of games matching filters."""
        result = result.upper() if result else ""
        indices = []
        for i, g in enumerate(self.games):
            if white and white.lower() not in g.white.lower():
                continue
            if black and black.lower() not in g.black.lower():
                continue
            if result and g.result != result:
                continue
            if date_from and g.date < date_from:
                continue
            if date_to and g.date > date_to:
                continue
            if min_moves > 0 and g.moves_count < min_moves:
                continue
            indices.append(i)
        return indices

    def __len__(self):
        return len(self.games)

    def __getitem__(self, index):
        return self.games[index]