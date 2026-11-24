import unittest

from config import Config
from core.metrics import Baseline, RawMetrics
from logic.alert_manager import AlertManager
from logic.state_machine import Evaluation, PersistenceTimer, StateMachine

CFG = Config()
BASE = Baseline(0, 0, 0, 1.0, 100.0, 0.3, 15.0)


def bad_posture():
    return RawMetrics(30.0, 100.0, 0.3, 0.0, 0.0, 1.0)


def good_posture():
    return RawMetrics(0.0, 100.0, 0.3, 0.0, 0.0, 1.0)


class StateTests(unittest.TestCase):
    def test_timer_accumulates_pauses_and_resets(self):
        t = PersistenceTimer(3.0)
        now = 0.0
        for _ in range(60):
            now += 0.5
            t.update(True, now)
        self.assertGreater(t.seconds, 25)
        before = t.seconds
        for _ in range(20):
            now += 0.5
            t.update(None, now)           # فقدان وجه: تجمّد
        self.assertEqual(t.seconds, before)
        for _ in range(10):
            now += 0.5
            t.update(False, now)          # تحسن 5 ثوانٍ > grace
        self.assertEqual(t.seconds, 0.0)

    def test_independent_counters(self):
        sm = StateMachine(CFG)
        now, ev = 0.0, None
        for _ in range(100):
            now += 0.5
            ev = sm.update(bad_posture(), BASE, 4.0, False, now)  # وضعية سيئة + رمش منخفض
        self.assertGreater(ev.durations["posture"], 20)
        self.assertGreater(ev.durations["eye"], 20)
        for _ in range(20):
            now += 0.5
            ev = sm.update(good_posture(), BASE, 4.0, False, now)  # تحسنت الوضعية فقط
        self.assertEqual(ev.durations["posture"], 0.0)
        self.assertGreater(ev.durations["eye"], 40)

    def test_alert_levels_fire_once(self):
        am = AlertManager(CFG, 0.0)
        got = []
        now = 0.0
        while now < 400:
            now += 1.0
            ev = Evaluation(True, 20.0, 1.0, 15.0, True, durations={"posture": now, "proximity": 0.0, "eye": 0.0})
            got += [(a.indicator, a.level) for a in am.update(ev, now)]
        self.assertEqual([g for g in got if g[0] == "posture"], [("posture", 1), ("posture", 2)])

    def test_alert_rearms_after_recovery(self):
        am = AlertManager(CFG, 0.0)
        ev = Evaluation(True, durations={"posture": 31.0, "proximity": 0.0, "eye": 0.0})
        self.assertEqual(len(am.update(ev, 1.0)), 1)
        self.assertEqual(len(am.update(ev, 2.0)), 0)
        am.update(Evaluation(True), 3.0)
        self.assertEqual(len(am.update(ev, 100.0)), 1)

    def test_break_snooze_once(self):
        am = AlertManager(CFG, 0.0)
        out = am.update(Evaluation(True), CFG.break_interval_seconds + 1)
        self.assertEqual([a.level for a in out], [3])
        self.assertTrue(am.snooze(CFG.break_interval_seconds + 2))
        later = CFG.break_interval_seconds + 2 + CFG.snooze_seconds + 1
        self.assertEqual([a.level for a in am.update(Evaluation(True), later)], [3])
        self.assertFalse(am.snooze(later + 1))      # التأجيل مرة واحدة فقط
        self.assertTrue(am.acknowledge_break(later + 2))

    def test_healthy_percent(self):
        sm = StateMachine(CFG)
        for i in range(1, 11):
            sm.update(good_posture() if i <= 5 else bad_posture(), BASE, 15.0, False, i * 0.5)
        self.assertGreater(sm.healthy_percent, 30)
        self.assertLess(sm.healthy_percent, 70)


if __name__ == "__main__":
    unittest.main()
