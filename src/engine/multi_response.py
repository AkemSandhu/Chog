from __future__ import annotations
from typing import List, Optional

class EngineResponse:
    """Single engine line (one PV)."""
    def __init__(self, pv: str = "", score_cp: int = 0, score_mate: int = 0,
                 depth: int = 0, nodes: int = 0, time: int = 0):
        self.pv = pv                    # string of moves "e2e3 e7e6 ..."
        self.score_cp = score_cp
        self.score_mate = score_mate
        self.depth = depth
        self.nodes = nodes
        self.time = time
        self.nag = 0
        self.text = ""                  # human readable label
        self.from_sq = ""
        self.to_sq = ""

    def centipawns_abs(self) -> float:
        if self.score_mate != 0:
            return 30000 if self.score_mate > 0 else -30000
        return self.score_cp

    def movimiento(self) -> str:
        return self.pv.split()[0] if self.pv else ""

    def abbrev_text_base(self) -> str:
        if self.score_mate:
            return f"Mate {self.score_mate}"
        return f"{self.score_cp/100:.2f}"

class MultiEngineResponse:
    def __init__(self, name: str = "", is_white: bool = True):
        self.name = name
        self.li_rm: List[EngineResponse] = []
        self.is_white = is_white
        self.time_label = ""
        self.time_engine = ""
        self.pos_selected = 0   # index of currently selected line

    def add(self, rm: EngineResponse):
        self.li_rm.append(rm)

    def ordena(self):
        """Sort lines by absolute score descending."""
        self.li_rm.sort(key=lambda rm: abs(rm.centipawns_abs()), reverse=True)

    def rm_best(self) -> Optional[EngineResponse]:
        if not self.li_rm:
            return None
        return max(self.li_rm, key=lambda rm: rm.centipawns_abs())

    def clone(self) -> MultiEngineResponse:
        """Return a deep copy."""
        import copy
        return copy.deepcopy(self)

    @staticmethod
    def from_info_lines(info_dicts: List[dict], is_white: bool = True) -> MultiEngineResponse:
        """Create from a list of parsed 'info' dicts (from protocol.py)."""
        mrm = MultiEngineResponse()
        mrm.is_white = is_white
        for info in info_dicts:
            rm = EngineResponse()
            rm.depth = info.get("depth", 0)
            rm.score_cp = info.get("score_cp", 0)
            rm.score_mate = info.get("score_mate", 0)
            pv = info.get("pv", [])
            rm.pv = " ".join(pv)
            if pv:
                rm.from_sq = pv[0][:2] if len(pv[0]) >= 2 else ""
                rm.to_sq = pv[0][2:4] if len(pv[0]) >= 4 else ""
            mrm.add(rm)
        mrm.ordena()
        return mrm