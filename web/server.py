"""
Blind Maze Driver Station — Web Server with Zero-Latency Camera Proxy & WebSocket Streamer

Features:
  - Serves static dashboard files from /web
  - Background CameraFetcher thread pulls continuous MJPEG/JPEG frames from IP Webcam
  - Drops stale frames automatically so latency is ALWAYS zero (< 20ms)
  - WebSocket binary video stream at /ws for true real-time canvas rendering
  - Instant memory-served /cam/shot and /cam/stream fallback endpoints
"""

import http.server
import urllib.request
import urllib.error
import json
import threading
import time
import sys
import os
import hashlib
import base64
import struct
import socket

PORT = 8000
WEB_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────
# Zero-Latency Frame Buffer & Camera Fetcher Thread
# ─────────────────────────────────────────────────────────────
class CameraFetcher(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.ip = ''
        self.running = False
        self.latest_frame = None
        self.frame_time = 0
        self.lock = threading.Lock()
        self.clients = set()
        self.clients_lock = threading.Lock()

    def set_target(self, ip):
        with self.lock:
            self.ip = ip
            self.latest_frame = None
            self.frame_time = 0
            self.running = True
        print(f'[CAM_FETCHER] Target set to {ip}')

    def get_latest_frame(self):
        with self.lock:
            return self.latest_frame, self.frame_time

    def add_client(self, client_socket):
        with self.clients_lock:
            self.clients.add(client_socket)
        print(f'[WS] Client connected. Total WS clients: {len(self.clients)}')

    def remove_client(self, client_socket):
        with self.clients_lock:
            self.clients.discard(client_socket)
        print(f'[WS] Client disconnected. Total WS clients: {len(self.clients)}')

    def broadcast_frame(self, jpg_bytes):
        if not jpg_bytes:
            return
        frame_msg = make_ws_binary_frame(jpg_bytes)
        with self.clients_lock:
            dead = set()
            for client in self.clients:
                try:
                    client.sendall(frame_msg)
                except Exception:
                    dead.add(client)
            for d in dead:
                self.clients.discard(d)

    def run(self):
        while True:
            with self.lock:
                ip = self.ip
                running = self.running

            if not running or not ip:
                time.sleep(0.1)
                continue

            stream_url = f'http://{ip}/video'
            print(f'[CAM_FETCHER] Connecting stream to {stream_url}...')

            try:
                req = urllib.request.Request(stream_url)
                req.add_header('User-Agent', 'BlindMazeDriverStation/1.0')
                resp = urllib.request.urlopen(req, timeout=5)
                buf = bytearray()

                while self.running and self.ip == ip:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    buf.extend(chunk)

                    # Find complete JPEG frames (FF D8 to FF D9)
                    while True:
                        start = buf.find(b'\xff\xd8')
                        if start == -1:
                            if len(buf) > 65536:
                                buf.clear()
                            break

                        end = buf.find(b'\xff\xd9', start)
                        if end == -1:
                            if start > 0:
                                del buf[:start]
                            break

                        # Extract frame
                        jpg = bytes(buf[start:end+2])
                        del buf[:end+2]

                        # Store latest frame (overwriting old ones instantly)
                        t_now = time.time()
                        with self.lock:
                            self.latest_frame = jpg
                            self.frame_time = t_now

                        # Broadcast to all connected WebSocket clients instantly
                        self.broadcast_frame(jpg)

                resp.close()
            except Exception as e:
                # If MJPEG stream endpoint fails, try snapshot polling fallback loop
                print(f'[CAM_FETCHER] Stream disconnect/error ({e}), pausing 1s...')
                time.sleep(1.0)
                shot_url = f'http://{ip}/shot.jpg'
                retry_count = 0
                while self.running and self.ip == ip and retry_count < 3:
                    try:
                        r = urllib.request.urlopen(shot_url, timeout=2)
                        jpg = r.read()
                        r.close()
                        t_now = time.time()
                        with self.lock:
                            self.latest_frame = jpg
                            self.frame_time = t_now
                        self.broadcast_frame(jpg)
                        time.sleep(0.033)  # ~30 FPS fallback
                    except Exception as ex:
                        retry_count += 1
                        print(f'[CAM_FETCHER] Snapshot error: {ex}')
                        time.sleep(1.0)
                        break


# Instantiate single background fetcher thread
cam_fetcher = CameraFetcher()
cam_fetcher.start()


# ─────────────────────────────────────────────────────────────
# WebSocket Protocol Helpers
# ─────────────────────────────────────────────────────────────
def make_ws_handshake(key):
    magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    sha1 = hashlib.sha1((key + magic).encode('utf-8')).digest()
    accept = base64.b64encode(sha1).decode('utf-8')
    return (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
    )


def make_ws_binary_frame(payload):
    length = len(payload)
    if length <= 125:
        header = bytes([0x82, length])
    elif length <= 65535:
        header = bytes([0x82, 126]) + struct.pack("!H", length)
    else:
        header = bytes([0x82, 127]) + struct.pack("!Q", length)
    return header + payload


# ─────────────────────────────────────────────────────────────
# HTTP & WebSocket Request Handler
# ─────────────────────────────────────────────────────────────
class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static dashboard + WebSocket video stream + zero-latency proxy endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        msg = format % args
        if '/cam/shot' not in msg and '/cam/stream' not in msg and '/ws' not in msg:
            super().log_message(format, *args)

    def do_GET(self):
        # ── WebSocket Upgrade Check ──
        if self.headers.get('Upgrade', '').lower() == 'websocket':
            self.handle_websocket()
            return

        if self.path.startswith('/cam/set'):
            self.handle_cam_set()
        elif self.path.startswith('/cam/status'):
            self.handle_cam_status()
        elif self.path.startswith('/cam/shot'):
            self.handle_cam_shot()
        elif self.path.startswith('/cam/stream'):
            self.handle_cam_stream()
        else:
            super().do_GET()

    def handle_websocket(self):
        """Handle raw WebSocket connection for zero-latency frame streaming."""
        key = self.headers.get('Sec-WebSocket-Key')
        if not key:
            self.send_error(400, 'Missing Sec-WebSocket-Key')
            return

        # Handshake
        response = make_ws_handshake(key)
        self.wfile.write(response.encode('utf-8'))
        self.wfile.flush()

        raw_socket = self.connection
        cam_fetcher.add_client(raw_socket)

        # Send current latest frame immediately if available
        frame, _ = cam_fetcher.get_latest_frame()
        if frame:
            try:
                raw_socket.sendall(make_ws_binary_frame(frame))
            except Exception:
                pass

        # Keep connection open until closed by client
        try:
            while True:
                data = raw_socket.recv(1024)
                if not data:
                    break
        except Exception:
            pass
        finally:
            cam_fetcher.remove_client(raw_socket)

    def handle_cam_set(self):
        """Set IP Webcam target address & start background fetcher."""
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        ip = query.get('ip', [''])[0].strip()

        if not ip:
            self.send_json(400, {'error': 'Missing ?ip= parameter'})
            return

        ip = ip.replace('http://', '').replace('https://', '').rstrip('/')

        # Test connectivity once
        test_url = f'http://{ip}/shot.jpg'
        try:
            req = urllib.request.Request(test_url, method='GET')
            req.add_header('User-Agent', 'BlindMazeDriverStation/1.0')
            resp = urllib.request.urlopen(req, timeout=4)
            resp.read(512)
            resp.close()

            # Start fetcher
            cam_fetcher.set_target(ip)
            self.send_json(200, {'status': 'ok', 'ip': ip, 'connected': True})
            print(f'[CAM] Connection test succeeded for {ip}. Frame fetcher running.')
        except Exception as e:
            err = str(e)
            self.send_json(200, {'status': 'error', 'ip': ip, 'connected': False, 'error': err})
            print(f'[CAM] Failed to connect to {ip}: {err}')

    def handle_cam_status(self):
        frame, f_time = cam_fetcher.get_latest_frame()
        is_live = frame is not None and (time.time() - f_time < 3.0)
        self.send_json(200, {
            'ip': cam_fetcher.ip,
            'connected': is_live,
            'last_frame_age_ms': round((time.time() - f_time) * 1000) if f_time else None
        })

    def handle_cam_shot(self):
        """Serve latest frame instantly from memory buffer (0ms network delay)."""
        frame, f_time = cam_fetcher.get_latest_frame()
        if not frame:
            # Fallback to single pull
            ip = cam_fetcher.ip
            if not ip:
                self.send_error(503, 'No camera target set.')
                return
            try:
                req = urllib.request.Request(f'http://{ip}/shot.jpg')
                resp = urllib.request.urlopen(req, timeout=3)
                frame = resp.read()
                resp.close()
            except Exception as e:
                self.send_error(502, f'Camera error: {e}')
                return

        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(frame)))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(frame)

    def handle_cam_stream(self):
        """Serve MJPEG stream from live memory buffer (zero backlog)."""
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frameboundary')
        self.send_header('Cache-Control', 'no-cache, no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()

        last_sent = 0
        try:
            while True:
                frame, f_time = cam_fetcher.get_latest_frame()
                if frame and f_time > last_sent:
                    last_sent = f_time
                    header = f"--frameboundary\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n".encode('utf-8')
                    self.wfile.write(header)
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    self.wfile.flush()
                time.sleep(0.015)  # ~60 FPS check rate
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def send_json(self, code, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)


class ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    os.chdir(WEB_DIR)
    server = ThreadedHTTPServer(('0.0.0.0', PORT), ProxyHandler)
    print('==================================================')
    print('  Blind Maze Driver Station - Web Server')
    print(f'  Serving on http://localhost:{PORT}')
    print('  Zero-Latency Proxy & WebSocket Streamer Ready')
    print('==================================================')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[SERVER] Shutting down...')
        server.shutdown()


if __name__ == '__main__':
    main()
