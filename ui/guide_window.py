"""نافذة الصور التعليمية للوضعية الصحيحة وتمارين العين."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Optional

from config import Config


GUIDE_TEXT = {
    "good_posture": {
        "title": "✅ الوضعية الصحيحة",
        "points": [
            "• اجلس منتصباً وظهرك مستند على الكرسي",
            "• القدمان مستويتان على الأرض",
            "• الكوع بزاوية 90-110 درجة",
            "• الشاشة على مستوى العين أو أقل قليلاً",
            "• المسافة من الشاشة 50-70 سم",
            "• الكتفان مرتخيان وليسا مرفوعين",
        ],
    },
    "bad_posture": {
        "title": "❌ أخطاء شائعة",
        "points": [
            "• الانحناء للأمام (رقبة متعبة)",
            "• رفع الكتفين (توتر)",
            "• الوجه قريب جداً من الشاشة",
            "• الجلوس على حافة الكرسي",
            "• التحديق دون رمش",
            "• وضعية ثابتة لساعات طويلة",
        ],
    },
    "eye_rest": {
        "title": "👁️ تمرين 20-20-20",
        "points": [
            "• كل 20 دقيقة",
            "• انظر لشيء على بعد 20 قدم (6 متر)",
            "• لمدة 20 ثانية",
            "• ارمش عدة مرات",
            "• حرّك عينيك بلطف (يمين/يسار/أعلى/أسفل)",
            "• هذا يقلل إجهاد العين الرقمي",
        ],
    },
}


class GuideWindow:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._root: Optional[tk.Toplevel] = None
        self._assets = Path(__file__).resolve().parent.parent / "assets" / "guides"

    def show(self, guide_name: str, parent: Optional[tk.Misc] = None) -> None:
        if self._root is not None:
            try:
                self._root.lift()
                return
            except Exception:
                self._root = None

        top = tk.Toplevel(parent) if parent else tk.Tk()
        top.title(GUIDE_TEXT.get(guide_name, {}).get("title", "دليل"))
        top.configure(bg="#1e1e1e")
        top.geometry("420x480")
        top.resizable(False, False)

        info = GUIDE_TEXT.get(guide_name, {"title": "دليل", "points": []})
        tk.Label(top, text=info["title"], font=("Segoe UI", 14, "bold"),
                 fg="#ffffff", bg="#1e1e1e", pady=12).pack()

        # محاولة عرض صورة إن وجدت
        img_path = self._assets / f"{guide_name}.png"
        if img_path.exists():
            try:
                img = tk.PhotoImage(file=str(img_path))
                lbl = tk.Label(top, image=img, bg="#1e1e1e")
                lbl.image = img
                lbl.pack(pady=6)
            except Exception:
                pass

        # نص تعليمي دائماً
        frame = tk.Frame(top, bg="#1e1e1e")
        frame.pack(fill="both", expand=True, padx=20, pady=10)
        for point in info["points"]:
            tk.Label(frame, text=point, font=("Segoe UI", 11), fg="#e0e0e0",
                     bg="#1e1e1e", anchor="w", justify="right").pack(fill="x", pady=2)

        tk.Button(top, text="إغلاق", command=self._close,
                  bg="#333", fg="white", relief="flat", padx=20, pady=6).pack(pady=10)
        self._root = top

    def _close(self) -> None:
        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None