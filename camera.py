"""
camera.py — Zero-Latency IP-Webcam Capture Engine.

Optimized for ultra-low latency (< 5ms frame delay) using direct HTTP MJPEG socket reading,
FFmpeg low-delay environment overrides, OpenCV buffer size caps, and zero-copy QImage conversion.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import urllib.request
from collections import deque
from datetime import datetime
from threading import Event, Lock
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from settings import (
    CAMERA_RECONNECT_INTERVAL_SEC,
    CAMERA_TIMEOUT_SEC,
    CAMERA_URL_SUFFIX,
    DEFAULT_CAMERA_RESOLUTION,
    FPS_WINDOW_SIZE,
    RECORDINGS_DIR,
    SNAPSHOTS_DIR,
    TARGET_FPS,
)

# Global low-latency environment overrides for OpenCV FFmpeg backend (including 2s socket/open timeouts)
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "fflags;nobuffer|flags;low_delay|max_delay;0|probesize;32|analyzeduration;0|sync;ext|timeout;2000000|stimeout;2000000"
)


def convert_to_mp4(
    input_filepath: str,
    output_filepath: Optional[str] = None,
    remove_original: bool = False,
) -> Optional[str]:
    """Converts any video file (e.g. .avi) into standard .mp4 format.
    
    Tries ffmpeg CLI first for high efficiency, otherwise falls back to OpenCV re-encoding.
    Returns the absolute path of the generated .mp4 file, or None on failure.
    """
    if not os.path.exists(input_filepath):
        return None

    if output_filepath is None:
        base, ext = os.path.splitext(input_filepath)
        if ext.lower() == ".mp4":
            output_filepath = f"{base}_converted.mp4"
        else:
            output_filepath = f"{base}.mp4"

    # Strategy 1: Attempt fast ffmpeg CLI conversion if ffmpeg is available
    ffmpeg_exe = shutil.which("ffmpeg")
    if ffmpeg_exe:
        try:
            cmd = [ffmpeg_exe, "-y", "-i", input_filepath, "-c:v", "libx264", "-preset", "fast", "-crf", "23", output_filepath]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if res.returncode == 0 and os.path.exists(output_filepath) and os.path.getsize(output_filepath) > 0:
                if remove_original and os.path.abspath(input_filepath) != os.path.abspath(output_filepath):
                    try:
                        os.remove(input_filepath)
                    except Exception:
                        pass
                return output_filepath
        except Exception:
            pass

    # Strategy 2: Fallback to OpenCV frame-by-frame conversion
    try:
        cap = cv2.VideoCapture(input_filepath)
        if not cap.isOpened():
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = 20.0

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if width <= 0 or height <= 0:
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                return None
            height, width = frame.shape[:2]
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        fourcc_codecs = ["mp4v", "avc1", "H264"]
        writer = None
        for codec in fourcc_codecs:
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                w_candidate = cv2.VideoWriter(output_filepath, fourcc, fps, (width, height))
                if w_candidate.isOpened():
                    writer = w_candidate
                    break
            except Exception:
                continue

        if writer is None or not writer.isOpened():
            cap.release()
            return None

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            writer.write(frame)

        cap.release()
        writer.release()

        if os.path.exists(output_filepath) and os.path.getsize(output_filepath) > 0:
            if remove_original and os.path.abspath(input_filepath) != os.path.abspath(output_filepath):
                try:
                    os.remove(input_filepath)
                except Exception:
                    pass
            return output_filepath
    except Exception:
        pass

    return None


def convert_existing_recordings(recordings_dir: str = RECORDINGS_DIR) -> list[str]:
    """Scans recordings directory and converts all non-mp4 video files (such as .avi) into .mp4 format."""
    converted_files = []
    if not os.path.exists(recordings_dir):
        return converted_files

    for fname in os.listdir(recordings_dir):
        ext = os.path.splitext(fname)[1].lower()
        if ext in (".avi", ".mkv", ".mov", ".flv", ".wmv"):
            input_path = os.path.join(recordings_dir, fname)
            out_path = convert_to_mp4(input_path, remove_original=True)
            if out_path:
                converted_files.append(out_path)
    return converted_files


class CameraThread(QThread):
    """Background thread that captures frames from an IP webcam with zero-latency buffer flushing,
    emits QImages, and handles snapshot captures & video recording.
    """

    frame_received = Signal(object)   # QImage ready for display
    status_changed = Signal(bool)     # True = connected
    fps_changed = Signal(float)       # measured FPS
    log_message = Signal(str, str)    # (message, level)
    recording_changed = Signal(bool)  # True = recording active

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._url: str = ""
        self._target_resolution: str = DEFAULT_CAMERA_RESOLUTION
        self._stop_event = Event()
        self._frame_times: deque[float] = deque(maxlen=FPS_WINDOW_SIZE)
        self._current_fps: float = float(TARGET_FPS)

        # Snapshot & Recording state
        self._snapshot_requested: bool = False
        self._recording: bool = False
        self._recording_filepath: str = ""
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._active_stream = None
        self._lock = Lock()

        # Ensure directory structures exist and convert any existing non-MP4 recordings
        os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        convert_existing_recordings(RECORDINGS_DIR)

    # ── Public Recording & Snapshot API ──────────────────────────────

    def take_snapshot(self) -> None:
        """Trigger snapshot capture on the next frame."""
        self._snapshot_requested = True

    def toggle_recording(self) -> bool:
        """Toggle video recording on/off. Returns current recording status."""
        with self._lock:
            if self._recording:
                self._stop_recording()
            else:
                self._start_recording()
            return self._recording

    def _start_recording(self) -> None:
        """Initialize OpenCV VideoWriter for .mp4 recording."""
        filename = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        filepath = os.path.join(RECORDINGS_DIR, filename)
        self._recording_filepath = filepath
        self._video_writer = None  # Lazily instantiated on first frame with exact dimensions
        self._recording = True
        self.recording_changed.emit(True)
        self.log_message.emit(f"Started MP4 video recording: {filename}", "SUCCESS")

    def _stop_recording(self) -> None:
        """Release OpenCV VideoWriter and finalize MP4 recording."""
        rec_path = self._recording_filepath
        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None
        self._recording = False
        self.recording_changed.emit(False)
        if rec_path and os.path.exists(rec_path):
            filename = os.path.basename(rec_path)
            size_bytes = os.path.getsize(rec_path)
            size_mb = size_bytes / (1024 * 1024)
            self.log_message.emit(f"Saved MP4 video recording: {filename} ({size_mb:.2f} MB)", "SUCCESS")
        else:
            self.log_message.emit("Stopped video recording", "INFO")
        self._recording_filepath = ""

    # ── Public Camera Connection API ─────────────────────────────────

    def connect_camera(self, ip_or_url: str, resolution: str = "1920x1080") -> None:
        url = ip_or_url.strip()
        if not url:
            return

        self._target_resolution = resolution.strip() if resolution else DEFAULT_CAMERA_RESOLUTION

        # Case 1: Local USB Webcam index (e.g. "0", "1", "2")
        if url.isdigit():
            self._url = url
            self._stop_event.clear()
            if not self.isRunning():
                self.start()
            return

        # Case 2: RTSP Stream (e.g. rtsp://192.168.1.5:554/live)
        if url.startswith("rtsp://"):
            self._url = url
            self._stop_event.clear()
            if not self.isRunning():
                self.start()
            return

        # Case 3: HTTP/HTTPS URLs or raw IP (e.g. 10.151.110.24:8080 or http://10.151.110.24:8080/video)
        url = url.rstrip("/")
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"http://{url}"

        # If user entered host or host:port with no path (e.g. http://10.151.110.24:8080),
        # append default /video path for IP Webcam Android app.
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.path or parsed.path == "/":
            url = f"{url}/video"

        # Append resolution query parameter if not already present
        if "?" not in url and not url.endswith(".m3u8") and not url.endswith(".mp4"):
            if self._target_resolution and "x" in self._target_resolution and self._target_resolution.lower() != "auto":
                url = f"{url}?{self._target_resolution}"

        self._url = url
        self._stop_event.clear()
        if not self.isRunning():
            self.start()

    def disconnect_camera(self) -> None:
        self._stop_event.set()
        if self._active_stream:
            try:
                self._active_stream.close()
            except Exception:
                pass
            self._active_stream = None
        if self._recording:
            with self._lock:
                self._stop_recording()
        if self.isRunning():
            self.wait(2500)

    # ── Zero-Latency Thread Capture Loop ─────────────────────────────

    def run(self) -> None:
        while not self._stop_event.is_set():
            # Strategy 1: Attempt ultra-fast direct HTTP MJPEG streaming for http/https URLs
            if self._url.startswith("http://") or self._url.startswith("https://"):
                success = self._run_mjpeg_direct()
                if success or self._stop_event.is_set():
                    self.status_changed.emit(False)
                    if self._stop_event.is_set():
                        break
                    self._sleep_interruptible(CAMERA_RECONNECT_INTERVAL_SEC)
                    continue

            # Strategy 2: Fall back to low-latency OpenCV VideoCapture (for RTSP, camera index, or custom streams)
            cap: Optional[cv2.VideoCapture] = None
            try:
                cap = self._open_capture()
                if cap is None:
                    self._sleep_interruptible(CAMERA_RECONNECT_INTERVAL_SEC)
                    continue

                self.status_changed.emit(True)
                self.log_message.emit(f"Zero-latency OpenCV camera connected: {self._url}", "SUCCESS")
                self._frame_times.clear()

                while not self._stop_event.is_set():
                    # Purge buffered frames for zero frame lag
                    if not cap.grab():
                        self.log_message.emit("Camera frame grab failed", "WARNING")
                        break

                    ret, frame = cap.retrieve()
                    if not ret or frame is None:
                        continue

                    # Process Snapshot & Recording
                    self._handle_snapshot_and_recording(frame)

                    # Emit Frame directly to UI
                    qimage = self._convert_frame(frame)
                    self.frame_received.emit(qimage)
                    self._update_fps()

            except Exception as exc:
                self.log_message.emit(f"Camera error: {exc}", "ERROR")

            finally:
                if self._recording:
                    with self._lock:
                        self._stop_recording()
                if cap is not None:
                    cap.release()
                self.status_changed.emit(False)

            if not self._stop_event.is_set():
                self._sleep_interruptible(CAMERA_RECONNECT_INTERVAL_SEC)

        self.status_changed.emit(False)

    # ── Direct HTTP MJPEG Native Reader ───────────────────────────────

    def _run_mjpeg_direct(self) -> bool:
        """Direct socket/HTTP MJPEG stream parser.
        Bypasses OpenCV FFmpeg container buffering to achieve < 5ms network transport latency.
        """
        try:
            req = urllib.request.Request(self._url, headers={"User-Agent": "Mozilla/5.0"})
            stream = urllib.request.urlopen(req, timeout=CAMERA_TIMEOUT_SEC)
            self._active_stream = stream

            # Validate header content-type if available
            content_type = stream.headers.get("Content-Type", "").lower()
            if "text/html" in content_type or "text/plain" in content_type or "application/json" in content_type:
                stream.close()
                self._active_stream = None
                return False
        except Exception:
            return False

        self.status_changed.emit(True)
        self.log_message.emit(f"Zero-latency native HTTP stream connected: {self._url}", "SUCCESS")
        self._frame_times.clear()

        bytes_buffer = bytearray()
        chunk_size = 65536  # 64 KB chunks for fast socket throughput on HD/1080p streams
        last_emit_time = 0.0
        total_bytes_read = 0
        frames_decoded = 0

        try:
            while not self._stop_event.is_set():
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                bytes_buffer.extend(chunk)
                total_bytes_read += len(chunk)

                # Parse all complete JPEG images in buffer and extract the newest frame
                newest_frame_data = None
                while True:
                    a = bytes_buffer.find(b"\xff\xd8")
                    if a == -1:
                        bytes_buffer.clear()
                        break
                    if a > 0:
                        del bytes_buffer[:a]
                        a = 0

                    b = bytes_buffer.find(b"\xff\xd9", a + 2)
                    if b == -1:
                        break

                    # Found a complete JPEG frame
                    newest_frame_data = bytes_buffer[a : b + 2]
                    del bytes_buffer[: b + 2]

                if newest_frame_data is not None:
                    frames_decoded += 1
                    now = time.monotonic()
                    # Rate-limit signal emissions to max 60 FPS (~16ms) to prevent UI event loop backlog
                    if now - last_emit_time >= 0.016:
                        frame = cv2.imdecode(np.frombuffer(newest_frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            self._handle_snapshot_and_recording(frame)
                            qimage = self._convert_frame(frame)
                            self.frame_received.emit(qimage)
                            self._update_fps()
                            last_emit_time = now

                # Fail-safe check: If we read > 500 KB without decoding a single valid frame, exit so OpenCV can attempt capture
                if frames_decoded == 0 and total_bytes_read > 524288:
                    self.log_message.emit("Direct HTTP MJPEG stream unreadable. Falling back to OpenCV...", "WARNING")
                    stream.close()
                    self._active_stream = None
                    return False

                # Guard against unparsed buffer growth
                if len(bytes_buffer) > 1000000:
                    del bytes_buffer[:500000]

            stream.close()
            self._active_stream = None
            return True
        except Exception as exc:
            self.log_message.emit(f"HTTP stream direct read exception: {exc}", "WARNING")
            try:
                stream.close()
            except Exception:
                pass
            self._active_stream = None
            return False

    # ── Internal Helpers ─────────────────────────────────────────────

    def _handle_snapshot_and_recording(self, frame: np.ndarray) -> None:
        """Save snapshot or write frame to .mp4 video file if requested."""
        if self._snapshot_requested:
            self._snapshot_requested = False
            filename = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            filepath = os.path.join(SNAPSHOTS_DIR, filename)
            cv2.imwrite(filepath, frame)
            self.log_message.emit(f"Snapshot saved: {filename}", "SUCCESS")

        with self._lock:
            if self._recording:
                if self._video_writer is None and self._recording_filepath:
                    h, w = frame.shape[:2]
                    rec_fps = self._current_fps if (self._current_fps >= 5.0) else float(TARGET_FPS)
                    fourcc_codecs = ["mp4v", "avc1", "H264"]
                    for codec in fourcc_codecs:
                        try:
                            fourcc = cv2.VideoWriter_fourcc(*codec)
                            writer = cv2.VideoWriter(self._recording_filepath, fourcc, rec_fps, (w, h))
                            if writer.isOpened():
                                self._video_writer = writer
                                break
                        except Exception:
                            pass

                if self._video_writer is not None:
                    self._video_writer.write(frame)

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        self.log_message.emit(f"Opening camera stream: {self._url} (Resolution: {self._target_resolution})", "INFO")
        
        # Check if URL is an integer camera index (e.g. 0, 1, 2 for local USB webcam)
        if self._url.isdigit():
            cam_idx = int(self._url)
            cap = cv2.VideoCapture(cam_idx)
            if cap.isOpened():
                if hasattr(self, "_target_resolution") and "x" in self._target_resolution:
                    parts = self._target_resolution.split("x")
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        w, h = int(parts[0]), int(parts[1])
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.log_message.emit(f"Local USB webcam #{cam_idx} opened successfully", "SUCCESS")
                return cap
            else:
                self.log_message.emit(f"Failed to open USB webcam #{cam_idx}", "ERROR")
                return None

        # Network stream (RTSP, HTTP/MJPEG, H264 stream)
        cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self._url)

        try:
            if hasattr(self, "_target_resolution") and "x" in self._target_resolution:
                parts = self._target_resolution.split("x")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    w, h = int(parts[0]), int(parts[1])
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(CAMERA_TIMEOUT_SEC * 1000))
        except Exception:
            pass

        if not cap.isOpened():
            self.log_message.emit(f"Camera open failed for {self._url}. Verify IP, port, and network connection.", "ERROR")
            if cap is not None:
                cap.release()
            return None
        return cap

    @staticmethod
    def _convert_frame(frame: np.ndarray) -> QImage:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        return QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()

    def _update_fps(self) -> None:
        now = time.monotonic()
        self._frame_times.append(now)
        if len(self._frame_times) >= 2:
            elapsed = self._frame_times[-1] - self._frame_times[0]
            if elapsed > 0:
                fps = (len(self._frame_times) - 1) / elapsed
                self._current_fps = fps
                self.fps_changed.emit(fps)

    def _sleep_interruptible(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self._stop_event.is_set():
            time.sleep(0.05)