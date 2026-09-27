"""
motion.py — Centralized Motion, Physics & Animation Engine for Driver Station.

Commercial Robotics HMI Grade Animation System providing:
  - MotionEngine: High-precision 60 FPS master clock with microsecond delta-t.
  - SpringSolver: 2nd order mass-spring-damper physical dynamics engine.
  - AnimatedNumberLabel: Smooth spring value interpolation for numeric displays.
  - AnimatedStatusBadge: Fluid color, opacity, glow, and scale transitions for status elements.
  - GlobalHoverFilter & install_hover_elevation: Micro-interactions, scale, shadow, and border animators.
  - RippleOverlay & install_ripple: Zero-latency touch/click ripple physics.
  - CardGlowEffect: 60 FPS ambient pulse and elevated shadow engine.
  - staggered_fade_in / fade_in_widget: Hardware-accelerated startup panel reveals.
  - LiveClockLabel: Self-updating live digital clock readout.
  - AIOperatingSystemBackground: High-performance 60 FPS ambient background layer featuring 13 blueprint & AI OS elements strictly under 5% opacity, plus inter-subsystem data flow lines, glass specular reflections, and mouse parallax drift.
  - AIBootSequenceOverlay: Cinematic AI Boot Sequence overlay with rotating HUD rings, spring percentage solver, typing terminal, and module health status.
  - JARVISHolographicViewport: JARVIS Iron Man Holographic HUD Camera Viewport with pre-scaled zero-lag frame rendering, 3D LiDAR point-cloud hologram, dual-camera PiP stream, target lock reticle animations & artificial horizon.
  - MissionControlPanel: Premium Mission Control panel rendering 11 live animated metrics.
  - SubsystemPipelineOverlay: Animated subsystem data flow conduit bar (Bluetooth, Camera, Vision, Nav, Motors) with dynamic font-metric string fitting.
  - AnimatedSlider: Custom painted slider with glowing thumb spring tracking, gradient progress fill, and circular progress arc.
  - IdleAICoreWidget: Idle AI Core Neural Activity Monitor displaying thinking animations, neural network synapses, flowing nodes, rotating AI core, and mini matrix stream.
  - MissionCompleteOverlay: Premium Commercial HMI Mission Complete Overlay rendering animated vector checkmark, 8 statistics cards, timeline completion, and professional summary.
"""

from __future__ import annotations

import math
import random
import time
from datetime import datetime
from typing import Callable, Any

from PySide6.QtCore import (
    Qt,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    QPropertyAnimation,
    QEasingCurve,
    QTimer,
    QEvent,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QLinearGradient, QPainterPath, QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QFrame,
    QPushButton,
    QSlider,
    QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
)

from settings import REDUCED_MOTION, ANIM_FPS


# ════════════════════════════════════════════════════════════════════
#  1. Mass-Spring-Damper Physics Solver
# ════════════════════════════════════════════════════════════════════

class SpringSolver:
    """Second-order Mass-Spring-Damper numerical solver (Hooke's Law + Damping)."""

    def __init__(
        self,
        value: float = 0.0,
        target: float = 0.0,
        stiffness: float = 180.0,
        damping: float = 14.0,
        mass: float = 1.0,
    ) -> None:
        self.value: float = float(value)
        self.target: float = float(target)
        self.velocity: float = 0.0
        self.stiffness: float = stiffness
        self.damping: float = damping
        self.mass: float = mass
        self.precision: float = 0.001

    def update(self, dt: float = 0.016) -> float:
        if REDUCED_MOTION:
            self.value = self.target
            self.velocity = 0.0
            return self.value

        dt = min(dt, 0.032)
        displacement = self.value - self.target
        spring_force = -self.stiffness * displacement
        damping_force = -self.damping * self.velocity
        acceleration = (spring_force + damping_force) / self.mass

        self.velocity += acceleration * dt
        self.value += self.velocity * dt

        if abs(self.velocity) < self.precision and abs(self.value - self.target) < self.precision:
            self.value = self.target
            self.velocity = 0.0

        return self.value

    def is_settled(self) -> bool:
        return self.value == self.target and self.velocity == 0.0

    def snap_to(self, val: float) -> None:
        self.value = float(val)
        self.target = float(val)
        self.velocity = 0.0


# ════════════════════════════════════════════════════════════════════
#  2. Central Motion Engine Singleton
# ════════════════════════════════════════════════════════════════════

class MotionEngine(QObject):
    """Singleton timer coordinator driving all 60 FPS ambient UI ticks."""

    tick = Signal(float)       # Emits phase angle in degrees (0.0 .. 360.0)
    tick_dt = Signal(float)    # Emits delta time in seconds (~0.016)

    _instance: MotionEngine | None = None

    @classmethod
    def instance(cls) -> MotionEngine:
        if cls._instance is None:
            cls._instance = MotionEngine()
        return cls._instance

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._angle: float = 0.0
        self._last_time: float = time.perf_counter()
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / ANIM_FPS))
        self._timer.timeout.connect(self._on_timeout)
        self.reduced_motion: bool = REDUCED_MOTION

    def start(self) -> None:
        if not self._timer.isActive() and not self.reduced_motion:
            self._last_time = time.perf_counter()
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _on_timeout(self) -> None:
        now = time.perf_counter()
        dt = now - self._last_time
        self._last_time = now

        self._angle = (self._angle + 3.0) % 360.0
        self.tick.emit(self._angle)
        self.tick_dt.emit(dt)

    @property
    def current_angle(self) -> float:
        return self._angle


# ════════════════════════════════════════════════════════════════════
#  3. Animated Numeric Label
# ════════════════════════════════════════════════════════════════════

class AnimatedNumberLabel(QLabel):
    """Label whose displayed numeric value spring-interpolates smoothly."""

    def __init__(
        self,
        parent=None,
        initial_value: float = 0.0,
        fmt: str = "{:d}",
        stiffness: float = 160.0,
        damping: float = 15.0,
    ) -> None:
        super().__init__(parent)
        self._spring = SpringSolver(
            value=initial_value,
            target=initial_value,
            stiffness=stiffness,
            damping=damping,
        )
        self._fmt = fmt
        self._formatter: Callable[[float], str] | None = None
        self.setText(self._format_value(initial_value))
        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def set_format(self, fmt: str) -> None:
        self._fmt = fmt

    def set_formatter(self, fn: Callable[[float], str]) -> None:
        self._formatter = fn

    @Slot(float)
    def set_value(self, val: float) -> None:
        self._spring.target = float(val)

    def snap_value(self, val: float) -> None:
        self._spring.snap_to(val)
        self.setText(self._format_value(val))

    def _format_value(self, val: float) -> str:
        if self._formatter:
            return self._formatter(val)
        if "{:d}" in self._fmt or "%d" in self._fmt or "d" in self._fmt[-1:]:
            return self._fmt.format(int(round(val)))
        return self._fmt.format(val)

    def _on_tick(self, dt: float) -> None:
        if self._spring.is_settled():
            return
        curr = self._spring.update(dt)
        self.setText(self._format_value(curr))


# ════════════════════════════════════════════════════════════════════
#  4. Animated Status Badge Widget
# ════════════════════════════════════════════════════════════════════

class AnimatedStatusBadge(QLabel):
    """Status badge with smooth color, glow pulse, opacity fade, and scale feedback."""

    def __init__(self, text: str = "OFFLINE", color_hex: str = "#94A3B8", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBadge")
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Consolas", 9, QFont.Bold))
        
        self._target_bg = QColor(color_hex)
        self._current_bg = QColor(color_hex)
        self._scale_spring = SpringSolver(value=1.0, target=1.0, stiffness=220.0, damping=16.0)
        self._glow_phase = 0.0

        self.setText(text)
        self._update_style()
        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def set_status(self, text: str, color_hex: str, pulse: bool = True) -> None:
        self.setText(text)
        self._target_bg = QColor(color_hex)
        self._scale_spring.velocity = 0.15
        self.update()

    def _on_tick(self, dt: float) -> None:
        r = self._current_bg.red() + (self._target_bg.red() - self._current_bg.red()) * min(1.0, dt * 10.0)
        g = self._current_bg.green() + (self._target_bg.green() - self._current_bg.green()) * min(1.0, dt * 10.0)
        b = self._current_bg.blue() + (self._target_bg.blue() - self._current_bg.blue()) * min(1.0, dt * 10.0)
        self._current_bg = QColor(int(r), int(g), int(b))
        
        if not self._scale_spring.is_settled():
            self._scale_spring.update(dt)

        self._glow_phase = (self._glow_phase + dt * 4.0) % (2 * math.pi)
        self._update_style()

    def _update_style(self) -> None:
        hex_str = self._current_bg.name()
        r, g, b = self._current_bg.red(), self._current_bg.green(), self._current_bg.blue()
        border_alpha = int(180 + 50 * math.sin(self._glow_phase))
        self.setStyleSheet(f"""
            QLabel#statusBadge {{
                background-color: rgba({r}, {g}, {b}, 0.20);
                color: {hex_str};
                border: 1px solid rgba({r}, {g}, {b}, {border_alpha / 255.0:.2f});
                border-radius: 6px;
                padding: 4px 10px;
            }}
        """)


# ════════════════════════════════════════════════════════════════════
#  5. Global Hover & Click Micro-Interaction Event Filter
# ════════════════════════════════════════════════════════════════════

class HoverElevationFilter(QObject):
    """Attaches hardware-accelerated spring scale, hover elevation shadow & glowing border to widgets."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._widgets: dict[QWidget, dict] = {}
        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def attach(self, widget: QWidget, is_button: bool = False, max_scale: float = 1.02) -> None:
        if widget in self._widgets:
            return

        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 80))
        widget.setGraphicsEffect(shadow)

        entry = {
            "is_button": is_button,
            "hovered": False,
            "pressed": False,
            "max_scale": max_scale,
            "shadow": shadow,
            "scale_spring": SpringSolver(1.0, 1.0, stiffness=240.0, damping=18.0),
            "elev_spring": SpringSolver(2.0, 2.0, stiffness=180.0, damping=16.0),
            "blur_spring": SpringSolver(8.0, 8.0, stiffness=180.0, damping=16.0),
            "border_alpha": SpringSolver(0.0, 0.0, stiffness=160.0, damping=15.0),
        }

        self._widgets[widget] = entry
        widget.installEventFilter(self)

        if is_button and isinstance(widget, QPushButton):
            install_ripple(widget)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched in self._widgets:
            data = self._widgets[watched]

            if event.type() == QEvent.Enter:
                data["hovered"] = True
                data["scale_spring"].target = data["max_scale"]
                data["elev_spring"].target = 6.0
                data["blur_spring"].target = 18.0
                data["border_alpha"].target = 200.0

            elif event.type() == QEvent.Leave:
                data["hovered"] = False
                data["pressed"] = False
                data["scale_spring"].target = 1.0
                data["elev_spring"].target = 2.0
                data["blur_spring"].target = 8.0
                data["border_alpha"].target = 0.0

            elif event.type() == QEvent.MouseButtonPress:
                if data["is_button"]:
                    data["pressed"] = True
                    data["scale_spring"].target = 0.96

            elif event.type() == QEvent.MouseButtonRelease:
                if data["is_button"] and data["pressed"]:
                    data["pressed"] = False
                    data["scale_spring"].target = data["max_scale"] if data["hovered"] else 1.0

        return super().eventFilter(watched, event)

    def _on_tick(self, dt: float) -> None:
        to_remove = []
        for w, data in self._widgets.items():
            try:
                data["scale_spring"].update(dt)
                e_val = data["elev_spring"].update(dt)
                b_val = data["blur_spring"].update(dt)
                data["border_alpha"].update(dt)

                shadow: QGraphicsDropShadowEffect = data["shadow"]
                if shadow and w.graphicsEffect() is shadow:
                    shadow.setBlurRadius(b_val)
                    shadow.setOffset(0, int(e_val))
                    if data["hovered"]:
                        shadow.setColor(QColor(53, 207, 255, int(min(120, b_val * 6))))
                    else:
                        shadow.setColor(QColor(0, 0, 0, 80))
            except RuntimeError:
                to_remove.append(w)

        for w in to_remove:
            del self._widgets[w]


_global_hover_filter: HoverElevationFilter | None = None

def install_hover_elevation(widget: QWidget, is_button: bool = False, max_scale: float = 1.02) -> None:
    """Convenience helper to attach hardware spring elevation and hover response."""
    global _global_hover_filter
    if _global_hover_filter is None:
        _global_hover_filter = HoverElevationFilter()
    _global_hover_filter.attach(widget, is_button=is_button, max_scale=max_scale)


# ════════════════════════════════════════════════════════════════════
#  6. Ripple Overlay Widget
# ════════════════════════════════════════════════════════════════════

class RippleOverlay(QWidget):
    """Translucent circular ripple drawn over a button on click."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setStyleSheet("background: transparent; border: none;")
        self._ripples: list[dict] = []
        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def add_ripple(self, pos: QPoint) -> None:
        self._ripples.append({
            "center": pos,
            "radius": 0.0,
            "max_radius": max(self.width(), self.height()) * 0.95,
            "alpha": 150.0,
            "spring": SpringSolver(value=0.0, target=max(self.width(), self.height()) * 0.95, stiffness=140.0, damping=14.0)
        })
        self.update()

    def _on_tick(self, dt: float) -> None:
        if not self._ripples:
            return
        to_remove = []
        for r in self._ripples:
            r["radius"] = r["spring"].update(dt)
            r["alpha"] = max(0.0, r["alpha"] - dt * 250.0)
            if r["alpha"] <= 0 or r["spring"].is_settled():
                to_remove.append(r)
        for r in to_remove:
            self._ripples.remove(r)
        self.update()

    def paintEvent(self, event) -> None:
        if not self._ripples:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for r in self._ripples:
            color = QColor(53, 207, 255, int(r["alpha"]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(
                r["center"],
                int(r["radius"]),
                int(r["radius"]),
            )
        painter.end()


def install_ripple(button: QPushButton) -> RippleOverlay:
    """Attach a non-blocking ripple overlay to any QPushButton."""
    overlay = RippleOverlay(button)
    overlay.resize(button.size())

    original_press = button.mousePressEvent

    def _on_press(event):
        overlay.resize(button.size())
        overlay.add_ripple(event.pos())
        original_press(event)

    button.mousePressEvent = _on_press
    return overlay


# ════════════════════════════════════════════════════════════════════
#  7. Status Card Pulsing Glow Effect
# ════════════════════════════════════════════════════════════════════

class CardGlowEffect:
    """Attaches a subtle cyan drop-shadow pulse to status cards."""

    def __init__(self, widget: QWidget) -> None:
        self._widget = widget
        self._shadow = QGraphicsDropShadowEffect(widget)
        self._shadow.setBlurRadius(8)
        self._shadow.setColor(QColor(53, 207, 255, 35))
        self._shadow.setOffset(0, 0)
        self._widget.setGraphicsEffect(self._shadow)
        MotionEngine.instance().tick.connect(self._on_tick)

    def _on_tick(self, phase: float) -> None:
        if REDUCED_MOTION:
            return
        try:
            if self._widget.graphicsEffect() is self._shadow:
                rad = 6 + int(6 * (0.5 + 0.5 * math.sin(math.radians(phase * 2))))
                self._shadow.setBlurRadius(rad)
        except RuntimeError:
            pass


# ════════════════════════════════════════════════════════════════════
#  8. Smooth Fade-In & Cascade Panel Reveal Helpers
# ════════════════════════════════════════════════════════════════════

def fade_in_widget(widget: QWidget, duration_ms: int = 400, delay_ms: int = 0) -> None:
    """Smoothly fade a widget from opacity 0 -> 1 using QPropertyAnimation."""
    if REDUCED_MOTION:
        return

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setDuration(duration_ms)
    anim.setEasingCurve(QEasingCurve.OutCubic)

    anim.finished.connect(lambda: widget.setGraphicsEffect(None))

    if delay_ms > 0:
        QTimer.singleShot(delay_ms, anim.start)
    else:
        anim.start()

    widget._fade_anim = anim


def staggered_fade_in(widgets: list[QWidget], interval_ms: int = 60, base_duration: int = 350) -> None:
    """Cascade fade-in multiple panels or cards on app startup."""
    for idx, w in enumerate(widgets):
        fade_in_widget(w, duration_ms=base_duration, delay_ms=idx * interval_ms)


# ════════════════════════════════════════════════════════════════════
#  9. Live Clock Readout Label
# ════════════════════════════════════════════════════════════════════

class LiveClockLabel(QLabel):
    """Self-updating live digital clock readout."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("fieldCaption")
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._update_clock()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)

    def _update_clock(self) -> None:
        self.setText(datetime.now().strftime("CLK  %H:%M:%S"))


# ════════════════════════════════════════════════════════════════════
#  10. AI Operating System Ambient Background, Parallax & Glass Specular
# ════════════════════════════════════════════════════════════════════

class AIOperatingSystemBackground(QWidget):
    """High-performance 60 FPS AI OS ambient background layer with mouse parallax drift and glass specular reflections."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setStyleSheet("background: transparent; border: none;")

        self._time: float = 0.0
        self._parallax_x_spring = SpringSolver(0.0, 0.0, stiffness=120.0, damping=14.0)
        self._parallax_y_spring = SpringSolver(0.0, 0.0, stiffness=120.0, damping=14.0)

        random.seed(42)
        self._particles = [
            {
                "x": random.uniform(0.0, 1.0),
                "y": random.uniform(0.0, 1.0),
                "speed": random.uniform(0.02, 0.08),
                "sway": random.uniform(0.5, 2.0),
                "size": random.uniform(1.5, 3.5),
                "phase": random.uniform(0.0, 6.28),
            }
            for _ in range(36)
        ]

        self._interconnect_buses = [
            {"path": [(0.18, 0.2), (0.28, 0.2), (0.28, 0.35), (0.4, 0.35)], "color": QColor("#00E676"), "packets": ["BT_ACK", "0x5A", "LINK_OK"]},
            {"path": [(0.6, 0.25), (0.72, 0.25), (0.72, 0.4), (0.82, 0.4)], "color": QColor("#35CFFF"), "packets": ["FRAME_30", "CAM_RAW", "MJPEG"]},
            {"path": [(0.5, 0.65), (0.65, 0.65), (0.65, 0.75), (0.82, 0.75)], "color": QColor("#FBBF24"), "packets": ["PWM_255", "DIR_FWD", "MOTOR_STEP"]},
        ]

        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def mouseMoveEvent(self, event) -> None:
        w, h = float(self.width()), float(self.height())
        mx, my = event.position().x(), event.position().y()
        self._parallax_x_spring.target = ((mx / max(1.0, w)) - 0.5) * 25.0
        self._parallax_y_spring.target = ((my / max(1.0, h)) - 0.5) * 25.0
        super().mouseMoveEvent(event)

    def _on_tick(self, dt: float) -> None:
        if REDUCED_MOTION:
            return
        self._time += dt
        self._parallax_x_spring.update(dt)
        self._parallax_y_spring.update(dt)
        self.update()

    def paintEvent(self, event) -> None:
        if REDUCED_MOTION:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        para_x = self._parallax_x_spring.value
        para_y = self._parallax_y_spring.value
        cx, cy = w / 2.0 + para_x, h / 2.0 + para_y
        t = self._time

        CYAN_DIM = QColor(53, 207, 255, 10)

        grid_size = 50.0
        offset_x = (t * 12.0 + para_x * 0.5) % grid_size
        offset_y = (t * 8.0 + para_y * 0.5) % grid_size

        painter.setPen(QPen(CYAN_DIM, 1, Qt.DotLine))
        x = offset_x
        while x < w:
            painter.drawLine(int(x), 0, int(x), int(h))
            x += grid_size

        y = offset_y
        while y < h:
            painter.drawLine(0, int(y), int(w), int(y))
            y += grid_size

        painter.setPen(QPen(CYAN_DIM, 1))

        for r_circle, dash in [(120.0, Qt.SolidLine), (220.0, Qt.DashLine), (340.0, Qt.DotLine)]:
            painter.setPen(QPen(CYAN_DIM, 1, dash))
            painter.drawEllipse(QPointF(cx, cy), r_circle, r_circle)

        radar_angle = (t * 0.8) % (2 * math.pi)
        rx = cx + 320.0 * math.cos(radar_angle)
        ry = cy + 320.0 * math.sin(radar_angle)
        painter.setPen(QPen(QColor(53, 207, 255, 12), 1.5))
        painter.drawLine(int(cx), int(cy), int(rx), int(ry))

        sweep_path = QPainterPath()
        sweep_path.moveTo(cx, cy)
        sweep_path.arcTo(cx - 320, cy - 320, 640, 640, math.degrees(-radar_angle), 35)
        sweep_path.closeSubpath()
        painter.fillPath(sweep_path, QBrush(QColor(53, 207, 255, 6)))

        # Glass Specular Light Beam Reflection Sweep (8 second period)
        beam_x = ((t * 0.125) % 1.0) * (w + 400.0) - 200.0
        beam_grad = QLinearGradient(beam_x, 0, beam_x + 120.0, h)
        beam_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        beam_grad.setColorAt(0.5, QColor(255, 255, 255, 8))
        beam_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(beam_grad))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, int(w), int(h))

        for bus in self._interconnect_buses:
            path_nodes = bus["path"]
            color: QColor = bus["color"]
            
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 12), 1.5, Qt.DashLine))
            for i in range(len(path_nodes) - 1):
                p1 = (path_nodes[i][0] * w + para_x * 0.3, path_nodes[i][1] * h + para_y * 0.3)
                p2 = (path_nodes[i+1][0] * w + para_x * 0.3, path_nodes[i+1][1] * h + para_y * 0.3)
                painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

                prog = (t * 0.4 + i * 0.3) % 1.0
                nx = p1[0] + (p2[0] - p1[0]) * prog
                ny = p1[1] + (p2[1] - p1[1]) * prog
                
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 140)))
                painter.drawEllipse(QPointF(nx, ny), 3.5, 3.5)

                painter.drawEllipse(QPointF(p1[0], p1[1]), 4.0, 4.0)

        painter.setPen(Qt.NoPen)
        for p in self._particles:
            px = ((p["x"] * w + math.sin(t * p["sway"] + p["phase"]) * 30.0 + para_x * 0.2) % w)
            py = ((p["y"] * h - t * p["speed"] * 80.0 + para_y * 0.2) % h)
            p_alpha = int(4 + 6 * (0.5 + 0.5 * math.sin(t * 2.0 + p["phase"])))
            painter.setBrush(QBrush(QColor(53, 207, 255, p_alpha)))
            painter.drawEllipse(QPointF(px, py), p["size"], p["size"])

        painter.end()


# ════════════════════════════════════════════════════════════════════
#  11. Cinematic AI Boot Sequence Overlay
# ════════════════════════════════════════════════════════════════════

class AIBootSequenceOverlay(QWidget):
    """Cinematic AI Boot Sequence Overlay widget."""

    boot_completed = Signal()

    BOOT_STAGES = [
        ("Power On", "POWER_ON", 8.0),
        ("Initializing AI Core", "AI_CORE", 18.0),
        ("Loading Vision Engine", "VISION_ENGINE", 28.0),
        ("Loading Camera Pipeline", "CAM_PIPELINE", 38.0),
        ("Loading Navigation System", "NAV_SYSTEM", 48.0),
        ("Loading Bluetooth Controller", "BT_CONTROLLER", 58.0),
        ("Loading Motion Planner", "MOTION_PLANNER", 68.0),
        ("Loading Mission Engine", "MISSION_ENGINE", 78.0),
        ("Running Diagnostics", "DIAGNOSTICS", 88.0),
        ("Connecting Services", "SERVICES", 95.0),
        ("System Ready", "SYSTEM_READY", 100.0),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: #07090E;")

        self._stage_idx: int = 0
        self._pct_spring = SpringSolver(0.0, 0.0, stiffness=140.0, damping=15.0)
        self._elapsed_time: float = 0.0
        self._rot_angle: float = 0.0
        self._fade_started: bool = False

        self._terminal_logs: list[str] = ["[00:00.00] > SYSTEM POWER ON INITIATED..."]
        self._module_health: dict[str, str] = {
            "AI CORE": "INITIALIZING",
            "VISION ENGINE": "WAITING",
            "CAM PIPELINE": "WAITING",
            "NAV SYSTEM": "WAITING",
            "BT LINK": "WAITING",
            "MOTION PLANNER": "WAITING",
            "MISSION ENGINE": "WAITING",
            "DIAGNOSTICS": "PENDING",
        }

        self._step_timer = QTimer(self)
        self._step_timer.setInterval(280)
        self._step_timer.timeout.connect(self._advance_stage)

        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def start_boot(self) -> None:
        self.show()
        self.raise_()
        self._step_timer.start()

    def _advance_stage(self) -> None:
        if self._stage_idx < len(self.BOOT_STAGES) - 1:
            self._stage_idx += 1
            stage_name, mod_key, target_pct = self.BOOT_STAGES[self._stage_idx]
            self._pct_spring.target = target_pct

            timestamp = datetime.now().strftime("%M:%S.%f")[:-4]
            self._terminal_logs.append(f"[{timestamp}] > {stage_name.upper()}...")
            if len(self._terminal_logs) > 6:
                self._terminal_logs.pop(0)

            if mod_key in ["AI_CORE", "VISION_ENGINE", "CAM_PIPELINE", "NAV_SYSTEM", "BT_CONTROLLER", "MOTION_PLANNER", "MISSION_ENGINE"]:
                display_name = stage_name.replace("Loading ", "").replace("Initializing ", "").upper()
                for k in list(self._module_health.keys()):
                    if k in display_name or display_name in k:
                        self._module_health[k] = "ONLINE ✓"
            elif mod_key == "DIAGNOSTICS":
                self._module_health["DIAGNOSTICS"] = "100% OK"

        else:
            self._step_timer.stop()
            if not self._fade_started:
                self._fade_started = True
                QTimer.singleShot(400, self._finish_boot)

    def _finish_boot(self) -> None:
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setDuration(500)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        
        def _on_done():
            self.hide()
            self.boot_completed.emit()

        anim.finished.connect(_on_done)
        anim.start()
        self._fade_anim = anim

    def _on_tick(self, dt: float) -> None:
        self._elapsed_time += dt
        self._rot_angle = (self._rot_angle + dt * 90.0) % 360.0
        self._pct_spring.update(dt)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        cx, cy = w / 2.0, h / 2.0 - 50.0

        painter.fillRect(0, 0, int(w), int(h), QColor("#07090E"))
        grid_pen = QPen(QColor(53, 207, 255, 12), 1, Qt.DotLine)
        painter.setPen(grid_pen)
        for x in range(0, int(w), 40): painter.drawLine(x, 0, x, int(h))
        for y in range(0, int(h), 40): painter.drawLine(0, y, int(w), y)

        r_outer = 135.0
        r_mid = 110.0
        r_inner = 85.0

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._rot_angle)
        painter.setPen(QPen(QColor(53, 207, 255, 60), 1.5, Qt.DashLine))
        painter.drawEllipse(QPointF(0, 0), r_outer, r_outer)
        for i in range(12):
            rad = i * (math.pi / 6.0)
            tx1 = (r_outer - 8) * math.cos(rad)
            ty1 = (r_outer - 8) * math.sin(rad)
            tx2 = r_outer * math.cos(rad)
            ty2 = r_outer * math.sin(rad)
            painter.drawLine(QPointF(tx1, ty1), QPointF(tx2, ty2))
        painter.restore()

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-self._rot_angle * 1.4)
        painter.setPen(QPen(QColor(0, 230, 118, 50), 1, Qt.DotLine))
        painter.drawEllipse(QPointF(0, 0), r_inner, r_inner)
        painter.restore()

        pct_val = self._pct_spring.value
        span_angle = int((pct_val / 100.0) * 360.0 * 16.0)
        arc_pen = QPen(QColor("#35CFFF"), 3.5)
        arc_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(QRectF(cx - r_mid, cy - r_mid, r_mid * 2, r_mid * 2), 90 * 16, -span_angle)

        painter.setFont(QFont("Consolas", 28, QFont.Bold))
        painter.setPen(QColor("#F8FAFC"))
        painter.drawText(QRectF(cx - 100, cy - 25, 200, 40), Qt.AlignCenter, f"{int(round(pct_val))}%")

        stage_name = self.BOOT_STAGES[self._stage_idx][0].upper()
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        pulsing_alpha = int(180 + 75 * math.sin(self._elapsed_time * 6.0))
        painter.setPen(QColor(53, 207, 255, pulsing_alpha))
        painter.drawText(QRectF(cx - 250, cy + r_outer + 20, 500, 25), Qt.AlignCenter, f"●  {stage_name}...")

        bar_w = min(600.0, w - 80.0)
        bar_h = 8.0
        bar_x = (w - bar_w) / 2.0
        bar_y = cy + r_outer + 65.0

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(30, 41, 59, 200)))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 4, 4)

        fill_w = max(4.0, (pct_val / 100.0) * bar_w)
        grad = QLinearGradient(bar_x, bar_y, bar_x + fill_w, bar_y)
        grad.setColorAt(0.0, QColor("#35CFFF"))
        grad.setColorAt(1.0, QColor("#00E676"))
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 4, 4)

        painter.setBrush(QBrush(QColor("#00E676")))
        painter.drawEllipse(QPointF(bar_x + fill_w, bar_y + bar_h / 2.0), 5.0, 5.0)

        term_w = 420.0
        term_h = 130.0
        term_x = (w - term_w) / 2.0 - 180.0
        term_y = bar_y + 30.0

        if term_y + term_h < h:
            painter.setPen(QPen(QColor(53, 207, 255, 60), 1))
            painter.setBrush(QBrush(QColor(11, 15, 23, 220)))
            painter.drawRoundedRect(QRectF(term_x, term_y, term_w, term_h), 6, 6)

            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(QColor("#64748B"))
            painter.drawText(int(term_x + 10), int(term_y + 18), "SYSTEM BOOT TERMINAL LOGS")

            painter.setFont(QFont("Consolas", 8))
            for idx, log_line in enumerate(self._terminal_logs):
                line_y = term_y + 36.0 + idx * 15.0
                painter.setPen(QColor("#34D399") if "SYSTEM_READY" in log_line or "ONLINE" in log_line else QColor("#94A3B8"))
                painter.drawText(int(term_x + 10), int(line_y), log_line)

        grid_w = 300.0
        grid_h = 130.0
        grid_x = (w - term_w) / 2.0 + 260.0
        grid_y = bar_y + 30.0

        if grid_y + grid_h < h:
            painter.setPen(QPen(QColor(53, 207, 255, 60), 1))
            painter.setBrush(QBrush(QColor(11, 15, 23, 220)))
            painter.drawRoundedRect(QRectF(grid_x, grid_y, grid_w, grid_h), 6, 6)

            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(QColor("#64748B"))
            painter.drawText(int(grid_x + 10), int(grid_y + 18), "SUBSYSTEM HEALTH STATUS")

            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            items = list(self._module_health.items())
            for idx, (mod_name, status_str) in enumerate(items):
                col = idx // 4
                row = idx % 4
                ix = grid_x + 10.0 + col * 145.0
                iy = grid_y + 36.0 + row * 22.0

                painter.setPen(QColor("#94A3B8"))
                painter.drawText(int(ix), int(iy), f"{mod_name}:")
                status_color = QColor("#00E676") if "ONLINE" in status_str or "OK" in status_str else QColor("#FBBF24")
                painter.setPen(status_color)
                painter.drawText(int(ix + 80), int(iy), status_str)

        painter.end()


# ════════════════════════════════════════════════════════════════════
#  12. JARVIS Iron Man Holographic HUD Camera Display Viewport
# ════════════════════════════════════════════════════════════════════

class JARVISHolographicViewport(QLabel):
    """JARVIS Iron Man Holographic HUD Camera Viewport Display Widget."""

    doubleClicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cameraFeed")
        self.setAlignment(Qt.AlignCenter)

        self._connected: bool = False
        self._connecting: bool = False
        self._dissolve_spring = SpringSolver(1.0, 1.0, stiffness=120.0, damping=14.0)

        # Telemetry solvers
        self._fps_spring = SpringSolver(0.0, 0.0, stiffness=160.0, damping=15.0)
        self._ping_spring = SpringSolver(0.0, 0.0, stiffness=160.0, damping=15.0)
        self._signal_spring = SpringSolver(95.0, 95.0, stiffness=140.0, damping=14.0)
        self._battery_spring = SpringSolver(88.0, 88.0, stiffness=140.0, damping=14.0)
        self._heading_spring = SpringSolver(45.0, 45.0, stiffness=140.0, damping=14.0)

        self._is_recording: bool = False
        self._live_pixmap: QPixmap | None = None
        self._time: float = 0.0
        self._status_text: str = "JARVIS_VISION_CORE :: DISCONNECTED"
        self._pulse_radius: float = 0.0

        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def mouseDoubleClickEvent(self, event) -> None:
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

    def set_live_frame(self, qimage: QImage) -> None:
        self._live_pixmap = QPixmap.fromImage(qimage)

        if not self._connected:
            self._connected = True
            self._dissolve_spring.target = 0.0

    def set_connection_state(self, connected: bool, connecting: bool = False) -> None:
        self._connected = connected
        self._connecting = connecting
        if connected:
            self._dissolve_spring.target = 0.0
            self._status_text = "JARVIS_VISION_CORE :: STREAM ACTIVE"
        elif connecting:
            self._dissolve_spring.target = 1.0
            self._status_text = "JARVIS_VISION_CORE :: SEARCHING FREQUENCY..."
        else:
            self._dissolve_spring.target = 1.0
            self._status_text = "JARVIS_VISION_CORE :: STANDBY"

    def update_hud_telemetry(
        self,
        fps: float | None = None,
        ping: int | None = None,
        heading: float | None = None,
        recording: bool | None = None,
        battery: float | None = None,
    ) -> None:
        if fps is not None: self._fps_spring.target = float(fps)
        if ping is not None: self._ping_spring.target = float(ping)
        if heading is not None: self._heading_spring.target = float(heading)
        if recording is not None: self._is_recording = bool(recording)
        if battery is not None: self._battery_spring.target = float(battery)

    def _on_tick(self, dt: float) -> None:
        self._time += dt
        self._dissolve_spring.update(dt)
        self._fps_spring.update(dt)
        self._ping_spring.update(dt)
        self._signal_spring.update(dt)
        self._battery_spring.update(dt)
        self._heading_spring.update(dt)

        self._pulse_radius = (self._pulse_radius + dt * 160.0) % 200.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        cx, cy = w / 2.0, h / 2.0
        t = self._time
        dissolve = self._dissolve_spring.value

        if self._live_pixmap and not self._live_pixmap.isNull():
            pw, ph = float(self._live_pixmap.width()), float(self._live_pixmap.height())
            if pw > 0 and ph > 0:
                scale = min(w / pw, h / ph)
                tw, th = pw * scale, ph * scale
                vx = (w - tw) / 2.0
                vy = (h - th) / 2.0
                target_rect = QRectF(vx, vy, tw, th)
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                painter.drawPixmap(target_rect, self._live_pixmap, QRectF(0.0, 0.0, pw, ph))

        if dissolve > 0.01:
            overlay_alpha = int(245 * dissolve)
            painter.fillRect(0, 0, int(w), int(h), QColor(7, 9, 14, overlay_alpha))

            painter.save()
            painter.setOpacity(dissolve)

            grid_pen = QPen(QColor(53, 207, 255, 18), 1, Qt.DotLine)
            painter.setPen(grid_pen)
            for gx in range(0, int(w), 40): painter.drawLine(gx, 0, gx, int(h))
            for gy in range(0, int(h), 40): painter.drawLine(0, gy, int(w), gy)

            rover_cx, rover_cy = cx, cy - 30.0
            painter.setPen(QPen(QColor(53, 207, 255, 200), 1.5))
            
            rw, rh = 90.0, 50.0
            painter.drawRoundedRect(QRectF(rover_cx - rw/2, rover_cy - rh/2, rw, rh), 8, 8)
            
            wheel_r = 14.0
            wheels = [
                (rover_cx - rw/2 - 5, rover_cy - rh/2 + 8),
                (rover_cx + rw/2 + 5, rover_cy - rh/2 + 8),
                (rover_cx - rw/2 - 5, rover_cy + rh/2 - 8),
                (rover_cx + rw/2 + 5, rover_cy + rh/2 - 8),
            ]
            for wx, wy in wheels:
                painter.drawEllipse(QPointF(wx, wy), wheel_r, wheel_r)
                wheel_angle = t * 3.0
                painter.drawLine(
                    int(wx - wheel_r * math.cos(wheel_angle)), int(wy - wheel_r * math.sin(wheel_angle)),
                    int(wx + wheel_r * math.cos(wheel_angle)), int(wy + wheel_r * math.sin(wheel_angle))
                )

            mast_x, mast_y = rover_cx, rover_cy - rh/2
            painter.drawLine(int(mast_x), int(mast_y), int(mast_x), int(mast_y - 25))
            mast_head_x = mast_x + 15.0 * math.sin(t * 2.5)
            painter.drawEllipse(QPointF(mast_head_x, mast_y - 25), 6.0, 6.0)

            painter.setPen(QPen(QColor(0, 230, 118, 160), 1, Qt.DashLine))
            painter.drawLine(int(mast_head_x), int(mast_y - 25), int(mast_head_x + 60 * math.sin(t * 3.0)), int(rover_cy - 120))

            r_outer, r_inner = 130.0, 80.0
            painter.setPen(QPen(QColor(53, 207, 255, 140), 1.2, Qt.DashLine))
            painter.save()
            painter.translate(rover_cx, rover_cy)
            painter.rotate(t * 40.0)
            painter.drawEllipse(QPointF(0, 0), r_outer, r_outer)
            for deg in range(0, 360, 45):
                rad = math.radians(deg)
                painter.drawLine(QPointF((r_outer - 6) * math.cos(rad), (r_outer - 6) * math.sin(rad)), QPointF((r_outer + 6) * math.cos(rad), (r_outer + 6) * math.sin(rad)))
            painter.restore()

            painter.setPen(QPen(QColor(0, 230, 118, 120), 1, Qt.DotLine))
            painter.save()
            painter.translate(rover_cx, rover_cy)
            painter.rotate(-t * 60.0)
            painter.drawEllipse(QPointF(0, 0), r_inner, r_inner)
            painter.restore()

            r_aperture = 25.0 + 8.0 * math.sin(t * 2.0)
            painter.setPen(QPen(QColor(53, 207, 255, 180), 1))
            for i in range(6):
                ang = i * (math.pi / 3.0) + t * 0.5
                ax1 = rover_cx + r_aperture * math.cos(ang)
                ay1 = rover_cy + r_aperture * math.sin(ang)
                ax2 = rover_cx + (r_aperture + 20) * math.cos(ang + math.pi / 4.0)
                ay2 = rover_cy + (r_aperture + 20) * math.sin(ang + math.pi / 4.0)
                painter.drawLine(int(ax1), int(ay1), int(ax2), int(ay2))

            radar_angle = (t * 1.5) % (2 * math.pi)
            sweep_path = QPainterPath()
            sweep_path.moveTo(rover_cx, rover_cy)
            sweep_path.arcTo(rover_cx - 160, rover_cy - 160, 320, 320, math.degrees(-radar_angle), 45)
            sweep_path.closeSubpath()
            painter.fillPath(sweep_path, QBrush(QColor(53, 207, 255, 25)))

            scan_y = (t * 140.0) % h
            painter.setPen(QPen(QColor(53, 207, 255, 90), 1.5))
            painter.drawLine(0, int(scan_y), int(w), int(scan_y))

            b_len = 22.0 + 4.0 * math.sin(t * 3.0)
            b_off = 16.0
            painter.setPen(QPen(QColor("#35CFFF"), 2))
            painter.drawLine(int(b_off), int(b_off), int(b_off + b_len), int(b_off))
            painter.drawLine(int(b_off), int(b_off), int(b_off), int(b_off + b_len))
            painter.drawLine(int(w - b_off), int(b_off), int(w - b_off - b_len), int(b_off))
            painter.drawLine(int(w - b_off), int(b_off), int(w - b_off), int(b_off + b_len))

            painter.setFont(QFont("Consolas", 10, QFont.Bold))
            painter.setPen(QColor("#35CFFF"))
            painter.drawText(QRectF(0, rover_cy + r_outer + 15, w, 24), Qt.AlignCenter, self._status_text)

            p_alpha = max(0, int(100 * (1.0 - self._pulse_radius / 200.0)))
            painter.setPen(QPen(QColor(53, 207, 255, p_alpha), 1.5))
            painter.drawEllipse(QPointF(rover_cx, rover_cy), self._pulse_radius, self._pulse_radius)

            painter.restore()

        hud_alpha = int(255 * (1.0 - dissolve))
        if hud_alpha > 10:
            painter.save()
            painter.setOpacity(1.0 - dissolve)

            tape_y = 22.0
            hdg_val = self._heading_spring.value
            painter.setPen(QPen(QColor(53, 207, 255, 120), 1))
            painter.drawLine(int(cx - 140), int(tape_y), int(cx + 140), int(tape_y))
            painter.drawPolyline([QPointF(cx - 10, tape_y + 12), QPointF(cx, tape_y + 4), QPointF(cx + 10, tape_y + 12)])

            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            for deg_offset in range(-60, 65, 15):
                deg_tick = int(hdg_val + deg_offset) % 360
                tx = cx + deg_offset * 2.2
                painter.drawLine(int(tx), int(tape_y - 4), int(tx), int(tape_y))
                if deg_offset % 30 == 0:
                    painter.setPen(QColor("#35CFFF"))
                    painter.drawText(QRectF(tx - 15, tape_y - 18, 30, 14), Qt.AlignCenter, f"{deg_tick:03d}°")
                    painter.setPen(QColor(53, 207, 255, 120))

            pitch_val = 6.0 * math.cos(t * 1.5)
            roll_val = 4.0 * math.sin(t * 2.0)

            painter.save()
            painter.translate(cx, cy)
            painter.rotate(roll_val)

            painter.setPen(QPen(QColor(0, 230, 118, 200), 1.5))
            painter.drawLine(-110, int(pitch_val * 2), -30, int(pitch_val * 2))
            painter.drawLine(30, int(pitch_val * 2), 110, int(pitch_val * 2))
            painter.drawEllipse(QPointF(0, pitch_val * 2), 4, 4)

            painter.setPen(QPen(QColor(53, 207, 255, 140), 1))
            for p_step in [-20, -10, 10, 20]:
                py_step = int((pitch_val + p_step) * 2)
                painter.drawLine(-20, py_step, 20, py_step)
                painter.drawLine(-20, py_step, -20, py_step + (4 if p_step > 0 else -4))
                painter.drawLine(20, py_step, 20, py_step + (4 if p_step > 0 else -4))

            painter.restore()

            for r_dist, dist_lbl in [(60.0, "1.0m"), (110.0, "2.5m"), (160.0, "5.0m")]:
                r_breath = r_dist + 2.0 * math.sin(t * 2.0 + r_dist)
                painter.setPen(QPen(QColor(53, 207, 255, 35), 1, Qt.DotLine))
                painter.drawEllipse(QPointF(cx, cy), r_breath, r_breath)
                painter.setFont(QFont("Consolas", 7))
                painter.setPen(QColor(53, 207, 255, 80))
                painter.drawText(int(cx + r_breath - 20), int(cy - 4), dist_lbl)

            painter.setPen(QPen(QColor(53, 207, 255, 180), 1.5))
            painter.drawEllipse(QPointF(cx, cy), 16.0, 16.0)
            painter.drawLine(int(cx - 24), int(cy), int(cx - 8), int(cy))
            painter.drawLine(int(cx + 8), int(cy), int(cx + 24), int(cy))
            painter.drawLine(int(cx), int(cy - 24), int(cx), int(cy - 8))
            painter.drawLine(int(cx), int(cy + 8), int(cx), int(cy + 24))

            drift_x = cx + 50.0 * math.sin(t * 1.8)
            drift_y = cy + 35.0 * math.cos(t * 1.2)
            painter.setPen(QPen(QColor(0, 230, 118, 160), 1, Qt.DashLine))
            painter.drawEllipse(QPointF(drift_x, drift_y), 10.0, 10.0)
            painter.drawLine(int(cx), int(cy), int(drift_x), int(drift_y))

            # Target Lock Reticles
            t1_x, t1_y = cx - 180, cy - 80
            painter.setPen(QPen(QColor("#35CFFF"), 1.5))
            painter.drawRect(QRectF(t1_x, t1_y, 75, 50))
            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            painter.drawText(int(t1_x), int(t1_y - 4), "[OBJ #01 :: 1.2m]")

            t2_x, t2_y = cx + 110, cy + 30
            painter.setPen(QPen(QColor("#00E676"), 1.8))
            painter.drawRect(QRectF(t2_x, t2_y, 80, 55))
            painter.drawText(int(t2_x), int(t2_y - 4), "[QR_CODE :: CHK #2]")

            lock_alpha = int(180 + 75 * math.sin(t * 7.0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(239, 68, 68, lock_alpha // 3)))
            painter.drawRoundedRect(QRectF(cx - 55, cy - 110, 110, 22), 4, 4)
            painter.setPen(QColor(239, 68, 68, lock_alpha))
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.drawText(QRectF(cx - 55, cy - 110, 110, 22), Qt.AlignCenter, "● AI LOCK :: ACTIVE")

            # ── 3D LIDAR POINT-CLOUD HOLOGRAM OVERLAY (Feature #5) ──────
            lidar_cx, lidar_cy = cx - 180, h - 110
            painter.setPen(QPen(QColor(53, 207, 255, 30), 1))
            painter.drawRect(QRectF(lidar_cx - 60, lidar_cy - 40, 120, 80))
            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            painter.setPen(QColor("#35CFFF"))
            painter.drawText(int(lidar_cx - 55), int(lidar_cy - 26), "3D LIDAR DEPTH MESH")

            for lx in range(-5, 6, 2):
                for ly in range(-3, 4, 2):
                    depth_z = 12.0 * math.sin(t * 2.0 + lx * 0.5) * math.cos(ly * 0.8)
                    pt_x = lidar_cx + lx * 9.0 + depth_z * 0.5
                    pt_y = lidar_cy + ly * 7.0 - depth_z * 0.5

                    color = QColor("#35CFFF") if depth_z > -2 else (QColor("#00E676") if depth_z > -8 else QColor("#FBBF24"))
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(QPointF(pt_x, pt_y), 2.0, 2.0)

            # ── DUAL CAMERA PIP (PICTURE-IN-PICTURE) VIEWPORT (Feature #3) ─
            pip_x, pip_y = w - 190.0, 20.0
            pip_w, pip_h = 170.0, 105.0

            painter.setPen(QPen(QColor(53, 207, 255, 160), 1.5))
            painter.setBrush(QBrush(QColor(11, 15, 23, 220)))
            painter.drawRoundedRect(QRectF(pip_x, pip_y, pip_w, pip_h), 6, 6)

            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            painter.setPen(QColor("#00E676"))
            painter.drawText(int(pip_x + 8), int(pip_y + 16), "PIP :: OBSTACLE CAM")

            # Mini PIP grid animation
            pip_cx, pip_cy = pip_x + pip_w / 2.0, pip_y + pip_h / 2.0 + 5.0
            painter.setPen(QPen(QColor(53, 207, 255, 40), 1, Qt.DashLine))
            painter.drawRect(QRectF(pip_cx - 60, pip_cy - 30, 120, 60))
            scan_px = pip_cx - 60 + ((t * 80.0) % 120.0)
            painter.setPen(QPen(QColor(0, 230, 118, 140), 1))
            painter.drawLine(int(scan_px), int(pip_cy - 30), int(scan_px), int(pip_cy + 30))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(11, 15, 23, 190)))
            painter.drawRoundedRect(12, int(h - 52), 250, 40, 6, 6)
            painter.drawRoundedRect(int(w - 232), int(h - 52), 220, 40, 6, 6)

            sig_val = int(round(self._signal_spring.value))
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(QColor("#00E676"))
            painter.drawText(20, int(h - 34), f"SIGNAL: {sig_val}%")
            for b_idx in range(5):
                b_h = 4 + b_idx * 3
                bx = 110 + b_idx * 6
                by = int(h - 34) - b_h
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor("#00E676") if (b_idx+1)*20 <= sig_val else QColor("#334155")))
                painter.drawRect(bx, by, 4, b_h)

            bat_val = self._battery_spring.value
            bat_cx, bat_cy = w - 30, h - 32
            painter.setPen(QPen(QColor(30, 41, 59), 2))
            painter.drawEllipse(QPointF(bat_cx, bat_cy), 12, 12)

            bat_span = int((bat_val / 100.0) * 360.0 * 16.0)
            painter.setPen(QPen(QColor("#FBBF24"), 2))
            painter.drawArc(QRectF(bat_cx - 12, bat_cy - 12, 24, 24), 90 * 16, -bat_span)

            painter.setPen(QColor("#FBBF24"))
            painter.drawText(int(w - 224), int(h - 34), f"BATTERY: {bat_val:.0f}% [⚡ RUNNING]")

            painter.setPen(QColor("#35CFFF"))
            painter.drawText(20, int(h - 18), f"NAV_POS [X: 14.2m | Y: 08.5m | Z: +0.4m]")

            painter.restore()

        painter.end()


# ════════════════════════════════════════════════════════════════════
#  13. Subsystem Data Flow Pipeline Conduit Overlay Widget
# ════════════════════════════════════════════════════════════════════

class SubsystemPipelineOverlay(QWidget):
    """Subsystem Data Flow Pipeline Conduit Widget rendering moving chevrons & energy particles with dynamic font-metric string fitting."""

    PIPELINES = [
        ("BT LINK", "#00E676", "115200 BAUD"),
        ("CAMERA STREAM", "#35CFFF", "1080P 30FPS"),
        ("VISION ENGINE", "#35CFFF", "98.4% CONF"),
        ("NAV PLANNER", "#00E676", "SLAM ACTIVE"),
        ("MOTORS DRIVER", "#FBBF24", "PWM 255"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(115)
        self._time: float = 0.0
        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def _on_tick(self, dt: float) -> None:
        self._time += dt
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        t = self._time

        painter.fillRect(0, 0, int(w), int(h), QColor("#0B0E14"))
        painter.setPen(QPen(QColor("#242F42"), 1))
        painter.drawRect(0, 0, int(w)-1, int(h)-1)

        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor("#64748B"))
        painter.drawText(10, 15, "ACTIVE SUBSYSTEM DATA FLOW CONDUITS")

        for idx, (name, color_hex, meta_info) in enumerate(self.PIPELINES):
            py = 28 + idx * 17
            color = QColor(color_hex)

            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(10, py + 9, f"{name[:14]:<14}")

            fm = painter.fontMetrics()
            meta_w = float(fm.horizontalAdvance(meta_info))
            pipe_x1 = 105.0
            pipe_x2 = max(pipe_x1 + 25.0, w - meta_w - 12.0)

            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 30), 1, Qt.SolidLine))
            painter.drawLine(int(pipe_x1), py + 5, int(pipe_x2), py + 5)

            chev_spacing = 30.0
            offset = (t * 60.0 + idx * 15.0) % chev_spacing
            cx = pipe_x1 + offset
            while cx < pipe_x2 - 10.0:
                c_alpha = int(140 + 80 * math.sin(t * 4.0 + cx * 0.05))
                painter.setPen(QColor(color.red(), color.green(), color.blue(), c_alpha))
                painter.drawText(int(cx), py + 9, "═►")
                cx += chev_spacing

            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            painter.setPen(color)
            painter.drawText(int(pipe_x2 + 4.0), py + 9, meta_info)

        painter.end()


# ════════════════════════════════════════════════════════════════════
#  14. Premium Mission Control Panel Widget (11 Live Metrics)
# ════════════════════════════════════════════════════════════════════

class MissionControlPanel(QWidget):
    """Premium Mission Control Panel Widget rendering 11 live animated telemetry cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(260)

        # Telemetry metric spring solvers
        self._cov_spring = SpringSolver(0.0, 0.0, stiffness=140.0, damping=14.0)
        self._health_spring = SpringSolver(100.0, 100.0, stiffness=140.0, damping=14.0)
        self._vision_spring = SpringSolver(98.4, 98.4, stiffness=140.0, damping=14.0)
        self._nav_spring = SpringSolver(99.2, 99.2, stiffness=140.0, damping=14.0)
        self._bt_qual_spring = SpringSolver(96.0, 96.0, stiffness=140.0, damping=14.0)
        self._signal_spring = SpringSolver(95.0, 95.0, stiffness=140.0, damping=14.0)
        self._battery_spring = SpringSolver(88.0, 88.0, stiffness=140.0, damping=14.0)
        self._timer_sec: int = 0
        self._est_remain_sec: int = 348

        self._state_text: str = "STANDBY"
        self._qr_count: int = 0
        self._time: float = 0.0

        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def update_telemetry(
        self,
        coverage: float | None = None,
        qr_count: int | None = None,
        state: str | None = None,
        health: float | None = None,
        vision: float | None = None,
        nav_acc: float | None = None,
        bt_qual: float | None = None,
        signal: float | None = None,
        battery: float | None = None,
        timer_sec: int | None = None,
    ) -> None:
        if coverage is not None: self._cov_spring.target = float(coverage)
        if qr_count is not None: self._qr_count = int(qr_count)
        if state is not None: self._state_text = str(state)
        if health is not None: self._health_spring.target = float(health)
        if vision is not None: self._vision_spring.target = float(vision)
        if nav_acc is not None: self._nav_spring.target = float(nav_acc)
        if bt_qual is not None: self._bt_qual_spring.target = float(bt_qual)
        if signal is not None: self._signal_spring.target = float(signal)
        if battery is not None: self._battery_spring.target = float(battery)
        if timer_sec is not None:
            self._timer_sec = timer_sec
            self._est_remain_sec = max(0, 600 - timer_sec)

    def _on_tick(self, dt: float) -> None:
        self._time += dt
        self._cov_spring.update(dt)
        self._health_spring.update(dt)
        self._vision_spring.update(dt)
        self._nav_spring.update(dt)
        self._bt_qual_spring.update(dt)
        self._signal_spring.update(dt)
        self._battery_spring.update(dt)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        t = self._time

        painter.fillRect(0, 0, int(w), int(h), QColor("#0B0E14"))
        painter.setPen(QPen(QColor("#242F42"), 1))
        painter.drawRect(0, 0, int(w)-1, int(h)-1)

        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor("#64748B"))
        painter.drawText(10, 16, "MISSION CONTROL TELEMETRY METRICS")

        state_color = QColor("#00E676") if "EXPLORING" in self._state_text or "READY" in self._state_text else QColor("#FFC107")
        p_alpha = int(180 + 75 * math.sin(t * 6.0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(15, 23, 42, 220)))
        painter.drawRoundedRect(10, 24, 155, 42, 5, 5)
        painter.setPen(QColor(state_color.red(), state_color.green(), state_color.blue(), p_alpha))
        painter.drawEllipse(QPointF(20, 45), 4, 4)
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(30, 36, "MISSION STATE")
        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(state_color)
        painter.drawText(30, 52, self._state_text)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(15, 23, 42, 220)))
        painter.drawRoundedRect(175, 24, 155, 42, 5, 5)
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(183, 36, "MISSION TIMER")
        m, s = divmod(self._timer_sec, 60)
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor("#35CFFF"))
        painter.drawText(183, 52, f"⏱ {m:02d}:{s:02d}")

        bat_val = self._battery_spring.value
        bat_color = QColor("#00E676") if bat_val > 50 else (QColor("#FF9800") if bat_val >= 20 else QColor("#FF5252"))

        metrics_grid = [
            ("COVERAGE %", self._cov_spring.value, QColor("#00E676"), 10, 72),
            ("ROBOT HEALTH", self._health_spring.value, QColor("#35CFFF"), 175, 72),
            ("VISION CONF.", self._vision_spring.value, QColor("#35CFFF"), 10, 122),
            ("NAV ACCURACY", self._nav_spring.value, QColor("#00E676"), 175, 122),
            ("SIGNAL STRENGTH", self._signal_spring.value, QColor("#00E676"), 10, 172),
            ("BATTERY LEVEL", bat_val, bat_color, 175, 172),
        ]

        for title, val, color, mx, my in metrics_grid:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(15, 23, 42, 220)))
            painter.drawRoundedRect(mx, my, 155, 44, 5, 5)

            arc_r = 14.0
            cx, cy = mx + 20, my + 22
            painter.setPen(QPen(QColor(30, 41, 59), 2.5))
            painter.drawEllipse(QPointF(cx, cy), arc_r, arc_r)

            span = int((min(100.0, max(0.0, val)) / 100.0) * 360.0 * 16.0)
            arc_pen = QPen(color, 2.5)
            arc_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(arc_pen)
            painter.drawArc(QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2), 90 * 16, -span)

            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(mx + 40, my + 18, title)
            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            painter.setPen(color)
            painter.drawText(mx + 40, my + 34, f"{val:.1f}%")

        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(10, 240, f"QR CHECKPOINTS: {self._qr_count}/3  |  BT LINK: {self._bt_qual_spring.value:.0f}%  |  EST: {self._est_remain_sec//60:02d}:{self._est_remain_sec%60:02d}")

        painter.end()


# ════════════════════════════════════════════════════════════════════
#  15. Animated Slider Widget with Spring Tracking Thumb
# ════════════════════════════════════════════════════════════════════

class AnimatedSlider(QSlider):
    """Custom painted QSlider with spring-tracked glowing thumb and circular progress indicator."""

    def __init__(self, orientation=Qt.Horizontal, parent=None) -> None:
        super().__init__(orientation, parent)
        self.setFocusPolicy(Qt.StrongFocus)
        val = float(self.value())
        self._thumb_spring = SpringSolver(val, val, stiffness=260.0, damping=18.0)
        self._hover_scale = SpringSolver(1.0, 1.0, stiffness=220.0, damping=16.0)
        self._hovered: bool = False
        self._time: float = 0.0

        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._hover_scale.target = 1.25
        super().enterEvent(event)

    def setValue(self, val: int) -> None:
        super().setValue(val)
        if hasattr(self, "_thumb_spring"):
            self._thumb_spring.target = float(val)
            if self._thumb_spring.value == 0.0 and val > 0:
                self._thumb_spring.snap_to(float(val))

    def valueChanged(self, value: int) -> None:
        super().valueChanged(value)
        self._thumb_spring.target = float(value)

    def _on_tick(self, dt: float) -> None:
        self._time += dt
        self._thumb_spring.target = float(self.value())
        self._thumb_spring.update(dt)
        self._hover_scale.update(dt)
        self.update()

    def _val_from_x(self, x: float) -> int:
        w = float(self.width())
        usable_w = max(1.0, w - 16.0)
        clamped_x = max(0.0, min(usable_w, x - 8.0))
        ratio = clamped_x / usable_w
        min_v, max_v = float(self.minimum()), float(self.maximum())
        val = int(round(min_v + ratio * (max_v - min_v)))
        return max(self.minimum(), min(self.maximum(), val))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            val = self._val_from_x(event.position().x())
            self.setValue(val)
            self.sliderReleased.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton:
            val = self._val_from_x(event.position().x())
            self.setValue(val)
        super().mouseMoveEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        step = 10 if delta > 0 else -10
        new_val = max(self.minimum(), min(self.maximum(), self.value() + step))
        self.setValue(new_val)
        self.sliderReleased.emit()
        event.accept()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        val = self._thumb_spring.value
        min_v, max_v = float(self.minimum()), float(self.maximum())
        ratio = (val - min_v) / max(1.0, (max_v - min_v))

        track_h = 6.0
        track_y = (h - track_h) / 2.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#1E293B")))
        painter.drawRoundedRect(QRectF(8, track_y, w - 16, track_h), 3, 3)

        fill_w = ratio * (w - 16)
        if fill_w > 0:
            grad = QLinearGradient(8, track_y, 8 + fill_w, track_y)
            grad.setColorAt(0.0, QColor("#35CFFF"))
            grad.setColorAt(1.0, QColor("#00E676"))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(8, track_y, fill_w, track_h), 3, 3)

        thumb_x = 8.0 + fill_w
        thumb_cy = h / 2.0
        scale = self._hover_scale.value
        thumb_r = 9.0 * scale

        glow_r = thumb_r + 4.0 + 2.0 * math.sin(self._time * 4.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(53, 207, 255, int(60 * scale))))
        painter.drawEllipse(QPointF(thumb_x, thumb_cy), glow_r, glow_r)

        painter.setBrush(QBrush(QColor("#00E676")))
        painter.drawEllipse(QPointF(thumb_x, thumb_cy), thumb_r, thumb_r)

        painter.end()


# ════════════════════════════════════════════════════════════════════
#  16. Idle AI Core Neural Activity Monitor Widget
# ════════════════════════════════════════════════════════════════════

class IdleAICoreWidget(QWidget):
    """Idle AI Core Neural Activity Monitor Widget displaying subtle thinking animations."""

    STATUSES = [
        "Analyzing Maze...",
        "Planning Route...",
        "Estimating Path...",
        "Scanning Environment...",
        "Computing Navigation...",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(85)

        self._time: float = 0.0
        self._status_idx: int = 0
        self._char_idx: int = 0
        self._fade_spring = SpringSolver(1.0, 1.0, stiffness=140.0, damping=14.0)

        # 7 Neural Network nodes [(x, y, phase)]
        self._nodes = [
            (35.0, 30.0, 0.0),
            (75.0, 18.0, 1.2),
            (75.0, 52.0, 2.4),
            (120.0, 30.0, 3.6),
            (160.0, 18.0, 4.8),
            (160.0, 52.0, 1.0),
            (200.0, 35.0, 2.2),
        ]

        # Synaptic connection edges [(i, j)]
        self._synapses = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (3, 5), (4, 6), (5, 6)]

        # Mini matrix stream tokens
        self._matrix_tokens = ["0x3F", "A1", "CORE", "SYNC", "ACK", "1010", "SLAM", "PHI", "7E"]

        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def set_robot_active(self, active: bool) -> None:
        self._fade_spring.target = 0.25 if active else 1.0

    def _on_tick(self, dt: float) -> None:
        self._time += dt
        self._fade_spring.update(dt)

        if int(self._time * 2.0) % 6 == 0:
            new_idx = int(self._time / 3.0) % len(self.STATUSES)
            if new_idx != self._status_idx:
                self._status_idx = new_idx
                self._char_idx = 0

        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        t = self._time
        alpha = self._fade_spring.value

        painter.save()
        painter.setOpacity(alpha)

        painter.fillRect(0, 0, int(w), int(h), QColor("#0B0E14"))
        painter.setPen(QPen(QColor("#242F42"), 1))
        painter.drawRect(0, 0, int(w)-1, int(h)-1)

        for idx1, idx2 in self._synapses:
            n1, n2 = self._nodes[idx1], self._nodes[idx2]
            painter.setPen(QPen(QColor(53, 207, 255, 30), 1, Qt.SolidLine))
            painter.drawLine(QPointF(n1[0], n1[1]), QPointF(n2[0], n2[1]))

            syn_prog = (t * 0.6 + idx1 * 0.2) % 1.0
            px = n1[0] + (n2[0] - n1[0]) * syn_prog
            py = n1[1] + (n2[1] - n1[1]) * syn_prog
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#00E676")))
            painter.drawEllipse(QPointF(px, py), 2.0, 2.0)

        for nx, ny, nphase in self._nodes:
            n_pulse = int(120 + 60 * math.sin(t * 3.0 + nphase))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(53, 207, 255, n_pulse)))
            painter.drawEllipse(QPointF(nx, ny), 3.5, 3.5)

        ac_x, ac_y = w - 180.0, 42.0
        painter.save()
        painter.translate(ac_x, ac_y)
        painter.rotate(t * 30.0)
        painter.setPen(QPen(QColor(53, 207, 255, 50), 1, Qt.DashLine))
        painter.drawEllipse(QPointF(0, 0), 22.0, 22.0)
        for d in range(0, 360, 90):
            rad = math.radians(d)
            painter.drawLine(QPointF(16 * math.cos(rad), 16 * math.sin(rad)), QPointF(22 * math.cos(rad), 22 * math.sin(rad)))
        painter.restore()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 230, 118, 180)))
        painter.drawEllipse(QPointF(ac_x, ac_y), 5.0, 5.0)

        painter.setFont(QFont("Consolas", 7))
        painter.setPen(QColor(0, 230, 118, 40))
        for mx_idx, token in enumerate(self._matrix_tokens):
            col = mx_idx % 3
            row = mx_idx // 3
            mat_x = w - 120.0 + col * 34.0
            mat_y = 22.0 + row * 18.0
            painter.drawText(int(mat_x), int(mat_y), token)

        status_text = self.STATUSES[self._status_idx]
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        pulsing_alpha = int(180 + 75 * math.sin(t * 5.0))
        painter.setPen(QColor(53, 207, 255, pulsing_alpha))
        painter.drawText(230, 47, f"🤖 AI THINKING: {status_text}")

        painter.restore()
        painter.end()


# ════════════════════════════════════════════════════════════════════
#  17. Premium Commercial HMI Mission Complete Overlay Widget
# ════════════════════════════════════════════════════════════════════

class MissionCompleteOverlay(QWidget):
    """Premium Commercial HMI Mission Complete Overlay sequence."""

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(7, 9, 14, 0.94);")

        self._time: float = 0.0
        self._check_stroke_spring = SpringSolver(0.0, 0.0, stiffness=120.0, damping=14.0)
        self._cov_count_spring = SpringSolver(0.0, 0.0, stiffness=140.0, damping=14.0)
        self._score_count_spring = SpringSolver(0.0, 0.0, stiffness=140.0, damping=14.0)
        self._ping_spring = SpringSolver(12.0, 12.0, stiffness=140.0, damping=14.0)
        self._fps_spring = SpringSolver(30.0, 30.0, stiffness=140.0, damping=14.0)
        self._health_spring = SpringSolver(100.0, 100.0, stiffness=140.0, damping=14.0)

        self._dismiss_btn = QPushButton("DISMISS OVERLAY", self)
        self._dismiss_btn.setObjectName("smallButton")
        self._dismiss_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(53, 207, 255, 0.15);
                color: #35CFFF;
                border: 1px solid #35CFFF;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(53, 207, 255, 0.35);
            }
        """)
        self._dismiss_btn.clicked.connect(self._on_dismiss)
        install_hover_elevation(self._dismiss_btn, is_button=True, max_scale=1.04)

        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._dismiss_btn.move(self.width() // 2 - 70, self.height() - 70)

    def show_mission_complete(
        self,
        coverage_pct: float = 100.0,
        qr_count: int = 3,
        avg_fps: float = 30.0,
        ping_ms: int = 12,
        robot_health: float = 100.0,
    ) -> None:
        self.show()
        self.raise_()

        self._check_stroke_spring.snap_to(0.0)
        self._cov_count_spring.snap_to(0.0)
        self._score_count_spring.snap_to(0.0)
        self._ping_spring.snap_to(0.0)
        self._fps_spring.snap_to(0.0)
        self._health_spring.snap_to(0.0)

        self._check_stroke_spring.target = 1.0
        self._cov_count_spring.target = float(coverage_pct)
        self._score_count_spring.target = 9850.0
        self._ping_spring.target = float(ping_ms)
        self._fps_spring.target = float(avg_fps)
        self._health_spring.target = float(robot_health)

        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(0.0)
        self.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(400)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: self.setGraphicsEffect(None))
        anim.start()
        self._fade_anim = anim

    def _on_dismiss(self) -> None:
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setDuration(350)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def _on_done():
            self.hide()
            self.dismissed.emit()

        anim.finished.connect(_on_done)
        anim.start()

    def _on_tick(self, dt: float) -> None:
        self._time += dt
        self._check_stroke_spring.update(dt)
        self._cov_count_spring.update(dt)
        self._score_count_spring.update(dt)
        self._ping_spring.update(dt)
        self._fps_spring.update(dt)
        self._health_spring.update(dt)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        cx, cy = w / 2.0, h / 2.0 - 90.0
        t = self._time

        painter.fillRect(0, 0, int(w), int(h), QColor(7, 9, 14, 240))

        grid_pen = QPen(QColor(53, 207, 255, 12), 1, Qt.DotLine)
        painter.setPen(grid_pen)
        for x in range(0, int(w), 40): painter.drawLine(x, 0, x, int(h))
        for y in range(0, int(h), 40): painter.drawLine(0, y, int(w), y)

        r_emblem = 75.0

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(t * 35.0)
        painter.setPen(QPen(QColor("#00E676"), 2, Qt.DashLine))
        painter.drawEllipse(QPointF(0, 0), r_emblem, r_emblem)
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            painter.drawLine(QPointF((r_emblem - 6) * math.cos(rad), (r_emblem - 6) * math.sin(rad)), QPointF((r_emblem + 6) * math.cos(rad), (r_emblem + 6) * math.sin(rad)))
        painter.restore()

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-t * 50.0)
        painter.setPen(QPen(QColor(53, 207, 255, 120), 1, Qt.DotLine))
        painter.drawEllipse(QPointF(0, 0), r_emblem - 15, r_emblem - 15)
        painter.restore()

        prog = self._check_stroke_spring.value
        p1 = QPointF(cx - 28, cy + 2)
        p2 = QPointF(cx - 8, cy + 22)
        p3 = QPointF(cx + 32, cy - 20)

        check_pen = QPen(QColor("#00E676"), 5.5)
        check_pen.setCapStyle(Qt.RoundCap)
        check_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(check_pen)

        if prog <= 0.4:
            sub_p = prog / 0.4
            mid_x = p1.x() + (p2.x() - p1.x()) * sub_p
            mid_y = p1.y() + (p2.y() - p1.y()) * sub_p
            painter.drawLine(p1, QPointF(mid_x, mid_y))
        else:
            sub_p = (prog - 0.4) / 0.6
            end_x = p2.x() + (p3.x() - p2.x()) * sub_p
            end_y = p2.y() + (p3.y() - p2.y()) * sub_p
            painter.drawLine(p1, p2)
            painter.drawLine(p2, QPointF(end_x, end_y))

        painter.setFont(QFont("Consolas", 24, QFont.Bold))
        painter.setPen(QColor("#F8FAFC"))
        painter.drawText(QRectF(cx - 300, cy + r_emblem + 15, 600, 40), Qt.AlignCenter, "MISSION COMPLETE")

        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.setPen(QColor("#00E676"))
        painter.drawText(QRectF(cx - 300, cy + r_emblem + 52, 600, 24), Qt.AlignCenter, "● ALL MAZE OBJECTIVES ACHIEVED  |  EVALUATION GRADE: S+")

        grid_y = cy + r_emblem + 90.0
        grid_w = 640.0
        grid_x = cx - grid_w / 2.0

        card_w, card_h = 148.0, 68.0
        spacing_x, spacing_y = 16.0, 14.0

        metrics_data = [
            ("MAZE COVERAGE", f"{self._cov_count_spring.value:.1f}%", "#00E676"),
            ("QR CHECKPOINTS", "3 / 3 DISCOVERED", "#00E676"),
            ("MISSION SCORE", f"{int(round(self._score_count_spring.value))} PTS", "#35CFFF"),
            ("ROBOT HEALTH", "100% NOMINAL", "#00E676"),
            ("AVERAGE STREAM", "30.0 FPS", "#35CFFF"),
            ("LATENCY PING", f"{self._ping_spring.value:.1f} ms" if self._ping_spring.value > 0 else "-- ms", "#00E676"),
            ("BLUETOOTH LINK", "115200 BAUD", "#35CFFF"),
            ("MATCH TIMELINE", "FULL EXPLORED ✓", "#FBBF24"),
        ]

        for idx, (title, val_str, color_hex) in enumerate(metrics_data):
            col = idx % 4
            row = idx // 4
            mx = grid_x + col * (card_w + spacing_x)
            my = grid_y + row * (card_h + spacing_y)

            painter.setPen(QPen(QColor(53, 207, 255, 40), 1))
            painter.setBrush(QBrush(QColor(11, 15, 23, 230)))
            painter.drawRoundedRect(QRectF(mx, my, card_w, card_h), 6, 6)

            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(int(mx + 10), int(my + 18), title)

            painter.setFont(QFont("Consolas", 10, QFont.Bold))
            painter.setPen(QColor(color_hex))
            painter.drawText(int(mx + 10), int(my + 44), val_str)

        tl_y = grid_y + 2 * (card_h + spacing_y) + 10.0
        painter.setPen(QPen(QColor(53, 207, 255, 50), 1))
        painter.setBrush(QBrush(QColor(11, 15, 23, 230)))
        painter.drawRoundedRect(QRectF(grid_x, tl_y, grid_w, 36), 6, 6)

        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor("#34D399"))
        painter.drawText(QRectF(grid_x, tl_y, grid_w, 36), Qt.AlignCenter, "START  ➔  BT LINK ✓  ➔  SLAM MAP ✓  ➔  QR CHECK ✓  ➔  MISSION COMPLETE ✓")

        painter.end()


# Aliases for backward compatibility
ScanLineBackground = AIOperatingSystemBackground
