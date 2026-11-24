"""حسابات رياضية بحتة (بدون كاميرا أو MediaPipe) ليسهل اختبارها."""
from __future__ import annotations

import json
import math
import statistics
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Deque, Dict, List, Optional, Sequence, Tuple
import numpy as np
from config import Config

Point = Tuple[float, float]
MOUTH_TOP, MOUTH_BOTTOM = 13, 14
MOUTH_LEFT, MOUTH_RIGHT = 78, 308

@dataclass
class Observation:
    face_ok: bool = False
    left_eye: Optional[np.ndarray] = None
    right_eye: Optional[np.ndarray] = None
    nose: Optional[Point] = None
    left_shoulder: Optional[Point] = None
    right_shoulder: Optional[Point] = None
    mouth_top: Optional[Point] = None
    mouth_bottom: Optional[Point] = None
    mouth_left: Optional[Point] = None
    mouth_right: Optional[Point] = None
    pose_points: Dict[int, Point] = field(default_factory=dict)

@dataclass
class RawMetrics:
    head_tilt: float
    ipd: float
    ear: float
    mar: Optional[float] = None
    shoulder_tilt: Optional[float] = None
    neck_angle: Optional[float] = None
    vertical_ratio: Optional[float] = None
    distance_cm: Optional[float] = None
    shoulder_width_px: Optional[float] = None

@dataclass
class Baseline:
    head_tilt: float
    shoulder_tilt: float
    neck_angle: float
    vertical_ratio: float
    ipd: float
    ear: float
    blink_rate: float
    calib_blinks: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self))

def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return float(math.hypot(a[0] - b[0], a[1] - b[1]))

def normalize_angle(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0

def line_angle_deg(p_from: Sequence[float], p_to: Sequence[float]) -> float:
    return math.degrees(math.atan2(p_to[1] - p_from[1], p_to[0] - p_from[0]))

def eye_aspect_ratio(pts: Sequence[Sequence[float]]) -> float:
    p = np.asarray(pts, dtype=float)
    if p.shape != (6, 2):
        raise ValueError("EAR requires 6 (x, y) points")
    horizontal = np.linalg.norm(p[0] - p[3])
    if horizontal < 1e-6:
        raise ValueError("degenerate eye geometry")
    vertical = np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
    return float(vertical / (2.0 * horizontal))

def mouth_aspect_ratio(top: Point, bottom: Point, left: Point, right: Point) -> float:
    vertical = _dist(top, bottom)
    horizontal = _dist(left, right)
    if horizontal < 1e-6:
        return 0.0
    return vertical / horizontal

def eye_center(pts: Sequence[Sequence[float]]) -> Point:
    p = np.asarray(pts, dtype=float)
    c = (p[0] + p[3]) / 2.0
    return float(c[0]), float(c[1])

def ipd_ratio(current_ipd: float, baseline_ipd: float) -> float:
    if baseline_ipd <= 0:
        raise ValueError("baseline_ipd must be positive")
    return current_ipd / baseline_ipd

def compute_raw(obs: Observation, cfg: Config) -> Optional[RawMetrics]:
    if not obs.face_ok or obs.left_eye is None or obs.right_eye is None:
        return None
    try:
        ear = (eye_aspect_ratio(obs.left_eye) + eye_aspect_ratio(obs.right_eye)) / 2.0
    except ValueError:
        return None
    
    lc, rc = eye_center(obs.left_eye), eye_center(obs.right_eye)
    ipd_px = _dist(lc, rc)
    if ipd_px < 1.0:
        return None
    
    mar = None
    if obs.mouth_top and obs.mouth_bottom and obs.mouth_left and obs.mouth_right:
        mar = mouth_aspect_ratio(obs.mouth_top, obs.mouth_bottom, obs.mouth_left, obs.mouth_right)
    
    raw = RawMetrics(head_tilt=line_angle_deg(rc, lc), ipd=ipd_px, ear=ear, mar=mar)
    
    if obs.nose and obs.left_shoulder and obs.right_shoulder:
        ls, rs, nose = obs.left_shoulder, obs.right_shoulder, obs.nose
        shoulder_width = _dist(ls, rs)
        
        if shoulder_width > 1.0:
            # حساب المسافة بالسنتيمتر
            fov_rad = math.radians(cfg.camera_fov_deg)
            focal_length_px = cfg.frame_width / (2.0 * math.tan(fov_rad / 2.0))
            distance_cm = (cfg.real_shoulder_width_cm * focal_length_px) / shoulder_width
            raw.distance_cm = distance_cm
            raw.shoulder_width_px = shoulder_width
            
            mid = ((ls[0] + rs[0]) / 2.0, (ls[1] + rs[1]) / 2.0)
            raw.shoulder_tilt = line_angle_deg(rs, ls)
            raw.neck_angle = math.degrees(math.atan2(nose[0] - mid[0], mid[1] - nose[1]))
            raw.vertical_ratio = (mid[1] - nose[1]) / shoulder_width
    return raw

def _median(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    return float(statistics.median(clean)) if clean else None

def _median_required(values: List[Optional[float]], name: str) -> float:
    m = _median(values)
    if m is None:
        raise ValueError(f"no valid values for {name}")
    return m

def median_raw(samples: Sequence[RawMetrics]) -> RawMetrics:
    if not samples:
        raise ValueError("no samples")
    return RawMetrics(
        head_tilt=_median_required([s.head_tilt for s in samples], "head_tilt"),
        ipd=_median_required([s.ipd for s in samples], "ipd"),
        ear=_median_required([s.ear for s in samples], "ear"),
        mar=_median([s.mar for s in samples]),
        shoulder_tilt=_median([s.shoulder_tilt for s in samples]),
        neck_angle=_median([s.neck_angle for s in samples]),
        vertical_ratio=_median([s.vertical_ratio for s in samples]),
        distance_cm=_median([s.distance_cm for s in samples]),
        shoulder_width_px=_median([s.shoulder_width_px for s in samples]),
    )

def posture_components(raw: RawMetrics, base: Baseline, cfg: Config) -> Dict[str, float]:
    comps = {"head_tilt": abs(normalize_angle(raw.head_tilt - base.head_tilt))}
    if raw.shoulder_tilt is not None:
        comps["shoulder_tilt"] = abs(normalize_angle(raw.shoulder_tilt - base.shoulder_tilt))
    if raw.neck_angle is not None:
        comps["neck_lean"] = abs(normalize_angle(raw.neck_angle - base.neck_angle))
    if raw.vertical_ratio is not None and base.vertical_ratio > 0:
        drop = max(0.0, 1.0 - raw.vertical_ratio / base.vertical_ratio)
        comps["head_drop"] = drop * cfg.vertical_to_deg
    return comps

def posture_deviation(raw: RawMetrics, base: Baseline, cfg: Config) -> float:
    return float(max(posture_components(raw, base, cfg).values()))

class BlinkDetector:
    def __init__(self, closed_thr: float, open_thr: float, cfg: Config) -> None:
        self._closed_thr, self._open_thr, self._cfg = closed_thr, open_thr, cfg
        self._closed = False
        self._closed_since = 0.0
        self._blinks: Deque[float] = deque()
        self._obs: Deque[Tuple[float, float]] = deque()
        self._last_t: Optional[float] = None
        self._last_blink_t: Optional[float] = None
        self.total_blinks = 0

    def update(self, ear: Optional[float], t: float) -> bool:
        dt = 0.0 if self._last_t is None else min(max(t - self._last_t, 0.0), 1.0)
        self._last_t = t
        if ear is None:
            self._closed = False
            if self._last_blink_t is not None:
                self._last_blink_t += dt
            return False
        if self._last_blink_t is None:
            self._last_blink_t = t
        self._obs.append((t, dt))
        self._prune(t)
        blink = False
        if not self._closed and ear < self._closed_thr:
            self._closed, self._closed_since = True, t
        elif self._closed and ear > self._open_thr:
            self._closed = False
            if t - self._closed_since <= self._cfg.blink_max_seconds:
                self._blinks.append(t)
                self.total_blinks += 1
                self._last_blink_t = t
                blink = True
        if self._closed:
            self._last_blink_t = t
        return blink

    def _prune(self, t: float) -> None:
        horizon = t - self._cfg.blink_window_seconds
        while self._blinks and self._blinks[0] < horizon:
            self._blinks.popleft()
        while self._obs and self._obs[0][0] < horizon:
            self._obs.popleft()

    def rate(self, t: float) -> float:
        self._prune(t)
        observed = sum(dt for _, dt in self._obs)
        prior = self._cfg.blink_prior_seconds
        n = len(self._blinks) + self._cfg.default_blink_rate * prior / 60.0
        return n / ((observed + prior) / 60.0)

    def is_staring(self, t: float) -> bool:
        return (not self._closed and self._last_blink_t is not None
                and t - self._last_blink_t >= self._cfg.stare_seconds)