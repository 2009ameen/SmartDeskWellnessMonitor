"""وضع التركيز (بومودورو) — يخفي التنبيهات لمدة محددة."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import Config


@dataclass
class FocusState:
    active: bool = False
    until: float = 0.0
    phase: str = "idle"   # idle | focus | break
    minutes_left: float = 0.0


class FocusMode:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._state = FocusState()

    @property
    def state(self) -> FocusState:
        return self._state

    def start(self, now: float, minutes: Optional[int] = None) -> None:
        mins = minutes or self._cfg.focus_default_minutes
        self._state = FocusState(active=True, until=now + mins * 60.0,
                                 phase="focus", minutes_left=float(mins))

    def start_break(self, now: float) -> None:
        mins = self._cfg.focus_break_minutes
        self._state = FocusState(active=True, until=now + mins * 60.0,
                                 phase="break", minutes_left=float(mins))

    def stop(self) -> None:
        self._state = FocusState()

    def tick(self, now: float) -> str:
        """يرجع: 'none' | 'focus_ended' | 'break_ended' | 'active'."""
        if not self._state.active:
            return "none"
        left = self._state.until - now
        self._state.minutes_left = max(0.0, left / 60.0)
        if left > 0:
            return "active"
        if self._state.phase == "focus":
            self._state.active = False
            return "focus_ended"
        if self._state.phase == "break":
            self._state.active = False
            return "break_ended"
        return "none"

    def is_active(self) -> bool:
        return self._state.active