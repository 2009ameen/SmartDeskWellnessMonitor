import unittest

from config import Config
from core.calibration import CalibrationError, Calibrator
from core.metrics import RawMetrics

CFG = Config()


def good(ear=0.3, shoulders=True):
    return RawMetrics(1.0, 100.0, ear, 0.5 if shoulders else None, 2.0 if shoulders else None,
                      0.9 if shoulders else None)


class CalibrationTests(unittest.TestCase):
    def test_median_ignores_outliers(self):
        c = Calibrator(CFG)
        for i in range(60):
            c.add(good(0.3), i / 6)
        c.add(RawMetrics(1.0, 500.0, 0.05, 0.5, 2.0, 0.9), 11.0)   # قيمة شاذة
        b = c.finish()
        self.assertAlmostEqual(b.ipd, 100.0)
        self.assertAlmostEqual(b.ear, 0.3)
        self.assertEqual(b.blink_rate, CFG.default_blink_rate)

    def test_rejects_low_quality(self):
        c = Calibrator(CFG)
        for i in range(60):
            c.add(good() if i % 3 == 0 else None, i / 6)
        with self.assertRaises(CalibrationError):
            c.finish()

    def test_rejects_too_few_frames_and_missing_shoulders(self):
        c = Calibrator(CFG)
        for i in range(5):
            c.add(good(), i)
        with self.assertRaises(CalibrationError):
            c.finish()
        c2 = Calibrator(CFG)
        for i in range(60):
            c2.add(good(shoulders=False), i / 6)
        with self.assertRaises(CalibrationError):
            c2.finish()

    def test_records_calibration_blinks(self):
        c = Calibrator(CFG)
        ears = [0.3] * 20 + [0.1, 0.1] + [0.3] * 20
        for i, e in enumerate(ears):
            c.add(good(e), i / 6)
        self.assertEqual(c.finish().calib_blinks, 1)


if __name__ == "__main__":
    unittest.main()
