"""إدارة أوضاع التشغيل — يعدّل العتبات ديناميكياً."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import Config, Profile, PROFILES


@dataclass
class EffectiveThresholds:
    """العتبات الفعلية بعد تطبيق الوضع الحالي + الوضع الليلي."""
    posture_warn_deg: float
    level1_seconds: float
    level2_seconds: float
    sound_enabled: bool
    overlay_opacity: float
    break_interval_seconds: float
    night_mode: bool = False


class ProfileManager:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._current = cfg.active_profile
        self._night_override = False

    @property
    def current_name(self) -> str:
        return self._current

    @property
    def current(self) -> Profile:
        return PROFILES.get(self._current, PROFILES["office"])

    def set_profile(self, name: str) -> bool:
        if name not in PROFILES:
            return False
        self._current = name
        return True

    def set_night_mode(self, enabled: bool) -> None:
        self._night_override = enabled

    def effective(self, hour: Optional[int] = None) -> EffectiveThresholds:
        p = self.current
        night = self._night_override
        if hour is not None:
            night = night or self._is_night_hour(hour)
        return EffectiveThresholds(
            posture_warn_deg=p.posture_warn_deg,
            level1_seconds=p.alert_level1_seconds,
            level2_seconds=p.alert_level2_seconds,
            sound_enabled=p.sound_enabled and not night,
            overlay_opacity=p.overlay_opacity * (0.7 if night else 1.0),
            break_interval_seconds=p.break_interval_seconds,
            night_mode=night,
        )

    def _is_night_hour(self, hour: int) -> bool:
        start, end = self._cfg.night_mode_start_hour, self._cfg.night_mode_end_hour
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end