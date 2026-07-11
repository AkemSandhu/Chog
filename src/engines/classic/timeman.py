"""
Time management adapted from Stockfish's timeman.cpp.
Uses engine options for adjustable parameters.
"""
import math
import time
from typing import Optional
from src.engines.classic.options import Options

class TimeManager:
    def __init__(self, options: Optional[Options] = None):
        self.optimum_time = 0
        self.maximum_time = 0
        self.start_time = 0.0
        self._options = options if options else Options()

    @property
    def _move_overhead(self) -> int:
        return self._options["Move Overhead"] if "Move Overhead" in self._options else 30

    @property
    def _min_thinking_time(self) -> int:
        return self._options["Minimum Thinking Time"] if "Minimum Thinking Time" in self._options else 20

    @property
    def _slow_mover(self) -> int:
        return self._options["Slow Mover"] if "Slow Mover" in self._options else 84

    @property
    def _ponder(self) -> bool:
        opt = self._options.get("Ponder")
        return opt.get_bool() if opt else False

    def init(self, us, wtime, btime, winc, binc, movestogo, ply):
        if us == 0:
            my_time = max(0, wtime)
            my_inc  = max(0, winc)
        else:
            my_time = max(0, btime)
            my_inc  = max(0, binc)

        self.start_time = time.time()
        self.optimum_time = max(my_time, self._min_thinking_time)
        self.maximum_time = self.optimum_time

        MoveHorizon = 50
        max_mtg = min(movestogo, MoveHorizon) if movestogo else MoveHorizon

        for hyp_mtg in range(1, max_mtg + 1):
            hyp_my_time = my_time + my_inc * (hyp_mtg - 1) \
                          - self._move_overhead * (2 + min(hyp_mtg, 40))
            hyp_my_time = max(hyp_my_time, 0)

            t1 = self._min_thinking_time + self._remaining(hyp_my_time, hyp_mtg, ply, self._slow_mover, optimum=True)
            t2 = self._min_thinking_time + self._remaining(hyp_my_time, hyp_mtg, ply, self._slow_mover, optimum=False)

            self.optimum_time = min(t1, self.optimum_time)
            self.maximum_time = min(t2, self.maximum_time)

        if self._ponder:
            self.optimum_time += self.optimum_time // 4

        self.maximum_time = max(self.maximum_time, self.optimum_time)

    def elapsed(self) -> int:
        return int((time.time() - self.start_time) * 1000)

    @staticmethod
    def _move_importance(ply):
        XScale = 6.85
        XShift = 64.5
        Skew   = 0.171
        return pow(1.0 + math.exp((ply - XShift) / XScale), -Skew) + 1e-300

    @staticmethod
    def _remaining(my_time, moves_to_go, ply, slow_mover, optimum):
        MaxRatio   = 1.0 if optimum else 7.3
        StealRatio = 0.0 if optimum else 0.34

        move_importance = (TimeManager._move_importance(ply) * slow_mover) / 100.0
        other_importance = 0.0
        for i in range(1, moves_to_go):
            other_importance += TimeManager._move_importance(ply + 2 * i)

        ratio1 = (MaxRatio * move_importance) / (MaxRatio * move_importance + other_importance)
        ratio2 = (move_importance + StealRatio * other_importance) / (move_importance + other_importance)

        return int(my_time * min(ratio1, ratio2))