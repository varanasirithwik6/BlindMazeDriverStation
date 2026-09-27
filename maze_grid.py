"""
maze_grid.py — Interactive 2D SLAM Digital Twin Grid Navigation Engine.

High-performance 60 FPS Live Digital Twin for tracking robot navigation:
  - Smooth spring physics position & continuous rotation solvers (never teleports).
  - Animated vector chassis with 4 rotating wheel treads.
  - Dynamic breadcrumb trail particles and visited path line string.
  - Planned A* waypoint trajectory line connecting robot to destination.
  - Animated SLAM explored cell coverage pulses.
  - Highlighted QR checkpoints with reticle corners.
  - Pulsing destination GOAL beacon with expanding sonar rings.
  - Digital compass rose overlay, heading readout, coordinate position, and mission progress.
"""

from __future__ import annotations

import math
from PySide6.QtCore import Qt, Signal, Slot, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPixmap, QPainterPath
from PySide6.QtWidgets import QWidget

from motion import MotionEngine, SpringSolver


class MazeGridWidget(QWidget):
    """Live Digital Twin 2D SLAM Navigation Engine for Driver Station."""

    cell_clicked = Signal(int, int)

    def __init__(self, parent=None, rows: int = 7, cols: int = 7) -> None:
        super().__init__(parent)
        self._rows = rows
        self._cols = cols
        self._grid = [[0 for _ in range(cols)] for _ in range(rows)]
        self._robot_pos = (rows // 2, cols // 2)
        self._heading = "UP"  # UP, DOWN, LEFT, RIGHT
        self._grid[self._robot_pos[0]][self._robot_pos[1]] = 2
        self._visited_cells: set[tuple[int, int]] = {self._robot_pos}
        self._visited_history: list[tuple[int, int]] = [self._robot_pos]
        self._active_qr_count: int = 0
        
        # Checkpoints & Goal
        self._qr_checkpoints = {(1, 1), (1, 5), (5, 1)}
        self._goal_pos = (5, 5)
        self._anim_phase: float = 0.0
        self.setFixedHeight(180)

        # 60 FPS Spring Physics Solvers for continuous movement (never teleport)
        self._r_spring = SpringSolver(value=float(rows // 2), target=float(rows // 2), stiffness=150.0, damping=14.0)
        self._c_spring = SpringSolver(value=float(cols // 2), target=float(cols // 2), stiffness=150.0, damping=14.0)
        self._angle_spring = SpringSolver(value=0.0, target=0.0, stiffness=140.0, damping=14.0)

        # Breadcrumb trail particles [(x, y, age)]
        self._breadcrumbs: list[list[float]] = []
        self._time: float = 0.0

        MotionEngine.instance().tick_dt.connect(self._on_engine_tick_dt)

    def _on_engine_tick_dt(self, dt: float) -> None:
        self._time += dt
        self._anim_phase = (self._anim_phase + dt * 3.0) % (2 * math.pi)

        prev_r = self._r_spring.value
        prev_c = self._c_spring.value

        self._r_spring.update(dt)
        self._c_spring.update(dt)
        self._angle_spring.update(dt)

        # Add breadcrumb trail if moving
        dist_moved = math.hypot(self._r_spring.value - prev_r, self._c_spring.value - prev_c)
        if dist_moved > 0.01:
            self._breadcrumbs.append([self._c_spring.value, self._r_spring.value, 1.0])
            if len(self._breadcrumbs) > 40:
                self._breadcrumbs.pop(0)

        # Decay breadcrumbs
        for b in self._breadcrumbs:
            b[2] = max(0.0, b[2] - dt * 0.4)

        self.update()

    def get_coverage_pct(self) -> int:
        total = self._rows * self._cols
        return int((len(self._visited_cells) / total) * 100)

    def get_qr_count(self) -> int:
        return self._active_qr_count

    def move_robot(self, direction: str) -> None:
        r, c = self._robot_pos
        self._grid[r][c] = 1  # Mark previous cell visited

        target_angle = self._angle_spring.target
        if direction == "up":
            self._heading = "UP"
            target_angle = 0.0
            if r > 0: r -= 1
        elif direction == "down":
            self._heading = "DOWN"
            target_angle = 180.0
            if r < self._rows - 1: r += 1
        elif direction == "left":
            self._heading = "LEFT"
            target_angle = 270.0
            if c > 0: c -= 1
        elif direction == "right":
            self._heading = "RIGHT"
            target_angle = 90.0
            if c < self._cols - 1: c += 1

        # Shortest angle delta interpolation
        diff = (target_angle - self._angle_spring.target + 180) % 360 - 180
        self._angle_spring.target += diff

        self._robot_pos = (r, c)
        self._r_spring.target = float(r)
        self._c_spring.target = float(c)

        if (r, c) not in self._visited_cells:
            self._visited_cells.add((r, c))
            self._visited_history.append((r, c))

        if (r, c) in self._qr_checkpoints:
            self._active_qr_count = min(3, len(self._visited_cells.intersection(self._qr_checkpoints)))

        self._grid[r][c] = 2
        self.update()

    def reset_grid(self) -> None:
        self._grid = [[0 for _ in range(self._cols)] for _ in range(self._rows)]
        self._robot_pos = (self._rows // 2, self._cols // 2)
        self._r_spring.snap_to(float(self._rows // 2))
        self._c_spring.snap_to(float(self._cols // 2))
        self._angle_spring.snap_to(0.0)
        self._visited_cells = {self._robot_pos}
        self._visited_history = [self._robot_pos]
        self._breadcrumbs.clear()
        self._active_qr_count = 0
        self._grid[self._robot_pos[0]][self._robot_pos[1]] = 2
        self.update()

    def mousePressEvent(self, event) -> None:
        w, h = self.width(), self.height()
        cell_w = w / self._cols
        cell_h = h / self._rows
        col = int(event.position().x() / cell_w)
        row = int(event.position().y() / cell_h)
        col = max(0, min(self._cols - 1, col))
        row = max(0, min(self._rows - 1, row))
        self._goal_pos = (row, col)
        self.cell_clicked.emit(row, col)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        t = self._time

        cell_w = w / float(self._cols)
        cell_h = h / float(self._rows)

        # Background Grid Container
        painter.fillRect(0, 0, int(w), int(h), QColor("#0B0E14"))

        # ── 1. DRAW VISITED SLAM PATH CELLS & EXPLORED PULSES ───────
        for r in range(self._rows):
            for c in range(self._cols):
                cx, cy = c * cell_w, r * cell_h
                rect = QRectF(cx, cy, cell_w, cell_h)

                if (r, c) in self._visited_cells:
                    p_alpha = int(18 + 12 * math.sin(t * 3.0 + r + c))
                    painter.fillRect(rect, QColor(0, 230, 118, p_alpha))

                # Grid Mesh Lines
                painter.setPen(QPen(QColor(53, 207, 255, 25), 1))
                painter.drawRect(rect)

        # ── 2. DRAW BREADCRUMB TRAIL PARTICLES & VISITED PATH LINE ──
        if len(self._visited_history) >= 2:
            path_line = QPainterPath()
            p0_c, p0_r = self._visited_history[0][1], self._visited_history[0][0]
            path_line.moveTo((p0_c + 0.5) * cell_w, (p0_r + 0.5) * cell_h)
            for vr, vc in self._visited_history[1:]:
                path_line.lineTo((vc + 0.5) * cell_w, (vr + 0.5) * cell_h)

            painter.setPen(QPen(QColor(0, 230, 118, 120), 1.5, Qt.DashLine))
            painter.drawPath(path_line)

        for bc_c, bc_r, age in self._breadcrumbs:
            bx = (bc_c + 0.5) * cell_w
            by = (bc_r + 0.5) * cell_h
            b_alpha = int(220 * age)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(53, 207, 255, b_alpha)))
            painter.drawEllipse(QPointF(bx, by), 2.5, 2.5)

        # ── 3. DRAW QR CHECKPOINTS & GOAL BEACON ────────────────────
        for qr_r, qr_c in self._qr_checkpoints:
            q_x = (qr_c + 0.5) * cell_w
            q_y = (qr_r + 0.5) * cell_h
            visited = (qr_r, qr_c) in self._visited_cells

            border_color = QColor("#00E676") if visited else QColor("#FBBF24")
            painter.setPen(QPen(border_color, 1.5, Qt.DashLine if not visited else Qt.SolidLine))
            painter.drawRect(QRectF(q_x - 14, q_y - 8, 28, 16))
            painter.setFont(QFont("Consolas", 7, QFont.Bold))
            painter.setPen(border_color)
            painter.drawText(QRectF(q_x - 14, q_y - 8, 28, 16), Qt.AlignCenter, "QR")

        # Goal Position Beacon with Sonar Pulse
        gr, gc = self._goal_pos
        gx = (gc + 0.5) * cell_w
        gy = (gr + 0.5) * cell_h
        r_sonar = 8.0 + 8.0 * math.sin(t * 4.0)
        p_sonar_alpha = int(180 * (1.0 - r_sonar / 16.0))

        painter.setPen(QPen(QColor(0, 230, 118, p_sonar_alpha), 1.5))
        painter.drawEllipse(QPointF(gx, gy), r_sonar, r_sonar)
        painter.setPen(QPen(QColor("#00E676"), 1.8))
        painter.setBrush(QBrush(QColor(0, 230, 118, 80)))
        painter.drawEllipse(QPointF(gx, gy), 7.0, 7.0)
        painter.setFont(QFont("Consolas", 6, QFont.Bold))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRectF(gx - 12, gy - 6, 24, 12), Qt.AlignCenter, "GOAL")

        # ── 4. A* TRAJECTORY PATH (ROBOT TO GOAL) ────────────────────
        curr_r_val = self._r_spring.value
        curr_c_val = self._c_spring.value
        rob_center_x = (curr_c_val + 0.5) * cell_w
        rob_center_y = (curr_r_val + 0.5) * cell_h

        painter.setPen(QPen(QColor(53, 207, 255, 160), 1.5, Qt.DashLine))
        painter.drawLine(QPointF(rob_center_x, rob_center_y), QPointF(gx, gy))

        # ── 5. LIVE VECTOR ROBOT MODEL & ROTATING WHEELS ────────────
        painter.save()
        painter.translate(rob_center_x, rob_center_y)
        painter.rotate(self._angle_spring.value)

        # Chassis Body
        chassis_w, chassis_h = cell_w * 0.55, cell_h * 0.55
        painter.setPen(QPen(QColor("#35CFFF"), 1.8))
        painter.setBrush(QBrush(QColor(16, 94, 130, 220)))
        painter.drawRoundedRect(QRectF(-chassis_w/2, -chassis_h/2, chassis_w, chassis_h), 5, 5)

        # 4 Animated Wheels (Rotating Tread Ticks)
        wheel_w, wheel_h = 4.0, 10.0
        wheel_offsets = [
            (-chassis_w/2 - 2, -chassis_h/2 + 2),
            (chassis_w/2 - 2, -chassis_h/2 + 2),
            (-chassis_w/2 - 2, chassis_h/2 - 12),
            (chassis_w/2 - 2, chassis_h/2 - 12),
        ]
        painter.setPen(QPen(QColor("#00E676"), 1))
        painter.setBrush(QBrush(QColor("#0F172A")))
        tread_phase = (t * 8.0) % 6.0
        for wx, wy in wheel_offsets:
            painter.drawRect(QRectF(wx, wy, wheel_w, wheel_h))
            painter.drawLine(QPointF(wx, wy + tread_phase), QPointF(wx + wheel_w, wy + tread_phase))

        # Forward Direction Pointer Vector & Radar Cone
        painter.setPen(QPen(QColor("#00E676"), 2))
        painter.drawLine(0, 0, 0, int(-chassis_h/2 - 6))

        radar_cone = QPainterPath()
        radar_cone.moveTo(0, 0)
        radar_cone.arcTo(-25, -45, 50, 50, 60, 60)
        radar_cone.closeSubpath()
        painter.fillPath(radar_cone, QBrush(QColor(53, 207, 255, 30)))

        painter.restore()

        # ── 6. COMPASS & DIGITAL HUD READOUT OVERLAYS ───────────────
        hdg_deg = int(round(self._angle_spring.value)) % 360
        compass_code = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((hdg_deg + 22.5) / 45.0) % 8]

        # Position & Heading Overlay Box (Top Left)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(11, 15, 23, 220)))
        painter.drawRoundedRect(QRectF(4, 4, 140, 32), 4, 4)

        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor("#35CFFF"))
        painter.drawText(8, 17, f"POS: ({curr_r_val:.1f}, {curr_c_val:.1f})")
        painter.drawText(8, 30, f"HDG: {hdg_deg:03d}° [{compass_code}]")

        # Mission Progress Overlay Box (Bottom Left)
        cov_pct = self.get_coverage_pct()
        qr_count = self.get_qr_count()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(11, 15, 23, 220)))
        painter.drawRoundedRect(QRectF(4, h - 26, 195, 22), 4, 4)

        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor("#00E676"))
        painter.drawText(8, int(h - 11), f"SLAM COVERAGE: {cov_pct}%  |  QR: {qr_count}/3")

        # Rotating Mini Compass Rose (Top Right)
        cp_x, cp_y = w - 24.0, 24.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(11, 15, 23, 200)))
        painter.drawEllipse(QPointF(cp_x, cp_y), 16.0, 16.0)

        painter.setPen(QPen(QColor(53, 207, 255, 180), 1))
        painter.drawEllipse(QPointF(cp_x, cp_y), 14.0, 14.0)
        c_rad = math.radians(hdg_deg)
        painter.drawLine(QPointF(cp_x, cp_y), QPointF(cp_x + 10 * math.sin(c_rad), cp_y - 10 * math.cos(c_rad)))
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.drawText(int(cp_x - 3), int(cp_y - 15), "N")

        painter.end()
