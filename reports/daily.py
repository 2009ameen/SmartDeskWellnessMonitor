"""تقارير يومية وأسبوعية مع رسوم بيانية (matplotlib)."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # بدون واجهة رسومية — نحفظ PNG
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from config import Config
from storage.database import Database


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


class ReportGenerator:
    def __init__(self, cfg: Config, db: Database) -> None:
        self._cfg = cfg
        self._db = db
        self._dir = _ensure_dir(cfg.reports_dir)

    def weekly_chart(self) -> Optional[Path]:
        rows = self._db.daily_summary(self._cfg.posture_warn_deg)
        if not rows:
            return None
        days = [datetime.fromisoformat(r["day"]).date() for r in rows][-7:]
        healthy = [r["healthy_posture_pct"] for r in rows][-7:]
        blink = [r["avg_blink_rate"] or 0 for r in rows][-7:]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
        ax1.plot(days, healthy, marker="o", color="#2e7d32", linewidth=2)
        ax1.axhline(self._cfg.daily_goal_healthy_pct, color="#ff9800",
                    linestyle="--", label=f"الهدف {self._cfg.daily_goal_healthy_pct:.0f}%")
        ax1.set_ylabel("وضعية صحية %")
        ax1.set_title("تقرير الأسبوع — Smart Desk Wellness")
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        ax1.set_ylim(0, 105)

        ax2.bar(days, blink, color="#1976d2", alpha=0.7)
        ax2.set_ylabel("رمش/دقيقة (متوسط)")
        ax2.set_xlabel("اليوم")
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        plt.xticks(rotation=45)
        plt.tight_layout()

        out = self._dir / f"weekly_{datetime.now().strftime('%Y%m%d')}.png"
        fig.savefig(out, dpi=110)
        plt.close(fig)
        return out

    def daily_text_summary(self) -> str:
        rows = self._db.daily_summary(self._cfg.posture_warn_deg)
        if not rows:
            return "لا توجد بيانات بعد."
        today = datetime.now().date().isoformat()
        today_row = next((r for r in rows if r["day"] == today), None)
        lines = ["=" * 44, "  تقرير اليوم", "=" * 44]
        if today_row:
            lines.append(f"  عدد العينات: {today_row['samples']}")
            lines.append(f"  متوسط الانحناء: {today_row['avg_posture_dev']:.1f}°")
            lines.append(f"  متوسط المسافة: {today_row['avg_ipd_ratio']:.2f}")
            lines.append(f"  متوسط الرمش: {today_row['avg_blink_rate']:.1f}/د")
            lines.append(f"  وضعية صحية: {today_row['healthy_posture_pct']:.0f}%")
        else:
            lines.append("  لا بيانات اليوم بعد.")
        if len(rows) >= 2:
            yesterday = rows[-2]
            diff = today_row["healthy_posture_pct"] - yesterday["healthy_posture_pct"] if today_row else 0
            arrow = "↑" if diff > 2 else ("↓" if diff < -2 else "→")
            lines.append(f"  مقارنة بالأمس: {arrow} {diff:+.0f}%")
        return "\n".join(lines)