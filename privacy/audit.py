"""وحدة تدقيق الخصوصية. تحدّ الاتصال الشبكي على مستوى Python فقط (انظر الحدود في README)."""
from __future__ import annotations

import errno
import socket
from collections import deque
from typing import Any, Deque, List, Optional


class NetworkGuard:
    """يمنع connect/connect_ex لمقابس INET داخل عملية Python ويعدّ المحاولات.
    لا يغطي الشيفرة الأصلية (C/C++) ولا UDP sendto؛ التحقق الشامل يتم بأدوات النظام."""

    def __init__(self) -> None:
        self.attempts = 0
        self.installed = False
        self._orig_connect: Any = None
        self._orig_connect_ex: Any = None

    def install(self) -> None:
        if self.installed:
            return
        guard = self
        self._orig_connect = socket.socket.connect
        self._orig_connect_ex = socket.socket.connect_ex
        orig_connect, orig_ex = self._orig_connect, self._orig_connect_ex

        def blocked_connect(sock: socket.socket, *a: Any, **k: Any) -> Any:
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                guard.attempts += 1
                raise OSError(errno.EACCES, "network blocked by Privacy Audit")
            return orig_connect(sock, *a, **k)

        def blocked_connect_ex(sock: socket.socket, *a: Any, **k: Any) -> Any:
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                guard.attempts += 1
                return errno.EACCES
            return orig_ex(sock, *a, **k)

        socket.socket.connect = blocked_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = blocked_connect_ex  # type: ignore[method-assign]
        self.installed = True

    def uninstall(self) -> None:
        if self.installed:
            socket.socket.connect = self._orig_connect  # type: ignore[method-assign]
            socket.socket.connect_ex = self._orig_connect_ex  # type: ignore[method-assign]
            self.installed = False


class PrivacyAudit:
    def __init__(self, guard: Optional[NetworkGuard] = None, fps_window: int = 30) -> None:
        self._guard = guard
        self.processed = 0
        self.skipped = 0
        self._times: Deque[float] = deque(maxlen=fps_window)

    def record_processed(self, t: float) -> None:
        self.processed += 1
        self._times.append(t)

    def record_skipped(self) -> None:
        self.skipped += 1

    def fps(self) -> float:
        if len(self._times) < 2 or self._times[-1] <= self._times[0]:
            return 0.0
        return (len(self._times) - 1) / (self._times[-1] - self._times[0])

    def report_lines(self) -> List[str]:
        attempts = self._guard.attempts if self._guard else 0
        guard_on = bool(self._guard and self._guard.installed)
        return [
            "Local processing: YES (frames analysed in RAM, never written to disk)",
            f"Python-level socket guard: {'ACTIVE' if guard_on else 'OFF'}; blocked attempts: {attempts}",
            "Network bytes: NOT MEASURED by the app (verify with TCPView/Wireshark, see README)",
            f"Frames processed: {self.processed} | skipped: {self.skipped} | FPS: {self.fps():.1f}",
        ]
