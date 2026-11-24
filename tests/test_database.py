import tempfile
import unittest
from pathlib import Path

from storage.database import Database


class DatabaseTests(unittest.TestCase):
    def test_roundtrip_and_summary(self):
        with tempfile.TemporaryDirectory() as d:
            db = Database(Path(d) / "t.db")
            sid = db.start_session('{"ear": 0.3}')
            for dev in (2.0, 4.0, 20.0, 30.0):
                db.add_metric(sid, dev, 1.0, 0.3, 15.0)
            db.end_session(sid)
            s = db.session_summary(sid, 12.0)
            self.assertEqual(s["samples"], 4)
            self.assertAlmostEqual(s["avg_posture_dev"], 14.0)
            self.assertAlmostEqual(s["healthy_posture_pct"], 50.0)
            self.assertEqual(len(db.daily_summary(12.0)), 1)
            db.close()

    def test_no_media_tables(self):
        db = Database(":memory:")
        names = {r[0] for r in db._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"sessions", "metrics"} <= names)
        db.close()


if __name__ == "__main__":
    unittest.main()
