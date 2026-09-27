"""
joystick_overlay.py — Movable, Resizable Floating Touch Joystick & Fullscreen Video Overlay.

Features:
  - Movable Joystick Widget: Drag outer ring or drag handle to position anywhere over the video feed.
  - Keyboard Arrow Keys & WASD Controls: Drive joystick stick knob with UP/DOWN/LEFT/RIGHT arrow keys or WASD.
  - Resizable Diameter: Interactive size slider/pinch adjustment (90px to 260px diameter).
  - 2D Vector Spring Knob: Drag inner stick knob to drive robot (UP/DOWN/LEFT/RIGHT/STOP).
  - VideoFullScreenDialog: Immersive 60 FPS full screen video viewport with floating JARVIS HUD and movable joystick.
"""

from __future__ import annotations

import math
from PySide6.QtCore import Qt, Signal, QPoint, QPointF, QRectF, Slot
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QImage, QPixmap, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QSlider,
    QHBoxLayout,
    QVBoxLayout,
    QGraphicsDropShadowEffect,
)

from motion import MotionEngine, SpringSolver


class MovableJoystickOverlay(QWidget):
    """Floating, draggable & resizable 2D vector joystick control widget supporting Mouse & Keyboard controls."""

    direction_changed = Signal(str)  # "up", "down", "left", "right", "stop"
    speed_changed = Signal(int)      # PWM 0..255

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

        self._joystick_diameter: float = 160.0
        self.setFixedSize(200, 240)

        # Physics solvers for stick knob offset (dx, dy)
        self._knob_x_spring = SpringSolver(0.0, 0.0, stiffness=240.0, damping=16.0)
        self._knob_y_spring = SpringSolver(0.0, 0.0, stiffness=240.0, damping=16.0)

        # Dragging state (moving widget vs dragging joystick knob)
        self._is_dragging_widget: bool = False
        self._is_dragging_knob: bool = False
        self._drag_start_pos: QPoint = QPoint()

        self._active_direction: str = "stop"
        self._time: float = 0.0

        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def set_joystick_size(self, diameter: int) -> None:
        self._joystick_diameter = float(max(90, min(260, diameter)))
        w = int(self._joystick_diameter + 40)
        h = int(self._joystick_diameter + 75)
        self.setFixedSize(w, h)
        self.update()

    def set_keyboard_direction(self, direction: str) -> None:
        """Move the joystick stick knob via keyboard Arrow Keys or WASD."""
        max_r = self._joystick_diameter / 2.0 - 15.0
        if direction == "up":
            self._knob_x_spring.target = 0.0
            self._knob_y_spring.target = -max_r
        elif direction == "down":
            self._knob_x_spring.target = 0.0
            self._knob_y_spring.target = max_r
        elif direction == "left":
            self._knob_x_spring.target = -max_r
            self._knob_y_spring.target = 0.0
        elif direction == "right":
            self._knob_x_spring.target = max_r
            self._knob_y_spring.target = 0.0
        else:
            self._knob_x_spring.target = 0.0
            self._knob_y_spring.target = 0.0

        self._set_direction(direction)

    def _on_tick(self, dt: float) -> None:
        self._time += dt
        self._knob_x_spring.update(dt)
        self._knob_y_spring.update(dt)
        self.update()

    # ── Mouse Interaction Logic ──────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        w, h = float(self.width()), float(self.height())
        center_x, center_y = w / 2.0, 30.0 + self._joystick_diameter / 2.0

        dist_to_center = math.hypot(pos.x() - center_x, pos.y() - center_y)
        max_r = self._joystick_diameter / 2.0

        if dist_to_center <= max_r + 15.0:
            # Clicked inside joystick knob area
            self._is_dragging_knob = True
            self._update_knob_position(pos.x() - center_x, pos.y() - center_y)
        else:
            # Clicked header/outer frame -> drag entire widget window
            self._is_dragging_widget = True
            self._drag_start_pos = event.globalPosition().toPoint() - self.pos()

        event.accept()

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        w, h = float(self.width()), float(self.height())
        center_x, center_y = w / 2.0, 30.0 + self._joystick_diameter / 2.0

        if self._is_dragging_knob:
            self._update_knob_position(pos.x() - center_x, pos.y() - center_y)
        elif self._is_dragging_widget:
            new_pos = event.globalPosition().toPoint() - self._drag_start_pos
            if self.parentWidget():
                # Clamp within parent bounds
                pw, ph = self.parentWidget().width(), self.parentWidget().height()
                new_x = max(0, min(pw - self.width(), new_pos.x()))
                new_y = max(0, min(ph - self.height(), new_pos.y()))
                self.move(new_x, new_y)
            else:
                self.move(new_pos)

        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._is_dragging_knob:
            self._is_dragging_knob = False
            self._knob_x_spring.target = 0.0
            self._knob_y_spring.target = 0.0
            self._set_direction("stop")
        self._is_dragging_widget = False
        event.accept()

    def _update_knob_position(self, dx: float, dy: float) -> None:
        max_r = self._joystick_diameter / 2.0 - 15.0
        dist = math.hypot(dx, dy)
        if dist > max_r:
            dx = (dx / dist) * max_r
            dy = (dy / dist) * max_r

        self._knob_x_spring.target = dx
        self._knob_y_spring.target = dy

        # Determine directional quadrant
        angle = math.degrees(math.atan2(-dy, dx)) % 360.0
        if dist < 12.0:
            new_dir = "stop"
        elif 45.0 <= angle < 135.0:
            new_dir = "up"
        elif 135.0 <= angle < 225.0:
            new_dir = "left"
        elif 225.0 <= angle < 315.0:
            new_dir = "down"
        else:
            new_dir = "right"

        self._set_direction(new_dir)

    def _set_direction(self, new_dir: str) -> None:
        if new_dir != self._active_direction:
            self._active_direction = new_dir
            self.direction_changed.emit(new_dir)

    # ── Paint Engine ──────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        t = self._time
        dia = self._joystick_diameter
        r_outer = dia / 2.0
        cx, cy = w / 2.0, 30.0 + r_outer

        # Header Title Bar (Drag Handle)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(11, 15, 23, 210)))
        painter.drawRoundedRect(QRectF(0, 0, w, h), 10, 10)

        painter.setPen(QPen(QColor(53, 207, 255, 120), 1))
        painter.drawRoundedRect(QRectF(0, 0, w, h), 10, 10)

        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor("#35CFFF"))
        painter.drawText(QRectF(0, 4, w, 20), Qt.AlignCenter, "❖ JOYSTICK  [ARROWS / WASD]")

        # Outer Ring & Directional Ticks
        painter.setPen(QPen(QColor(53, 207, 255, 60), 2))
        painter.setBrush(QBrush(QColor(15, 23, 42, 180)))
        painter.drawEllipse(QPointF(cx, cy), r_outer, r_outer)

        for d_deg in range(0, 360, 45):
            rad = math.radians(d_deg)
            tx1 = (r_outer - 8) * math.cos(rad)
            ty1 = (r_outer - 8) * math.sin(rad)
            tx2 = r_outer * math.cos(rad)
            ty2 = r_outer * math.sin(rad)
            painter.setPen(QPen(QColor(53, 207, 255, 120), 1))
            painter.drawLine(QPointF(cx + tx1, cy + ty1), QPointF(cx + tx2, cy + ty2))

        # Inner Stick Knob Position
        kx = cx + self._knob_x_spring.value
        ky = cy + self._knob_y_spring.value
        r_knob = max(18.0, dia * 0.18)

        # Stick Vector Connection Line
        painter.setPen(QPen(QColor("#00E676"), 2, Qt.DashLine))
        painter.drawLine(QPointF(cx, cy), QPointF(kx, ky))

        # Glowing Knob Body
        knob_color = QColor("#00E676") if self._active_direction != "stop" else QColor("#35CFFF")
        glow_r = r_knob + 4.0 + 2.0 * math.sin(t * 5.0)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(knob_color.red(), knob_color.green(), knob_color.blue(), 50)))
        painter.drawEllipse(QPointF(kx, ky), glow_r, glow_r)

        painter.setBrush(QBrush(knob_color))
        painter.drawEllipse(QPointF(kx, ky), r_knob, r_knob)

        # Direction Arrow on Knob
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor("#0F172A"))
        dir_symbols = {"up": "▲", "down": "▼", "left": "◀", "right": "▶", "stop": "●"}
        painter.drawText(QRectF(kx - 12, ky - 10, 24, 20), Qt.AlignCenter, dir_symbols.get(self._active_direction, "●"))

        # Footer Status Label
        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(QRectF(0, h - 22, w, 18), Qt.AlignCenter, f"CMD: {self._active_direction.upper()}")

        painter.end()


# ════════════════════════════════════════════════════════════════════
#  Video Fullscreen Dialog Modal
# ════════════════════════════════════════════════════════════════════

class VideoFullScreenDialog(QDialog):
    """Immersive Fullscreen Video Viewport with floating JARVIS HUD and Movable Joystick Overlay."""

    def __init__(self, parent_dashboard=None) -> None:
        super().__init__(None)
        self.dashboard = parent_dashboard
        self.setWindowTitle("JARVIS Holographic Vision Core :: Full Screen")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setStyleSheet("background-color: #07090E;")

        self._live_pixmap: QPixmap | None = None
        self._pressed_fs_keys: set[int] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main Video Container
        self.video_label = QLabel(self)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setScaledContents(True)
        self.video_label.setStyleSheet("background-color: #07090E;")
        layout.addWidget(self.video_label, 1)

        # Floating Top Action Bar Overlay
        self.top_bar = QFrame(self)
        self.top_bar.setStyleSheet("""
            QFrame {
                background-color: rgba(11, 15, 23, 0.85);
                border-bottom: 1px solid #293548;
            }
        """)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(16, 8, 16, 8)

        title_lbl = QLabel("🎥 FULLSCREEN JARVIS VISION FEED  [ARROWS / WASD ACTIVE]")
        title_lbl.setStyleSheet("color: #35CFFF; font-weight: 800; font-size: 12px; font-family: Consolas;")

        size_caption = QLabel("JOYSTICK SIZE:")
        size_caption.setStyleSheet("color: #94A3B8; font-weight: 700; font-size: 10px; font-family: Consolas;")

        self.size_slider = QSlider(Qt.Horizontal, self)
        self.size_slider.setRange(90, 240)
        self.size_slider.setValue(160)
        self.size_slider.setFixedWidth(140)
        self.size_slider.valueChanged.connect(self._on_joystick_size_changed)

        self.reset_pos_btn = QPushButton("RESET POS")
        self.reset_pos_btn.setStyleSheet("""
            QPushButton {
                background-color: #1F2636;
                color: #35CFFF;
                border: 1px solid #293548;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284C7;
                color: white;
            }
        """)
        self.reset_pos_btn.clicked.connect(self._reset_joystick_pos)

        self.exit_btn = QPushButton("✕ EXIT FULLSCREEN [ESC]")
        self.exit_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                color: #EF4444;
                border: 1px solid #EF4444;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #DC2626;
                color: white;
            }
        """)
        self.exit_btn.clicked.connect(self.close)

        top_layout.addWidget(title_lbl)
        top_layout.addStretch()
        top_layout.addWidget(size_caption)
        top_layout.addWidget(self.size_slider)
        top_layout.addWidget(self.reset_pos_btn)
        top_layout.addWidget(self.exit_btn)

        self.top_bar.move(0, 0)

        # Floating Movable & Resizable Joystick Overlay
        self.joystick_overlay = MovableJoystickOverlay(self)
        self.joystick_overlay.direction_changed.connect(self._on_joystick_direction)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.showFullScreen()
        self.top_bar.resize(self.width(), 44)
        self._reset_joystick_pos()
        self.setFocus()
        self.activateWindow()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "top_bar") and self.top_bar:
            self.top_bar.resize(self.width(), 44)

    def update_frame(self, qimage: QImage) -> None:
        self.video_label.setPixmap(QPixmap.fromImage(qimage))

    def _reset_joystick_pos(self) -> None:
        # Default bottom-right corner positioning
        jw, jh = self.joystick_overlay.width(), self.joystick_overlay.height()
        self.joystick_overlay.move(self.width() - jw - 40, self.height() - jh - 40)

    def _on_joystick_size_changed(self, val: int) -> None:
        self.joystick_overlay.set_joystick_size(val)

    def _on_joystick_direction(self, direction: str) -> None:
        if self.dashboard:
            if direction == "stop":
                if hasattr(self.dashboard, "_on_stop_pressed"):
                    self.dashboard._on_stop_pressed()
                elif hasattr(self.dashboard, "send_command"):
                    self.dashboard.send_command("stop")
            else:
                if hasattr(self.dashboard, "_on_input_press"):
                    self.dashboard._on_input_press(direction)
                elif hasattr(self.dashboard, "send_command"):
                    self.dashboard.send_command(direction)

    # ── Keyboard Arrow Keys & WASD Controls ──────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key_Escape:
            self.close()
            return

        key_map = {
            Qt.Key_Up: "up",
            Qt.Key_W: "up",
            Qt.Key_Down: "down",
            Qt.Key_S: "down",
            Qt.Key_Left: "left",
            Qt.Key_A: "left",
            Qt.Key_Right: "right",
            Qt.Key_D: "right",
        }

        if key in key_map:
            self._pressed_fs_keys.add(key)
            direction = key_map[key]
            self.joystick_overlay.set_keyboard_direction(direction)
            if self.dashboard and hasattr(self.dashboard, "_on_input_press"):
                self.dashboard._on_input_press(direction)
            elif self.dashboard and hasattr(self.dashboard, "send_command"):
                self.dashboard.send_command(direction)
        else:
            if self.dashboard:
                self.dashboard.keyPressEvent(event)
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        key = event.key()
        key_map = {
            Qt.Key_Up: "up", Qt.Key_W: "up",
            Qt.Key_Down: "down", Qt.Key_S: "down",
            Qt.Key_Left: "left", Qt.Key_A: "left",
            Qt.Key_Right: "right", Qt.Key_D: "right",
        }
        if key in key_map:
            direction = key_map[key]
            self._pressed_fs_keys.discard(key)
            if self.dashboard and hasattr(self.dashboard, "_on_input_release"):
                self.dashboard._on_input_release(direction)
            if not any(k in key_map for k in self._pressed_fs_keys):
                self.joystick_overlay.set_keyboard_direction("stop")
        else:
            if self.dashboard:
                self.dashboard.keyReleaseEvent(event)
            super().keyReleaseEvent(event)
