from __future__ import annotations
import re
from typing import List, Dict, Tuple, Optional, TextIO
from src.core.pieces import PieceType, PIECE_SYMBOLS
from src.core.movegen import Move
from src.core.variations import MoveNode

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


class Token:
    TAG, MOVE, NAG, COMMENT, VARIATION_START, VARIATION_END, RESULT, EOF = range(8)

    def __init__(self, type_: int, value: str = ""):
        self.type = type_
        self.value = value


def tokenize_fpgn(text: str) -> List[Token]:
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == '[':
            j = text.index(']', i)
            tag_str = text[i+1:j]
            tokens.append(Token(Token.TAG, tag_str.strip()))
            i = j + 1
        elif c == '{':
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
            j = i + 4
            if j < n and text[j] == '=':
                j += 1
                while j < n and text[j].isalpha():
                    j += 1
            token_str = text[i:j]
            tokens.append(Token(Token.MOVE, token_str))
            i = j
        elif c.isdigit():
            j = i
            while j < n and (text[j].isdigit() or text[j] == '.'):
                j += 1
            i = j
        else:
            i += 1
    tokens.append(Token(Token.EOF))
    return tokens


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
        headers = {}
        while self.current.type == Token.TAG:
            tag_str = self.current.value
            match = re.match(r'(\w+)\s+"(.*)"', tag_str)
            if match:
                headers[match.group(1)] = match.group(2)
            self.advance()

        root = MoveNode(None, None)
        self._parse_movetext(root)
        return headers, root

    def _parse_movetext(self, parent: MoveNode):
        while self.current.type != Token.EOF and self.current.type != Token.RESULT:
            if self.current.type == Token.VARIATION_START:
                self.advance()
                last_main = parent
                while last_main.next_main:
                    last_main = last_main.next_main
                if last_main.move:
                    self._parse_variation(last_main)
                else:
                    self._parse_variation(parent)
            elif self.current.type == Token.MOVE:
                move_str = self.current.value
                move = fpgn_to_move(move_str)
                if move:
                    node = parent.add_main_move(move)
                    self._parse_move_suffix(node)
                self.advance()
            elif self.current.type == Token.COMMENT:
                last = self._last_move_node(parent)
                if last and last.comment_after == "":
                    last.comment_after = self.current.value
                self.advance()
            else:
                self.advance()
        if self.current.type == Token.RESULT:
            self.advance()

    def _parse_variation(self, parent: MoveNode):
        if self.current.type == Token.MOVE:
            move_str = self.current.value
            move = fpgn_to_move(move_str)
            if move:
                var_node = parent.add_variation(move)
                self._parse_move_suffix(var_node)
                self.advance()
                self._parse_movetext(var_node)
        self.expect(Token.VARIATION_END)

    def _parse_move_suffix(self, node: MoveNode):
        while self.pos + 1 < len(self.tokens):
            nxt = self.tokens[self.pos + 1]
            if nxt.type == Token.NAG:
                node.nags.append(int(nxt.value))
                self.advance()
            elif nxt.type == Token.COMMENT:
                node.comment_after += (" " + nxt.value).strip()
                self.advance()
            else:
                break

    def _last_move_node(self, node: MoveNode) -> Optional[MoveNode]:
        if node.next_main is None:
            return node if node.move else None
        last = node.next_main
        while last.next_main:
            last = last.next_main
        return last


class FPGNReader:
    @staticmethod
    def read_file(filepath: str) -> List[Tuple[Dict[str, str], List[Move]]]:
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
            moves = []
            node = root.next_main
            while node:
                moves.append(node.move)
                node = node.next_main
            games.append((headers, moves))
        return games

    @staticmethod
    def read_file_tree(filepath: str) -> List[Tuple[Dict[str, str], MoveNode]]:
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

    def write_tree(self, root: MoveNode, result: str = "*"):
        lines = []
        self._collect_tree(root.next_main, lines, 1, True)
        if lines:
            last = lines[-1].rstrip()
            lines[-1] = last + f" {result}\n"
        else:
            self.file.write(f"{result}\n")
            return
        self.file.write("".join(lines))

    def _collect_tree(self, node: MoveNode, lines: list, move_number: int, is_white: bool):
        if node is None:
            return
        move_str = move_to_fpgn(node.move, PieceType.PAWN)
        if is_white:
            line = f"{move_number}. {move_str} "
        else:
            line = f"{move_str} "
            move_number += 1

        # Write each variation (recursively) – pass 'child', not child.next_main
        for child in node.children:
            var_lines = []
            self._collect_tree(child, var_lines, move_number, not is_white)
            if var_lines:
                line += "( " + " ".join(var_lines).strip() + " ) "

        lines.append(line)
        next_number = move_number + 1 if is_white else move_number
        self._collect_tree(node.next_main, lines, next_number, not is_white)

    def close(self):
        if self.file and not self.file.closed:
            self.file.close()