"""إعدادات مركزية للمشروع."""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import sys
import os

# إذا كنا داخل ملف exe، نستخدم مسار ملف exe. وإلا نستخدم مسار الكود.
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

@dataclass(frozen=True)
class Profile:
    name: str
    posture_warn_deg: float
    alert_level1_seconds: float
    alert_level2_seconds: float
    sound_enabled: bool
    overlay_opacity: float
    break_interval_seconds: float
    description: str = ""

PROFILES: Dict[str, Profile] = {
    "office": Profile(
        name="عمل مكتبي", posture_warn_deg=12.0,
        alert_level1_seconds=30.0, alert_level2_seconds=180.0,
        sound_enabled=True, overlay_opacity=0.85,
        break_interval_seconds=1200.0,
        description="عتبات قياسية للعمل المكتبي",
    ),
    "study": Profile(
        name="دراسة", posture_warn_deg=15.0,
        alert_level1_seconds=45.0, alert_level2_seconds=240.0,
        sound_enabled=True, overlay_opacity=0.85,
        break_interval_seconds=1500.0,
        description="يسمح بانحناء أكبر قليلاً أثناء الدراسة",
    ),
    "gaming": Profile(
        name="ألعاب", posture_warn_deg=20.0,
        alert_level1_seconds=120.0, alert_level2_seconds=600.0,
        sound_enabled=False, overlay_opacity=0.7,
        break_interval_seconds=2400.0,
        description="تنبيهات أقل، مناسب للألعاب",
    ),
    "silent": Profile(
        name="صامت", posture_warn_deg=12.0,
        alert_level1_seconds=60.0, alert_level2_seconds=300.0,
        sound_enabled=False, overlay_opacity=0.6,
        break_interval_seconds=1200.0,
        description="HUD فقط، بدون أي صوت",
    ),
}

@dataclass(frozen=True)
class Config:
    # الكاميرا والعينة الزمنية
    camera_index: int = 0
    frame_width: int = 640
    frame_height: int = 480
    target_fps: float = 6.0
    min_fps: float = 5.0
    max_fps: float = 8.0
    max_camera_failures: int = 60
    show_preview: bool = True
    smoothing_window: int = 5

    # المعايرة
    calibration_seconds: float = 10.0
    calibration_min_frames: int = 20
    calibration_min_valid_ratio: float = 0.7
    calibration_max_attempts: int = 3

    # عتبات المؤشرات
    posture_warn_deg: float = 12.0
    vertical_to_deg: float = 60.0
    ipd_close_ratio: float = 1.15
    
    # معايرة المسافة (جديد)
    camera_fov_deg: float = 60.0          # مجال رؤية الكاميرا التقريبي
    real_shoulder_width_cm: float = 45.0  # متوسط عرض الكتفين للإنسان البالغ
    distance_warn_cm: float = 50.0        # التنبيه إذا اقترب أكثر من 50 سم

    # النعاس (EAR المطلق)
    ear_drowsy_threshold: float = 0.25    # عتبة إغلاق العين
    drowsy_eye_closed_seconds: float = 2.0 # مدة الإغلاق = نعاس
    yawn_mar_threshold: float = 0.6
    yawn_min_seconds: float = 1.5
    fatigue_score_warn: float = 0.7

    # عتبات الرمش
    ear_closed_ratio: float = 0.75
    ear_open_ratio: float = 0.85
    blink_max_seconds: float = 0.5
    blink_window_seconds: float = 60.0
    blink_prior_seconds: float = 30.0
    default_blink_rate: float = 15.0
    low_blink_rate: float = 8.0
    stare_seconds: float = 10.0
    clear_grace_seconds: float = 3.0

    # التنبيهات
    level1_seconds: float = 30.0
    level2_seconds: float = 180.0
    alert_min_gap_seconds: float = 20.0
    break_interval_seconds: float = 1200.0
    break_duration_seconds: float = 20.0
    snooze_seconds: float = 300.0
    alert_display_seconds: float = 10.0

    # العرض وقاعدة البيانات
    console_interval_seconds: float = 2.0
    db_path: Path = BASE_DIR / "data" / "wellness.db"
    db_write_interval_seconds: float = 1.0
    db_flush_interval_seconds: float = 5.0

    # الواجهة
    overlay_enabled: bool = True
    overlay_opacity: float = 0.85
    tray_enabled: bool = True
    notify_via_system: bool = True

    # الأهداف
    daily_goal_healthy_pct: float = 70.0
    goal_streak_bonus: bool = True

    # وضع التركيز
    focus_default_minutes: int = 25
    focus_break_minutes: int = 5

    # التقارير
    reports_dir: Path = BASE_DIR / "data" / "reports"
    baseline_cache_path: Path = BASE_DIR / "data" / "baseline.json"
    baseline_max_age_days: int = 7

    # الوضع الليلي
    night_mode_start_hour: int = 20
    night_mode_end_hour: int = 7

    # الوضع الحالي
    active_profile: str = "office"

    def profile(self) -> Profile:
        return PROFILES.get(self.active_profile, PROFILES["office"])

CONFIG = Config()