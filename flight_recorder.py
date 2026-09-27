"""
flight_recorder.py — Black-Box Flight Telemetry Recorder & Replay Engine.

Logs 60 FPS robot telemetry runs into JSON flight logs and provides real-time
playback at 1x, 2x, and 4x speed multipliers with signal synchronization.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from PySide6.QtCore import QObject, Signal, Slot

from settings import RECORDINGS_DIR


class FlightRecorder(QObject):
    """Black-box telemetry recorder capturing session runs for flight replay."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._is_recording: bool = False
        self._frames: list[dict] = []
        self._start_time: float = 0.0

        if not os.path.exists(RECORDINGS_DIR):
            os.makedirs(RECORDINGS_DIR, exist_ok=True)

    def start_recording(self) -> None:
        self._is_recording = True
        self._frames.clear()
        self._start_time = time.perf_counter()

    def record_frame(
        self,
        x: float,
        y: float,
        heading: float,
        speed: int,
        fps: float,
        ping: float | int,
        command: str = "STOP",
    ) -> None:
        if not self._is_recording:
            return
        t_rel = time.perf_counter() - self._start_time
        self._frames.append({
            "t_rel": round(t_rel, 3),
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "x": round(x, 2),
            "y": round(y, 2),
            "heading": round(heading, 1),
            "speed": speed,
            "fps": round(fps, 1),
            "ping": round(float(ping), 1),
            "command": command,
        })

    def stop_recording(self) -> str | None:
        if not self._is_recording or not self._frames:
            self._is_recording = False
            return None

        self._is_recording = False
        filename = f"flight_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(RECORDINGS_DIR, filename)

        session_data = {
            "version": "1.0",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_frames": len(self._frames),
            "duration_sec": round(self._frames[-1]["t_rel"], 2),
            "frames": self._frames,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

        return filepath


class ReplayEngine(QObject):
    """60 FPS flight log playback engine supporting 1x, 2x, 4x speeds."""

    frame_replayed = Signal(dict)
    replay_finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._is_replaying: bool = False
        self._speed_multiplier: float = 1.0
        self._frames: list[dict] = []
        self._current_idx: int = 0

    @Slot(str)
    def load_session_file(self, filepath: str) -> bool:
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._frames = data.get("frames", [])
                self._current_idx = 0
                return len(self._frames) > 0
        except Exception:
            return False

    def set_speed_multiplier(self, multiplier: float) -> None:
        self._speed_multiplier = multiplier

    def start_replay(self) -> None:
        if not self._frames:
            return
        self._is_replaying = True
        self._current_idx = 0

    def pause_replay(self) -> None:
        self._is_replaying = False

    def step_tick(self) -> None:
        if not self._is_replaying or self._current_idx >= len(self._frames):
            if self._is_replaying and self._current_idx >= len(self._frames):
                self._is_replaying = False
                self.replay_finished.emit()
            return

        frame = self._frames[self._current_idx]
        self.frame_replayed.emit(frame)
        step = max(1, int(1 * self._speed_multiplier))
        self._current_idx += step
