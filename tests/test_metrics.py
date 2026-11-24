import math
import unittest

import numpy as np

from config import Config
from core.metrics import (Baseline, BlinkDetector, Observation, RawMetrics, compute_raw,
                          eye_aspect_ratio, ipd_ratio, posture_deviation)

CFG = Config()


def eye(h: float) -> np.ndarray:
    return np.array([[0, 0], [1, h], [2, h], [3, 0], [2, -h], [1, -h]], dtype=float)


def base() -> Baseline:
    return Baseline(0.0, 0.0, 0.0, 1.0, 100.0, 0.3, 15.0)


class MetricsTests(unittest.TestCase):
    def test_ear_open_closed(self):
        self.assertAlmostEqual(eye_aspect_ratio(eye(1.0)), 2 * 2 / (2 * 3))
        self.assertLess(eye_aspect_ratio(eye(0.1)), 0.1)
        with self.assertRaises(ValueError):
            eye_aspect_ratio(np.zeros((6, 2)))

    def test_ipd_ratio(self):
        self.assertAlmostEqual(ipd_ratio(120, 100), 1.2)
        with self.assertRaises(ValueError):
            ipd_ratio(1, 0)

    def test_blink_counted_once(self):
        d = BlinkDetector(0.225, 0.255, CFG)
        t, blinks = 0.0, 0
        for ear in [0.3] * 5 + [0.1, 0.1] + [0.3] * 5:
            blinks += d.update(ear, t)
            t += 1 / 6
        self.assertEqual(blinks, 1)

    def test_long_closure_not_blink_and_not_stare(self):
        d = BlinkDetector(0.225, 0.255, CFG)
        t = 0.0
        for ear in [0.3] * 3 + [0.1] * 12 + [0.3] * 3:
            d.update(ear, t)
            t += 1 / 6
        self.assertEqual(d.total_blinks, 0)

    def test_blink_rate_starts_at_default_then_follows_data(self):
        d = BlinkDetector(0.225, 0.255, CFG)
        d.update(0.3, 0.0)
        self.assertAlmostEqual(d.rate(0.0), CFG.default_blink_rate, places=1)
        t = 0.0
        for _ in range(240):        # 40 s بدون رمش
            t += 1 / 6
            d.update(0.3, t)
        self.assertLess(d.rate(t), CFG.low_blink_rate)

    def test_staring_and_face_loss_pause(self):
        d = BlinkDetector(0.225, 0.255, CFG)
        t = 0.0
        for _ in range(80):         # ~13 s بلا رمش
            d.update(0.3, t)
            t += 1 / 6
        self.assertTrue(d.is_staring(t))
        d2 = BlinkDetector(0.225, 0.255, CFG)
        d2.update(0.3, 0.0)
        for i in range(1, 80):
            d2.update(None, i / 6)  # الوجه مفقود: لا تحديق
        self.assertFalse(d2.is_staring(80 / 6))

    def test_posture_deviation(self):
        b = base()
        same = RawMetrics(0.0, 100, 0.3, 0.0, 0.0, 1.0)
        self.assertAlmostEqual(posture_deviation(same, b, CFG), 0.0)
        tilt = RawMetrics(10.0, 100, 0.3, 2.0, 1.0, 1.0)
        self.assertAlmostEqual(posture_deviation(tilt, b, CFG), 10.0)
        slouch = RawMetrics(0.0, 100, 0.3, 0.0, 0.0, 0.7)
        self.assertAlmostEqual(posture_deviation(slouch, b, CFG), 0.3 * CFG.vertical_to_deg)

    def test_compute_raw(self):
        obs = Observation(True, eye(1.0) + [200, 100], eye(1.0) + [100, 100], (150, 100),
                          (260, 300), (40, 300))
        raw = compute_raw(obs)
        self.assertIsNotNone(raw)
        self.assertAlmostEqual(raw.head_tilt, 0.0)
        self.assertAlmostEqual(raw.ipd, 100.0)
        self.assertAlmostEqual(raw.vertical_ratio, 200 / 220)
        self.assertIsNone(compute_raw(Observation()))


if __name__ == "__main__":
    unittest.main()
