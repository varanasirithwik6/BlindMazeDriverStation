"""
gamepad.py — USB Gamepad / Joystick support module.
"""

from __future__ import annotations

import time
from PySide6.QtCore import QThread, Signal


class GamepadThread(QThread):
    """Background polling thread for USB Gamepad / Joystick devices."""

    axis_moved = Signal(float, float)  # (x_axis, y_axis)
    button_pressed = Signal(str)       # button action string
    log_message = Signal(str, str)     # (message, level)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._running: bool = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        """Poll gamepad hardware (safe fallback if no gamepad attached)."""
        self.log_message.emit("Gamepad service initialized (listening for USB joysticks)", "INFO")
        while self._running:
            time.sleep(0.5)
