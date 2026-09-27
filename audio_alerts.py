"""
audio_alerts.py — System Audio Beeps & Voice Alerts module.
"""

from __future__ import annotations

import threading
from PySide6.QtCore import QObject


class AudioAlertSystem(QObject):
    """Provides audio beeps for driver station events."""

    @staticmethod
    def alert_e_stop() -> None:
        threading.Thread(target=AudioAlertSystem._beep, args=(1000, 400), daemon=True).start()

    @staticmethod
    def alert_connect() -> None:
        threading.Thread(target=AudioAlertSystem._beep, args=(800, 150), daemon=True).start()

    @staticmethod
    def alert_disconnect() -> None:
        threading.Thread(target=AudioAlertSystem._beep, args=(400, 300), daemon=True).start()

    @staticmethod
    def _beep(freq: int, duration: int) -> None:
        try:
            import winsound
            winsound.Beep(freq, duration)
        except Exception:
            pass
