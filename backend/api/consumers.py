"""
WebSocket consumer for real-time CV feed - METADATA ONLY.
No base64 frames sent via WebSocket.
"""
import json
import time
import logging
import threading
from queue import Queue

from channels.generic.websocket import WebsocketConsumer

logger = logging.getLogger(__name__)


class CVFeedConsumer(WebsocketConsumer):
    _instances = set()
    _lock = threading.Lock()

    def connect(self):
        self.accept()
        with self._lock:
            self._instances.add(self)
        self._meta_queue = Queue(maxsize=2)
        self._running = True
        self._last_sent = 0.0
        self._sender_thread = threading.Thread(target=self._send_loop, daemon=True)
        self._sender_thread.start()
        logger.info('WebSocket connected (%d total)', len(self._instances))

        # Do NOT auto-start engine on connect. Start only via explicit command.

    def disconnect(self, close_code):
        self._running = False
        with self._lock:
            self._instances.discard(self)
        logger.info('WebSocket disconnected (%d total)', len(self._instances))

    def receive(self, text_data=None, bytes_data=None):
        if text_data:
            try:
                data = json.loads(text_data)
                command = data.get('command', '')
                if command == 'start':
                    from api.apps import start_engine
                    from api.mjpeg_server import get_mjpeg_port
                    start_engine()
                    self.send(text_data=json.dumps({
                        'type': 'status',
                        'message': 'Engine started',
                        'mjpeg_port': get_mjpeg_port(),
                    }))
                elif command == 'stop':
                    from api.apps import stop_engine
                    stop_engine()
                    self.send(text_data=json.dumps({'type': 'status', 'message': 'Engine stopped'}))
                elif command == 'reload_embeddings':
                    from api.apps import get_engine
                    get_engine().reload_embeddings()
                    self.send(text_data=json.dumps({'type': 'status', 'message': 'Embeddings reloaded'}))
            except json.JSONDecodeError:
                pass
            except Exception as e:
                self.send(text_data=json.dumps({'type': 'error', 'message': str(e)}))

    def enqueue_metadata(self, meta_data: dict):
        if self._meta_queue.full():
            try:
                self._meta_queue.get_nowait()
            except Exception:
                pass
        try:
            self._meta_queue.put_nowait(meta_data)
        except Exception:
            pass

    def _send_loop(self):
        while self._running:
            try:
                data = self._meta_queue.get(timeout=0.5)
            except Exception:
                continue

            try:
                payload = json.dumps({
                    'type': 'tracks',
                    'tracks': data.get('tracks', []),
                    'fps': data.get('fps', 0),
                    'frame_number': data.get('frame_number', 0),
                })
                self.send(text_data=payload)
                self._last_sent = time.time()
            except Exception:
                break

    @classmethod
    def broadcast(cls, frame_data: dict):
        with cls._lock:
            for consumer in cls._instances.copy():
                try:
                    consumer.enqueue_metadata(frame_data)
                except Exception:
                    pass

    @classmethod
    def broadcast_attendance(cls, event: dict):
        """Send attendance event directly to all clients (not queued — instant)."""
        payload = json.dumps({
            'type': 'attendance',
            'person_name': event.get('person_name', 'Unknown'),
            'action': event.get('action', 'entry'),
            'confidence': event.get('confidence', 0),
            'person_id': event.get('person_id'),
        })
        with cls._lock:
            for consumer in cls._instances.copy():
                try:
                    consumer.send(text_data=payload)
                except Exception:
                    pass
