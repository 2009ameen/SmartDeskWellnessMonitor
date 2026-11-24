"""كشف النعاس بناءً على إغلاق العيون المطلق (EAR) والتثاؤب (MAR)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from config import Config
from core.metrics import RawMetrics

@dataclass
class FatigueState:
    drowsy: bool = False
    yawning: bool = False
    eyes_closed_seconds: float = 0.0
    yawn_count: int = 0
    fatigue_score: float = 0.0

class FatigueDetector:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._closed_since: Optional[float] = None
        self._yawn_start: Optional[float] = None
        self._yawn_count = 0
        self._recent_yawns: list[float] = []
        self._state = FatigueState()

    def update(self, raw: Optional[RawMetrics], t: float) -> FatigueState:
        cfg = self._cfg
        if raw is None:
            self._closed_since = None
            self._yawn_start = None
            return self._state

        # --- كشف إغلاق العيون المستمر (EAR المطلق) ---
        ear_closed = raw.ear < cfg.ear_drowsy_threshold
        if ear_closed:
            if self._closed_since is None:
                self._closed_since = t
            closed_secs = t - self._closed_since
        else:
            self._closed_since = None
            closed_secs = 0.0

        drowsy = closed_secs >= cfg.drowsy_eye_closed_seconds

        # --- كشف التثاؤب ---
        yawning = False
        if raw.mar is not None and raw.mar >= cfg.yawn_mar_threshold:
            if self._yawn_start is None:
                self._yawn_start = t
            elif t - self._yawn_start >= cfg.yawn_min_seconds:
                yawning = True
        else:
            if self._yawn_start is not None and t - self._yawn_start >= cfg.yawn_min_seconds:
                self._yawn_count += 1
                self._recent_yawns.append(t)
            self._yawn_start = None

        # تنظيف التثاؤب القديم (آخر 10 دقائق)
        horizon = t - 600.0
        self._recent_yawns = [yt for yt in self._recent_yawns if yt >= horizon]

        # --- حساب درجة الإجهاد ---
        eye_factor = min(1.0, closed_secs / (cfg.drowsy_eye_closed_seconds * 1.5))
        yawn_factor = min(1.0, len(self._recent_yawns) / 5.0)
        fatigue_score = 0.7 * eye_factor + 0.3 * yawn_factor

        self._state = FatigueState(
            drowsy=drowsy,
            yawning=yawning,
            eyes_closed_seconds=closed_secs,
            yawn_count=len(self._recent_yawns),
            fatigue_score=fatigue_score,
        )
        return self._state