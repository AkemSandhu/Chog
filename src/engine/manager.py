from PySide6.QtCore import QObject, Signal, QProcess, QTimer
from typing import Optional, List, Dict
from enum import Enum, auto
import os
import psutil
import time

from src.engine.protocol import (
    uci_to_move, parse_info_line, parse_bestmove_line, parse_ponder_move,
    build_go_command, build_position_command_fen, build_position_command_from_moves,
    build_learn_command, build_setoption_command, build_saveweights_command,
    build_loadweights_command
)

class EngineState(Enum):
    OFF = auto()
    INITIALIZING = auto()
    READY = auto()
    THINKING = auto()
    PONDERING = auto()
    STOPPING = auto()
    ERROR = auto()

class EngineManager(QObject):
    info_received = Signal(dict)
    bestmove_received = Signal(str)
    engine_ready = Signal()
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, engine_path: str, parent=None):
        super().__init__(parent)
        self.path_exe = engine_path
        self.process: Optional[QProcess] = None
        self._state = EngineState.OFF
        self._buffer = ""
        self._pending_options: List[tuple] = []
        self._multipv = 1
        self._move_stop_timer = QTimer(self)
        self._move_stop_timer.setSingleShot(True)
        self._move_stop_timer.timeout.connect(self._on_move_timer_timeout)
        self._current_bestmove = ""
        self._ponder_move = ""
        self._pondering = False
        self._ponderhit_sent = False

    @property
    def state(self):
        return self._state

    @property
    def is_thinking(self):
        return self._state in (EngineState.THINKING, EngineState.PONDERING)

    def start(self):
        if self.process is not None:
            self.close()
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)
        self.process.setProgram(self.path_exe)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._on_finished)

        self.process.start()
        if not self.process.waitForStarted(3000):
            self.error_occurred.emit(f"Engine {self.path_exe} failed to start")
            return
        self._state = EngineState.INITIALIZING
        self._send_command("chog")   # CUEP handshake

    def close(self):
        if self._state == EngineState.OFF:
            return
        self._move_stop_timer.stop()
        if self.process and self.process.state() != QProcess.NotRunning:
            self._send_command("quit")
            if not self.process.waitForFinished(2000):
                self._kill_process_tree()
        self._state = EngineState.OFF
        if self.process:
            self.process = None
        self.finished.emit()

    def _kill_process_tree(self):
        if self.process is None:
            return
        try:
            pid = self.process.processId()
            if pid > 0:
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.terminate()
                psutil.wait_procs(children, timeout=2)
                for child in children:
                    if child.is_running():
                        child.kill()
                if parent.is_running():
                    parent.terminate()
                    parent.wait(timeout=2)
                    if parent.is_running():
                        parent.kill()
        except (psutil.NoSuchProcess, Exception):
            pass
        self.process.kill()
        self.process.waitForFinished(1000)

    def set_multipv(self, value: int):
        self._multipv = value
        if self._state in (EngineState.READY, EngineState.THINKING):
            self._set_option("MultiPV", str(value))

    def set_option(self, name: str, value: str):
        if self._state in (EngineState.READY, EngineState.THINKING):
            self._set_option(name, value)
        else:
            self._pending_options.append((name, value))

    def _set_option(self, name: str, value: str):
        self._send_command(f"setoption name {name} value {value}")

    def isready(self):
        if self._state in (EngineState.READY, EngineState.THINKING):
            self._send_command("isready")

    def set_position(self, fen_or_moves, moves_list: List[str] = None):
        if isinstance(fen_or_moves, list):  # list of Move
            cmd = build_position_command_from_moves(fen_or_moves)
        else:
            cmd = build_position_command_fen(fen_or_moves, moves_list)
        self._send_command(cmd)

    def go(self, movetime: int = None, depth: int = None, nodes: int = None,
           infinite: bool = False, wtime: int = None, btime: int = None,
           winc: int = None, binc: int = None, ponder: bool = False):
        if self._state not in (EngineState.READY, EngineState.PONDERING):
            return
        cmd = build_go_command(wtime=wtime, btime=btime, movetime=movetime,
                               depth=depth, nodes=nodes, infinite=infinite,
                               ponder=ponder, winc=winc, binc=binc)
        self._current_bestmove = ""
        self._state = EngineState.THINKING if not ponder else EngineState.PONDERING
        self._pondering = ponder
        self._send_command(cmd)
        if movetime and movetime > 0:
            self._move_stop_timer.start(movetime + 200)

    def ponderhit(self):
        """Called when the opponent has moved; switches from pondering to thinking."""
        if self._state == EngineState.PONDERING:
            self._send_command("ponderhit")
            self._state = EngineState.THINKING
            self._pondering = False

    def stop(self):
        if self._state in (EngineState.THINKING, EngineState.PONDERING):
            self._move_stop_timer.stop()
            self._state = EngineState.STOPPING
            self._send_command("stop")

    def _on_move_timer_timeout(self):
        if self._state == EngineState.THINKING:
            self.stop()

    def send_command(self, command: str):
        self._send_command(command)

    # ----------------------- Internal -----------------------
    def _send_command(self, cmd: str):
        if self.process and self.process.state() == QProcess.Running:
            self.process.write((cmd + "\n").encode())

    def _read_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._process_line(line.strip())

    def _read_stderr(self):
        data = self.process.readAllStandardError().data().decode()
        if data:
            self.error_occurred.emit(f"Engine stderr: {data.strip()}")

    def _process_line(self, line: str):
        if not line:
            return
        # Handshake
        if self._state == EngineState.INITIALIZING:
            if line == "chogok":
                self._state = EngineState.READY
                for name, value in self._pending_options:
                    self._set_option(name, value)
                self._pending_options.clear()
                self._set_option("MultiPV", str(self._multipv))
                self._send_command("isready")
            elif line.startswith("id ") or line.startswith("option "):
                pass  # store engine info if desired
        elif self._state == EngineState.READY:
            if line == "readyok":
                self.engine_ready.emit()
        elif self._state in (EngineState.THINKING, EngineState.PONDERING, EngineState.STOPPING):
            if line.startswith("info "):
                info = parse_info_line(line)
                if info:
                    self.info_received.emit(info)
            elif line.startswith("bestmove "):
                best = parse_bestmove_line(line)
                if best:
                    self._current_bestmove = best
                    # Check for ponder move
                    ponder_move = parse_ponder_move(line)
                    if ponder_move and self._pondering:
                        # Engine expects us to use ponder move for pondering
                        pass  # we store it; next go with ponder will use it
                    self._state = EngineState.READY
                    self._move_stop_timer.stop()
                    self.bestmove_received.emit(best)

    def _on_finished(self, exit_code, exit_status):
        self._state = EngineState.OFF
        self.finished.emit()