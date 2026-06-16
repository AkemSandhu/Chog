from src.books.chog_book import compute_zobrist
from src.core.board import Board

class TTEntry:
    def __init__(self, depth: int, score: int, flag: str):
        self.depth = depth
        self.score = score
        self.flag = flag  # 'exact', 'lower', 'upper'

class TranspositionTable:
    def __init__(self, size: int = 2**20):
        self.table = {}
        self.size = size

    def probe(self, board: Board):
        key = compute_zobrist(board) % self.size
        return self.table.get(key, None)

    def store(self, board: Board, depth: int, score: int, flag: str):
        key = compute_zobrist(board) % self.size
        existing = self.table.get(key)
        if existing is None or depth >= existing.depth:
            self.table[key] = TTEntry(depth, score, flag)