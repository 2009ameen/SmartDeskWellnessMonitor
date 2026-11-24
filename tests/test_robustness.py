import socket
import unittest
from typing import Any

import numpy as np

from config import Config
from core.camera import AdaptiveSampler, Camera, CameraError
from core.detector import LandmarkDetector
from core.metrics import Observation, compute_raw
from main import Pipeline
from privacy.audit import NetworkGuard, PrivacyAudit

CFG = Config()


class BrokenSolver:
    def process(self, _: Any) -> Any:
        raise RuntimeError("mediapipe failure")

    def close(self) -> None:
        pass


class FakeCap:
    def __init__(self, opened=True, ok=True):
        self._o, self._ok = opened, ok

    def isOpened(self): return self._o
    def set(self, *_): return True
    def grab(self): return self._ok
    def retrieve(self): return self._ok, np.zeros((48, 64, 3), np.uint8)
    def release(self): pass


class FakeDetector:
    def process(self, _):
        e = np.array([[0, 0], [1, 1], [2, 1], [3, 0], [2, -1], [1, -1]], float)
        return Observation(True, e + [200, 100], e + [100, 100], (150, 100), (260, 300), (40, 300))

    def close(self): pass


class RobustnessTests(unittest.TestCase):
    def test_camera_unavailable_raises_clean_error(self):
        with self.assertRaises(CameraError):
            Camera(0, 64, 48, lambda: FakeCap(opened=False)).open()

    def test_camera_read_failures_do_not_crash(self):
        cam = Camera(0, 64, 48, lambda: FakeCap(ok=False))
        cam.open()
        self.assertFalse(cam.grab())
        self.assertEqual(cam.consecutive_failures, 1)
        cam.release()
        self.assertFalse(cam.grab())

    def test_detector_survives_mediapipe_failure(self):
        det = LandmarkDetector(face=BrokenSolver(), pose=BrokenSolver())
        obs = det.process(np.zeros((48, 64, 3), np.uint8))
        self.assertIsNone(compute_raw(obs))
        self.assertEqual(det.errors, 1)

    def test_pipeline_end_to_end_with_fakes(self):
        cam = Camera(0, 64, 48, lambda: FakeCap())
        cam.open()
        audit = PrivacyAudit()
        pipe = Pipeline(CFG, cam, FakeDetector(), audit)  # type: ignore[arg-type]
        import time
        results = []
        end = time.monotonic() + 0.6
        while time.monotonic() < end:
            r = pipe.step()
            if r:
                results.append(r)
        self.assertGreaterEqual(len(results), 2)
        self.assertGreater(audit.skipped, 0)               # أخذ العينات التكيفي يتجاهل إطارات
        self.assertAlmostEqual(results[0][0].ipd, 100.0)

    def test_sampler_stays_in_range(self):
        s = AdaptiveSampler(6, 5, 8)
        for i in range(50):
            s.done(i, 0.5)                                  # معالجة بطيئة
        self.assertAlmostEqual(s.interval, 0.2)

    def test_network_guard_blocks_and_counts(self):
        g = NetworkGuard()
        g.install()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            with self.assertRaises(OSError):
                s.connect(("127.0.0.1", 9))
            s.close()
            self.assertEqual(g.attempts, 1)
        finally:
            g.uninstall()


if __name__ == "__main__":
    unittest.main()
