from __future__ import annotations
import re
from typing import List, Dict, Tuple, Optional, TextIO
from src.core.pieces import PieceType, PIECE_SYMBOLS
from src.core.movegen import Move
from src.core.variations import MoveNode

# ----------------------------------------------------------------------
#  Move string converters (unchanged)
# ----------------------------------------------------------------------
def _col_from_char(c: str) -> int:
    return ord(c) - ord('a')

def _col_to_char(c: int) -> str:
    return chr(ord('a') + c)

def move_to_fpgn(move: Move, moved_piece_type: PieceType) -> str:
    base = f"{_col_to_char(move.from_c)}{move.from_r}{_col_to_char(move.to_c)}{move.to_r}"
    if moved_piece_type == PieceType.PAWN and move.promotion is not None:
        base += f"={PIECE_SYMBOLS[move.promotion]}"
    return base

def fpgn_to_move(fpgn_str: str) -> Optional[Move]:
    fpgn_str = fpgn_str.strip()
    fpgn_str = re.sub(r'[+#]', '', fpgn_str)
    match = re.match(r'([a-j])(\d)([a-j])(\d)(?:=(\w+))?', fpgn_str)
    if not match:
        return None
    fc, fr, tc, tr = match.group(1), match.group(2), match.group(3), match.group(4)
    promo_str = match.group(5)
    from_c = _col_from_char(fc)
    from_r = int(fr)
    to_c = _col_from_char(tc)
    to_r = int(tr)
    promotion = None
    if promo_str:
        symbol = promo_str.upper()
        for pt, sym in PIECE_SYMBOLS.items():
            if sym == symbol:
                promotion = pt
                break
    return Move(from_r, from_c, to_r, to_c, promotion)


# ----------------------------------------------------------------------
#  Tokenizer
# ----------------------------------------------------------------------
class Token:
    TAG, MOVE, NAG, COMMENT, VARIATION_START, VARIATION_END, RESULT, EOF = range(8)

    def __init__(self, type_: int, value: str = ""):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


def tokenize_fpgn(text: str) -> List[Token]:
    """Break FPGN text into tokens."""
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == '[':
            # Tag
            j = text.index(']', i)
            tag_str = text[i+1:j]
            tokens.append(Token(Token.TAG, tag_str.strip()))
            i = j + 1
        elif c == '{':
            # Comment
            j = text.index('}', i)
            comment = text[i+1:j]
            tokens.append(Token(Token.COMMENT, comment.strip()))
            i = j + 1
        elif c == '(':
            tokens.append(Token(Token.VARIATION_START))
            i += 1
        elif c == ')':
            tokens.append(Token(Token.VARIATION_END))
            i += 1
        elif c == '$':
            # NAG
            j = i + 1
            while j < n and text[j].isdigit():
                j += 1
            nag_str = text[i+1:j]
            if nag_str.isdigit():
                tokens.append(Token(Token.NAG, nag_str))
            i = j
        elif c == '*':
            tokens.append(Token(Token.RESULT, '*'))
            i += 1
        elif text[i:i+3] in ('1-0', '0-1'):
            tokens.append(Token(Token.RESULT, text[i:i+3]))
            i += 3
        elif text[i:i+7] == '1/2-1/2':
            tokens.append(Token(Token.RESULT, '1/2-1/2'))
            i += 7
        elif re.match(r'[a-j]\d[a-j]\d', text[i:i+4]):
            # Move token (long algebraic)
            # Could be followed by '=' and promotion
            j = i + 4
            if j < n and text[j] == '=':
                j += 1
                while j < n and text[j].isalpha():
                    j += 1
            token_str = text[i:j]
            tokens.append(Token(Token.MOVE, token_str))
            i = j
        elif c.isdigit():
            # Move numbers – skip them
            j = i
            while j < n and (text[j].isdigit() or text[j] == '.'):
                j += 1
            i = j
        else:
            # Unknown, skip
            i += 1
    tokens.append(Token(Token.EOF))
    return tokens


# ----------------------------------------------------------------------
#  Parser (token stream → MoveNode tree)
# ----------------------------------------------------------------------
class FPGNParser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.current = tokens[0] if tokens else Token(Token.EOF)

    def advance(self):
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current = self.tokens[self.pos]
        else:
            self.current = Token(Token.EOF)

    def expect(self, type_: int, value: Optional[str] = None):
        if self.current.type != type_ or (value and self.current.value != value):
            raise ValueError(f"Expected token {type_} {value}, got {self.current}")
        self.advance()

    def parse(self) -> Tuple[Dict[str, str], MoveNode]:
        """Parse the tokens and return (headers, root_node)."""
        headers = {}
        while self.current.type == Token.TAG:
            tag_str = self.current.value
            match = re.match(r'(\w+)\s+"(.*)"', tag_str)
            if match:
                headers[match.group(1)] = match.group(2)
            self.advance()

        root = MoveNode(None, None)  # dummy root
        self._parse_movetext(root)
        return headers, root

    def _parse_movetext(self, parent: MoveNode):
        """Parse a sequence of moves (main line + variations)."""
        while self.current.type != Token.EOF and self.current.type != Token.RESULT:
            if self.current.type == Token.VARIATION_START:
                self.advance()
                # The variation is attached to the last move of the main line.
                # We need to find the last move node.
                last_main = parent
                while last_main.next_main:
                    last_main = last_main.next_main
                # If last_main has no move (i.e., root), we skip? In PGN, variations after the first move.
                if last_main.move:
                    self._parse_variation(last_main)
                else:
                    # Variation at the start – we can attach to root for now.
                    self._parse_variation(parent)
            elif self.current.type == Token.MOVE:
                move_str = self.current.value
                move = fpgn_to_move(move_str)
                if move:
                    node = parent.add_main_move(move)
                    # After adding the move, we might have NAGs or comments
                    self._parse_move_suffix(node)
                self.advance()
            elif self.current.type == Token.COMMENT:
                # Comment before the next move – attach to the last node
                last = self._last_move_node(parent)
                if last and last.comment_after == "":
                    last.comment_after = self.current.value
                self.advance()
            else:
                self.advance()  # skip unexpected tokens
        # Optional result token
        if self.current.type == Token.RESULT:
            # Store result in headers maybe? We'll ignore for now.
            self.advance()

    def _parse_variation(self, parent: MoveNode):
        """Parse a variation (inside parentheses)."""
        # The first move of the variation becomes a child of `parent`.
        if self.current.type == Token.MOVE:
            move_str = self.current.value
            move = fpgn_to_move(move_str)
            if move:
                var_node = parent.add_variation(move)
                self._parse_move_suffix(var_node)
                self.advance()
                # Now parse the rest of the variation as a normal move text
                self._parse_movetext(var_node)
        self.expect(Token.VARIATION_END)

    def _parse_move_suffix(self, node: MoveNode):
        """Parse NAGs and comments that follow a move."""
        # We need to look ahead but not consume move tokens.
        # We'll peek the next token.
        while self.pos + 1 < len(self.tokens):
            nxt = self.tokens[self.pos + 1]
            if nxt.type == Token.NAG:
                node.nags.append(int(nxt.value))
                self.advance()  # consume NAG
            elif nxt.type == Token.COMMENT:
                node.comment_after += (" " + nxt.value).strip()
                self.advance()
            else:
                break

    def _last_move_node(self, node: MoveNode) -> Optional[MoveNode]:
        """Return the last move node in the main line from `node`."""
        if node.next_main is None:
            return node if node.move else None
        last = node.next_main
        while last.next_main:
            last = last.next_main
        return last


# ----------------------------------------------------------------------
#  High‑level reader
# ----------------------------------------------------------------------
class FPGNReader:
    @staticmethod
    def read_file(filepath: str) -> List[Tuple[Dict[str, str], List[Move]]]:
        """
        Returns a list of (headers, moves) for each game in the file.
        moves: list of Move objects (main line only, for backward compatibility).
        For full tree, use read_file_tree().
        """
        games = []
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        raw_games = re.split(r'\n\s*\n', content.strip())
        for raw_game in raw_games:
            if not raw_game.strip():
                continue
            tokens = tokenize_fpgn(raw_game)
            parser = FPGNParser(tokens)
            headers, root = parser.parse()
            # Extract main line moves
            moves = []
            node = root.next_main
            while node:
                moves.append(node.move)
                node = node.next_main
            games.append((headers, moves))
        return games

    @staticmethod
    def read_file_tree(filepath: str) -> List[Tuple[Dict[str, str], MoveNode]]:
        """
        Returns a list of (headers, root_node) for each game.
        The root_node contains the full move tree with variations.
        """
        games = []
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        raw_games = re.split(r'\n\s*\n', content.strip())
        for raw_game in raw_games:
            if not raw_game.strip():
                continue
            tokens = tokenize_fpgn(raw_game)
            parser = FPGNParser(tokens)
            headers, root = parser.parse()
            games.append((headers, root))
        return games


# ----------------------------------------------------------------------
#  Writer (unchanged, but now could be enhanced to write variations)
# ----------------------------------------------------------------------
class FPGNWriter:
    def __init__(self, filepath: str, headers: Dict[str, str]):
        self.file = open(filepath, 'w', encoding='utf-8')
        self.move_number = 1
        self.pending_white = None
        self._write_headers(headers)

    def _write_headers(self, headers: Dict[str, str]):
        for key, value in headers.items():
            self.file.write(f'[{key} "{value}"]\n')
        self.file.write('\n')

    def add_move(self, move: Move, moved_piece_type: PieceType, comment: Optional[str] = None):
        fpgn_str = move_to_fpgn(move, moved_piece_type)
        if self.pending_white is None:
            self.pending_white = fpgn_str
            if comment:
                self.pending_white += f" {{{comment}}}"
        else:
            white_str = self.pending_white
            black_str = fpgn_str
            if comment:
                black_str += f" {{{comment}}}"
            self.file.write(f"{self.move_number}. {white_str} {black_str} ")
            self.pending_white = None
            self.move_number += 1

    def add_result(self, result: str):
        if self.pending_white is not None:
            self.file.write(f"{self.move_number}. {self.pending_white} ")
            self.pending_white = None
        self.file.write(f"{result}\n")

    def close(self):
        if self.file and not self.file.closed:
            self.file.close()