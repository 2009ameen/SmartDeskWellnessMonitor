"""تنبيهات متعددة المستويات بعدادات مستقلة + قاعدة 20-20-20."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from config import Config
from logic.state_machine import INDICATORS, Evaluation


@dataclass(frozen=True)
class Alert:
    indicator: str
    level: int
    message: str


class AlertManager:
    def __init__(self, cfg: Config, now: float) -> None:
        self._cfg = cfg
        self._fired: Dict[str, Set[int]] = {k: set() for k in INDICATORS}
        self._last: Dict[str, Optional[float]] = {k: None for k in INDICATORS}
        self._break_due = now + cfg.break_interval_seconds
        self._break_until: Optional[float] = None
        self._snooze_used = False
        self.alert_count = 0
        self.break_responses = 0

    def update(self, ev: Evaluation, now: float) -> List[Alert]:
        out: List[Alert] = []
        cfg = self._cfg
        for ind in INDICATORS:
            d = ev.durations.get(ind, 0.0)
            if d <= 0.0:
                self._fired[ind].clear()
                continue
            level = 2 if d >= cfg.level2_seconds else (1 if d >= cfg.level1_seconds else 0)
            if level == 0 or level in self._fired[ind]:
                continue
            last = self._last[ind]
            if last is not None and now - last < cfg.alert_min_gap_seconds:
                continue
            self._fired[ind].update(range(1, level + 1))
            self._last[ind] = now
            self.alert_count += 1
            out.append(Alert(ind, level, self._message(ind, level, d, ev)))
        if self._break_until is None and now >= self._break_due:
            self._break_until = now + cfg.break_duration_seconds
            self.alert_count += 1
            out.append(Alert("break", 3, "20-20-20: look at something ~20 feet (6 m) away for 20 s. "
                                         "[b] done, [s] snooze (once)"))
        elif self._break_until is not None and now >= self._break_until:
            self._finish_break(now)
        return out

    def snooze(self, now: float) -> bool:
        if self._break_until is None or self._snooze_used:
            return False
        self._break_until = None
        self._break_due = now + self._cfg.snooze_seconds
        self._snooze_used = True
        return True

    def acknowledge_break(self, now: float) -> bool:
        if self._break_until is None:
            return False
        self.break_responses += 1
        self._finish_break(now)
        return True

    def _finish_break(self, now: float) -> None:
        self._break_until = None
        self._break_due = now + self._cfg.break_interval_seconds
        self._snooze_used = False

    @staticmethod
    def _message(ind: str, level: int, d: float, ev: Evaluation) -> str:
        mins = d / 60.0
        if level == 1:
            return {
                "posture": "Gentle reminder: adjust your sitting posture.",
                "proximity": "Gentle reminder: you are close to the screen.",
                "eye": "Gentle reminder: rest your eyes and blink.",
                "fatigue": "Gentle reminder: you look tired. Take a short break.",
            }.get(ind, "Gentle reminder.")
        if ind == "posture":
            dev = f"{ev.posture_dev:.0f} deg " if ev.posture_dev is not None else ""
            return (f"Posture deviation {dev}for {mins:.0f}+ min. Straighten your back, "
                    "relax shoulders, keep head over shoulders.")
        if ind == "proximity":
            r = f"(IPD ratio {ev.ipd_ratio:.2f}) " if ev.ipd_ratio is not None else ""
            return f"Too close to the screen {r}for {mins:.0f}+ min. Move back to your calibrated distance."
        if ind == "fatigue":
            if ev.drowsy:
                return "Drowsiness detected (eyes closed for a while). Take a break now."
            return "Fatigue signs detected (yawning / tired eyes). Rest, hydrate, move a bit."
        if ev.staring:
            return "Long staring detected. Blink several times and look away briefly."
        return "Blink rate is low compared with your baseline (behavioural estimate, not a diagnosis). Rest your eyes."