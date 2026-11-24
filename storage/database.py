"""SQLite محلي للأرقام فقط (لا صور ولا فيديو ولا بيانات شخصية)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    baseline_json TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    posture_dev REAL,
    ipd_ratio REAL,
    ear REAL,
    blink_rate REAL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_metrics_session_ts ON metrics(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._buffer: List[Tuple[Any, ...]] = []

    def start_session(self, baseline_json: Optional[str]) -> int:
        cur = self._conn.execute("INSERT INTO sessions(start_time, baseline_json) VALUES (?, ?)",
                                 (_now(), baseline_json))
        self._conn.commit()
        return int(cur.lastrowid)

    def add_metric(self, session_id: int, posture_dev: Optional[float], ipd_ratio: Optional[float],
                   ear: Optional[float], blink_rate: Optional[float],
                   timestamp: Optional[str] = None) -> None:
        self._buffer.append((session_id, timestamp or _now(), posture_dev, ipd_ratio, ear, blink_rate))

    def flush(self) -> None:
        if not self._buffer:
            return
        try:
            self._conn.executemany(
                "INSERT INTO metrics(session_id, timestamp, posture_dev, ipd_ratio, ear, blink_rate) "
                "VALUES (?, ?, ?, ?, ?, ?)", self._buffer)
            self._conn.commit()
            self._buffer.clear()
        except sqlite3.Error:
            self._conn.rollback()
            raise

    def end_session(self, session_id: int) -> None:
        self.flush()
        self._conn.execute("UPDATE sessions SET end_time=? WHERE id=?", (_now(), session_id))
        self._conn.commit()

    def session_summary(self, session_id: int, posture_warn_deg: float) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT COUNT(*), AVG(posture_dev), AVG(ipd_ratio), AVG(blink_rate), "
            "AVG(CASE WHEN posture_dev < ? THEN 1.0 ELSE 0.0 END) FROM metrics WHERE session_id=?",
            (posture_warn_deg, session_id)).fetchone()
        s = self._conn.execute("SELECT start_time, end_time FROM sessions WHERE id=?",
                               (session_id,)).fetchone()
        duration = None
        if s and s[1]:
            duration = (datetime.fromisoformat(s[1]) - datetime.fromisoformat(s[0])).total_seconds()
        return {"samples": row[0], "avg_posture_dev": row[1], "avg_ipd_ratio": row[2],
                "avg_blink_rate": row[3],
                "healthy_posture_pct": None if row[4] is None else 100.0 * row[4],
                "duration_s": duration}

    def daily_summary(self, posture_warn_deg: float) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT substr(timestamp,1,10), COUNT(*), AVG(posture_dev), AVG(ipd_ratio), AVG(blink_rate), "
            "AVG(CASE WHEN posture_dev < ? THEN 1.0 ELSE 0.0 END) FROM metrics "
            "GROUP BY substr(timestamp,1,10) ORDER BY 1", (posture_warn_deg,)).fetchall()
        return [{"day": r[0], "samples": r[1], "avg_posture_dev": r[2], "avg_ipd_ratio": r[3],
                 "avg_blink_rate": r[4], "healthy_posture_pct": 100.0 * r[5]} for r in rows]

    def close(self) -> None:
        try:
            self.flush()
        finally:
            self._conn.close()
