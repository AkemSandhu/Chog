from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QMessageBox
from typing import Optional, List, Tuple, Dict
from datetime import datetime
import os

from src.core.board import Board
from src.core.pieces import Colour, PieceType, Piece, PIECE_SYMBOLS, PROMOTABLE_TYPES, PROMOTION_TARGETS
from src.core.movegen import Move
from src.core.rules import legal_moves, _is_promotion_zone, _piece_can_move_from, material_score
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
    game_mode_changed = Signal(str)   # 'playing' or 'review'

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

        # Variation tree
        self.root = MoveNode(None, None)
        self.current_node = self.root
        self.move_history: List[Move] = []
        self.comments: List[str] = []

        # Analysis database
        self.analysis_db = AnalysisDB(os.path.join("config", "analysis.db"))

        # Clocks setup
        self.white_clock.set_time(time_control_seconds, increment_seconds)
        self.black_clock.set_time(time_control_seconds, increment_seconds)

        # Engine setup
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

        # Connect UI signals
        self.board_widget.square_clicked.connect(self._on_square_clicked)
        self.move_list.move_selected.connect(self._goto_ply)
        self.move_list.takeback_requested.connect(self.takeback)
        self.move_list.delete_move_requested.connect(self.delete_move)
        self.move_list.new_variation_requested.connect(self.add_variation)
        self.move_list.switch_variation_requested.connect(self.switch_variation)
        self.move_list.promote_variation_requested.connect(self.promote_variation)
        self.move_list.save_analysis_requested.connect(self.save_current_analysis)
        self.move_list.load_analysis_requested.connect(self.load_analysis)
        self.white_clock.timeout.connect(self._on_timeout)
        self.black_clock.timeout.connect(self._on_timeout)

        # Multi-game navigation
        self.loaded_games: List[Tuple[str, List[Move]]] = []
        self.current_game_index: int = -1

        # Promotion toolbar (set by main window)
        self.promotion_toolbar = None

    # -----------------------------------------------------------------
    # Game lifecycle
    # -----------------------------------------------------------------
    def start_new_game(self):
        self._stop_engines()
        self.state = GameState()
        self.selected_square = None
        self.current_legal_moves = []
        self.move_history.clear()
        self.comments.clear()
        self.move_list.clear_moves()
        self.root = MoveNode(None, None)
        self.current_node = self.root
        self.white_clock.reset()
        self.black_clock.reset()
        self.white_clock.set_time(self.time_control, self.increment)
        self.black_clock.set_time(self.time_control, self.increment)
        self.board_widget.set_board(self.state.board)
        self.board_widget.set_selected(None, [])
        self.board_widget.set_last_move(None)
        self.board_widget.clear_annotations()
        self._init_recording()
        self.game_active = True
        self.review_mode = False
        self.engine_thinking = False
        self._start_engines()
        self._start_turn()
        self.position_changed.emit()
        self.update_captured_display()
        self.game_mode_changed.emit("playing")
        self.status_update.emit("White's turn")

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

    # -----------------------------------------------------------------
    # Turn management
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

        if not self.review_mode:
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
    # Human move handling
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

    def _handle_promotion(self, move: Move) -> Optional[Move]:
        piece = self.state.board.get_piece(move.from_r, move.from_c)
        if piece.ptype not in PROMOTABLE_TYPES:
            return move
        in_zone = _is_promotion_zone(move.to_r, piece.colour)
        if not in_zone:
            return move

        forced = False
        if move.promotion is None:
            temp_board = self.state.board.copy()
            self._apply_move_to_board(temp_board, move)
            if not _piece_can_move_from(temp_board, move.to_r, move.to_c, piece.ptype, piece.colour):
                forced = True

        if forced and piece.ptype != PieceType.PAWN:
            target = PROMOTION_TARGETS[piece.ptype][0]
            return Move(move.from_r, move.from_c, move.to_r, move.to_c, target)

        dlg = PromotionDialog(piece.ptype, piece.colour, forced)
        if forced:
            if dlg.exec() == QDialog.Accepted and dlg.chosen_piece:
                return Move(move.from_r, move.from_c, move.to_r, move.to_c, dlg.chosen_piece)
            return None
        else:
            if dlg.exec() == QDialog.Accepted and dlg.chosen_piece:
                return Move(move.from_r, move.from_c, move.to_r, move.to_c, dlg.chosen_piece)
            return Move(move.from_r, move.from_c, move.to_r, move.to_c)

    # -----------------------------------------------------------------
    # Execute move
    # -----------------------------------------------------------------
    def _execute_move(self, move: Move, comment: str = ""):
        piece = self.state.board.get_piece(move.from_r, move.from_c)
        move_str = move_to_fpgn(move, piece.ptype)

        def apply_move_after_animation():
            if not self.review_mode:
                if piece.colour == Colour.WHITE:
                    self.white_clock.stop()
                else:
                    self.black_clock.stop()

            if self.fpgn_writer and not self.review_mode:
                self.fpgn_writer.add_move(move, piece.ptype, comment=comment if comment else None)

            self.state.make_move(move)
            self.move_history.append(move)
            self.comments.append(comment)
            self.move_list.add_move(move_str, piece.colour == Colour.WHITE, comment)

            new_node = self.current_node.add_main_move(move)
            self.current_node = new_node

            self.board_widget.set_board(self.state.board)
            self.board_widget.set_last_move((move.from_r, move.from_c, move.to_r, move.to_c))
            self.selected_square = None
            self.current_legal_moves = []
            self.board_widget.set_selected(None, [])

            if not self.review_mode:
                if piece.colour == Colour.WHITE:
                    self.white_clock.add_increment()
                else:
                    self.black_clock.add_increment()

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

    # -----------------------------------------------------------------
    # Engine move handling
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
    # Takeback & Delete Move
    # -----------------------------------------------------------------
    def takeback(self, ply: int = -1):
        if not self.move_history:
            return
        if ply == -1:
            ply = len(self.move_history) - 1
        elif ply >= len(self.move_history):
            return
        while len(self.move_history) > ply:
            self.move_history.pop()
            self.comments.pop()
            self.state.unmake_move()
        self._rebuild_tree_from_history()
        self._refresh_after_takeback()

    def delete_move(self, ply: int):
        if ply < 0 or ply >= len(self.move_history):
            return
        remaining_moves = self.move_history[ply+1:]
        while len(self.move_history) > ply:
            self.move_history.pop()
            self.comments.pop()
            self.state.unmake_move()
        for move in remaining_moves:
            self.state.make_move(move)
            self.move_history.append(move)
            self.comments.append("")
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
            self.move_list.add_move(move_str, piece.colour == Colour.WHITE, self.comments[i])
        self.board_widget.set_board(self.state.board)
        self.board_widget.set_last_move(None)
        if self.move_history:
            last = self.move_history[-1]
            self.board_widget.set_last_move((last.from_r, last.from_c, last.to_r, last.to_c))
        self.position_changed.emit()
        self.update_captured_display()
        if not self.review_mode and self.game_active:
            self._start_turn()

    # -----------------------------------------------------------------
    # Variation management
    # -----------------------------------------------------------------
    def add_variation(self):
        self._adding_variation = True
        self.status_update.emit("Play moves for the new variation.")

    def switch_variation(self, node: MoveNode):
        if node.parent != self.current_node:
            return
        self.current_node = node
        self._replay_to_node(node)
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

    # -----------------------------------------------------------------
    # Analysis DB integration
    # -----------------------------------------------------------------
    def save_current_analysis(self, pv: str, mrm: MultiEngineResponse, movetime: int = 0, depth: int = 0):
        self.analysis_db.save_analysis(self.state, pv, mrm, movetime, depth)

    def load_analysis(self, pv: str, name: str) -> Optional[MultiEngineResponse]:
        return self.analysis_db.load_analysis(self.state, pv, name)

    # -----------------------------------------------------------------
    # Captured pieces display
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
    # Game end
    # -----------------------------------------------------------------
    def _handle_game_end(self, result):
        if result[0] == 'draw':
            score_diff = result[1]
            if score_diff > 0:
                winner, win_desc, fpgn_result = Colour.WHITE, "White wins on tiebreak", "1-0"
            elif score_diff < 0:
                winner, win_desc, fpgn_result = Colour.BLACK, "Black wins on tiebreak", "0-1"
            else:
                self._tiebreak_new_game()
                return
        else:
            winner_str = result[0]
            if winner_str == 'white':
                winner, win_desc, fpgn_result = Colour.WHITE, "White wins", "1-0"
            else:
                winner, win_desc, fpgn_result = Colour.BLACK, "Black wins", "0-1"
        self._end_game(winner, win_desc)
        if self.fpgn_writer:
            self.fpgn_writer.add_result(fpgn_result)
            self.fpgn_writer.close()
        if self.sound_manager:
            self.sound_manager.play("game_end")

    def _end_game(self, winner: Colour, reason: str):
        self.white_clock.stop()
        self.black_clock.stop()
        self.game_active = False
        self.game_ended.emit(reason)

    def _tiebreak_new_game(self):
        self.white_engine, self.black_engine = self.black_engine, self.white_engine
        if self.fpgn_writer:
            self.fpgn_writer.add_result("1/2-1/2")
            self.fpgn_writer.close()
        self.start_new_game()

    def _on_timeout(self):
        if self.white_clock.time_left_ms == 0:
            self._end_game(Colour.BLACK, "White timeout")
        elif self.black_clock.time_left_ms == 0:
            self._end_game(Colour.WHITE, "Black timeout")

    # -----------------------------------------------------------------
    # Navigation
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
        self.position_changed.emit()
        self.white_clock.stop()
        self.black_clock.stop()
        self.update_captured_display()

    def get_legal_moves(self) -> List[Move]:
        return legal_moves(self.state.board, self.state.turn)

    # -----------------------------------------------------------------
    # FPGN loading with multi-game support
    # -----------------------------------------------------------------
    def load_games_from_fpgn(self, file_path: str):
        games = FPGNReader.read_file(file_path)
        if not games:
            self.status_update.emit("No valid games found.")
            return
        self.loaded_games = [(file_path, moves) for _, moves in games]
        self.current_game_index = 0
        self._load_game_by_index(0)

    def _load_game_by_index(self, index: int):
        if index < 0 or index >= len(self.loaded_games):
            return
        self.current_game_index = index
        file_path, moves = self.loaded_games[index]
        self._stop_engines()
        self.state = GameState()
        self.move_history.clear()
        self.comments.clear()
        self.move_list.clear_moves()
        self.root = MoveNode(None, None)
        self.current_node = self.root
        self.white_clock.stop()
        self.black_clock.stop()
        self.game_active = False
        self.review_mode = True
        self.engine_thinking = False
        self.selected_square = None
        self.current_legal_moves = []
        self.board_widget.set_board(self.state.board)
        self.board_widget.set_last_move(None)
        for move in moves:
            piece = self.state.board.get_piece(move.from_r, move.from_c)
            if piece is None:
                continue
            self.state.make_move(move)
            self.move_history.append(move)
            move_str = move_to_fpgn(move, piece.ptype)
            self.move_list.add_move(move_str, piece.colour == Colour.WHITE, "")
            self.comments.append("")
            self.current_node = self.current_node.add_main_move(move)
        self.board_widget.set_board(self.state.board)
        if self.move_history:
            last = self.move_history[-1]
            self.board_widget.set_last_move((last.from_r, last.from_c, last.to_r, last.to_c))
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
        games = FPGNReader.read_file(file_path)
        if not games or game_index >= len(games):
            self.status_update.emit("No valid game found.")
            return
        self.loaded_games = [(file_path, moves) for _, moves in games]
        self.current_game_index = game_index
        self._load_game_by_index(game_index)