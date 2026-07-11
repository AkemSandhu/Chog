"""
Engine options for MasterLion, inspired by Stockfish's ucioption.cpp.
Supports standard UCI options: Hash, MultiPV, Move Overhead, etc.
"""
from typing import Any, Callable, Dict

class Option:
    def __init__(self, default_value: Any, otype: str = "spin",
                 minv: int = 0, maxv: int = 0, on_change: Callable = None):
        self.type = otype          # "spin", "check", "string", "button", "combo"
        self.min = minv
        self.max = maxv
        self.default = str(default_value)
        self.current = str(default_value)
        self.on_change = on_change

    def set_value(self, value: str):
        if self.type == "button":
            if self.on_change:
                self.on_change(self)
            return
        if self.type == "check" and value not in ("true", "false"):
            return
        if self.type == "spin":
            try:
                v = int(value)
                if v < self.min or v > self.max:
                    return
            except ValueError:
                return
        # For combo, we could validate, but we don't have combos yet.
        self.current = value
        if self.on_change:
            self.on_change(self)

    def get_int(self) -> int:
        return int(self.current)

    def get_bool(self) -> bool:
        return self.current.lower() == "true"

    def get_str(self) -> str:
        return self.current


class Options:
    def __init__(self):
        self._options: Dict[str, Option] = {}
        self._init_defaults()

    def _init_defaults(self):
        self._add("Hash", 16, "spin", 1, 131072, self._on_hash_size)
        self._add("Threads", 1, "spin", 1, 512)
        self._add("MultiPV", 1, "spin", 1, 500)
        self._add("Move Overhead", 30, "spin", 0, 5000)
        self._add("Minimum Thinking Time", 20, "spin", 0, 5000)
        self._add("Slow Mover", 84, "spin", 10, 1000)
        self._add("UCI_AnalyseMode", False, "check")
        self._add("Ponder", False, "check")
        self._add("Clear Hash", None, "button", on_change=self._on_clear_hash)

    def _add(self, name: str, default, otype: str = "spin",
             minv: int = 0, maxv: int = 0, on_change: Callable = None):
        self._options[name] = Option(default, otype, minv, maxv, on_change)

    def set_option(self, name: str, value: str):
        if name in self._options:
            self._options[name].set_value(value)

    def get(self, name: str) -> Option:
        return self._options.get(name, None)

    def __getitem__(self, name: str) -> int:
        opt = self._options.get(name)
        if opt and opt.type in ("spin", "check"):
            return opt.get_int()
        return 0

    def __contains__(self, name: str) -> bool:
        return name in self._options

    def print_options(self) -> str:
        """Return the UCI option list."""
        lines = []
        for name, opt in self._options.items():
            if opt.type == "spin":
                lines.append(f"option name {name} type spin default {opt.default} min {opt.min} max {opt.max}")
            elif opt.type == "check":
                lines.append(f"option name {name} type check default {opt.default}")
            elif opt.type == "string":
                lines.append(f"option name {name} type string default {opt.default}")
            elif opt.type == "button":
                lines.append(f"option name {name} type button")
        return "\n".join(lines)

    # Callbacks
    def _on_hash_size(self, opt: Option):
        # The search's TT will be resized via engine reference
        pass

    def _on_clear_hash(self, opt: Option):
        pass  # will be handled by engine