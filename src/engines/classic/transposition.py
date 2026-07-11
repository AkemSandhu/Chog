"""
Transposition table for Chog.
Bucket-based with depth-preferred aging, inspired by Stockfish's tt.cpp.
"""
from src.books.chog_book import compute_zobrist
from src.core.board import Board
from src.core.movegen import Move

CLUSTER_SIZE = 3

# ----------------------------------------------------------------------
# Move encoding for 16-bit storage
# ----------------------------------------------------------------------
def _encode_move(move: Move) -> int:
    if move is None:
        return 0
    return (move.from_r << 12) | (move.from_c << 8) | (move.to_r << 4) | move.to_c

def _decode_move(encoded: int) -> Move | None:
    if encoded == 0:
        return None
    to_c   =  encoded & 0xF
    to_r   = (encoded >> 4) & 0xF
    from_c = (encoded >> 8) & 0xF
    from_r = (encoded >> 12) & 0xF
    return Move(from_r, from_c, to_r, to_c, promotion=None)


# ----------------------------------------------------------------------
# TT Entry
# ----------------------------------------------------------------------
class TTEntry:
    __slots__ = ('key16', 'value16', 'eval16', 'depth8', 'genBound8', 'move16')

    def __init__(self):
        self.key16     = 0
        self.value16   = 0
        self.eval16    = 0
        self.depth8    = 0
        self.genBound8 = 0
        self.move16    = 0

    def save(self, key: int, value: int, pv: bool, bound: int,
             depth: int, move: Move | None, eval_: int, generation: int):
        if move is not None or (key >> 48) != self.key16:
            self.move16 = _encode_move(move)

        if (    (key >> 48) != self.key16
            or  depth > (self.depth8 + 4)
            or  bound == 3):
            self.key16 = (key >> 48) & 0xFFFF
            self.value16 = self._clamp(value)
            self.eval16  = self._clamp(eval_)
            self.depth8  = min(depth, 255)
            gen4 = generation & 0xF
            self.genBound8 = (gen4 << 4) | (int(pv) << 3) | bound

    @staticmethod
    def _clamp(x: int) -> int:
        return max(-32768, min(32767, x))

    def is_pv(self) -> bool:
        return bool(self.genBound8 & 0x08)

    def bound(self) -> int:
        return self.genBound8 & 0x07

    def depth(self) -> int:
        return self.depth8

    def value(self) -> int:
        return self.value16

    def eval(self) -> int:
        return self.eval16

    def move(self) -> Move | None:
        return _decode_move(self.move16)


# ----------------------------------------------------------------------
# Transposition table
# ----------------------------------------------------------------------
class TranspositionTable:
    def __init__(self, hash_size_mb: int = 16):
        self.cluster_count = (hash_size_mb * 1024 * 1024) // (CLUSTER_SIZE * 24)
        self.table = [[TTEntry() for _ in range(CLUSTER_SIZE)] for _ in range(self.cluster_count)]
        self.generation = 0

    def new_search(self):
        self.generation = (self.generation + 1) & 0xF

    def resize(self, hash_size_mb: int):
        """Resize the hash table to `hash_size_mb` MB."""
        self.cluster_count = (hash_size_mb * 1024 * 1024) // (CLUSTER_SIZE * 24)
        self.table = [[TTEntry() for _ in range(CLUSTER_SIZE)] for _ in range(self.cluster_count)]
        self.generation = 0

    def clear(self):
        """Clear all entries (reset to empty)."""
        self.table = [[TTEntry() for _ in range(CLUSTER_SIZE)] for _ in range(self.cluster_count)]
        self.generation = 0

    def probe(self, key: int):
        cluster_idx = key % self.cluster_count
        cluster = self.table[cluster_idx]
        key16 = (key >> 48) & 0xFFFF

        for entry in cluster:
            if entry.key16 == key16:
                gen4 = self.generation & 0xF
                entry.genBound8 = (gen4 << 4) | (entry.genBound8 & 0x0F)
                return True, entry
            elif entry.key16 == 0:
                return False, entry

        replace = cluster[0]
        for entry in cluster[1:]:
            age_replace = (replace.depth8 - ((263 + self.generation - (replace.genBound8 >> 4)) & 0xF8))
            age_entry   = (entry.depth8   - ((263 + self.generation - (entry.genBound8 >> 4)) & 0xF8))
            if age_replace > age_entry:
                replace = entry
        return False, replace

    def store(self, key: int, value: int, pv: bool, bound: int,
              depth: int, move: Move | None, eval_: int):
        found, entry = self.probe(key)
        entry.save(key, value, pv, bound, depth, move, eval_, self.generation)

    def hashfull(self) -> int:
        cnt = 0
        samples = min(1000 // CLUSTER_SIZE, self.cluster_count)
        for i in range(samples):
            for entry in self.table[i]:
                if entry.key16 != 0 and (entry.genBound8 >> 4) == (self.generation & 0xF):
                    cnt += 1
        return cnt * 1000 // (CLUSTER_SIZE * samples)