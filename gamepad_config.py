"""
gamepad_config.py — In-App Gamepad Controller Calibration & Keybinding Configurator.

Provides an interactive 60 FPS modal for live joystick axis visualization,
trigger response curve tuning, deadzone adjustment, and custom keybindings.
"""

from __future__ import annotations

import math
from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QFrame,
    QGridLayout,
    QWidget,
)

from motion import MotionEngine, SpringSolver, install_hover_elevation


class JoystickAxisVisualizer(QWidget):
    """60 FPS interactive 2D joystick axis meter widget."""

    def __init__(self, title: str = "LEFT STICK", parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(110, 110)
        self._title = title
        self._axis_x = SpringSolver(0.0, 0.0, stiffness=200.0, damping=16.0)
        self._axis_y = SpringSolver(0.0, 0.0, stiffness=200.0, damping=16.0)
        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def set_axis(self, x: float, y: float) -> None:
        self._axis_x.target = max(-1.0, min(1.0, x))
        self._axis_y.target = max(-1.0, min(1.0, y))

    def _on_tick(self, dt: float) -> None:
        self._axis_x.update(dt)
        self._axis_y.update(dt)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = float(self.width()), float(self.height())
        cx, cy = w / 2.0, h / 2.0 - 6.0
        r_outer = 40.0

        painter.fillRect(0, 0, int(w), int(h), QColor("#0B0E14"))
        painter.setPen(QPen(QColor("#242F42"), 1))
        painter.drawRect(0, 0, int(w)-1, int(h)-1)

        painter.setPen(QPen(QColor(53, 207, 255, 60), 1, Qt.DashLine))
        painter.drawEllipse(QPointF(cx, cy), r_outer, r_outer)
        painter.drawLine(int(cx - r_outer), int(cy), int(cx + r_outer), int(cy))
        painter.drawLine(int(cx), int(cy - r_outer), int(cx), int(cy + r_outer))

        stick_x = cx + self._axis_x.value * (r_outer - 6.0)
        stick_y = cy + self._axis_y.value * (r_outer - 6.0)

        painter.setPen(QPen(QColor("#00E676"), 1.5))
        painter.drawLine(QPointF(cx, cy), QPointF(stick_x, stick_y))
        painter.setBrush(QBrush(QColor("#35CFFF")))
        painter.drawEllipse(QPointF(stick_x, stick_y), 6.0, 6.0)

        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(QRectF(0, h - 18, w, 16), Qt.AlignCenter, self._title)

        painter.end()


class GamepadConfigDialog(QDialog):
    """In-App Controller Calibration & Keybinding Configurator Dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gamepad Controller Calibration & Profile Manager")
        self.setFixedSize(540, 420)
        self.setStyleSheet("""
            QDialog { background-color: #0F1117; color: #E2E8F0; }
            QLabel { color: #E2E8F0; font-family: "Segoe UI", sans-serif; }
            QFrame { background-color: #171C28; border: 1px solid #293548; border-radius: 10px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Title
        title_lbl = QLabel("🎮 GAMEPAD CONTROLLER CALIBRATION & HARDWARE MAPPING")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #35CFFF; letter-spacing: 1px;")
        layout.addWidget(title_lbl)

        # Axis Visualizer Row
        axis_frame = QFrame()
        axis_layout = QHBoxLayout(axis_frame)
        axis_layout.setContentsMargins(12, 10, 12, 10)

        self.left_stick = JoystickAxisVisualizer("LEFT STICK (STEER)")
        self.right_stick = JoystickAxisVisualizer("RIGHT STICK (LOOK)")
        axis_layout.addWidget(self.left_stick)
        axis_layout.addWidget(self.right_stick)

        # Sensitivity & Deadzone Tuning
        sliders_layout = QVBoxLayout()

        deadzone_lbl = QLabel("DEADZONE THRESHOLD: 15%")
        deadzone_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #94A3B8;")
        self.deadzone_slider = QSlider(Qt.Horizontal)
        self.deadzone_slider.setRange(5, 35)
        self.deadzone_slider.setValue(15)
        self.deadzone_slider.valueChanged.connect(lambda v: deadzone_lbl.setText(f"DEADZONE THRESHOLD: {v}%"))

        sens_lbl = QLabel("STICK SENSITIVITY: 100%")
        sens_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #94A3B8;")
        self.sens_slider = QSlider(Qt.Horizontal)
        self.sens_slider.setRange(50, 150)
        self.sens_slider.setValue(100)
        self.sens_slider.valueChanged.connect(lambda v: sens_lbl.setText(f"STICK SENSITIVITY: {v}%"))

        sliders_layout.addWidget(deadzone_lbl)
        sliders_layout.addWidget(self.deadzone_slider)
        sliders_layout.addWidget(sens_lbl)
        sliders_layout.addWidget(self.sens_slider)

        axis_layout.addLayout(sliders_layout, 1)
        layout.addWidget(axis_frame)

        # Button Test Matrix Grid
        btn_frame = QFrame()
        btn_grid = QGridLayout(btn_frame)
        btn_grid.setContentsMargins(12, 10, 12, 10)
        btn_grid.setSpacing(8)

        self.btn_indicators: dict[str, QLabel] = {}
        button_names = ["A (FWD)", "B (E-STOP)", "X (LEFT)", "Y (RIGHT)", "LB (REVERSE)", "RB (TURBO)"]
        for idx, bname in enumerate(button_names):
            lbl = QLabel(f"● {bname}")
            lbl.setStyleSheet("background-color: #111520; border: 1px solid #293548; border-radius: 6px; padding: 6px; font-size: 10px; font-weight: 700; color: #64748B;")
            lbl.setAlignment(Qt.AlignCenter)
            btn_grid.addWidget(lbl, idx // 3, idx % 3)
            self.btn_indicators[bname] = lbl

        layout.addWidget(btn_frame)

        # Action Button Row
        btn_row = QHBoxLayout()
        self.test_pulse_btn = QPushButton("TEST JOYSTICK PULSE")
        self.test_pulse_btn.setObjectName("smallButton")
        self.test_pulse_btn.clicked.connect(self._simulate_test_pulse)
        install_hover_elevation(self.test_pulse_btn, is_button=True, max_scale=1.03)

        self.save_btn = QPushButton("SAVE PROFILE")
        self.save_btn.clicked.connect(self.accept)
        install_hover_elevation(self.save_btn, is_button=True, max_scale=1.03)

        btn_row.addWidget(self.test_pulse_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self._pulse_t: float = 0.0

    def _simulate_test_pulse(self) -> None:
        self.left_stick.set_axis(0.65, -0.45)
        self.right_stick.set_axis(-0.35, 0.75)
        for lbl in self.btn_indicators.values():
            lbl.setStyleSheet("background-color: rgba(0, 230, 118, 0.15); border: 1px solid #00E676; border-radius: 6px; padding: 6px; font-size: 10px; font-weight: 700; color: #00E676;")
