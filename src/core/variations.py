from __future__ import annotations
from typing import List, Optional, Dict, Any
from src.core.movegen import Move

class MoveNode:
    """A node in a move tree. Represents a move and its variations."""

    def __init__(self, move: Move, parent: Optional[MoveNode] = None):
        self.move = move               # the Move object
        self.parent = parent            # parent node (None for root)
        self.children: List[MoveNode] = []   # list of variations (branches)
        self.next_main: Optional[MoveNode] = None  # next move in the main line
        self.comment_before: str = ""   # comment before the move
        self.comment_after: str = ""    # comment after the move
        self.nags: List[int] = []       # numeric annotation glyphs (not used yet)

    def add_main_move(self, move: Move) -> MoveNode:
        """Append a move to the main line, returning the new node."""
        node = MoveNode(move, self)
        if self.next_main is None:
            self.next_main = node
        else:
            # Already has a main move – add to the end of the main line
            current = self.next_main
            while current.next_main:
                current = current.next_main
            current.next_main = node
        return node

    def add_variation(self, move: Move) -> MoveNode:
        """Start a new variation (branch) from this node."""
        node = MoveNode(move, self)
        self.children.append(node)
        return node

    def is_root(self) -> bool:
        return self.parent is None and self.move is None

    def to_list(self) -> List[Move]:
        """Return the move sequence from the root to this node (main line only)."""
        moves = []
        node = self
        while node.parent is not None:
            moves.append(node.move)
            node = node.parent
        moves.reverse()
        return moves

    def __repr__(self):
        if self.move:
            return f"MoveNode({self.move})"
        return "MoveNode(root)"