"""معايرة شخصية: وسيط القياسات خلال 10 ثوانٍ مع رفض الجودة المنخفضة."""
from __future__ import annotations

from typing import List, Optional, Tuple

from config import Config
from core.metrics import Baseline, BlinkDetector, RawMetrics, median_raw


class CalibrationError(RuntimeError):
    """تُرفع عندما تكون جودة الكشف غير كافية."""


class Calibrator:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._samples: List[RawMetrics] = []
        self._ear_series: List[Tuple[float, float]] = []
        self._total = 0

    def add(self, raw: Optional[RawMetrics], t: float) -> None:
        self._total += 1
        if raw is not None:
            self._samples.append(raw)
            self._ear_series.append((t, raw.ear))

    def finish(self) -> Baseline:
        cfg = self._cfg
        if self._total < cfg.calibration_min_frames:
            raise CalibrationError("too few frames analysed; check the camera and retry")
        if len(self._samples) / self._total < cfg.calibration_min_valid_ratio:
            raise CalibrationError("face not detected reliably; improve lighting and face the camera")
        with_shoulders = [s for s in self._samples if s.vertical_ratio is not None]
        if len(with_shoulders) / self._total < cfg.calibration_min_valid_ratio:
            raise CalibrationError("shoulders not visible; sit back so head and shoulders are in frame")
        med = median_raw(self._samples)
        if med.vertical_ratio is None or med.vertical_ratio <= 0 or med.ear <= 0:
            raise CalibrationError("invalid baseline measurements; retry")
        base = Baseline(
            head_tilt=med.head_tilt, shoulder_tilt=med.shoulder_tilt or 0.0,
            neck_angle=med.neck_angle or 0.0, vertical_ratio=med.vertical_ratio,
            ipd=med.ipd, ear=med.ear, blink_rate=cfg.default_blink_rate)
        # الرمشات أثناء المعايرة تُسجَّل للمعلومية فقط (10 ثوانٍ لا تكفي لتقدير المعدل الشخصي)
        det = BlinkDetector(base.ear * cfg.ear_closed_ratio, base.ear * cfg.ear_open_ratio, cfg)
        for t, ear in self._ear_series:
            det.update(ear, t)
        base.calib_blinks = det.total_blinks
        return base
