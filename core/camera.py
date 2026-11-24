"""الكاميرا (grab/retrieve) + أخذ عينات تكيفي. الإطارات تبقى في الذاكرة فقط."""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


class CameraError(RuntimeError):
    pass


class AdaptiveSampler:
    """يضبط الفاصل بين التحليلات ضمن [1/max_fps, 1/min_fps] حسب كلفة المعالجة."""

    def __init__(self, target_fps: float, min_fps: float, max_fps: float) -> None:
        self._target = 1.0 / target_fps
        self._lo, self._hi = 1.0 / max_fps, 1.0 / min_fps
        self.interval = self._target
        self._next = 0.0
        self._ema: Optional[float] = None

    def due(self, now: float) -> bool:
        return now >= self._next

    def done(self, now: float, cost: float) -> None:
        self._ema = cost if self._ema is None else 0.8 * self._ema + 0.2 * cost
        if self._ema > 0.8 * self.interval:
            self.interval = min(self._hi, self.interval * 1.1)
        elif self.interval > self._target and self._ema < 0.5 * self.interval:
            self.interval = max(self._target, self.interval / 1.1)
        self.interval = max(self._lo, min(self._hi, self.interval))
        self._next = now + self.interval


class Camera:
    def __init__(self, index: int, width: int, height: int,
                 capture_factory: Optional[Callable[[], Any]] = None) -> None:
        self._index, self._w, self._h = index, width, height
        self._factory = capture_factory or self._default_factory
        self._cap: Any = None
        self.consecutive_failures = 0

    def _default_factory(self) -> Any:
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        return cv2.VideoCapture(self._index, backend)

    def open(self) -> None:
        try:
            cap = self._factory()
        except Exception as exc:
            raise CameraError(f"cannot create capture: {exc}") from exc
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            raise CameraError("camera not available (in use by another app or no permission)")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._h)
        self._cap = cap

    def grab(self) -> bool:
        if self._cap is None:
            return False
        try:
            ok = bool(self._cap.grab())
        except Exception:
            ok = False
        self.consecutive_failures = 0 if ok else self.consecutive_failures + 1
        return ok

    def retrieve(self) -> Optional[np.ndarray]:
        if self._cap is None:
            return None
        try:
            ok, frame = self._cap.retrieve()
        except Exception:
            return None
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()
