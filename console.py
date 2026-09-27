"""
console.py — System console widget for the Driver Station.

Upgraded with character typewriter reveal animation, 60 FPS spring scroll & shake
physics, and a high-tech blinking terminal cursor block.
"""

from __future__ import annotations

import math
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit

from settings import CONSOLE_MAX_LINES
from motion import MotionEngine, SpringSolver

_LEVEL_COLOURS: dict[str, str] = {
    "INFO":    "#60A5FA",
    "WARNING": "#FBBF24",
    "ERROR":   "#F87171",
    "SUCCESS": "#34D399",
}

_DEFAULT_COLOUR: str = "#D1D5DB"


class SystemConsole(QTextEdit):
    """Read-only auto-scrolling console with typewriter reveal, blinking cursor block, and spring physics."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setObjectName("systemConsole")
        self.setFocusPolicy(Qt.NoFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._line_count: int = 0

        # Typewriter queue & timers
        self._type_queue: list[dict] = []
        self._type_timer = QTimer(self)
        self._type_timer.setInterval(18)
        self._type_timer.timeout.connect(self._process_typewriter_step)

        self._cursor_blink: bool = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(450)
        self._cursor_timer.timeout.connect(self._toggle_cursor)
        self._cursor_timer.start()

        # Spring Solvers
        self._shake_spring = SpringSolver(0.0, 0.0, stiffness=350.0, damping=18.0)
        self._scroll_spring = SpringSolver(0.0, 0.0, stiffness=220.0, damping=16.0)

        MotionEngine.instance().tick_dt.connect(self._on_tick)

    def _toggle_cursor(self) -> None:
        self._cursor_blink = not self._cursor_blink
        self.update()

    @Slot(str, str)
    def log(self, message: str, level: str = "INFO") -> None:
        level = level.upper()
        colour = _LEVEL_COLOURS.get(level, _DEFAULT_COLOUR)
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        level_prefix = {
            "INFO": "ℹ",
            "SUCCESS": "✓",
            "WARNING": "⚠",
            "ERROR": "✖",
        }.get(level, "●")

        self._type_queue.append({
            "timestamp": timestamp,
            "level": level,
            "level_prefix": level_prefix,
            "colour": colour,
            "message": message,
            "char_idx": 0,
        })

        if not self._type_timer.isActive():
            self._type_timer.start()

        if level == "ERROR":
            self._shake_horizontal()

    def _process_typewriter_step(self) -> None:
        if not self._type_queue:
            self._type_timer.stop()
            return

        item = self._type_queue[0]
        msg = item["message"]
        idx = item["char_idx"] + 3
        item["char_idx"] = idx

        partial_msg = msg[:idx]
        is_done = idx >= len(msg)
        cursor_tag = "" if is_done else '<span style="color:#35CFFF">█</span>'

        html = (
            f'<div style="background-color:rgba(53,207,255,0.08); padding:3px 6px; border-radius:4px; margin-bottom:2px;">'
            f'<span style="color:#64748B">[{item["timestamp"]}]</span> '
            f'<span style="color:{item["colour"]};font-weight:bold">{item["level_prefix"]} [{item["level"]}]</span> '
            f'<span style="color:#E2E8F0">{_escape_html(partial_msg)}</span>'
            f'{cursor_tag}'
            f'</div>'
        )

        if idx <= 3:
            self.append(html)
            self._line_count += 1
        else:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.insertHtml(html)

        self._trim_if_needed()
        self._scroll_to_bottom_smooth()

        if is_done:
            self._type_queue.pop(0)

    def clear_console(self) -> None:
        self.clear()
        self._line_count = 0
        self._type_queue.clear()

    def _shake_horizontal(self) -> None:
        self._shake_spring.velocity = 120.0

    def _trim_if_needed(self) -> None:
        if self._line_count <= CONSOLE_MAX_LINES:
            return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, self._line_count - CONSOLE_MAX_LINES)
        cursor.removeSelectedText()
        cursor.deleteChar()
        self._line_count = CONSOLE_MAX_LINES

    def _scroll_to_bottom_smooth(self) -> None:
        scrollbar = self.verticalScrollBar()
        self._scroll_spring.target = float(scrollbar.maximum())

    def _on_tick(self, dt: float) -> None:
        if not self._shake_spring.is_settled():
            offset_x = self._shake_spring.update(dt)
            vp = self.viewport()
            vp.move(int(offset_x), vp.y())

        if not self._scroll_spring.is_settled():
            curr_val = self._scroll_spring.update(dt)
            scrollbar = self.verticalScrollBar()
            scrollbar.setValue(int(curr_val))


def _escape_html(text: str) -> str:
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
