"""
network_monitor.py — Background thread measuring real-time socket latency to the IP Camera.
"""

from __future__ import annotations

import socket
import time
from PySide6.QtCore import QThread, Signal


class NetworkPingThread(QThread):
    """Measures socket ping latency to the camera IP."""

    ping_updated = Signal(float)      # latency in ms
    status_updated = Signal(str)      # string ping status
    log_message = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._target_host: str = ""
        self._target_port: int = 8080
        self._running: bool = False

    def set_target(self, host_port: str) -> None:
        try:
            clean = host_port.replace("http://", "").replace("https://", "").replace("rtsp://", "").split("/")[0]
            if clean.isdigit():
                self._target_host = "local"
                self._target_port = 0
                return

            if ":" in clean:
                parts = clean.split(":")
                self._target_host = parts[0]
                try:
                    self._target_port = int(parts[1])
                except ValueError:
                    self._target_port = 8080
            else:
                self._target_host = clean
                self._target_port = 8080
        except Exception:
            self._target_host = ""

    def start_monitoring(self, host_port: str) -> None:
        self.set_target(host_port)
        self._running = True
        if not self.isRunning():
            self.start()

    def stop_monitoring(self) -> None:
        self._running = False

    def run(self) -> None:
        while self._running:
            if not self._target_host:
                time.sleep(0.5)
                continue

            if self._target_host == "local":
                self.ping_updated.emit(0.0)
                self.status_updated.emit("⚡ Ping  :  0.0 ms (Local Cam)")
                time.sleep(1.5)
                continue

            latency = self._measure_latency(self._target_host, self._target_port)
            if latency >= 0:
                self.ping_updated.emit(latency)
                self.status_updated.emit(f"⚡ Ping  :  {latency:.1f} ms")
                time.sleep(1.5)
            else:
                self.status_updated.emit("⚡ Ping  :  Timeout")
                time.sleep(2.0)

    @staticmethod
    def _measure_latency(host: str, port: int) -> float:
        """Measures network connection round-trip latency in milliseconds using high-precision perf_counter."""
        try:
            start = time.perf_counter()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.25)
            s.connect((host, port))
            s.close()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return round(elapsed_ms, 2)
        except Exception:
            try:
                start = time.perf_counter()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.25)
                s.connect((host, 80 if port != 80 else 8080))
                s.close()
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                return round(elapsed_ms, 2)
            except Exception:
                return -1.0
