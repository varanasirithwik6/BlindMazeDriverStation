"""
settings.py — Centralised configuration for the Blind Maze Driver Station.

Every tunable constant lives here so that no magic numbers leak into
the rest of the codebase.
"""

from __future__ import annotations

import os
from PySide6.QtCore import Qt

# ── Application ──────────────────────────────────────────────────────
APP_TITLE: str = "Blind Maze Driver Station Pro"
APP_WIDTH: int = 1600
APP_HEIGHT: int = 950

# ── Motion & Animation Config ───────────────────────────────────────
REDUCED_MOTION: bool = False               # Disable ambient decorative animations if True
ANIM_FPS: int = 60                          # Shared animation engine target FPS (16ms)

# ── Camera ───────────────────────────────────────────────────────────
DEFAULT_CAMERA_IP: str = "10.151.110.24:8080"
CAMERA_URL_SUFFIX: str = "/video"          # IP Webcam Android default
CAMERA_TIMEOUT_SEC: float = 2.0            # give up after this
CAMERA_RECONNECT_INTERVAL_SEC: float = 3.0 # wait before retry
TARGET_FPS: int = 30                       # desired display FPS cap
FPS_WINDOW_SIZE: int = 30                  # rolling window for FPS calc
DEFAULT_CAMERA_RESOLUTION: str = "1920x1080" # Default 1080p Full HD resolution
CAMERA_RESOLUTIONS: list[tuple[str, str]] = [
    ("1080p Full HD (1920×1080)", "1920x1080"),
    ("720p HD (1280×720)", "1280x720"),
    ("2K QHD (2560×1440)", "2560x1440"),
    ("4K UHD (3840×2160)", "3840x2160"),
    ("Default / Auto", "auto"),
]


# Recording / Snapshots
RECORDINGS_DIR: str = os.path.join("assets", "recordings")
SNAPSHOTS_DIR: str = os.path.join("assets", "snapshots")

# ── Bluetooth / Serial ──────────────────────────────────────────────
DEFAULT_COM_PORT: str = "COM12"
DEFAULT_BAUD_RATE: int = 9600
BT_SERIAL_TIMEOUT_SEC: float = 1.0
BT_RECONNECT_INTERVAL_SEC: float = 3.0
BT_COMMAND_DEDUP_MS: int = 0             # 0ms suppression for instant command dispatch

# Direction → serial character mapping (sent over HC‑05)
BT_COMMAND_MAP: dict[str, str] = {
    "up":    "F",
    "down":  "B",
    "left":  "L",
    "right": "R",
    "stop":  "S",
}

# ── Robot Control ────────────────────────────────────────────────────
DEFAULT_SPEED: int = 180
SPEED_MIN: int = 0
SPEED_MAX: int = 255
EMERGENCY_LOCKOUT_MS: int = 2000  # how long e-stop disables controls

# Speed Presets
SPEED_PRESETS: dict[str, int] = {
    "CRAWL 30%": 76,
    "CRUISE 70%": 178,
    "TURBO 100%": 255,
}

# Keyboard → direction command mapping (arrows + WASD)
DIRECTIONS: dict[int, str] = {
    Qt.Key_Up:    "up",
    Qt.Key_W:     "up",
    Qt.Key_Left:  "left",
    Qt.Key_A:     "left",
    Qt.Key_Right: "right",
    Qt.Key_D:     "right",
    Qt.Key_Down:  "down",
    Qt.Key_S:     "down",
}
STOP_KEY: int = Qt.Key_Space
EMERGENCY_KEY: int = Qt.Key_Escape

# ── Match Timer ──────────────────────────────────────────────────────
MATCH_DURATION_SEC: int | None = None

# ── Console ──────────────────────────────────────────────────────────
CONSOLE_MAX_LINES: int = 500

# ── UI Layout ────────────────────────────────────────────────────────
LEFT_PANEL_WIDTH: int = 360
RIGHT_PANEL_WIDTH: int = 340
MAIN_MARGIN: int = 15
MAIN_SPACING: int = 15
DIR_BUTTON_SIZE: int = 80
EMERGENCY_BUTTON_HEIGHT: int = 65
CAMERA_MIN_HEIGHT: int = 420
CONSOLE_MAX_HEIGHT: int = 150
