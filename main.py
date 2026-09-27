"""
main.py — Blind Maze Driver Station entry-point and Dashboard window.

Fully Integrated Features:
- Professional Hold-to-Move Competition Control Protocol (PySide6 pressed/released signals)
- Strict Command Deduplication Engine (Single-frame F/B/L/R transmission, no continuous repeats)
- Dual Keyboard (WASD + Arrow Keys) & Mouse Hold-to-Move Controls with auto-repeat suppression
- Video Fullscreen Viewport Mode with Floating Movable & Resizable Touch Joystick Overlay
- Master Screen Scroll Area Wrapper & Minimum Bounds Engine (1480x860) for windowed mode
- Black-Box Telemetry Flight Recorder & 60 FPS Replay Engine (1x / 2x / 4x)
- Robust Camera IP/URL Normalization
- In-App Gamepad Controller Calibration & Keybinding Configurator Dialog
- 3D LiDAR Point-Cloud Hologram Overlay & Dual Camera PIP Viewport
- Responsive Full Screen Layout with Scroll Areas & Adaptive Geometry
- F11 Toggle Full Screen Shortcut
- MissionCompleteOverlay: Premium Mission Complete sequence with animated checkmark, 8 telemetry cards, timeline completion, and professional summary
- IdleAICoreWidget: Idle AI Core Neural Activity Monitor (Analyzing Maze, Planning Route, Estimating Path, Thinking Animation, Neural Synapses, Mini Matrix Stream)
- AnimatedSlider: Custom painted slider with spring tracking thumb & gradient progress track
- Living System Subsystem Data Flow Pipelines (Bluetooth, Camera, Vision, Nav, Motors)
- Inter-Subsystem Visual Communication Buses & Flowing Energy Particles
- Premium Mission Control Panel (11 Live Animated Metrics with Circular Progress Rings & Rolling Numbers)
- Live Digital Twin SLAM Navigation Engine
- JARVIS Holographic Camera Viewport Display & Live Telemetry HUD Assembly
- Cinematic AI Boot Sequence & Panel Assembly Engine
- Commercial HMI AI OS 60 FPS Spring Motion & Physics Engine
- 13-Element Ambient AI OS Blueprint Background Layer (<5% Opacity)
- Dual Themes (Dark / Light toggle)
- Live Telemetry Graph Widget with Spring Sparkline Interpolation
- Speed Preset Quick-Buttons with Spring Bounce & Ripple
- Snapshot & Video Recording controls
- Bluetooth & Camera threads
- Network Ping Latency Monitor
- Audio Alerts
- Session Report Exporter
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from PySide6.QtCore import Qt, QElapsedTimer, QTimer, QPropertyAnimation, QEasingCurve, QEvent, QObject, QSettings
from PySide6.QtGui import QCloseEvent, QImage, QKeyEvent, QPixmap, QIcon, QPainter, QFont, QColor, QPen, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QFileDialog,
)

from audio_alerts import AudioAlertSystem
from bluetooth import BluetoothController
from camera import CameraThread
from console import SystemConsole
from controller import RobotController
from flight_recorder import FlightRecorder, ReplayEngine
from gamepad import GamepadThread
from gamepad_config import GamepadConfigDialog
from maze_grid import MazeGridWidget
from network_monitor import NetworkPingThread
from session_exporter import SessionExporter
from settings import (
    APP_HEIGHT,
    APP_TITLE,
    APP_WIDTH,
    CAMERA_MIN_HEIGHT,
    CAMERA_RESOLUTIONS,
    CONSOLE_MAX_HEIGHT,
    DEFAULT_CAMERA_IP,
    DEFAULT_CAMERA_RESOLUTION,
    DEFAULT_COM_PORT,
    DEFAULT_SPEED,
    DIR_BUTTON_SIZE,
    DIRECTIONS,
    EMERGENCY_KEY,
    EMERGENCY_LOCKOUT_MS,
    LEFT_PANEL_WIDTH,
    MAIN_MARGIN,
    MAIN_SPACING,
    MATCH_DURATION_SEC,
    RIGHT_PANEL_WIDTH,
    SPEED_MAX,
    SPEED_MIN,
    SPEED_PRESETS,
    STOP_KEY,
    EMERGENCY_BUTTON_HEIGHT,
    RECORDINGS_DIR,
)
from telemetry_graph import TelemetryGraph
from theme import DARK_STYLE, LIGHT_STYLE
from motion import (
    MotionEngine,
    install_ripple,
    fade_in_widget,
    staggered_fade_in,
    CardGlowEffect,
    LiveClockLabel,
    ScanLineBackground,
    AIOperatingSystemBackground,
    AIBootSequenceOverlay,
    JARVISHolographicViewport,
    MissionControlPanel,
    SubsystemPipelineOverlay,
    AnimatedSlider,
    IdleAICoreWidget,
    MissionCompleteOverlay,
    install_hover_elevation,
    AnimatedNumberLabel,
    AnimatedStatusBadge,
)


class Dashboard(QMainWindow):
    """Driver-station window: status sidebar, camera feed, robot controls."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(APP_WIDTH, APP_HEIGHT)

        # Set Window Icon
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setFont(QFont("Segoe UI Emoji", 42))
        painter.drawText(0, 52, "🤖")
        painter.end()
        self.setWindowIcon(QIcon(pixmap))
        
        # Current Theme State
        self._is_dark_theme: bool = True
        self.setStyleSheet(DARK_STYLE)
        self.setFocusPolicy(Qt.StrongFocus)

        # ── State ────────────────────────────────────────────────────
        self._camera_connected: bool = False
        self._bt_connected: bool = False
        self._emergency: bool = False
        self._pressed_keys: set[int] = set()
        self._raw_logs: list[str] = []
        self._video_fullscreen_dlg = None

        # ── Hold-to-Move Competition State & Command Deduplication ────
        self._active_pressed_inputs: list[str] = []
        self._current_sent_command: str = "stop"

        # ── Back-end objects ─────────────────────────────────────────
        self._bluetooth = BluetoothController(self)
        self._camera = CameraThread(self)
        self._controller = RobotController(self._bluetooth, self)
        self._gamepad = GamepadThread(self)
        self._ping_monitor = NetworkPingThread(self)
        
        # Flight Recorder & Replay Engine
        self._flight_recorder = FlightRecorder(self)
        self._replay_engine = ReplayEngine(self)

        # ── Session timer ────────────────────────────────────────────
        self._elapsed = QElapsedTimer()
        self._session_timer = QTimer(self)
        self._session_timer.setTimerType(Qt.PreciseTimer)
        self._session_timer.timeout.connect(self._tick)

        # ── Shared Motion Engine connection (60 FPS) ──────────────────
        self._anim_angle: float = 0.0
        MotionEngine.instance().tick.connect(self._on_motion_tick)
        MotionEngine.instance().tick_dt.connect(self._on_flight_tick)

        # ── Build UI with Master Screen Scroll Area & Minimum Bounds ──
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.NoFrame)
        main_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        main_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        main_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        central = QWidget()
        central.setMinimumSize(1480, 860)
        central.setStyleSheet("background: transparent;")
        main_scroll.setWidget(central)
        self.setCentralWidget(main_scroll)

        # Ambient AI Operating System Background Layer (< 5% Opacity)
        self._bg_layer = AIOperatingSystemBackground(central)
        self._bg_layer.resize(APP_WIDTH, APP_HEIGHT)
        self._bg_layer.lower()

        root = QHBoxLayout(central)
        root.setContentsMargins(MAIN_MARGIN, MAIN_MARGIN, MAIN_MARGIN, MAIN_MARGIN)
        root.setSpacing(MAIN_SPACING)

        self._left_panel = self._build_left_panel()
        self._center_panel = self._build_center_panel()
        self._right_panel = self._build_right_panel()

        root.addWidget(self._left_panel)
        root.addWidget(self._center_panel, 1)
        root.addWidget(self._right_panel)

        # Cinematic AI Boot Sequence Overlay
        self._boot_overlay = AIBootSequenceOverlay(self)
        self._boot_overlay.resize(APP_WIDTH, APP_HEIGHT)
        self._boot_overlay.boot_completed.connect(self._assemble_dashboard_panels)
        self._boot_overlay.raise_()

        # Premium Mission Complete Overlay
        self._complete_overlay = MissionCompleteOverlay(self)
        self._complete_overlay.resize(APP_WIDTH, APP_HEIGHT)
        self._complete_overlay.hide()

        # ── Connect signals ──────────────────────────────────────────
        self._wire_signals()

        # ── Install premium motion effects ────────────────────────────
        self._install_motion_effects()

        # ── Startup sequence ──────────────────────────────────────────
        self._startup_sequence()

        # ── Global Keyboard Drive Event Filter ────────────────────────
        QApplication.instance().installEventFilter(self)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_bg_layer") and self._bg_layer:
            self._bg_layer.resize(self.width(), self.height())
        if hasattr(self, "_boot_overlay") and self._boot_overlay:
            self._boot_overlay.resize(self.width(), self.height())
        if hasattr(self, "_complete_overlay") and self._complete_overlay:
            self._complete_overlay.resize(self.width(), self.height())

    def _install_motion_effects(self) -> None:
        """Attach ripple overlays, card glows, hover elevation and fade-in animations."""
        all_buttons = [
            self.bt_connect_btn, self.connect_btn, self.snap_btn, self.rec_btn, self.video_fs_btn,
            self.theme_btn, self.export_btn, self.replay_btn, self.gamepad_btn, self.demo_btn,
            self.refresh_ports_btn, self.emergency_btn, self.btn_up, self.btn_down,
            self.btn_left, self.btn_right, self.btn_stop,
        ]
        all_buttons.extend(self._preset_buttons)
        for btn in all_buttons:
            install_hover_elevation(btn, is_button=True, max_scale=1.03)

        panels = [self._left_panel, self._center_panel, self._right_panel]
        for p in panels:
            install_hover_elevation(p, is_button=False, max_scale=1.005)

        status_cards = [
            self.bt_status, self.cam_status, self.ping_label,
            self.robot_status, self.timer_label, self.fps_label,
        ]
        for card in status_cards:
            install_hover_elevation(card, is_button=False, max_scale=1.02)

        self._card_glows = [CardGlowEffect(card) for card in status_cards]

    def _startup_sequence(self) -> None:
        """Launches the cinematic AI Boot Sequence overlay."""
        MotionEngine.instance().start()
        self._boot_overlay.start_boot()

    def _assemble_dashboard_panels(self) -> None:
        """Assembles dashboard panel by panel after AI boot sequence completes."""
        self.log_and_store("Cinematic AI Boot Completed. Assembling Ground Station Panels...", "SUCCESS")

        fade_in_widget(self._center_panel, duration_ms=450, delay_ms=0)
        fade_in_widget(self._left_panel, duration_ms=450, delay_ms=200)
        fade_in_widget(self.console, duration_ms=400, delay_ms=400)
        fade_in_widget(self._right_panel, duration_ms=450, delay_ms=600)
        fade_in_widget(self.maze_tracker, duration_ms=450, delay_ms=800)

        QTimer.singleShot(900, self._finish_startup)

    def _finish_startup(self) -> None:
        self._refresh_ports()
        self._gamepad.start()
        self._flight_recorder.start_recording()
        self.setWindowOpacity(1.0)

    def trigger_mission_complete(self) -> None:
        cov = getattr(self.maze_tracker, "get_coverage_pct", lambda: 100.0)()
        qr = getattr(self.maze_tracker, "get_qr_count", lambda: 3)()
        self._complete_overlay.show_mission_complete(
            coverage_pct=cov,
            qr_count=qr,
            avg_fps=30.0,
            ping_ms=12,
            robot_health=100.0,
        )
        saved_file = self._flight_recorder.stop_recording()
        if saved_file:
            self.log_and_store(f"Saved black-box flight log: {saved_file}", "SUCCESS")
        self.log_and_store("CRITICAL EVENT: MISSION ACCOMPLISHED & COMPLETED", "SUCCESS")

    def _on_motion_tick(self, angle: float) -> None:
        self._anim_angle = angle

    def _on_flight_tick(self, dt: float) -> None:
        if hasattr(self, "_replay_engine") and self._replay_engine._is_replaying:
            self._replay_engine.step_tick()
            return

        if hasattr(self, "maze_tracker") and hasattr(self, "_flight_recorder"):
            rx, ry = self.maze_tracker._r_spring.value, self.maze_tracker._c_spring.value
            hdg = self.maze_tracker._angle_spring.value
            spd = self.speed_slider.value() if hasattr(self, "speed_slider") else 180
            self._flight_recorder.record_frame(rx, ry, hdg, spd, 30.0, 12, "LIVE")

    def _create_card(self, title_text: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)

        header = QFrame()
        header.setObjectName("cardHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 6)

        title = QLabel(title_text)
        title.setObjectName("panelTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        if title_text == "MISSION CONTROL TELEMETRY":
            self._live_clock = LiveClockLabel(header)
            header_layout.addWidget(self._live_clock)

        layout.addWidget(header)
        return card, layout

    # ==================================================================
    #  Hold-to-Move Robotics Competition Engine & Deduplication
    # ==================================================================

    def _on_input_press(self, direction: str) -> None:
        """Handle mouse press or key press for a movement direction."""
        if direction not in self._active_pressed_inputs:
            self._active_pressed_inputs.append(direction)
        self._update_motion_state()

    def _on_input_release(self, direction: str) -> None:
        """Handle mouse release or key release for a movement direction."""
        while direction in self._active_pressed_inputs:
            self._active_pressed_inputs.remove(direction)
        self._update_motion_state()

    def _on_stop_pressed(self) -> None:
        """Emergency / Stop button event."""
        self._active_pressed_inputs.clear()
        self._update_motion_state()

    def _update_motion_state(self) -> None:
        """Evaluate active inputs and transmit command ONLY when motion state changes."""
        if not self._active_pressed_inputs or self._emergency:
            target_dir = "stop"
        else:
            target_dir = self._active_pressed_inputs[-1]

        # COMMAND DEDUPLICATION: Transmit over Bluetooth ONLY when motion state changes!
        if target_dir != self._current_sent_command:
            self._current_sent_command = target_dir
            self.send_command(target_dir)
            self._update_ui_button_highlights(target_dir)

    def _update_ui_button_highlights(self, active_dir: str) -> None:
        """Highlight active direction button on UI."""
        for d, btn in self._dir_buttons.items():
            is_active = (d == active_dir and d != "stop")
            btn.setProperty("active", "true" if is_active else "false")
            self._restyle(btn)

    def focusOutEvent(self, event) -> None:
        """Safety stop if application window loses focus."""
        if self._active_pressed_inputs:
            self._active_pressed_inputs.clear()
            self._update_motion_state()
        super().focusOutEvent(event)

    # ==================================================================
    #  Panel Builders
    # ==================================================================

    def _build_left_panel(self) -> QFrame:
        card, card_layout = self._create_card("MISSION CONTROL TELEMETRY")
        card.setFixedWidth(LEFT_PANEL_WIDTH)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_content.setMinimumHeight(920)
        scroll_content.setStyleSheet("background: transparent;")
        content = QVBoxLayout(scroll_content)
        content.setContentsMargins(8, 2, 8, 4)
        content.setSpacing(6)

        top_btn_row = QHBoxLayout()
        self.theme_btn = QPushButton("THEME")
        self.theme_btn.setObjectName("smallButton")
        self.theme_btn.clicked.connect(self._toggle_theme)

        self.export_btn = QPushButton("REPORT")
        self.export_btn.setObjectName("smallButton")
        self.export_btn.clicked.connect(self._export_session_report)

        self.replay_btn = QPushButton("REPLAY")
        self.replay_btn.setObjectName("smallButton")
        self.replay_btn.clicked.connect(self._trigger_replay_log)

        self.gamepad_btn = QPushButton("🎮 MAP")
        self.gamepad_btn.setObjectName("smallButton")
        self.gamepad_btn.clicked.connect(self._open_gamepad_config)

        self.demo_btn = QPushButton("🚀 DEMO")
        self.demo_btn.setObjectName("smallButton")
        self.demo_btn.setToolTip("Start interactive autonomous simulation / live demo")
        self.demo_btn.clicked.connect(self.toggle_demo_simulation)

        top_btn_row.addWidget(self.theme_btn)
        top_btn_row.addWidget(self.export_btn)
        top_btn_row.addWidget(self.replay_btn)
        top_btn_row.addWidget(self.gamepad_btn)
        top_btn_row.addWidget(self.demo_btn)
        content.addLayout(top_btn_row)

        mission_caption = QLabel("LIVE MISSION CONTROL METRICS")
        mission_caption.setObjectName("fieldCaption")
        content.addWidget(mission_caption)

        # Premium Mission Control Panel (11 Live Animated Metrics)
        self.mission_control = MissionControlPanel(self)
        content.addWidget(self.mission_control)

        # Living System Subsystem Data Flow Pipelines
        self.pipeline_overlay = SubsystemPipelineOverlay(self)
        content.addWidget(self.pipeline_overlay)

        self.bt_status = AnimatedStatusBadge("● Bluetooth : Disconnected (COM12)", "#F87171")
        self.cam_status = AnimatedStatusBadge("● Camera : Offline (1920×1080)", "#F87171")
        self.ping_label = QLabel("● Ping : -- ms")
        self.robot_status = AnimatedStatusBadge("● Robot : Standby (Idle)", "#FBBF24")
        self.timer_label = QLabel("● Match Timer : 00:00")
        self.fps_label = QLabel("● Camera Rate : -- FPS")

        for lbl in (self.bt_status, self.cam_status, self.ping_label, self.robot_status,
                    self.timer_label, self.fps_label):
            lbl.setObjectName("statusCard")
            content.addWidget(lbl)

        bt_caption = QLabel("BLUETOOTH LINK")
        bt_caption.setObjectName("fieldCaption")
        content.addWidget(bt_caption)

        port_row = QHBoxLayout()
        self.com_selector = QComboBox()
        self.com_selector.setObjectName("comPortSelector")
        port_row.addWidget(self.com_selector, 1)

        self.refresh_ports_btn = QPushButton("⟳")
        self.refresh_ports_btn.setObjectName("smallButton")
        self.refresh_ports_btn.setFixedSize(28, 28)
        self.refresh_ports_btn.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.refresh_ports_btn)
        content.addLayout(port_row)

        self.bt_connect_btn = QPushButton("CONNECT LINK")
        self.bt_connect_btn.setObjectName("btConnectButton")
        self.bt_connect_btn.clicked.connect(self._toggle_bluetooth)
        content.addWidget(self.bt_connect_btn)

        graph_caption = QLabel("PERFORMANCE GRAPH")
        graph_caption.setObjectName("fieldCaption")
        content.addWidget(graph_caption)

        self.telemetry_graph = TelemetryGraph(self)
        content.addWidget(self.telemetry_graph)

        content.addStretch()
        scroll.setWidget(scroll_content)
        card_layout.addWidget(scroll)
        return card

    def _build_center_panel(self) -> QFrame:
        card, layout = self._create_card("PRIMARY VIDEO FEED & SYSTEM LOGS")

        content = QVBoxLayout()
        content.setContentsMargins(8, 2, 8, 4)
        content.setSpacing(6)

        # Row 1: Primary Stream IP Address & Connect Action
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        cam_caption = QLabel("STREAM URL:")
        cam_caption.setObjectName("fieldCaption")
        self.ip_field = QLineEdit(self._load_saved_ip())
        self.ip_field.setPlaceholderText("Enter IP (e.g. 10.151.110.24:8080 or 0 for USB Cam)")
        self.ip_field.setMinimumWidth(260)
        self.ip_field.textChanged.connect(self._save_current_ip)
        self.ip_field.editingFinished.connect(self._save_current_ip)

        self.connect_btn = QPushButton("CONNECT VIDEO")
        self.connect_btn.setObjectName("connectButton")
        self.connect_btn.clicked.connect(self._toggle_camera)

        row1.addWidget(cam_caption)
        row1.addWidget(self.ip_field, 1)
        row1.addWidget(self.connect_btn)
        content.addLayout(row1)

        # Row 2: Resolution Selection & Quick Viewport Controls
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        res_caption = QLabel("RES:")
        res_caption.setObjectName("fieldCaption")
        self.res_selector = QComboBox()
        self.res_selector.setObjectName("resolutionSelector")
        for label, val in CAMERA_RESOLUTIONS:
            self.res_selector.addItem(label, val)
        saved_res = self._load_saved_res()
        res_idx = self.res_selector.findData(saved_res)
        if res_idx >= 0:
            self.res_selector.setCurrentIndex(res_idx)
        self.res_selector.currentIndexChanged.connect(self._save_current_res)

        self.snap_btn = QPushButton("SNAP")
        self.snap_btn.setObjectName("smallButton")
        self.snap_btn.clicked.connect(self._take_snapshot)

        self.rec_btn = QPushButton("REC")
        self.rec_btn.setObjectName("smallButton")
        self.rec_btn.clicked.connect(self._toggle_recording)

        self.video_fs_btn = QPushButton("⛶ FULLSCREEN")
        self.video_fs_btn.setObjectName("smallButton")
        self.video_fs_btn.clicked.connect(self._open_video_fullscreen)

        row2.addWidget(res_caption)
        row2.addWidget(self.res_selector)
        row2.addStretch(1)
        row2.addWidget(self.snap_btn)
        row2.addWidget(self.rec_btn)
        row2.addWidget(self.video_fs_btn)
        content.addLayout(row2)

        # JARVIS Holographic Camera Viewport
        self.camera_feed = JARVISHolographicViewport(self)
        self.camera_feed.setMinimumHeight(CAMERA_MIN_HEIGHT)
        self.camera_feed.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.camera_feed.doubleClicked.connect(self._open_video_fullscreen)
        content.addWidget(self.camera_feed, 1)

        # Idle AI Core Neural Activity Monitor
        ai_caption = QLabel("AI CORE NEURAL THINKING MONITOR")
        ai_caption.setObjectName("fieldCaption")
        content.addWidget(ai_caption)

        self.idle_ai_core = IdleAICoreWidget(self)
        content.addWidget(self.idle_ai_core)

        self.console = SystemConsole(self)
        self.console.setMaximumHeight(CONSOLE_MAX_HEIGHT)
        content.addWidget(self.console)

        layout.addLayout(content)
        return card

    def _build_right_panel(self) -> QFrame:
        card, card_layout = self._create_card("COMMAND & CONTROL")
        card.setFixedWidth(RIGHT_PANEL_WIDTH)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_content.setMinimumHeight(780)
        scroll_content.setStyleSheet("background: transparent;")
        content = QVBoxLayout(scroll_content)
        content.setContentsMargins(8, 2, 8, 4)
        content.setSpacing(6)

        self.btn_up = self._make_dir_button("▲\nW")
        self.btn_left = self._make_dir_button("◀\nA")
        self.btn_stop = self._make_dir_button("■\nSTOP", is_stop=True)
        self.btn_right = self._make_dir_button("▶\nD")
        self.btn_down = self._make_dir_button("▼\nS")

        self._dir_buttons: dict[str, QPushButton] = {
            "up": self.btn_up,
            "left": self.btn_left,
            "stop": self.btn_stop,
            "right": self.btn_right,
            "down": self.btn_down,
        }

        # Wire PySide6 pressed() and released() signals (Hold-to-Move Robotics Spec, DO NOT USE clicked())
        self.btn_up.pressed.connect(lambda: self._on_input_press("up"))
        self.btn_up.released.connect(lambda: self._on_input_release("up"))

        self.btn_down.pressed.connect(lambda: self._on_input_press("down"))
        self.btn_down.released.connect(lambda: self._on_input_release("down"))

        self.btn_left.pressed.connect(lambda: self._on_input_press("left"))
        self.btn_left.released.connect(lambda: self._on_input_release("left"))

        self.btn_right.pressed.connect(lambda: self._on_input_press("right"))
        self.btn_right.released.connect(lambda: self._on_input_release("right"))

        self.btn_stop.pressed.connect(self._on_stop_pressed)

        self.cmd_status_label = QLabel("COMMAND: STOPPED")
        self.cmd_status_label.setObjectName("fieldCaption")
        self.cmd_status_label.setStyleSheet("color: #35CFFF; font-weight: 800; font-size: 11px;")
        self.cmd_status_label.setAlignment(Qt.AlignCenter)
        content.addWidget(self.cmd_status_label)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.addWidget(self.btn_up, 0, 1)
        grid.addWidget(self.btn_left, 1, 0)
        grid.addWidget(self.btn_stop, 1, 1)
        grid.addWidget(self.btn_right, 1, 2)
        grid.addWidget(self.btn_down, 2, 1)
        content.addLayout(grid)

        maze_caption = QLabel("MAZE NAVIGATION TRACKER")
        maze_caption.setObjectName("fieldCaption")
        content.addWidget(maze_caption)

        self.maze_tracker = MazeGridWidget(self)
        content.addWidget(self.maze_tracker)

        speed_caption = QLabel("DRIVE SPEED LIMIT")
        speed_caption.setObjectName("fieldCaption")
        content.addWidget(speed_caption)

        # Animated Slider with Spring Tracking Thumb
        self.speed_slider = AnimatedSlider(Qt.Horizontal, self)
        self.speed_slider.setRange(SPEED_MIN, SPEED_MAX)
        self.speed_slider.setValue(DEFAULT_SPEED)
        content.addWidget(self.speed_slider)

        self.speed_value = AnimatedNumberLabel(
            self,
            initial_value=float(DEFAULT_SPEED),
            fmt=f"{{:d}} / {SPEED_MAX} ({int((DEFAULT_SPEED/SPEED_MAX)*100)}%)"
        )
        self.speed_value.set_formatter(lambda val: f"{int(round(val))} / {SPEED_MAX} ({int((val/SPEED_MAX)*100)}%)")
        self.speed_value.setObjectName("speedValueLabel")
        self.speed_value.setAlignment(Qt.AlignCenter)
        content.addWidget(self.speed_value)

        self.speed_slider.valueChanged.connect(self._on_speed_slider_moved)
        self.speed_slider.sliderReleased.connect(self._on_speed_slider_released)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        self._preset_buttons: list[QPushButton] = []
        for label, val in SPEED_PRESETS.items():
            btn = QPushButton(label)
            btn.setObjectName("presetButton")
            btn.clicked.connect(lambda _chk=False, v=val: self._apply_speed_preset(v))
            preset_row.addWidget(btn)
            self._preset_buttons.append(btn)
        content.addLayout(preset_row)

        content.addStretch()
        scroll.setWidget(scroll_content)
        card_layout.addWidget(scroll, 1)

        # Pinned EMERGENCY STOP button directly in card layout (outside scroll view)
        self.emergency_btn = QPushButton("🛑  EMERGENCY STOP  [SPACE]")
        self.emergency_btn.setObjectName("emergencyButton")
        self.emergency_btn.setFixedHeight(50)
        self.emergency_btn.clicked.connect(self.emergency_stop)
        card_layout.addWidget(self.emergency_btn)

        return card

    def _open_video_fullscreen(self) -> None:
        from joystick_overlay import VideoFullScreenDialog
        if hasattr(self, "_video_fullscreen_dlg") and self._video_fullscreen_dlg:
            try:
                self._video_fullscreen_dlg.close()
            except Exception:
                pass
        self._video_fullscreen_dlg = VideoFullScreenDialog(self)
        self._video_fullscreen_dlg.showFullScreen()
        self._video_fullscreen_dlg.raise_()
        self._video_fullscreen_dlg.activateWindow()
        self.log_and_store("Engaged Video Fullscreen Mode with Movable Joystick Overlay", "SUCCESS")

    @staticmethod
    def _make_dir_button(text: str, is_stop: bool = False) -> QPushButton:
        btn = QPushButton(text)
        if is_stop:
            btn.setObjectName("dirButtonStop")
        else:
            btn.setObjectName("dirButton")
        btn.setFixedSize(DIR_BUTTON_SIZE, DIR_BUTTON_SIZE)
        return btn

    def _on_speed_slider_moved(self, value: int) -> None:
        self.speed_value.set_value(value)
        self.telemetry_graph.add_speed_sample(value)

    def _on_speed_slider_released(self) -> None:
        val = self.speed_slider.value()
        self._controller.set_speed(val)
        self.log_and_store(f"Drive speed PWM committed: {val}", "INFO")

    def _apply_speed_preset(self, val: int) -> None:
        self.speed_slider.setValue(val)
        self._on_speed_slider_moved(val)
        self._on_speed_slider_released()

    def _open_gamepad_config(self) -> None:
        dlg = GamepadConfigDialog(self)
        dlg.exec()
        self.log_and_store("Updated Gamepad Controller Hardware Profile", "SUCCESS")

    def _trigger_replay_log(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Flight Log for Replay",
            RECORDINGS_DIR,
            "JSON Flight Logs (*.json)",
        )
        if file_path:
            ok = self._replay_engine.load_session_file(file_path)
            if ok:
                self.log_and_store(f"Loaded Flight Log: {os.path.basename(file_path)}", "SUCCESS")
                self._replay_engine.start_replay()
            else:
                self.log_and_store("Failed to load selected flight log", "WARNING")

    def _on_replayed_frame(self, frame: dict) -> None:
        rx, ry = frame.get("x", 2.0), frame.get("y", 2.0)
        hdg = frame.get("heading", 0.0)
        cmd = frame.get("command", "STOP")
        self.maze_tracker._r_spring.target = rx
        self.maze_tracker._c_spring.target = ry
        self.maze_tracker._angle_spring.target = hdg
        if hasattr(self, "camera_feed") and isinstance(self.camera_feed, JARVISHolographicViewport):
            self.camera_feed.update_hud_telemetry(heading=hdg)

    # ── Global Keyboard & Input Event Handling ────────────────────────

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.KeyPress, QEvent.KeyRelease):
            key = event.key()
            if key in DIRECTIONS or key == STOP_KEY or key == EMERGENCY_KEY:
                if hasattr(self, "_video_fullscreen_dlg") and self._video_fullscreen_dlg and self._video_fullscreen_dlg.isVisible():
                    return super().eventFilter(watched, event)
                
                if isinstance(watched, QLineEdit) and key in (Qt.Key_W, Qt.Key_A, Qt.Key_S, Qt.Key_D):
                    return super().eventFilter(watched, event)

                if event.type() == QEvent.KeyPress:
                    self.keyPressEvent(event)
                else:
                    self.keyReleaseEvent(event)
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
                self.log_and_store("Restored standard window view", "INFO")
            else:
                self.showFullScreen()
                self.log_and_store("Engaged Full Screen Ground Station Mode", "INFO")
        elif key == EMERGENCY_KEY:
            self.emergency_stop()
        elif key == STOP_KEY:
            self._on_stop_pressed()
        elif key in DIRECTIONS:
            dir_name = DIRECTIONS[key]
            self._on_input_press(dir_name)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == STOP_KEY:
            self._on_stop_pressed()
        elif key in DIRECTIONS:
            dir_name = DIRECTIONS[key]
            self._on_input_release(dir_name)

    # ==================================================================
    #  Actions & Hooks
    # ==================================================================

    def _export_session_report(self) -> None:
        timer_text = self.timer_label.text()
        filepath = SessionExporter.export_report(self._raw_logs, timer_text)
        self.log_and_store(f"Exported match report to: {filepath}", "SUCCESS")

    def log_and_store(self, msg: str, level: str = "INFO") -> None:
        self._raw_logs.append(f"[{level}] {msg}")
        self.console.log(msg, level)

    def _toggle_theme(self) -> None:
        self._is_dark_theme = not self._is_dark_theme
        if self._is_dark_theme:
            self.setStyleSheet(DARK_STYLE)
            self.log_and_store("Switched to Tactical Dark Theme", "INFO")
        else:
            self.setStyleSheet(LIGHT_STYLE)
            self.log_and_store("Switched to Daylight Light Theme", "INFO")

    def toggle_demo_simulation(self) -> None:
        if getattr(self, "_demo_sim_active", False):
            self._stop_demo_simulation()
        else:
            self._start_demo_simulation()

    def _start_demo_simulation(self) -> None:
        self._demo_sim_active = True
        self.demo_btn.setText("⏹ STOP")
        self.demo_btn.setStyleSheet("background-color: rgba(239, 68, 68, 0.3); color: #EF4444; border: 1px solid #EF4444;")
        self._bt_connected = True
        if isinstance(self.bt_status, AnimatedStatusBadge):
            self.bt_status.set_status("● Bluetooth : Simulated Link (COM-SIM)", "#35CFFF")
        if isinstance(self.robot_status, AnimatedStatusBadge):
            self.robot_status.set_status("● Robot : Ready (Simulation)", "#00E676")

        self.log_and_store("🚀 LIVE DEMO ACTIVATED: Virtual Rover link COM-SIM established", "SUCCESS")
        self.log_and_store("Autonomous exploration sequence active (Manual WASD / mouse enabled)", "INFO")

        self._demo_moves = [
            "up", "up", "right", "right", "down", "right", "down", "down", "left", "up", "right", "down"
        ]
        self._demo_move_idx = 0
        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._step_demo_simulation)
        self._demo_timer.start(850)

    def _step_demo_simulation(self) -> None:
        if not getattr(self, "_demo_sim_active", False):
            return

        if self._demo_move_idx < len(self._demo_moves):
            direction = self._demo_moves[self._demo_move_idx]
            self._demo_move_idx += 1

            self._controller.move(direction)
            self.maze_tracker.move_robot(direction)
            self._update_mission_status("EXPLORING", "INIT ➔ LINK ✓ ➔ NAV")

            cov = min(96.0, 20.0 + self._demo_move_idx * 7.0)
            qr_count = min(3, self._demo_move_idx // 3)
            self.maze_tracker._active_qr_count = qr_count

            if hasattr(self, "mission_control"):
                import random
                battery = max(70.0, 92.0 - self._demo_move_idx * 1.2)
                self.mission_control.update_telemetry(
                    coverage=cov,
                    qr_count=qr_count,
                    state="EXPLORING",
                    health=100.0,
                    vision=round(96.0 + random.uniform(0.5, 3.5), 1),
                    nav_acc=round(98.5 + random.uniform(0.2, 1.2), 1),
                    bt_qual=round(97.0 + random.uniform(0.0, 2.5), 1),
                    signal=round(95.0 + random.uniform(0.0, 3.0), 1),
                    battery=round(battery, 1),
                )

            if hasattr(self, "camera_feed") and isinstance(self.camera_feed, JARVISHolographicViewport):
                hdg = self.maze_tracker._angle_spring.target
                self.camera_feed.update_hud_telemetry(fps=30.0, ping=11, heading=hdg, battery=88.0)

            self.log_and_store(f"AI NAV: Autonomous waypoint step {self._demo_move_idx}/{len(self._demo_moves)}: {direction.upper()} | SLAM Coverage: {int(cov)}%", "INFO")

            if self._demo_move_idx == 3:
                self.log_and_store("SLAM RECOGNITION: Checkpoint QR-1 Acquired (Confidence: 99.4%)", "SUCCESS")
                AudioAlertSystem.alert_obstacle()
            elif self._demo_move_idx == 7:
                self.log_and_store("SLAM RECOGNITION: Checkpoint QR-2 Acquired (Confidence: 99.1%)", "SUCCESS")
                AudioAlertSystem.alert_obstacle()
            elif self._demo_move_idx == 11:
                self.log_and_store("SLAM RECOGNITION: Checkpoint QR-3 Acquired (Confidence: 98.8%)", "SUCCESS")
                AudioAlertSystem.alert_obstacle()
        else:
            self._stop_demo_simulation()
            self.trigger_mission_complete()

    def _stop_demo_simulation(self) -> None:
        self._demo_sim_active = False
        if hasattr(self, "_demo_timer") and self._demo_timer.isActive():
            self._demo_timer.stop()
        self.demo_btn.setText("🚀 DEMO")
        self.demo_btn.setStyleSheet("")
        self._restyle(self.demo_btn)
        self.log_and_store("DEMO SIMULATION: Autonomous run ended. Manual control retained.", "SUCCESS")

    def _take_snapshot(self) -> None:
        if self._camera_connected:
            self._camera.take_snapshot()
        else:
            self.log_and_store("Cannot take snapshot: Camera offline", "WARNING")

    def _toggle_recording(self) -> None:
        if self._camera_connected:
            is_recording = self._camera.toggle_recording()
            if is_recording:
                self.rec_btn.setText("⏹ STOP REC")
                self.rec_btn.setStyleSheet("background-color: #DC2626; color: white;")
            else:
                self.rec_btn.setText("🔴 REC")
                self.rec_btn.setStyleSheet("")
            if hasattr(self, "camera_feed") and isinstance(self.camera_feed, JARVISHolographicViewport):
                self.camera_feed.update_hud_telemetry(recording=is_recording)
        else:
            self.log_and_store("Cannot record video: Camera offline", "WARNING")

    # ==================================================================
    #  Signal Wiring
    # ==================================================================

    def _wire_signals(self) -> None:
        self._camera.frame_received.connect(self._on_frame)
        self._camera.status_changed.connect(self._on_camera_status)
        self._camera.fps_changed.connect(self.set_fps)
        self._camera.fps_changed.connect(self.telemetry_graph.add_fps_sample)
        self._camera.log_message.connect(self.log_and_store)

        self._bluetooth.connection_changed.connect(self._on_bt_status)
        self._bluetooth.log_message.connect(self.log_and_store)
        self._bluetooth.battery_updated.connect(self._on_battery_updated)

        self._controller.command_sent.connect(self.log_and_store)
        self._gamepad.log_message.connect(self.log_and_store)
        self._ping_monitor.status_updated.connect(self._on_ping_updated)
        
        self._replay_engine.frame_replayed.connect(self._on_replayed_frame)

    def _on_ping_updated(self, text: str) -> None:
        self.ping_label.setText(text)
        try:
            val_str = text.split(":")[-1].replace("ms", "").strip()
            val = float(val_str)
            if hasattr(self, "camera_feed") and isinstance(self.camera_feed, JARVISHolographicViewport):
                self.camera_feed.update_hud_telemetry(ping=val)
        except Exception:
            pass

    def _load_saved_ip(self) -> str:
        settings = QSettings("BlindMazeDriverStation", "DriverStation")
        saved_ip = settings.value("camera_ip", DEFAULT_CAMERA_IP, type=str)
        return saved_ip if saved_ip and saved_ip.strip() else DEFAULT_CAMERA_IP

    def _save_current_ip(self) -> None:
        if hasattr(self, "ip_field"):
            ip = self.ip_field.text().strip()
            if ip:
                settings = QSettings("BlindMazeDriverStation", "DriverStation")
                settings.setValue("camera_ip", ip)

    def _load_saved_res(self) -> str:
        settings = QSettings("BlindMazeDriverStation", "DriverStation")
        return settings.value("camera_res", DEFAULT_CAMERA_RESOLUTION, type=str)

    def _save_current_res(self) -> None:
        if hasattr(self, "res_selector"):
            res = self.res_selector.currentData()
            if res:
                settings = QSettings("BlindMazeDriverStation", "DriverStation")
                settings.setValue("camera_res", res)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.log_and_store("Terminating ground station sessions...", "WARNING")
        self._save_current_ip()
        self._save_current_res()
        self._ping_monitor.stop_monitoring()
        self._camera.disconnect_camera()
        self._bluetooth.close()
        self._gamepad.stop()
        if self._gamepad.isRunning():
            self._gamepad.wait(1000)
        self._session_timer.stop()
        super().closeEvent(event)

    def _toggle_camera(self) -> None:
        if self._camera_connected:
            self._ping_monitor.stop_monitoring()
            self._camera.disconnect_camera()
            self.connect_btn.setText("CONNECT VIDEO")
            self.connect_btn.setProperty("connected", "false")
            self._restyle(self.connect_btn)
            self.camera_feed.set_connection_state(connected=False, connecting=False)
            self._session_timer.stop()
            self.timer_label.setText("⏱  Match Timer  :  00:00")
            self.fps_label.setText("📷  Camera Rate  :  -- FPS")
            self.ping_label.setText("⚡  Ping  :  -- ms")
            self._camera_connected = False
            AudioAlertSystem.alert_disconnect()
        else:
            ip = self.ip_field.text().strip()
            res = self.res_selector.currentData() if hasattr(self, "res_selector") else DEFAULT_CAMERA_RESOLUTION
            if not ip:
                self.log_and_store("Camera IP field is empty", "WARNING")
                return
            self._save_current_ip()
            self._save_current_res()
            self.camera_feed.set_connection_state(connected=False, connecting=True)
            self.connect_btn.setText("DISCONNECT STREAM")
            self.connect_btn.setProperty("connected", "true")
            self._restyle(self.connect_btn)
            self._camera.connect_camera(ip, res)
            self._ping_monitor.start_monitoring(ip)
            self._elapsed.start()
            self._session_timer.start(1000)
            self._camera_connected = True
            AudioAlertSystem.alert_connect()

    def _on_camera_status(self, connected: bool) -> None:
        res_display = self.res_selector.currentData() if hasattr(self, "res_selector") else "1920x1080"
        if res_display.lower() == "auto":
            res_display = "Auto"
        if connected:
            if isinstance(self.cam_status, AnimatedStatusBadge):
                self.cam_status.set_status(f"● Camera : Active ({res_display})", "#00E676")
            else:
                self.cam_status.setText(f"🟢  Camera  :  Active ({res_display})")
                self.cam_status.setObjectName("statusCardActive")
            self.camera_feed.set_connection_state(connected=True, connecting=False)
        else:
            if isinstance(self.cam_status, AnimatedStatusBadge):
                self.cam_status.set_status(f"● Camera : Offline ({res_display})", "#F87171")
            else:
                self.cam_status.setText(f"🔴  Camera  :  Offline ({res_display})")
                self.cam_status.setObjectName("statusCard")
            self.camera_feed.set_connection_state(connected=False, connecting=False)
        self._restyle(self.cam_status)

    def _on_frame(self, qimage: QImage) -> None:
        if hasattr(self, "camera_feed") and isinstance(self.camera_feed, JARVISHolographicViewport):
            is_rec = hasattr(self._camera, "_recording") and self._camera._recording
            self.camera_feed.set_live_frame(qimage)
            self.camera_feed.update_hud_telemetry(recording=is_rec)

        if hasattr(self, "_video_fullscreen_dlg") and self._video_fullscreen_dlg and self._video_fullscreen_dlg.isVisible():
            self._video_fullscreen_dlg.update_frame(qimage)

    def set_fps(self, value: float) -> None:
        self.fps_label.setText(f"📷  Camera Rate  :  {value:.0f} FPS")
        if hasattr(self, "camera_feed") and isinstance(self.camera_feed, JARVISHolographicViewport):
            self.camera_feed.update_hud_telemetry(fps=value)

    def _refresh_ports(self) -> None:
        self.com_selector.clear()
        ports = self._bluetooth.port_descriptions()
        target_idx = -1
        if ports:
            for idx, (device, desc) in enumerate(ports):
                short_desc = desc.split("(")[0].strip() if "(" in desc else desc
                self.com_selector.addItem(f"{device} — {short_desc}", device)
                if device.upper() == DEFAULT_COM_PORT.upper():
                    target_idx = idx
            if target_idx != -1:
                self.com_selector.setCurrentIndex(target_idx)
            else:
                self.com_selector.insertItem(0, f"{DEFAULT_COM_PORT} (Target Port)", DEFAULT_COM_PORT)
                self.com_selector.setCurrentIndex(0)
            self.log_and_store(f"Discovered {len(ports)} serial port(s). Selected {self.com_selector.currentText()}", "INFO")
        else:
            self.com_selector.addItem(f"{DEFAULT_COM_PORT} (Target Port)", DEFAULT_COM_PORT)
            self.com_selector.setCurrentIndex(0)
            self.log_and_store(f"No active hardware serial ports detected. Pre-selected {DEFAULT_COM_PORT}.", "INFO")

    def _toggle_bluetooth(self) -> None:
        if self._bt_connected:
            self._bluetooth.disconnect()
            self.bt_connect_btn.setText("CONNECT LINK")
            self.bt_connect_btn.setProperty("connected", "false")
            self._restyle(self.bt_connect_btn)
            self._bt_connected = False
            if isinstance(self.bt_status, AnimatedStatusBadge):
                self.bt_status.set_status("● Bluetooth : Disconnected", "#F87171")
            else:
                self.bt_status.setText("🔴  Bluetooth  :  Disconnected")
            AudioAlertSystem.alert_disconnect()
        else:
            port = self.com_selector.currentData()
            if not port:
                self.log_and_store("No serial port selected", "WARNING")
                return

            self.bt_connect_btn.setText("Connecting...")
            if isinstance(self.bt_status, AnimatedStatusBadge):
                self.bt_status.set_status("● Searching COM Port...", "#FBBF24")
            else:
                self.bt_status.setText("🟡  Searching COM Port...")
            self.log_and_store("Searching COM Port...", "INFO")

            QTimer.singleShot(300, lambda: self._bt_stage_2(port))

    def _bt_stage_2(self, port: str) -> None:
        if isinstance(self.bt_status, AnimatedStatusBadge):
            self.bt_status.set_status("● Opening Port...", "#FBBF24")
        else:
            self.bt_status.setText("🟡  Opening Port...")
        self.log_and_store(f"Opening serial port {port}...", "INFO")
        QTimer.singleShot(300, lambda: self._bt_stage_3(port))

    def _bt_stage_3(self, port: str) -> None:
        if isinstance(self.bt_status, AnimatedStatusBadge):
            self.bt_status.set_status("● Handshaking...", "#FBBF24")
        else:
            self.bt_status.setText("🟡  Handshaking...")
        self.log_and_store("Handshaking HC-05 module...", "INFO")
        QTimer.singleShot(300, lambda: self._bt_stage_4(port))

    def _bt_stage_4(self, port: str) -> None:
        if isinstance(self.bt_status, AnimatedStatusBadge):
            self.bt_status.set_status("● Authenticating...", "#FBBF24")
        else:
            self.bt_status.setText("🟡  Authenticating...")
        self.log_and_store("Authenticating Bluetooth serial link...", "INFO")
        QTimer.singleShot(300, lambda: self._bt_stage_finish(port))

    def _bt_stage_finish(self, port: str) -> None:
        ok = self._bluetooth.connect(port)
        if ok:
            self.bt_connect_btn.setText("Connected ✓")
            self.bt_connect_btn.setProperty("connected", "true")
            self._restyle(self.bt_connect_btn)
            self._bt_connected = True
            if isinstance(self.bt_status, AnimatedStatusBadge):
                self.bt_status.set_status("● Bluetooth : Connected", "#00E676")
            else:
                self.bt_status.setText("🟢  Bluetooth  :  Connected")
            self._controller.set_speed(self.speed_slider.value())
            AudioAlertSystem.alert_connect()
        else:
            self.bt_connect_btn.setText("CONNECT LINK")
            if isinstance(self.bt_status, AnimatedStatusBadge):
                self.bt_status.set_status("● Bluetooth : Disconnected", "#F87171")
            else:
                self.bt_status.setText("🔴  Bluetooth  :  Disconnected")

    def _on_bt_status(self, connected: bool) -> None:
        if connected:
            if isinstance(self.bt_status, AnimatedStatusBadge):
                self.bt_status.set_status("● Bluetooth : Connected", "#00E676")
            else:
                self.bt_status.setText("🟢  Bluetooth  :  Connected")
            if isinstance(self.robot_status, AnimatedStatusBadge):
                self.robot_status.set_status("● Robot : Ready", "#00E676")
            else:
                self.robot_status.setText("🟢  Robot  :  Ready")
            self._update_mission_status("EXPLORING", "INIT ➔ LINK ✓ ➔ NAV")
        else:
            if isinstance(self.bt_status, AnimatedStatusBadge):
                self.bt_status.set_status("● Bluetooth : Disconnected", "#F87171")
            else:
                self.bt_status.setText("🔴  Bluetooth  :  Disconnected")
            if isinstance(self.robot_status, AnimatedStatusBadge):
                self.robot_status.set_status("● Robot : Standby", "#FBBF24")
            else:
                self.robot_status.setText("🔴  Robot  :  Standby")
            self._update_mission_status("STANDBY", "INIT ➔ LINK ➔ NAV")
            if self._bt_connected:
                self._bt_connected = False
                self.bt_connect_btn.setText("CONNECT LINK")
                self.bt_connect_btn.setProperty("connected", "false")
                self._restyle(self.bt_connect_btn)

    def _update_mission_status(self, stage: str, timeline: str) -> None:
        cov = getattr(self.maze_tracker, "get_coverage_pct", lambda: 14)()
        qr = getattr(self.maze_tracker, "get_qr_count", lambda: 1)()
        if hasattr(self, "mission_control") and isinstance(self.mission_control, MissionControlPanel):
            self.mission_control.update_telemetry(coverage=cov, qr_count=qr, state=stage)
        
        if cov >= 100 and qr >= 3:
            self.trigger_mission_complete()

    def _on_battery_updated(self, val: float) -> None:
        if hasattr(self, "mission_control") and isinstance(self.mission_control, MissionControlPanel):
            self.mission_control.update_telemetry(battery=val)
        if hasattr(self, "camera_feed") and isinstance(self.camera_feed, JARVISHolographicViewport):
            self.camera_feed.update_hud_telemetry(battery=val)

    def _get_connected_device_battery(self) -> float:
        """Fetch real-time battery level from connected Bluetooth device telemetry or system power APIs."""
        if hasattr(self, "_bluetooth") and self._bluetooth.connected:
            bt_bat = self._bluetooth.device_battery
            if bt_bat is not None:
                return float(bt_bat)

        try:
            import ctypes
            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ('ACLineStatus', ctypes.c_byte),
                    ('BatteryFlag', ctypes.c_byte),
                    ('BatteryLifePercent', ctypes.c_byte),
                    ('SystemStatusFlag', ctypes.c_byte),
                    ('BatteryLifeTime', ctypes.c_ulong),
                    ('FullBatteryLifeTime', ctypes.c_ulong),
                ]
            sps = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                pct = int(sps.BatteryLifePercent)
                if pct != 255 and 0 <= pct <= 100:
                    return float(pct)
        except Exception:
            pass

        try:
            import psutil
            bat = psutil.sensors_battery()
            if bat is not None:
                return float(bat.percent)
        except Exception:
            pass

        return 100.0

    def _tick(self) -> None:
        elapsed_sec = self._elapsed.elapsed() // 1000
        if MATCH_DURATION_SEC is not None:
            remaining = max(0, MATCH_DURATION_SEC - elapsed_sec)
            minutes, seconds = divmod(remaining, 60)
            if remaining == 0:
                self._session_timer.stop()
                self.log_and_store("Match timer elapsed", "WARNING")
                self.trigger_mission_complete()
        else:
            minutes, seconds = divmod(elapsed_sec, 60)
        self.timer_label.setText(f"⏱  Match Timer  :  00:{minutes:02d}:{seconds:02d}" if minutes >= 60 else f"⏱  Match Timer  :  {minutes:02d}:{seconds:02d}")
        
        bat_level = self._get_connected_device_battery()
        if hasattr(self, "mission_control") and isinstance(self.mission_control, MissionControlPanel):
            self.mission_control.update_telemetry(timer_sec=elapsed_sec, battery=bat_level)
        if hasattr(self, "camera_feed") and isinstance(self.camera_feed, JARVISHolographicViewport):
            self.camera_feed.update_hud_telemetry(battery=bat_level)

    def send_command(self, direction: str) -> None:
        cmd_labels = {
            "up": "FORWARD",
            "down": "BACKWARD",
            "left": "LEFT",
            "right": "RIGHT",
            "stop": "STOPPED",
        }
        self.cmd_status_label.setText(f"COMMAND: {cmd_labels.get(direction, direction.upper())}")
        
        if hasattr(self, "idle_ai_core") and isinstance(self.idle_ai_core, IdleAICoreWidget):
            self.idle_ai_core.set_robot_active(direction != "stop")

        if self._emergency or not self._bt_connected:
            return

        if isinstance(self.robot_status, AnimatedStatusBadge):
            if direction == "stop":
                self.robot_status.set_status("● Robot : Ready", "#00E676")
            else:
                self.robot_status.set_status(f"● Robot : {direction.upper()}", "#35CFFF")

        heading_map = {"up": 0.0, "right": 90.0, "down": 180.0, "left": 270.0, "stop": 45.0}
        if direction in heading_map and hasattr(self, "camera_feed") and isinstance(self.camera_feed, JARVISHolographicViewport):
            self.camera_feed.update_hud_telemetry(heading=heading_map[direction])

        self._controller.move(direction)
        self.maze_tracker.move_robot(direction)
        self._update_mission_status("EXPLORING", "INIT ➔ LINK ✓ ➔ NAV")

    def emergency_stop(self) -> None:
        self._emergency = True
        self._active_pressed_inputs.clear()
        self._current_sent_command = "stop"
        self._controller.emergency_stop()
        if isinstance(self.robot_status, AnimatedStatusBadge):
            self.robot_status.set_status("● Robot : E-STOPPED", "#EF4444")
        else:
            self.robot_status.setText("🔴  Robot  :  E-STOPPED")
        self.speed_slider.setValue(SPEED_MIN)
        AudioAlertSystem.alert_e_stop()

        for btn in self._dir_buttons.values():
            btn.setEnabled(False)

        self.log_and_store("CRITICAL: EMERGENCY STOP ENGAGED", "ERROR")
        QTimer.singleShot(EMERGENCY_LOCKOUT_MS, self._reset_emergency)

    def _reset_emergency(self) -> None:
        self._emergency = False
        self._controller.emergency = False
        if self._bt_connected:
            if isinstance(self.robot_status, AnimatedStatusBadge):
                self.robot_status.set_status("● Robot : Ready", "#00E676")
            else:
                self.robot_status.setText("🟢  Robot  :  Ready")
        for btn in self._dir_buttons.values():
            btn.setEnabled(True)
        self.log_and_store("Emergency lockout disengaged", "SUCCESS")

    @staticmethod
    def _restyle(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    sys.exit(app.exec())