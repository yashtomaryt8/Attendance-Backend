"""
Tiny dedicated MJPEG server on port 8765.
Spawned by apps.py when the CV engine starts.
Bypass Daphne's ASGI response-buffering which prevents StreamingHttpResponse
from flushing MJPEG frames to the browser.
"""
import threading
import logging
import socket

from http.server import BaseHTTPRequestHandler, HTTPServer  # stdlib only

logger = logging.getLogger(__name__)


class _ReuseAddrHTTPServer(HTTPServer):
    """HTTPServer with SO_REUSEADDR so it can rebind after restart.
    Without this, Windows holds the port in TIME_WAIT and the next
    start.bat fails with 'address in use' (silently)."""
    allow_reuse_address = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


def _build_handler(get_frame_fn):
    """Return a handler class that serves MJPEG from get_frame_fn()."""

    class MJPEGHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Suppress access-log noise

        def do_GET(self):
            # Accept any path (including /feed, /api/engine/feed, etc.)
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            import time
            import cv2
            import numpy as np

            # 1×1 grey placeholder while camera warms up
            placeholder = np.full((2, 2, 3), 128, dtype=np.uint8)
            _, pbuf = cv2.imencode('.jpg', placeholder)
            placeholder_bytes = pbuf.tobytes()

            try:
                while True:
                    frame = get_frame_fn() or placeholder_bytes
                    header = (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n'
                        b'Content-Length: ' + str(len(frame)).encode() + b'\r\n'
                        b'\r\n'
                    )
                    self.wfile.write(header + frame + b'\r\n')
                    self.wfile.flush()
                    time.sleep(0.033)  # ~30 fps
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                logger.debug(f'MJPEG handler error: {e}')

    return MJPEGHandler


_mjpeg_server = None
_mjpeg_lock = threading.Lock()
_mjpeg_port = None  # Tracks the actual port the server bound to


def get_mjpeg_port():
    """Return the port the MJPEG server is listening on (or None if not started)."""
    return _mjpeg_port


def start_mjpeg_server(engine, port: int = 8765):
    """Start the MJPEG server in a daemon thread. Safe to call multiple times.
    Tries ports 8765-8774 until one is available (handles Windows TIME_WAIT)."""
    global _mjpeg_server, _mjpeg_port

    with _mjpeg_lock:
        if _mjpeg_server is not None:
            return  # Already running

        handler = _build_handler(lambda: engine.latest_annotated_frame)

        for try_port in range(port, port + 10):
            try:
                server = _ReuseAddrHTTPServer(('0.0.0.0', try_port), handler)
                _mjpeg_server = server
                _mjpeg_port = try_port
                t = threading.Thread(target=server.serve_forever, daemon=True, name='MJPEGServer')
                t.start()
                logger.info(f'MJPEG server started on port {try_port}')
                print(f'[MJPEG] Server started on port {try_port}', flush=True)
                return
            except OSError as e:
                logger.warning(f'MJPEG server could not bind port {try_port}: {e}')
                print(f'[MJPEG] Port {try_port} unavailable ({e}), trying next...', flush=True)

        logger.error(f'MJPEG server could not start on any port {port}-{port+9}')
        print(f'[MJPEG] ERROR: could not bind any port in range {port}-{port+9}', flush=True)


def stop_mjpeg_server():
    global _mjpeg_server, _mjpeg_port
    with _mjpeg_lock:
        if _mjpeg_server:
            _mjpeg_server.shutdown()
            _mjpeg_server = None
            _mjpeg_port = None
