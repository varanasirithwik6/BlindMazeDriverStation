"""
telemetry_graph.py — Real-time performance sparkline graph widget.

Upgraded with 60 FPS spring physics continuous interpolation, smooth Bezier
splines, pulsing endpoint nodes, generous vertical framing, and dynamic interactive tooltips.
"""

from __future__ import annotations

import math
from collections import deque
from PySide6.QtCore import Qt, Slot, QPoint, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPainterPath
from PySide6.QtWidgets import QWidget, QToolTip

from motion import MotionEngine, SpringSolver


class TelemetryGraph(QWidget):
    """Real-time performance sparkline graph widget with tooltip hover and spring dynamics."""

    def __init__(self, parent=None, max_points: int = 50) -> None:
        super().__init__(parent)
        self._max_points = max_points
        self._speed_raw: deque[int] = deque([0] * max_points, maxlen=max_points)
        self._fps_raw: deque[float] = deque([0.0] * max_points, maxlen=max_points)

        # Smooth spring values for latest display
        self._speed_spring = SpringSolver(0.0, 0.0, stiffness=160.0, damping=14.0)
        self._fps_spring = SpringSolver(0.0, 0.0, stiffness=160.0, damping=14.0)

        self._pulse_phase: float = 0.0
        self._grid_cache: QPixmap | None = None
        self.setFixedHeight(125)
        self.setMouseTracking(True)
        MotionEngine.instance().tick_dt.connect(self._on_engine_tick_dt)

    def _on_engine_tick_dt(self, dt: float) -> None:
        self._pulse_phase = (self._pulse_phase + dt * 4.0) % (2 * math.pi)
        self._speed_spring.update(dt)
        self._fps_spring.update(dt)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._grid_cache = None

    @Slot(int)
    def add_speed_sample(self, speed: int) -> None:
        self._speed_raw.append(speed)
        self._speed_spring.target = float(speed)
        self.update()

    @Slot(float)
    def add_fps_sample(self, fps: float) -> None:
        self._fps_raw.append(fps)
        self._fps_spring.target = float(fps)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        x = event.position().x()
        w = float(self.width())
        idx = int((x / w) * (self._max_points - 1))
        idx = max(0, min(self._max_points - 1, idx))
        speed_val = self._speed_raw[idx]
        fps_val = self._fps_raw[idx]
        QToolTip.showText(
            self.mapToGlobal(QPoint(int(x), 10)),
            f"SAMPLE #{idx}\nDRIVE PWM: {speed_val}\nCAMERA FPS: {fps_val:.1f}",
            self
        )

    def _rebuild_grid_cache(self, w: int, h: int) -> None:
        pixmap = QPixmap(w, h)
        pixmap.fill(QColor("#111520"))
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor("#293548"), 1, Qt.DashLine))
        painter.drawLine(0, h // 2, w, h // 2)
        painter.drawLine(0, h // 4, w, h // 4)
        painter.drawLine(0, (h * 3) // 4, w, (h * 3) // 4)
        painter.end()
        self._grid_cache = pixmap

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        if self._grid_cache is None or self._grid_cache.size() != self.size():
            self._rebuild_grid_cache(w, h)
        painter.drawPixmap(0, 0, self._grid_cache)

        # Smooth Bezier Spline Curves
        self._plot_smooth_series(painter, self._speed_raw, 255.0, QColor("#35CFFF"), w, h)
        self._plot_smooth_series(painter, self._fps_raw, 60.0, QColor("#00E676"), w, h)

        # Legend Readout
        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor("#35CFFF"))
        painter.drawText(8, 16, f"PWM: {int(round(self._speed_spring.value))}")
        painter.setPen(QColor("#00E676"))
        painter.drawText(95, 16, f"FPS: {self._fps_spring.value:.0f}")

    def _plot_smooth_series(
        self, painter: QPainter, data: deque, max_val: float, color: QColor, w: int, h: int
    ) -> None:
        if len(data) < 2:
            return
        step = float(w) / float(self._max_points - 1)

        points: list[QPointF] = []
        top_margin = 24.0
        draw_h = float(h) - top_margin - 8.0

        for i, val in enumerate(data):
            px = i * step
            py = float(h) - 6.0 - (min(max_val, max(0.0, float(val))) / max_val * draw_h)
            points.append(QPointF(px, py))

        # Bezier Spline Path
        path = QPainterPath()
        path.moveTo(points[0])
        for i in range(1, len(points)):
            p0 = points[i - 1]
            p1 = points[i]
            cp1 = QPointF(p0.x() + step / 2.0, p0.y())
            cp2 = QPointF(p1.x() - step / 2.0, p1.y())
            path.cubicTo(cp1, cp2, p1)

        painter.setPen(QPen(color, 1.8))
        painter.drawPath(path)

        # Pulsing Latest Endpoint Node
        last_pt = points[-1]
        r_pulse = 3.5 + 1.5 * math.sin(self._pulse_phase)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(last_pt, r_pulse, r_pulse)
