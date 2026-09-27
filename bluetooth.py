"""
bluetooth.py — Thread-safe HC-05 Bluetooth serial controller.

Provides automatic COM-port detection, connection with retries,
duplicate-command suppression, and signal-based status reporting.

Public API (preserved from original):
    BluetoothController.available_ports()
    BluetoothController.connect(port, baud)
    BluetoothController.disconnect()
    BluetoothController.send(command)
    BluetoothController.forward / backward / left / right / stop
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, Signal

from settings import (
    BT_COMMAND_DEDUP_MS,
    BT_RECONNECT_INTERVAL_SEC,
    BT_SERIAL_TIMEOUT_SEC,
    DEFAULT_BAUD_RATE,
)


class BluetoothController(QObject):
    """Thread-safe wrapper around ``pyserial`` for HC-05 communication."""

    # Signals for UI integration
    connection_changed = Signal(bool)    # True = connected
    error_occurred = Signal(str)         # human-readable error
    log_message = Signal(str, str)       # (message, level)
    battery_updated = Signal(float)      # Device battery percentage
    telemetry_received = Signal(str)     # Raw incoming telemetry line

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._serial: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._connected: bool = False
        self._last_command: str = ""
        self._last_command_time: float = 0.0
        self._port: str = ""
        self._baud: int = DEFAULT_BAUD_RATE
        self._reconnecting: bool = False
        self._device_battery: Optional[float] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_running: bool = False

    # ── Properties ───────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        """Whether the serial link is currently open."""
        return self._connected

    @property
    def device_battery(self) -> Optional[float]:
        """Return last known battery level received from connected device."""
        return self._device_battery

    # ── Port Discovery ───────────────────────────────────────────────

    @staticmethod
    def available_ports() -> list[str]:
        """Return a list of available COM port device names."""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    @staticmethod
    def port_descriptions() -> list[tuple[str, str]]:
        """Return ``(device, description)`` for every COM port."""
        ports = serial.tools.list_ports.comports()
        return [(p.device, p.description) for p in ports]

    # ── Connect / Disconnect ─────────────────────────────────────────

    def connect(self, port: str, baud: int = DEFAULT_BAUD_RATE) -> bool:
        """Open a serial connection.

        Args:
            port: COM port string, e.g. ``"COM5"``.
            baud: Baud rate (default 9600).

        Returns:
            ``True`` on success.
        """
        self._port = port
        self._baud = baud

        with self._lock:
            try:
                if self._serial and self._serial.is_open:
                    self._serial.close()

                self._serial = serial.Serial(
                    port,
                    baud,
                    timeout=BT_SERIAL_TIMEOUT_SEC,
                )
                self._connected = True
                self._last_command = ""
                self._start_reader()
                self.connection_changed.emit(True)
                self.log_message.emit(
                    f"Bluetooth connected on {port} @ {baud} baud", "SUCCESS",
                )
                return True

            except serial.SerialException as exc:
                self._connected = False
                self.connection_changed.emit(False)
                msg = f"Bluetooth connect failed ({port}): {exc}"
                self.error_occurred.emit(msg)
                self.log_message.emit(msg, "ERROR")
                return False

    def disconnect(self) -> None:
        """Close the serial connection and emit status."""
        with self._lock:
            self._close_port()
        self.log_message.emit("Bluetooth disconnected", "INFO")

    # ── Background Telemetry Reader ──────────────────────────────────

    def _start_reader(self) -> None:
        self._reader_running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def _stop_reader(self) -> None:
        self._reader_running = False

    def _read_loop(self) -> None:
        """Background thread reading incoming serial telemetry."""
        while self._reader_running and self._connected:
            try:
                if self._serial and self._serial.is_open and self._serial.in_waiting > 0:
                    raw_line = self._serial.readline().decode("utf-8", errors="ignore").strip()
                    if raw_line:
                        self.telemetry_received.emit(raw_line)
                        self._parse_telemetry(raw_line)
                else:
                    time.sleep(0.001)
            except Exception:
                time.sleep(0.001)

    def _parse_telemetry(self, line: str) -> None:
        """Parse incoming telemetry lines for battery or status metrics."""
        upper = line.upper()
        # Pattern: BAT:85, BATTERY:92, B:78
        for prefix in ("BATTERY:", "BAT:", "B:"):
            if prefix in upper:
                try:
                    val_str = upper.split(prefix)[1].strip().rstrip("%")
                    val = float(val_str)
                    val = max(0.0, min(100.0, val))
                    self._device_battery = val
                    self.battery_updated.emit(val)
                    return
                except (ValueError, IndexError):
                    pass

    # ── Send ─────────────────────────────────────────────────────────

    def send(self, command: str) -> bool:
        """Send a raw string over serial.

        Duplicate commands within ``BT_COMMAND_DEDUP_MS`` are suppressed.

        Args:
            command: The string to write (will be encoded to bytes).

        Returns:
            ``True`` if the write succeeded.
        """
        if not self._connected:
            return False

        # Deduplicate rapid identical commands
        now = time.monotonic()
        if (
            command == self._last_command
            and (now - self._last_command_time) * 1000 < BT_COMMAND_DEDUP_MS
        ):
            return True  # silently suppress

        with self._lock:
            try:
                if self._serial and self._serial.is_open:
                    self._serial.write(command.encode())
                    self._last_command = command
                    self._last_command_time = now
                    return True
                else:
                    self._handle_disconnect()
                    return False
            except serial.SerialException as exc:
                self._handle_disconnect()
                self.error_occurred.emit(f"BT write error: {exc}")
                self.log_message.emit(f"BT write error: {exc}", "ERROR")
                return False

    # ── Convenience wrappers (original API) ──────────────────────────

    def forward(self) -> None:
        """Send the 'forward' command."""
        self.send("F")

    def backward(self) -> None:
        """Send the 'backward' command."""
        self.send("B")

    def left(self) -> None:
        """Send the 'left' command."""
        self.send("L")

    def right(self) -> None:
        """Send the 'right' command."""
        self.send("R")

    def stop(self) -> None:
        """Send the 'stop' command."""
        self.send("S")

    # ── Reconnect ────────────────────────────────────────────────────

    def attempt_reconnect(self) -> bool:
        """Try to re-establish the last known connection.

        Returns:
            ``True`` if reconnected successfully.
        """
        if not self._port:
            return False
        self.log_message.emit(
            f"Attempting BT reconnect on {self._port}…", "WARNING",
        )
        return self.connect(self._port, self._baud)

    # ── Cleanup ──────────────────────────────────────────────────────

    def close(self) -> None:
        """Guaranteed resource cleanup.  Safe to call multiple times."""
        with self._lock:
            self._close_port()

    # ── Internal helpers ─────────────────────────────────────────────

    def _close_port(self) -> None:
        """Close the serial port (caller must hold ``_lock``)."""
        self._stop_reader()
        if self._serial:
            try:
                if self._serial.is_open:
                    self._serial.close()
            except Exception:
                pass
            self._serial = None
        if self._connected:
            self._connected = False
            self.connection_changed.emit(False)

    def _handle_disconnect(self) -> None:
        """React to an unexpected disconnect (caller must hold ``_lock``)."""
        self._close_port()
        self.log_message.emit("Bluetooth connection lost", "ERROR")