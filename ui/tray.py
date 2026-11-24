"""أيقونة شريط النظام — تحكم كامل."""
from __future__ import annotations

import threading
from typing import Callable, Dict, Optional

from PIL import Image, ImageDraw

from config import PROFILES


def create_tray_icon() -> Image.Image:
    img = Image.new("RGB", (64, 64), "#1a1a1a")
    draw = ImageDraw.Draw(img)
    draw.ellipse([12, 20, 52, 44], outline="#00c800", width=3)
    draw.ellipse([26, 28, 38, 40], fill="#00c800")
    return img


class TrayIcon:
    def __init__(self,
                 on_show: Callable[[], None],
                 on_quit: Callable[[], None],
                 on_report: Optional[Callable[[], None]] = None,
                 on_guide: Optional[Callable[[str], None]] = None,
                 on_profile: Optional[Callable[[str], None]] = None,
                 on_focus: Optional[Callable[[], None]] = None,
                 on_recalibrate: Optional[Callable[[], None]] = None) -> None:
        self._on_show = on_show
        self._on_quit = on_quit
        self._on_report = on_report
        self._on_guide = on_guide
        self._on_profile = on_profile
        self._on_focus = on_focus
        self._on_recalibrate = on_recalibrate
        self._icon = None

    def start(self) -> None:
        import pystray
        items = [pystray.MenuItem("إظهار النافذة", self._show, default=True)]
        if self._on_report:
            items.append(pystray.MenuItem("📊 التقرير الأسبوعي", self._report))
        if self._on_guide:
            items.append(pystray.MenuItem("📖 دليل الوضعية", lambda i, it: self._on_guide("good_posture")))
            items.append(pystray.MenuItem("👁️ تمرين العين", lambda i, it: self._on_guide("eye_rest")))
        if self._on_focus:
            items.append(pystray.MenuItem("⏱️ وضع التركيز", self._focus))
        if self._on_profile:
            profile_menu = pystray.Menu(*[
                pystray.MenuItem(p.name, (lambda name: lambda i, it: self._on_profile(name))(key))
                for key, p in PROFILES.items()
            ])
            items.append(pystray.MenuItem("⚙️ الوضع", profile_menu))
        if self._on_recalibrate:
            items.append(pystray.MenuItem("🔄 إعادة معايرة", self._recalibrate))
        items.append(pystray.MenuItem("خروج", self._quit))

        self._icon = pystray.Icon("wellness", create_tray_icon(),
                                   "Smart Desk Wellness", pystray.Menu(*items))
        threading.Thread(target=self._icon.run, daemon=True).start()

    def _show(self, icon=None, item=None):
        if self._on_show: self._on_show()
    def _report(self, icon=None, item=None):
        if self._on_report: self._on_report()
    def _focus(self, icon=None, item=None):
        if self._on_focus: self._on_focus()
    def _recalibrate(self, icon=None, item=None):
        if self._on_recalibrate: self._on_recalibrate()
    def _quit(self, icon=None, item=None):
        if self._icon: self._icon.stop()
        if self._on_quit: self._on_quit()

    def stop(self) -> None:
        if self._icon:
            try: self._icon.stop()
            except Exception: pass
            self._icon = None