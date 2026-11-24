"""الأهداف اليومية — تتبع التقدم بدون إزعاج."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import Config


@dataclass
class DailyGoalState:
    day: str
    target_pct: float
    achieved_pct: float = 0.0
    achieved: bool = False
    streak_days: int = 0
    total_seconds: float = 0.0
    good_seconds: float = 0.0

    @property
    def progress(self) -> float:
        if self.target_pct <= 0:
            return 1.0
        return min(1.0, self.achieved_pct / self.target_pct)


class GoalTracker:
    """يحفظ الحالة في JSON ويحسب السلسلة (streak)."""

    def __init__(self, cfg: Config, path: Optional[Path] = None) -> None:
        self._cfg = cfg
        self._path = path or (cfg.reports_dir.parent / "goals.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()
        self._ensure_today()

    def _load(self) -> DailyGoalState:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                return DailyGoalState(**data)
            except Exception:
                pass
        return DailyGoalState(day=date.today().isoformat(),
                              target_pct=self._cfg.daily_goal_healthy_pct)

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps(self._state.__dict__, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        except Exception:
            pass

    def _ensure_today(self) -> None:
        today = date.today().isoformat()
        if self._state.day != today:
            # يوم جديد: هل حقق أمس الهدف؟
            if self._state.achieved and self._cfg.goal_streak_bonus:
                self._state.streak_days += 1
            else:
                self._state.streak_days = 0
            self._state.day = today
            self._state.achieved_pct = 0.0
            self._state.achieved = False
            self._state.total_seconds = 0.0
            self._state.good_seconds = 0.0
            self._save()

    def add_time(self, dt: float, good: bool) -> None:
        self._ensure_today()
        self._state.total_seconds += dt
        if good:
            self._state.good_seconds += dt
        if self._state.total_seconds > 0:
            self._state.achieved_pct = 100.0 * self._state.good_seconds / self._state.total_seconds
        if not self._state.achieved and self._state.achieved_pct >= self._state.target_pct:
            self._state.achieved = True
        self._save()

    @property
    def state(self) -> DailyGoalState:
        self._ensure_today()
        return self._state

    def summary_line(self) -> str:
        s = self._state
        bar_len = 10
        filled = int(round(bar_len * s.progress))
        bar = "█" * filled + "░" * (bar_len - filled)
        star = "⭐" if s.achieved else "  "
        return f"الهدف: [{bar}] {s.achieved_pct:.0f}%/{s.target_pct:.0f}% {star} (سلسلة: {s.streak_days}ي)"