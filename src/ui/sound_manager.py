import os
import queue
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QApplication

class SoundManager:
    """Lazy‑loading sound player. Uses WAV files, falls back to system beep."""

    def __init__(self, sound_folder: str = "sounds"):
        self.sound_folder = sound_folder
        self._sounds: dict[str, QSoundEffect | None] = {}
        self._queue = queue.Queue()
        self._current = None
        os.makedirs(sound_folder, exist_ok=True)

    def _load(self, key: str) -> QSoundEffect | None:
        path = os.path.join(self.sound_folder, f"{key}.wav")
        if not os.path.isfile(path):
            return None
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(path))
        return effect

    def play(self, key: str) -> None:
        """Play a sound by key. If file missing, beep."""
        if key not in self._sounds:
            self._sounds[key] = self._load(key)
        effect = self._sounds.get(key)
        if effect is None:
            QApplication.beep()
            return
        self._queue.put(effect)
        if self._current is None or not self._current.isPlaying():
            self._next()

    def _next(self) -> None:
        if self._queue.empty():
            self._current = None
            return
        self._current = self._queue.get()
        self._current.play()
        # Check when finished
        QTimer.singleShot(100, self._check_finished)

    def _check_finished(self) -> None:
        if self._current and not self._current.isPlaying():
            self._next()
        elif self._current:
            QTimer.singleShot(100, self._check_finished)