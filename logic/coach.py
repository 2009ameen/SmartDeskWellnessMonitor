"""مدرّب الوضعية: يعرض المؤشرات الدقيقة."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
from config import Config
from core.metrics import Baseline, RawMetrics, posture_components, normalize_angle
from logic.fatigue import FatigueState

@dataclass
class CoachResult:
    status: str
    headline: str
    details: List[str] = field(default_factory=list)
    deviation: Optional[float] = None
    fatigue: Optional[FatigueState] = None

class Coach:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._posture_bad = False

    def update(self, raw: Optional[RawMetrics], base: Baseline,
               too_close: bool = False, staring: bool = False,
               fatigue: Optional[FatigueState] = None) -> CoachResult:
        if raw is None:
            return CoachResult("unknown", "I can't see you - face the camera", fatigue=fatigue)

        # كشف النعاس له الأولوية القصوى
        if fatigue and fatigue.drowsy:
            return CoachResult(
                "bad", "SLEEPING - WAKE UP",
                [f"Eyes closed for {fatigue.eyes_closed_seconds:.1f}s", "Move your body!"],
                fatigue=fatigue,
            )

        if raw.vertical_ratio is None:
            return CoachResult("unknown", "Show head and shoulders", fatigue=fatigue)

        comps = posture_components(raw, base, self._cfg)
        
        # عرض الزوايا الدقيقة
        details = []
        if raw.shoulder_tilt is not None:
            details.append(f"Shoulder tilt: {abs(raw.shoulder_tilt - base.shoulder_tilt):.1f} deg")
        if raw.neck_angle is not None:
            details.append(f"Neck lean: {abs(raw.neck_angle - base.neck_angle):.1f} deg")
        if raw.head_tilt is not None:
            details.append(f"Head tilt: {abs(raw.head_tilt - base.head_tilt):.1f} deg")
        if raw.distance_cm is not None:
            details.append(f"Distance: {raw.distance_cm:.0f} cm")

        warn = self._cfg.posture_warn_deg
        thr = warn * 0.8 if self._posture_bad else warn
        bad_posture = sorted(((v, k) for k, v in comps.items() if v >= thr), reverse=True)
        
        if too_close:
            details.append("⚠️ Too close!")
        
        self._posture_bad = bool(bad_posture)
        
        if bad_posture:
            return CoachResult("bad", "FIX POSTURE", details, max(comps.values()), fatigue=fatigue)
        
        return CoachResult("good", "GOOD POSTURE", details, 0.0, fatigue=fatigue)