"""
controller.py — Robot command dispatch layer.

Translates high-level direction strings into serial commands and
forwards them through ``BluetoothController``.  This is the single
point where direction + speed are encoded into the wire protocol.

Public API (preserved from original):
    RobotController(bluetooth)
    RobotController.forward / backward / left / right / stop
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal

from bluetooth import BluetoothController
from settings import BT_COMMAND_MAP, DEFAULT_SPEED, SPEED_MAX, SPEED_MIN


class RobotController(QObject):
    """High-level robot command interface.

    Encodes direction + speed and delegates to ``BluetoothController``.
    """

    # Emitted whenever a command is dispatched (for console logging)
    command_sent = Signal(str, str)  # (message, level)

    def __init__(
        self,
        bluetooth: BluetoothController,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._bt = bluetooth
        self._speed: int = DEFAULT_SPEED
        self._emergency: bool = False

    # ── Properties ───────────────────────────────────────────────────

    @property
    def speed(self) -> int:
        return self._speed

    @property
    def emergency(self) -> bool:
        return self._emergency

    @emergency.setter
    def emergency(self, value: bool) -> None:
        self._emergency = value

    # ── Speed ────────────────────────────────────────────────────────

    def set_speed(self, speed: int) -> None:
        """Update the movement speed (clamped to valid range).

        Sends a speed command to the robot immediately.
        """
        self._speed = max(SPEED_MIN, min(SPEED_MAX, speed))
        cmd = f"V{self._speed}\n"
        self._bt.send(cmd)
        self.command_sent.emit(f"Speed set to {self._speed}", "INFO")

    # ── Movement ─────────────────────────────────────────────────────

    def move(self, direction: str) -> None:
        """Send a direction command to the robot.

        Args:
            direction: One of ``"up"``, ``"down"``, ``"left"``,
                       ``"right"``, ``"stop"``.
        """
        if self._emergency:
            return

        char = BT_COMMAND_MAP.get(direction)
        if char is None:
            self.command_sent.emit(
                f"Unknown direction: {direction}", "WARNING",
            )
            return

        self._bt.send(char)
        self.command_sent.emit(
            f"Command: {direction.upper()} (speed {self._speed})", "INFO",
        )

    # ── Convenience wrappers (original API) ──────────────────────────

    def forward(self) -> None:
        """Move the robot forward."""
        self.move("up")

    def backward(self) -> None:
        """Move the robot backward."""
        self.move("down")

    def left(self) -> None:
        """Turn the robot left."""
        self.move("left")

    def right(self) -> None:
        """Turn the robot right."""
        self.move("right")

    def stop(self) -> None:
        """Stop the robot."""
        self.move("stop")

    # ── Emergency ────────────────────────────────────────────────────

    def emergency_stop(self) -> None:
        """Immediate halt — bypasses the emergency flag check."""
        self._emergency = True
        self._bt.send(BT_COMMAND_MAP["stop"])
        self.command_sent.emit("EMERGENCY STOP activated", "ERROR")