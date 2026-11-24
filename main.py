"""نقطة التشغيل: معايرة ثم مراقبة. HUD + tray + تقارير + أهداف + تركيز."""
from __future__ import annotations

import logging
import os
import sqlite3
import textwrap
import threading
import time
from collections import deque
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np

from config import CONFIG, Config, PROFILES
from core.calibration import CalibrationError, Calibrator
from core.camera import AdaptiveSampler, Camera, CameraError
from core.detector import DetectorError, LandmarkDetector
from core.metrics import (Baseline, BlinkDetector, Observation, RawMetrics, compute_raw,
                          eye_center, median_raw, normalize_angle)
from logic.alert_manager import AlertManager
from logic.coach import Coach
from logic.fatigue import FatigueDetector, FatigueState
from logic.focus_mode import FocusMode
from logic.goals import GoalTracker
from logic.profiles import ProfileManager
from logic.state_machine import Evaluation, StateMachine
from privacy.audit import NetworkGuard, PrivacyAudit
from reports.daily import ReportGenerator
from storage.database import Database
from ui.guide_window import GuideWindow
from ui.overlay import OverlayWindow
from ui.tray import TrayIcon

log = logging.getLogger("wellness")
StepResult = Tuple[Optional[RawMetrics], Optional[RawMetrics], float]


class Pipeline:
    def __init__(self, cfg: Config, cam: Camera, det: LandmarkDetector, audit: PrivacyAudit) -> None:
        self._cfg, self._cam, self._det, self._audit = cfg, cam, det, audit
        self._sampler = AdaptiveSampler(cfg.target_fps, cfg.min_fps, cfg.max_fps)
        self._hist: Deque[RawMetrics] = deque(maxlen=cfg.smoothing_window)
        self._misses = 0
        self.last_frame: Optional[np.ndarray] = None
        self.last_obs: Optional[Observation] = None

    def reset(self) -> None:
        self._hist.clear()

    def step(self) -> Optional[StepResult]:
        now = time.monotonic()
        if not self._cam.grab():
            if self._cam.consecutive_failures >= self._cfg.max_camera_failures:
                raise CameraError("camera stopped delivering frames")
            time.sleep(0.02)
            return None
        if not self._sampler.due(now):
            self._audit.record_skipped()
            time.sleep(0.01)
            return None
        frame = self._cam.retrieve()
        if frame is None:
            return None
        obs = self._det.process(frame)
        self.last_obs = obs
        self.last_frame = frame if self._cfg.show_preview else None
        del frame
        raw = compute_raw(obs, self._cfg)
        if raw is not None:
            self._misses = 0
            self._hist.append(raw)
            smooth: Optional[RawMetrics] = median_raw(list(self._hist))
        else:
            self._misses += 1
            if self._misses > 5:
                self._hist.clear()
            smooth = None
        end = time.monotonic()
        self._sampler.done(end, end - now)
        self._audit.record_processed(end)
        return raw, smooth, end


WINDOW = "Smart Desk Wellness Monitor"
GREEN, RED, ORANGE = (0, 200, 0), (0, 0, 230), (0, 150, 255)
STATUS_COLOR = {"good": GREEN, "bad": RED, "unknown": ORANGE}
POSE_LINKS = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (15, 17), (15, 19), (15, 21),
              (16, 18), (16, 20), (16, 22), (17, 19), (18, 20)]


def render_preview(frame, obs, color, headline, details, alert) -> None:
    h, w = frame.shape[:2]
    img = cv2.flip(frame, 1)

    def P(pt): return int(w - 1 - pt[0]), int(pt[1])

    if obs is not None:
        pts = obs.pose_points
        for a, b in POSE_LINKS:
            if a in pts and b in pts:
                cv2.line(img, P(pts[a]), P(pts[b]), color, 4, cv2.LINE_AA)
        for q in pts.values():
            cv2.circle(img, P(q), 7, color, -1, cv2.LINE_AA)
        if obs.left_eye is not None and obs.right_eye is not None:
            for eye in (obs.left_eye, obs.right_eye):
                for x, y in eye:
                    cv2.circle(img, P((x, y)), 2, color, -1)
            cv2.line(img, P(eye_center(obs.right_eye)), P(eye_center(obs.left_eye)), color, 2, cv2.LINE_AA)
        if obs.nose:
            cv2.circle(img, P(obs.nose), 6, color, -1, cv2.LINE_AA)
            if obs.left_shoulder and obs.right_shoulder:
                mid = ((obs.left_shoulder[0] + obs.right_shoulder[0]) / 2,
                       (obs.left_shoulder[1] + obs.right_shoulder[1]) / 2)
                cv2.line(img, P(mid), P(obs.nose), color, 3, cv2.LINE_AA)

    cv2.rectangle(img, (0, 0), (w - 1, h - 1), color, 8)
    cv2.rectangle(img, (0, 0), (w, 52), color, -1)

    safe_headline = headline.encode("ascii", "ignore").decode("ascii")
    if not safe_headline.strip():
        safe_headline = "STATUS"
    cv2.putText(img, safe_headline, (14, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)

    for i, text in enumerate(details):
        safe_text = text.encode("ascii", "ignore").decode("ascii")
        if safe_text.strip():
            cv2.putText(img, safe_text, (14, 82 + 28 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(img, safe_text, (14, 82 + 28 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                        color, 1, cv2.LINE_AA)

    if alert:
        safe_alert = alert.encode("ascii", "ignore").decode("ascii")
        if safe_alert.strip():
            rows = textwrap.wrap(safe_alert, 56)
            top = h - 26 * len(rows) - 14
            cv2.rectangle(img, (0, top), (w, h), (0, 90, 220), -1)
            for i, text in enumerate(rows):
                cv2.putText(img, text, (10, top + 24 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                            (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imshow(WINDOW, img)


def calibrate(pipe: Pipeline, cfg: Config) -> Baseline:
    for attempt in range(1, cfg.calibration_max_attempts + 1):
        print(f"\n[Calibration {attempt}/{cfg.calibration_max_attempts}] اجلس بوضعية صحية، "
              f"الرأس والكتفان في الإطار. اثبت {cfg.calibration_seconds:.0f} ثانية...")
        pipe.reset()
        cal = Calibrator(cfg)
        start = time.monotonic()
        while time.monotonic() - start < cfg.calibration_seconds:
            res = pipe.step()
            if res is not None:
                cal.add(res[0], res[2])
                if pipe.last_frame is not None:
                    left = cfg.calibration_seconds - (time.monotonic() - start)
                    render_preview(pipe.last_frame, pipe.last_obs, ORANGE,
                                   f"CALIBRATING {max(left, 0):.0f}s",
                                   ["Keep head and shoulders in view"], "")
                    cv2.waitKey(1)
        try:
            base = cal.finish()
            print(f"✅ المعايرة مقبولة.")
            return base
        except CalibrationError as exc:
            print(f"❌ المعايرة مرفوضة: {exc}")
    raise CalibrationError("calibration failed after all attempts")


def build_status_lines(ev: Evaluation, fatigue: Optional[FatigueState], fps: float, 
                       raw: Optional[RawMetrics], baseline: Baseline) -> List[str]:
    lines = []
    if ev.available and raw is not None:
        # 1. المسافة بالسنتيمتر
        if raw.distance_cm:
            lines.append(f"المسافة: {raw.distance_cm:.0f} سم {'⚠️' if raw.distance_cm < 50 else '✅'}")
        
        # 2. زوايا الجسم الدقيقة
        if raw.shoulder_tilt is not None:
            s_dev = abs(normalize_angle(raw.shoulder_tilt - baseline.shoulder_tilt))
            lines.append(f"ميل الكتفين: {s_dev:.1f}° {'⚠️' if s_dev > 5 else '✅'}")
        
        if raw.neck_angle is not None:
            n_dev = abs(normalize_angle(raw.neck_angle - baseline.neck_angle))
            lines.append(f"ميل الرقبة: {n_dev:.1f}° {'⚠️' if n_dev > 10 else '✅'}")
            
        if raw.head_tilt is not None:
            h_dev = abs(normalize_angle(raw.head_tilt - baseline.head_tilt))
            lines.append(f"ميل الرأس: {h_dev:.1f}° {'⚠️' if h_dev > 10 else '✅'}")
            
        # 3. الرمش والحالة
        lines.append(f"الرمش/د: {ev.blink_rate:.1f} {'⚠️' if ev.eye_warn else '✅'}")
        
        if fatigue:
            status = "😴 نائم" if fatigue.drowsy else f"الإجهاد: {fatigue.fatigue_score*100:.0f}%"
            lines.append(f"الحالة: {status}")
    else:
        lines.append("لا وجه مرئي")
    
    lines.append(f"FPS: {fps:.1f}")
    return lines


def run(cfg: Config = CONFIG) -> int:
    os.system("")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    guard = NetworkGuard()
    guard.install()
    audit = PrivacyAudit(guard)
    db: Optional[Database] = None
    session_id: Optional[int] = None
    overlay: Optional[OverlayWindow] = None
    tray: Optional[TrayIcon] = None
    guide: Optional[GuideWindow] = None
    stop_event = threading.Event()
    profile_mgr = ProfileManager(cfg)
    goal = GoalTracker(cfg)
    focus = FocusMode(cfg)
    report_gen: Optional[ReportGenerator] = None

    def request_stop():
        stop_event.set()

    def show_guide(name: str) -> None:
        if guide:
            guide.show(name)

    def show_report() -> None:
        if report_gen:
            path = report_gen.weekly_chart()
            text = report_gen.daily_text_summary()
            print(text)
            if path:
                print(f"📊 التقرير: {path}")
                try:
                    os.startfile(str(path))
                except Exception:
                    pass

    def start_focus() -> None:
        focus.start(time.monotonic())
        print(f"⏱️ وضع التركيز: {cfg.focus_default_minutes} دقيقة")

    try:
        db = Database(cfg.db_path)
        report_gen = ReportGenerator(cfg, db)
        guide = GuideWindow(cfg)

        if cfg.overlay_enabled:
            overlay = OverlayWindow(cfg, on_close=request_stop,
                                    on_show_guide=show_guide,
                                    on_toggle_profile=None,
                                    on_focus=start_focus)
            threading.Thread(target=overlay.start, daemon=True).start()
            time.sleep(0.5)

        if cfg.tray_enabled:
            tray = TrayIcon(on_show=lambda: None, on_quit=request_stop,
                            on_report=show_report, on_guide=show_guide,
                            on_profile=profile_mgr.set_profile,
                            on_focus=start_focus,
                            on_recalibrate=lambda: None)
            tray.start()

        with Camera(cfg.camera_index, cfg.frame_width, cfg.frame_height) as cam:
            det = LandmarkDetector()
            try:
                pipe = Pipeline(cfg, cam, det, audit)
                baseline = calibrate(pipe, cfg)
                pipe.reset()
                session_id = db.start_session(baseline.to_json())
                blink = BlinkDetector(baseline.ear * cfg.ear_closed_ratio,
                                      baseline.ear * cfg.ear_open_ratio, cfg)
                fatigue_det = FatigueDetector(cfg)
                sm = StateMachine(cfg)
                coach = Coach(cfg)
                t0 = time.monotonic()
                am = AlertManager(cfg, t0)
                last_print = last_db = last_flush = t0
                alert_text, alert_until = "", 0.0
                ev = Evaluation(available=False)
                fatigue_state: Optional[FatigueState] = None
                last_focus_check = t0

                while not stop_event.is_set():
                    res = pipe.step()
                    key = cv2.waitKey(1) & 0xFF
                    now = time.monotonic()
                    if key in (ord("q"), 27):
                        break
                    if key == ord("s") and am.snooze(now):
                        alert_text, alert_until = "تم تأجيل التذكير.", now + 3
                    if key == ord("b") and am.acknowledge_break(now):
                        alert_text, alert_until = "تم تسجيل الاستراحة.", now + 3

                    f_status = focus.tick(now)
                    if f_status == "focus_ended":
                        alert_text, alert_until = "انتهى وضع التركيز — خذ استراحة 5 دقائق.", now + 10
                        focus.start_break(now)
                    elif f_status == "break_ended":
                        alert_text, alert_until = "انتهت الاستراحة — جاهز للتركيز؟", now + 5

                    if res is None:
                        continue
                    raw, smooth, t = res
                    blink.update(raw.ear if raw else None, t)
                    fatigue_state = fatigue_det.update(smooth, t)
                    ev = sm.update(smooth, baseline, blink.rate(t),
                                   raw is not None and blink.is_staring(t), t, fatigue_state)

                    if ev.available:
                        dt = 0.0 if last_focus_check == 0 else min(t - last_focus_check, 1.0)
                        good = not ev.posture_warn and not ev.drowsy
                        goal.add_time(dt, good)
                        last_focus_check = t

                    if not focus.is_active():
                        for a in am.update(ev, t):
                            alert_text, alert_until = a.message, t + cfg.alert_display_seconds
                    if t >= alert_until:
                        alert_text = ""

                    if ev.available and t - last_db >= cfg.db_write_interval_seconds and smooth:
                        db.add_metric(session_id, ev.posture_dev, ev.ipd_ratio, smooth.ear, ev.blink_rate)
                        last_db = t
                    if t - last_flush >= cfg.db_flush_interval_seconds:
                        try: db.flush()
                        except sqlite3.Error as exc: log.warning("db flush failed: %s", exc)
                        last_flush = t

                    cr = coach.update(smooth, baseline, ev.too_close, ev.staring, fatigue_state)

                    if overlay:
                        lines = build_status_lines(ev, fatigue_state, audit.fps(), smooth, baseline)
                        focus_text = ""
                        if focus.is_active():
                            focus_text = f"{focus.state.phase} — {focus.state.minutes_left:.0f}د"
                        gs = goal.state
                        overlay.update(lines, alert_text,
                                       goal_pct=gs.achieved_pct,
                                       goal_target=gs.target_pct,
                                       profile_name=profile_mgr.current.name,
                                       focus_text=focus_text)

                    if pipe.last_frame is not None and cfg.show_preview:
                        render_preview(pipe.last_frame, pipe.last_obs, STATUS_COLOR[cr.status],
                                       cr.headline, cr.details, alert_text)

                    if t - last_print >= cfg.console_interval_seconds:
                        print("\033[2J\033[H" + goal.summary_line(), flush=True)
                        last_print = t
            finally:
                det.close()
        return 0
    except (CameraError, DetectorError, CalibrationError) as exc:
        print(f"\nخطأ: {exc}")
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        if overlay: overlay.stop()
        if tray: tray.stop()
        if db is not None:
            try:
                if session_id is not None:
                    db.end_session(session_id)
                    print("\nملخص الجلسة:", db.session_summary(session_id, cfg.posture_warn_deg))
            except sqlite3.Error as exc:
                print(f"خطأ قاعدة البيانات: {exc}")
            db.close()
        cv2.destroyAllWindows()
        guard.uninstall()


if __name__ == "__main__":
    raise SystemExit(run())