"""تقييم الحالة + عدادات استمرار مستقلة لكل مؤشر."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from config import Config
from core.metrics import Baseline, RawMetrics, ipd_ratio, posture_deviation
from logic.fatigue import FatigueState

INDICATORS = ("posture", "proximity", "eye", "fatigue")


class PersistenceTimer:
    def __init__(self, grace: float) -> None:
        self.seconds = 0.0
        self._clear = 0.0
        self._grace = grace
        self._last: Optional[float] = None

    def update(self, active: Optional[bool], now: float) -> float:
        dt = 0.0 if self._last is None else min(max(now - self._last, 0.0), 1.0)
        self._last = now
        if active is None:
            return self.seconds
        if active:
            self.seconds += dt
            self._clear = 0.0
        else:
            self._clear += dt
            if self._clear >= self._grace:
                self.seconds = 0.0
        return self.seconds


@dataclass
class Evaluation:
    available: bool
    posture_dev: Optional[float] = None
    ipd_ratio: Optional[float] = None
    blink_rate: Optional[float] = None
    posture_warn: bool = False
    too_close: bool = False
    eye_warn: bool = False
    staring: bool = False
    drowsy: bool = False
    fatigue_score: float = 0.0
    durations: Dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in INDICATORS})


class StateMachine:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._timers = {k: PersistenceTimer(cfg.clear_grace_seconds) for k in INDICATORS}
        self._last: Optional[float] = None
        self._was_staring = False
        self.good_seconds = 0.0
        self.total_seconds = 0.0
        self.stare_events = 0

    @property
    def healthy_percent(self) -> float:
        return 100.0 * self.good_seconds / self.total_seconds if self.total_seconds > 0 else 0.0

    def update(self, raw: Optional[RawMetrics], base: Baseline, blink_rate: float,
               staring: bool, now: float, fatigue: Optional[FatigueState] = None) -> Evaluation:
        dt = 0.0 if self._last is None else min(max(now - self._last, 0.0), 1.0)
        self._last = now
        if raw is None:
            durs = {k: t.update(None, now) for k, t in self._timers.items()}
            return Evaluation(available=False, durations=durs)
        dev = posture_deviation(raw, base, self._cfg)
        ratio = ipd_ratio(raw.ipd, base.ipd)
        pw = dev >= self._cfg.posture_warn_deg
        tc = ratio >= self._cfg.ipd_close_ratio
        ew = blink_rate < self._cfg.low_blink_rate or staring
        
        # التنبيه فقط عند النوم الفعلي (إغلاق العينين المستمر)
        fw = bool(fatigue and fatigue.drowsy)
        
        self.total_seconds += dt
        if not pw and not fw:
            self.good_seconds += dt
        if staring and not self._was_staring:
            self.stare_events += 1
        self._was_staring = staring
        flags = {"posture": pw, "proximity": tc, "eye": ew, "fatigue": fw}
        durs = {k: self._timers[k].update(flags[k], now) for k in INDICATORS}
        return Evaluation(True, dev, ratio, blink_rate, pw, tc, ew, staring,
                          fatigue.drowsy if fatigue else False,
                          fatigue.fatigue_score if fatigue else 0.0, durs)