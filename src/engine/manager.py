from PySide6.QtCore import QObject, Signal, QProcess
from typing import Optional, List
from chog.core.movegen import Move
from chog.engine.protocol import (
    uci_to_move, parse_info_line, parse_bestmove_line,
    build_position_command, build_go_command,
    build_learn_command, build_setoption_command,
    build_saveweights_command, build_loadweights_command
)

class EngineManager(QObject):
    info_received = Signal(dict)
    bestmove_received = Signal(str)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, engine_path: str, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)
        self.process.setProgram(engine_path)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._on_finished)
        self._buffer = ""
        self._bestmove_pending = False
        self._init_complete = False
        self._ready = False
        self._init_commands: List[str] = []

    def start(self):
        self.process.start()
        if not self.process.waitForStarted(3000):
            self.error_occurred.emit("Engine failed to start")
            return
        self._send_command("fv")

    def stop(self):
        if self.process.state() != QProcess.NotRunning:
            self._send_command("quit")
            if not self.process.waitForFinished(2000):
                self.process.kill()
                self.process.waitForFinished(1000)

    def send_command(self, command: str):
        if self._ready:
            self._write(command)
        else:
            self._init_commands.append(command)

    def send_position(self, moves: List[Move]):
        self.send_command(build_position_command(moves))

    def send_go(self, wtime: int = 60000, btime: int = 60000,
                movetime: int = None, depth: int = None, infinite: bool = False):
        cmd = build_go_command(wtime, btime, movetime, depth, infinite)
        self.send_command(cmd)
        self._bestmove_pending = True

    def send_stop(self):
        self._write("stop")

    # ---- Learning hooks ----
    def send_learn(self, fen: str, result: str, score: Optional[int] = None):
        cmd = build_learn_command(fen, result, score)
        self.send_command(cmd)

    def send_setoption(self, name: str, value: str):
        self.send_command(build_setoption_command(name, value))

    def send_save_weights(self, filepath: str):
        self.send_command(build_saveweights_command(filepath))

    def send_load_weights(self, filepath: str):
        self.send_command(build_loadweights_command(filepath))

    # ---- Internal ----
    def _write(self, text: str):
        self.process.write((text + "\n").encode())

    def _send_command(self, command: str):
        self._write(command)

    def _read_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._process_line(line.strip())

    def _read_stderr(self):
        data = self.process.readAllStandardError().data().decode()
        self.error_occurred.emit(f"Engine stderr: {data.strip()}")

    def _process_line(self, line: str):
        if not line:
            return
        if line.startswith("id "):
            return   # could store name/author
        if line == "fvok":
            self._init_complete = True
            for cmd in self._init_commands:
                self._write(cmd)
            self._init_commands.clear()
            return
        if line == "readyok":
            self._ready = True
            return
        info = parse_info_line(line)
        if info:
            self.info_received.emit(info)
            return
        best = parse_bestmove_line(line)
        if best:
            self._bestmove_pending = False
            self.bestmove_received.emit(best)
            return

    def _on_finished(self, exitCode, exitStatus):
        self._ready = False
        self.finished.emit()