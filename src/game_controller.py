from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QMessageBox, QMenu
from PySide6.QtGui import QCursor
from typing import Optional, List, Tuple
from datetime import datetime
import os

from src.core.board import Board
from src.core.pieces import Colour, PieceType, Piece, PIECE_SYMBOLS, PROMOTABLE_TYPES, PROMOTION_TARGETS
from src.core.movegen import Move, _is_promotion_zone
from src.core.rules import legal_moves, material_score
from src.core.game_state import GameState, game_result
from src.core.variations import MoveNode
from src.io.fpgn import FPGNWriter, move_to_fpgn, FPGNReader
from src.engine.manager import EngineManager
from src.engine.protocol import uci_to_move
from src.engine.multi_response import MultiEngineResponse, EngineResponse
from src.core.analysis_db import AnalysisDB
from src.ui.board_widget import BoardWidget, BoardArrow, BoardMarker
from src.ui.move_list import MoveListWidget
from src.ui.clock_widget import ClockWidget
from src.ui.promotion_dialog import PromotionDialog
from src.ui.sound_manager import SoundManager


class GameController(QObject):
    move_made = Signal()
    game_ended = Signal(str)
    status_update = Signal(str)
    position_changed = Signal()
    variations_changed = Signal()
    game_mode_changed = Signal(str)

    def __init__(self,
                 board_widget: BoardWidget,
                 move_list: MoveListWidget,
                 white_clock: ClockWidget,
                 black_clock: ClockWidget,
                 white_engine_path: Optional[str] = None,
                 black_engine_path: Optional[str] = None,
                 time_control_seconds: int = 600,
                 increment_seconds: int = 0,
                 animation_enabled: bool = True,
                 sound_manager: Optional[SoundManager] = None):
        super().__init__()
        self.board_widget = board_widget
        self.move_list = move_list
        self.white_clock = white_clock
        self.black_clock = black_clock
        self.time_control = time_control_seconds
        self.increment = increment_seconds
        self.animation_enabled = animation_enabled
        self.sound_manager = sound_manager

        self.state = GameState()
        self.selected_square = None
        self.current_legal_moves: List[Move] = []
        self.fpgn_writer: Optional[FPGNWriter] = None
        self.game_active = False
        self.engine_thinking = False
        self.review_mode = False

        self.current_ply = -1
        self.clock_auto_start = False

        self.root = MoveNode(None, None)
        self.current_node = self.root
        self.move_history: List[Move] = []
        self.comments: List[str] = []
        self.move_indicators: List[str] = []

        self.analysis_db = AnalysisDB(os.path.join("config", "analysis.db"))

        self.white_clock.set_time(time_control_seconds, increment_seconds)
        self.black_clock.set_time(time_control_seconds, increment_seconds)

        self.white_engine: Optional[EngineManager] = None
        self.black_engine: Optional[EngineManager] = None
        if white_engine_path:
            self.white_engine = EngineManager(white_engine_path)
            self.white_engine.bestmove_received.connect(self._on_engine_bestmove)
            self.white_engine.info_received.connect(self._on_engine_info)
            self.white_engine.error_occurred.connect(self._on_engine_error)
        if black_engine_path:
            self.black_engine = EngineManager(black_engine_path)
            self.black_engine.bestmove_received.connect(self._on_engine_bestmove)
            self.black_engine.info_received.connect(self._on_engine_info)
            self.black_engine.error_occurred.connect(self._on_engine_error)

        self.board_widget.square_clicked.connect(self._on_square_clicked)
        self.move_list.move_selected.connect(self._goto_ply)
        self.move_list.takeback_requested.connect(self.takeback)
        self.move_list.delete_move_requested.connect(self.delete_move)
        self.move_list.new_variation_requested.connect(self.add_variation)
        self.move_list.switch_variation_requested.connect(self.switch_variation)
        self.move_list.promote_variation_requested.connect(self.promote_variation)
        self.move_list.list_variations_requested.connect(self._on_list_variations)
        self.move_list.save_analysis_requested.connect(self.save_current_analysis)
        self.move_list.load_analysis_requested.connect(self.load_analysis)
        self.white_clock.timeout.connect(self._on_timeout)
        self.black_clock.timeout.connect(self._on_timeout)

        self.loaded_games: List[Tuple[str, MoveNode]] = []
        self.current_game_index: int = -1

        # Variation mode: when True, all moves go as variations of _variation_parent
        self._in_variation = False
        self._variation_parent: Optional[MoveNode] = None

    # -----------------------------------------------------------------
    def start_new_game(self):
        self._stop_engines()
        self.board_widget._animating = False
        self.state = GameState()
        self.selected_square = None
        self.current_legal_moves = []
        self.move_history.clear()
        self.comments.clear()
        self.move_indicators.clear()
        self.move_list.clear_moves()
        self.root = MoveNode(None, None)
        self.current_node = self.root
        self._in_variation = False
        self._variation_parent = None
        self.white_clock.reset()
        self.black_clock.reset()
        self.white_clock.set_time(self.time_control, self.increment)
        self.black_clock.set_time(self.time_control, self.increment)
        self.board_widget.set_board(self.state.board)
        self.board_widget.set_selected(None, [])
        self.board_widget.set_last_move(None)
        self.board_widget.clear_annotations()
        self.fpgn_writer = None
        self.game_active = True
        self.review_mode = False
        self.engine_thinking = False
        self.current_ply = -1
        self._start_engines()
        self._start_turn()
        self.position_changed.emit()
        self.update_captured_display()
        self.game_mode_changed.emit("playing")
        self.status_update.emit("White's turn")

    def close_review(self):
        self._stop_engines()
        self.start_new_game()

    def _stop_engines(self):
        if self.white_engine: self.white_engine.stop()
        if self.black_engine: self.black_engine.stop()

    def _start_engines(self):
        if self.white_engine: self.white_engine.start()
        if self.black_engine: self.black_engine.start()

    def _init_recording(self):
        os.makedirs("games", exist_ok=True)
        filename = f"games/{datetime.now().strftime('%Y%m%d_%H%M%S')}.fpgn"
        self.fpgn_writer = FPGNWriter(filename, {
            "Event": "Casual Game",
            "Site": "Local",
            "Date": datetime.now().strftime("%Y.%m.%d"),
            "Round": "?",
            "White": "Player" if not self.white_engine else "Engine White",
            "Black": "Player" if not self.black_engine else "Engine Black",
            "Variant": "Fusion"
        })

    def save_game(self):
        """Manually save the current game, replaying to get correct piece types."""
        if not self.move_history:
            self.status_update.emit("No moves to save.")
            return
        self._init_recording()
        temp_state = GameState()
        for move in self.move_history:
            piece = temp_state.board.get_piece(move.from_r, move.from_c)
            ptype = piece.ptype if piece else PieceType.PAWN
            self.fpgn_writer.add_move(move, ptype, comment="")
            temp_state.make_move(move)
        result = game_result(self.state)
        result_str = "*"
        if result is not None:
            if result[0] == 'white':
                result_str = "1-0"
            elif result[0] == 'black':
                result_str = "0-1"
            elif result[0] == 'draw':
                result_str = "1/2-1/2"
        self.fpgn_writer.add_result(result_str)
        self.fpgn_writer.close()
        self.status_update.emit("Game saved.")

    # -----------------------------------------------------------------
    def _current_engine(self) -> Optional[EngineManager]:
        return self.white_engine if self.state.turn == Colour.WHITE else self.black_engine

    def _start_turn(self):
        if not self.game_active:
            return
        result = game_result(self.state)
        if result is not None:
            self._handle_game_end(result)
            return

        if not self.review_mode and self.clock_auto_start:
            if self.state.turn == Colour.WHITE:
                self.white_clock.start()
                self.black_clock.stop()
            else:
                self.black_clock.start()
                self.white_clock.stop()

        engine = self._current_engine()
        if engine and not self.engine_thinking and not self.review_mode:
            engine.send_position(self.move_history)
            engine.send_go(movetime=10000)
            self.engine_thinking = True
            self.status_update.emit("Engine thinking...")
        else:
            self.status_update.emit(f"{'White' if self.state.turn == Colour.WHITE else 'Black'}'s turn")

    # -----------------------------------------------------------------
    def _on_square_clicked(self, row: int, col: int):
        if not self.game_active or self.engine_thinking or self.review_mode:
            return
        if self._current_engine() is not None:
            return
        if self.selected_square is None:
            piece = self.state.board.get_piece(row, col)
            if piece and piece.colour == self.state.turn:
                self.selected_square = (row, col)
                all_legal = legal_moves(self.state.board, self.state.turn)
                self.current_legal_moves = [m for m in all_legal if m.from_r == row and m.from_c == col]
                dests = [(m.to_r, m.to_c) for m in self.current_legal_moves]
                self.board_widget.set_selected((row, col), dests)
                self.status_update.emit(f"Selected {piece.symbol()}")
        else:
            src_r, src_c = self.selected_square
            for move in self.current_legal_moves:
                if move.to_r == row and move.to_c == col:
                    final_move = self._handle_promotion(move)
                    if final_move is None:
                        return
                    self._execute_move(final_move)
                    return
            piece = self.state.board.get_piece(row, col)
            if piece and piece.colour == self.state.turn:
                self.selected_square = (row, col)
                all_legal = legal_moves(self.state.board, self.state.turn)
                self.current_legal_moves = [m for m in all_legal if m.from_r == row and m.from_c == col]
                dests = [(m.to_r, m.to_c) for m in self.current_legal_moves]
                self.board_widget.set_selected((row, col), dests)
            else:
                self.selected_square = None
                self.current_legal_moves = []
                self.board_widget.set_selected(None, [])

    # -----------------------------------------------------------------
    # Promotion – rules as specified
    # -----------------------------------------------------------------
    def _handle_promotion(self, move: Move) -> Optional[Move]:
        piece = self.state.board.get_piece(move.from_r, move.from_c)
        if piece.ptype not in PROMOTABLE_TYPES:
            return move

        in_zone = _is_promotion_zone(move.to_r, piece.colour)
        if not in_zone:
            return move

        colour = piece.colour
        ptype = piece.ptype

        forced = False
        if colour == Colour.WHITE:
            if ptype in (PieceType.PAWN, PieceType.LANCE, PieceType.EAGLE):
                if move.to_r == 9:
                    forced = True
            elif ptype == PieceType.HORSE:
                if move.to_r == 8:
                    forced = True
        else:
            if ptype in (PieceType.PAWN, PieceType.LANCE, PieceType.EAGLE):
                if move.to_r == 0:
                    forced = True
            elif ptype == PieceType.HORSE:
                if move.to_r == 1:
                    forced = True

        if forced and ptype != PieceType.PAWN:
            target = PROMOTION_TARGETS[ptype][0]
            return Move(move.from_r, move.from_c, move.to_r, move.to_c, target)

        dlg = PromotionDialog(ptype, colour, forced)
        if forced:
            if dlg.exec() == QDialog.Accepted and dlg.chosen_piece:
                return Move(move.from_r, move.from_c, move.to_r, move.to_c, dlg.chosen_piece)
            return None
        else:
            if dlg.exec() == QDialog.Accepted and dlg.chosen_piece:
                return Move(move.from_r, move.from_c, move.to_r, move.to_c, dlg.chosen_piece)
            return Move(move.from_r, move.from_c, move.to_r, move.to_c)

    # -----------------------------------------------------------------
    def _execute_move(self, move: Move, comment: str = ""):
        piece = self.state.board.get_piece(move.from_r, move.from_c)
        move_str = move_to_fpgn(move, piece.ptype)
        parent_node = self.current_node

        def apply_move_after_animation():
            if not self.review_mode:
                if piece.colour == Colour.WHITE:
                    self.white_clock.stop()
                else:
                    self.black_clock.stop()

            self.state.make_move(move)
            self.move_history.append(move)
            self.comments.append(comment)
            indicator = ""
            if self._in_variation:
                var_node = parent_node.add_variation(move)
                self.current_node = var_node
                self._variation_parent = parent_node  # stay in variation mode
                indicator = "V"
            else:
                new_node = parent_node.add_main_move(move)
                self.current_node = new_node
                if parent_node.children and self.move_indicators:
                    self.move_indicators[-1] = "V"
            self.move_indicators.append(indicator)
            self.move_list.add_move(move_str, piece.colour == Colour.WHITE, comment, "", indicator)

            self.board_widget.set_board(self.state.board)
            self.board_widget.set_last_move((move.from_r, move.from_c, move.to_r, move.to_c))
            self.selected_square = None
            self.current_legal_moves = []
            self.board_widget.set_selected(None, [])

            if not self.review_mode and self.clock_auto_start:
                if piece.colour == Colour.WHITE:
                    self.white_clock.add_increment()
                else:
                    self.black_clock.add_increment()

            self.current_ply = len(self.move_history) - 1
            self.position_changed.emit()
            self.move_made.emit()
            self.update_captured_display()

            if self.sound_manager and not self.review_mode:
                self.sound_manager.play("move")

            result = game_result(self.state)
            if result is not None:
                self._handle_game_end(result)
            else:
                self._start_turn()

        if self.animation_enabled and not self.review_mode:
            self.board_widget.animate_move(move.from_r, move.from_c, move.to_r, move.to_c,
                                           piece, apply_move_after_animation)
        else:
            apply_move_after_animation()

    @staticmethod
    def _apply_move_to_board(board: Board, move: Move):
        piece = board.get_piece(move.from_r, move.from_c)
        board.clear_square(move.from_r, move.from_c)
        if move.promotion:
            piece = Piece(move.promotion, piece.colour)
        board.set_piece(move.to_r, move.to_c, piece)

    def _resolve_promotion_placeholder(self, move: Move, board: Board) -> Move:
        if move.promotion == PieceType.BERS:
            piece = board.get_piece(move.from_r, move.from_c)
            if piece and piece.ptype in PROMOTABLE_TYPES and piece.ptype != PieceType.PAWN:
                targets = PROMOTION_TARGETS[piece.ptype]
                if targets:
                    return Move(move.from_r, move.from_c, move.to_r, move.to_c, targets[0])
        return move

    # -----------------------------------------------------------------
    def _on_engine_bestmove(self, uci_str: str):
        if not self.engine_thinking:
            return
        self.engine_thinking = False
        if uci_str == "0000":
            self._handle_engine_resign()
            return
        move = uci_to_move(uci_str)
        if move is None:
            self._handle_engine_illegal_move("Invalid move format")
            return
        legal = legal_moves(self.state.board, self.state.turn)
        valid = any(m.from_r == move.from_r and m.from_c == move.from_c and
                    m.to_r == move.to_r and m.to_c == move.to_c and
                    m.promotion == move.promotion for m in legal)
        if not valid:
            self._handle_engine_illegal_move(f"Illegal move: {uci_str}")
            return
        self._execute_move(move)

    def _on_engine_info(self, info: dict): pass
    def _on_engine_error(self, err_msg: str):
        self.status_update.emit(f"Engine error: {err_msg}")

    def _handle_engine_resign(self):
        self._end_game(self.state.turn.opponent(), "resignation")
    def _handle_engine_illegal_move(self, reason: str):
        self._end_game(self.state.turn.opponent(), "illegal move")

    # -----------------------------------------------------------------
    def takeback(self, ply: int = -1):
        if not self.review_mode:
            self.status_update.emit("Takeback only available in review mode.")
            return
        if not self.move_history:
            return
        if ply == -1:
            ply = len(self.move_history) - 1
        elif ply >= len(self.move_history):
            return
        while len(self.move_history) > ply:
            self.move_history.pop()
            self.comments.pop()
            self.move_indicators.pop()
            self.state.unmake_move()
        self._rebuild_tree_from_history()
        self._refresh_after_takeback()

    def delete_move(self, ply: int):
        if not self.review_mode:
            self.status_update.emit("Delete only available in review mode.")
            return
        if ply < 0 or ply >= len(self.move_history):
            return
        remaining_moves = self.move_history[ply+1:]
        remaining_comments = self.comments[ply+1:]
        remaining_indicators = self.move_indicators[ply+1:]
        while len(self.move_history) > ply:
            self.move_history.pop()
            self.comments.pop()
            self.move_indicators.pop()
            self.state.unmake_move()
        for move in remaining_moves:
            self.state.make_move(move)
            self.move_history.append(move)
        self.comments.extend(remaining_comments)
        self.move_indicators.extend(remaining_indicators)
        self._rebuild_tree_from_history()
        self._refresh_after_takeback()

    def _rebuild_tree_from_history(self):
        self.root = MoveNode(None, None)
        self.current_node = self.root
        for move in self.move_history:
            self.current_node = self.current_node.add_main_move(move)

    def _refresh_after_takeback(self):
        self.move_list.clear_moves()
        for i, move in enumerate(self.move_history):
            piece = self.state.board.get_piece(move.from_r, move.from_c)
            move_str = move_to_fpgn(move, piece.ptype)
            self.move_list.add_move(move_str, piece.colour == Colour.WHITE, self.comments[i], "", self.move_indicators[i])
        self.board_widget.set_board(self.state.board)
        self.board_widget.set_last_move(None)
        if self.move_history:
            last = self.move_history[-1]
            self.board_widget.set_last_move((last.from_r, last.from_c, last.to_r, last.to_c))
        self.current_ply = len(self.move_history) - 1
        self.position_changed.emit()
        self.update_captured_display()
        if not self.review_mode and self.game_active:
            self._start_turn()

    # -----------------------------------------------------------------
    # Variation management
    # -----------------------------------------------------------------
    def add_variation(self):
        """Enter variation mode. All subsequent moves become a variation of the current node."""
        self._in_variation = True
        self._variation_parent = self.current_node
        self.status_update.emit("Variation mode ON. Right-click a move and choose 'Return to main line' to exit.")

    def return_to_main_line(self):
        """Exit variation mode and return to the main line."""
        self._in_variation = False
        self._variation_parent = None
        # Replay main line from root
        self.state = GameState()
        node = self.root.next_main
        self.move_history.clear()
        self.comments.clear()
        self.move_indicators.clear()
        self.move_list.clear_moves()
        while node:
            self.state.make_move(node.move)
            self.move_history.append(node.move)
            move_str = move_to_fpgn(node.move, PieceType.PAWN)
            self.move_list.add_move(move_str, node.move and self.state.turn == Colour.BLACK, "", "", "")
            self.comments.append("")
            self.move_indicators.append("")
            self.current_node = node
            node = node.next_main
        self.board_widget.set_board(self.state.board)
        self.position_changed.emit()
        self.status_update.emit("Returned to main line.")

    def switch_variation(self, node: MoveNode):
        self.state = GameState()
        path = []
        n = node
        while n.parent is not None:
            path.append(n.move)
            n = n.parent
        path.reverse()
        self.move_history = path
        self.comments = [""] * len(path)
        self.move_indicators = [""] * len(path)
        for move in path:
            self.state.make_move(move)
        self.current_node = node
        self.move_list.clear_moves()
        for i, move in enumerate(path):
            piece = self.state.board.get_piece(move.from_r, move.from_c)
            move_str = move_to_fpgn(move, piece.ptype)
            self.move_list.add_move(move_str, piece.colour == Colour.WHITE, "", "", "")
        self.board_widget.set_board(self.state.board)
        if path:
            last = path[-1]
            self.board_widget.set_last_move((last.from_r, last.from_c, last.to_r, last.to_c))
        else:
            self.board_widget.set_last_move(None)
        self.position_changed.emit()
        self.variations_changed.emit()

    def promote_variation(self, node: MoveNode):
        parent = node.parent
        if parent:
            old_main = parent.next_main
            parent.children.remove(node)
            if old_main:
                parent.children.append(old_main)
            parent.next_main = node
            self._replay_to_node(node)
            self.variations_changed.emit()

    def _replay_to_node(self, target_node: MoveNode):
        self.state = GameState()
        node = self.root.next_main
        self.move_history.clear()
        while node and node != target_node.next_main:
            self.state.make_move(node.move)
            self.move_history.append(node.move)
            if node == target_node:
                break
            node = node.next_main
        self.board_widget.set_board(self.state.board)
        self.position_changed.emit()

    def _on_list_variations(self, ply: int):
        node = self.root
        for i in range(ply + 1):
            if node is None:
                break
            node = node.next_main
        if node is None or not node.children:
            self.status_update.emit("No variations here.")
            return
        menu = QMenu(self.board_widget)
        for var_node in node.children:
            pv_list = var_node.to_list()
            label = " ".join(move_to_uci(m) for m in pv_list[:5])
            action = menu.addAction(label)
            action.triggered.connect(lambda checked, n=var_node: self.switch_variation(n))
        menu.addSeparator()
        # Option to return to main line
        if self._in_variation:
            ret_action = menu.addAction("Return to main line")
            ret_action.triggered.connect(self.return_to_main_line)
        menu.exec(QCursor.pos())

    # -----------------------------------------------------------------
    def save_current_analysis(self, pv: str, mrm: MultiEngineResponse, movetime: int = 0, depth: int = 0):
        if mrm is not None:
            self.analysis_db.save_analysis(self.state, pv, mrm, movetime, depth)

    def load_analysis(self, pv: str, name: str) -> Optional[MultiEngineResponse]:
        return self.analysis_db.load_analysis(self.state, pv, name)

    # -----------------------------------------------------------------
    def update_captured_display(self):
        white_score = material_score(self.state.board, Colour.WHITE)
        black_score = material_score(self.state.board, Colour.BLACK)
        diff = white_score - black_score
        if diff > 0:
            self.white_clock.set_captured(f"<b>+{diff}</b>")
            self.black_clock.set_captured("")
        elif diff < 0:
            self.white_clock.set_captured("")
            self.black_clock.set_captured(f"<b>+{-diff}</b>")
        else:
            self.white_clock.set_captured("")
            self.black_clock.set_captured("")

    # -----------------------------------------------------------------
    def _handle_game_end(self, result):
        if result[0] == 'draw':
            score_diff = result[1]
            if score_diff > 0:
                win_desc = "White wins on tiebreak"
            elif score_diff < 0:
                win_desc = "Black wins on tiebreak"
            else:
                self._tiebreak_new_game()
                return
        else:
            winner_str = result[0]
            if winner_str == 'white':
                win_desc = "White wins"
            else:
                win_desc = "Black wins"

        self._end_game(win_desc)
        if self.sound_manager:
            self.sound_manager.play("game_end")

    def _end_game(self, reason: str):
        self.white_clock.stop()
        self.black_clock.stop()
        self.game_active = False
        self.game_ended.emit(reason)

    def _tiebreak_new_game(self):
        self.white_engine, self.black_engine = self.black_engine, self.white_engine
        self.start_new_game()

    def _on_timeout(self):
        if self.white_clock.time_left_ms == 0:
            self._end_game("White timeout")
        elif self.black_clock.time_left_ms == 0:
            self._end_game("Black timeout")

    # -----------------------------------------------------------------
    def _goto_ply(self, ply: int):
        if ply < 0 or ply >= len(self.move_history):
            return
        self.state = GameState()
        self.board_widget.set_board(self.state.board)
        self.board_widget.set_last_move(None)
        for i in range(ply + 1):
            move = self.move_history[i]
            self.state.make_move(move)
            if i == ply:
                self.board_widget.set_last_move((move.from_r, move.from_c, move.to_r, move.to_c))
        self.board_widget.set_board(self.state.board)
        self.move_list.set_current_ply(ply)
        self.current_ply = ply
        self.position_changed.emit()
        self.white_clock.stop()
        self.black_clock.stop()
        self.update_captured_display()

    def get_legal_moves(self) -> List[Move]:
        return legal_moves(self.state.board, self.state.turn)

    # -----------------------------------------------------------------
    def load_games_from_fpgn(self, file_path: str):
        games = FPGNReader.read_file_tree(file_path)
        if not games:
            games_simple = FPGNReader.read_file(file_path)
            if games_simple:
                games = []
                for headers, moves in games_simple:
                    root = MoveNode(None, None)
                    node = root
                    for m in moves:
                        node = node.add_main_move(m)
                    games.append((headers, root))
        if not games:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if content.strip():
                from src.io.fpgn import tokenize_fpgn, FPGNParser
                tokens = tokenize_fpgn(content)
                parser = FPGNParser(tokens)
                headers, root = parser.parse()
                if root.next_main:
                    games = [(headers, root)]
        if not games:
            self.status_update.emit("No valid games found.")
            return
        self.loaded_games = [(file_path, root) for _, root in games]
        self.current_game_index = 0
        self._load_game_by_index(0)

    def _load_game_by_index(self, index: int):
        if index < 0 or index >= len(self.loaded_games):
            return
        self.current_game_index = index
        file_path, root = self.loaded_games[index]
        self._stop_engines()
        self.board_widget._animating = False
        self.state = GameState()
        self.move_history.clear()
        self.comments.clear()
        self.move_indicators.clear()
        self.move_list.clear_moves()
        self.root = root
        self.current_node = root
        self._in_variation = False
        self._variation_parent = None
        self.white_clock.stop()
        self.black_clock.stop()
        self.game_active = False
        self.review_mode = True
        self.engine_thinking = False
        self.selected_square = None
        self.current_legal_moves = []
        self.board_widget.set_board(self.state.board)
        self.board_widget.set_last_move(None)

        node = root.next_main
        while node:
            move = self._resolve_promotion_placeholder(node.move, self.state.board)
            self.state.make_move(move)
            self.move_history.append(move)
            move_str = move_to_fpgn(move, PieceType.PAWN)
            indicator = "V" if node.children else ""
            self.move_list.add_move(move_str, move and self.state.turn == Colour.BLACK, node.comment_after, "", indicator)
            self.comments.append(node.comment_after)
            self.move_indicators.append(indicator)
            self.current_node = node
            node = node.next_main

        self.board_widget.set_board(self.state.board)
        if self.move_history:
            last = self.move_history[-1]
            self.board_widget.set_last_move((last.from_r, last.from_c, last.to_r, last.to_c))
        self.current_ply = len(self.move_history) - 1
        self.board_widget.update()
        self.position_changed.emit()
        self.update_captured_display()
        self.game_mode_changed.emit("review")
        self.status_update.emit(f"Loaded game {index+1}/{len(self.loaded_games)} from {file_path}")

    def previous_game(self):
        if self.loaded_games and self.current_game_index > 0:
            self._load_game_by_index(self.current_game_index - 1)

    def next_game(self):
        if self.loaded_games and self.current_game_index < len(self.loaded_games) - 1:
            self._load_game_by_index(self.current_game_index + 1)

    def load_game_from_fpgn(self, file_path: str, game_index: int = 0):
        self.load_games_from_fpgn(file_path)
        if self.loaded_games and game_index < len(self.loaded_games):
            self._load_game_by_index(game_index)