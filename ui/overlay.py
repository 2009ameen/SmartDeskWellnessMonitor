"""نافذة شفافة فوق كل التطبيقات + شريط تقدم الهدف + زر الدليل."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional

from config import Config


class OverlayWindow:
    def __init__(self, cfg: Config, on_close: Optional[Callable[[], None]] = None,
                 on_show_guide: Optional[Callable[[str], None]] = None,
                 on_toggle_profile: Optional[Callable[[], None]] = None,
                 on_focus: Optional[Callable[[], None]] = None) -> None:
        self._cfg = cfg
        self._on_close = on_close
        self._on_show_guide = on_show_guide
        self._on_toggle_profile = on_toggle_profile
        self._on_focus = on_focus
        self._root: Optional[tk.Tk] = None
        self._status_label: Optional[tk.Label] = None
        self._goal_bar: Optional[tk.Canvas] = None
        self._goal_label: Optional[tk.Label] = None
        self._alert_label: Optional[tk.Label] = None
        self._profile_label: Optional[tk.Label] = None

    def start(self) -> None:
        self._root = tk.Tk()
        self._root.title("Wellness HUD")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", self._cfg.overlay_opacity)
        self._root.configure(bg="#1a1a1a")
        self._root.geometry("420x300+20+20")

        header = tk.Frame(self._root, bg="#1a1a1a")
        header.pack(fill="x")
        self._profile_label = tk.Label(header, text="الوضع: عمل مكتبي",
                                        font=("Segoe UI", 9), fg="#4fc3f7", bg="#1a1a1a")
        self._profile_label.pack(side="right", padx=6)
        tk.Button(header, text="×", command=self._close, fg="#888", bg="#1a1a1a",
                  bd=0, font=("Arial", 12)).pack(side="right")

        self._status_label = tk.Label(
            self._root, text="جاري التحميل...", justify="right", anchor="ne",
            font=("Segoe UI", 10), fg="#e0e0e0", bg="#1a1a1a", padx=10, pady=8,
        )
        self._status_label.pack(fill="both", expand=True)

        # شريط الهدف
        goal_frame = tk.Frame(self._root, bg="#1a1a1a")
        goal_frame.pack(fill="x", padx=10, pady=(0, 4))
        self._goal_label = tk.Label(goal_frame, text="الهدف: 0%", font=("Segoe UI", 8),
                                     fg="#aaa", bg="#1a1a1a")
        self._goal_label.pack(anchor="w")
        self._goal_bar = tk.Canvas(goal_frame, height=8, bg="#333", highlightthickness=0)
        self._goal_bar.pack(fill="x", pady=2)

        # أزرار
        btns = tk.Frame(self._root, bg="#1a1a1a")
        btns.pack(fill="x", padx=10, pady=4)
        tk.Button(btns, text="📖 دليل", command=lambda: self._guide("good_posture"),
                  bg="#333", fg="white", relief="flat", font=("Segoe UI", 8)).pack(side="right", padx=2)
        tk.Button(btns, text="👁️ عين", command=lambda: self._guide("eye_rest"),
                  bg="#333", fg="white", relief="flat", font=("Segoe UI", 8)).pack(side="right", padx=2)
        tk.Button(btns, text="⏱️ تركيز", command=self._focus,
                  bg="#333", fg="white", relief="flat", font=("Segoe UI", 8)).pack(side="right", padx=2)

        self._alert_label = tk.Label(
            self._root, text="", justify="right", anchor="e",
            font=("Segoe UI", 9, "bold"), fg="#ffaa00", bg="#2a2a2a", padx=10, pady=4,
        )
        self._alert_label.pack(fill="x", side="bottom")

        self._root.mainloop()

    def update(self, lines: List[str], alert: str = "",
               goal_pct: float = 0.0, goal_target: float = 70.0,
               profile_name: str = "", focus_text: str = "") -> None:
        if not self._root:
            return
        text = "\n".join(lines)
        if focus_text:
            text = f"⏱️ {focus_text}\n" + text
        try:
            self._root.after(0, lambda: self._status_label.config(text=text))
            self._root.after(0, lambda: self._alert_label.config(text=alert))
            if self._profile_label and profile_name:
                self._root.after(0, lambda: self._profile_label.config(text=f"الوضع: {profile_name}"))
            self._root.after(0, lambda: self._draw_goal(goal_pct, goal_target))
        except Exception:
            pass

    def _draw_goal(self, pct: float, target: float) -> None:
        if not self._goal_bar:
            return
        self._goal_bar.delete("all")
        w = self._goal_bar.winfo_width() or 380
        h = 8
        # خلفية
        self._goal_bar.create_rectangle(0, 0, w, h, fill="#333", outline="")
        # تقدم
        progress = min(1.0, pct / target) if target > 0 else 0
        color = "#4caf50" if pct >= target else "#ff9800"
        self._goal_bar.create_rectangle(0, 0, int(w * progress), h, fill=color, outline="")
        if self._goal_label:
            star = "⭐" if pct >= target else ""
            self._goal_label.config(text=f"الهدف: {pct:.0f}% / {target:.0f}% {star}")

    def _guide(self, name: str) -> None:
        if self._on_show_guide:
            self._on_show_guide(name)

    def _focus(self) -> None:
        if self._on_focus:
            self._on_focus()

    def _close(self) -> None:
        self.stop()
        if self._on_close:
            self._on_close()

    def stop(self) -> None:
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception:
                pass
            self._root = None