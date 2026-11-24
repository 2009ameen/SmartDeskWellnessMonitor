"""غلاف MediaPipe (واجهة Solutions القديمة: FaceMesh + Pose)."""
from __future__ import annotations

import logging
from typing import Any, Optional

import cv2
import numpy as np

from core.metrics import Observation

LEFT_EYE_IDX = (362, 385, 387, 263, 373, 380)
RIGHT_EYE_IDX = (33, 160, 158, 133, 153, 144)
NOSE_IDX = 1
MOUTH_TOP_IDX, MOUTH_BOTTOM_IDX = 13, 14
MOUTH_LEFT_IDX, MOUTH_RIGHT_IDX = 78, 308
log = logging.getLogger(__name__)


class DetectorError(RuntimeError):
    pass


class LandmarkDetector:
    def __init__(self, face: Any = None, pose: Any = None, min_visibility: float = 0.5) -> None:
        if face is None or pose is None:
            try:
                import mediapipe as mp
                face = face or mp.solutions.face_mesh.FaceMesh(
                    max_num_faces=1, refine_landmarks=False,
                    min_detection_confidence=0.5, min_tracking_confidence=0.5)
                pose = pose or mp.solutions.pose.Pose(
                    model_complexity=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)
            except Exception as exc:
                raise DetectorError(f"MediaPipe initialisation failed: {exc}") from exc
        self._face, self._pose, self._min_vis = face, pose, min_visibility
        self.errors = 0

    def process(self, frame_bgr: np.ndarray) -> Observation:
        try:
            h, w = frame_bgr.shape[:2]
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            face_res = self._face.process(rgb)
            pose_res = self._pose.process(rgb)
            return self._build(face_res, pose_res, w, h)
        except Exception as exc:
            self.errors += 1
            log.warning("detector failure #%d: %s", self.errors, exc)
            return Observation()

    def _build(self, face_res: Any, pose_res: Any, w: int, h: int) -> Observation:
        obs = Observation()
        faces = getattr(face_res, "multi_face_landmarks", None)
        if faces:
            lm = faces[0].landmark

            def pt(i: int):
                return (lm[i].x * w, lm[i].y * h)

            def pts(idx: tuple) -> np.ndarray:
                return np.array([pt(i) for i in idx], dtype=float)

            obs.left_eye, obs.right_eye = pts(LEFT_EYE_IDX), pts(RIGHT_EYE_IDX)
            obs.nose = pt(NOSE_IDX)
            obs.mouth_top, obs.mouth_bottom = pt(MOUTH_TOP_IDX), pt(MOUTH_BOTTOM_IDX)
            obs.mouth_left, obs.mouth_right = pt(MOUTH_LEFT_IDX), pt(MOUTH_RIGHT_IDX)
            obs.face_ok = True
        plm = getattr(pose_res, "pose_landmarks", None)
        if plm is not None:
            ls, rs = plm.landmark[11], plm.landmark[12]
            if ls.visibility >= self._min_vis and rs.visibility >= self._min_vis:
                obs.left_shoulder = (ls.x * w, ls.y * h)
                obs.right_shoulder = (rs.x * w, rs.y * h)
            for i in range(11, 23):
                q = plm.landmark[i]
                if q.visibility >= self._min_vis:
                    obs.pose_points[i] = (q.x * w, q.y * h)
        return obs

    def close(self) -> None:
        for m in (self._face, self._pose):
            try:
                m.close()
            except Exception:
                pass