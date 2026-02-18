"""WebSocket connection to AIVory backend."""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import TYPE_CHECKING, Any

try:
    import websockets  # noqa: F401
    from websockets.sync.client import connect as ws_connect
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

if TYPE_CHECKING:
    from ..config import AgentConfig
    from ..exceptions.capture import ExceptionCapture


class BackendConnection:
    """WebSocket connection to AIVory backend."""

    def __init__(self, config: 'AgentConfig') -> None:
        self.config = config
        self._ws: Any = None
        self._connected = False
        self._authenticated = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._reconnect_delay = 1.0
        self._message_queue: queue.Queue[str] = queue.Queue(maxsize=100)
        self._send_thread: threading.Thread | None = None
        self._receive_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._shutdown = threading.Event()
        self._breakpoint_callback: Any = None

    def connect(self) -> None:
        """Connect to the backend."""
        if not HAS_WEBSOCKETS:
            print('[AIVory Monitor] websockets package not installed. Install with: pip install websockets')
            return

        if self._connected:
            return

        self._shutdown.clear()

        # Start connection in background thread
        self._send_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self._send_thread.start()

    def disconnect(self) -> None:
        """Disconnect from the backend."""
        self._shutdown.set()
        self._connected = False
        self._authenticated = False

        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def send_exception(self, capture: 'ExceptionCapture') -> None:
        """Send an exception capture to the backend."""
        payload = {
            **capture.to_dict(),
            'agent_id': self.config.agent_id,
            'environment': self.config.environment,
            **self.config.get_runtime_info(),
        }

        self._send('exception', payload)

    def send_breakpoint_hit(self, breakpoint_id: str, data: dict[str, Any]) -> None:
        """Send a breakpoint hit notification."""
        self._send('breakpoint_hit', {
            'breakpoint_id': breakpoint_id,
            'agent_id': self.config.agent_id,
            **data,
        })

    def set_breakpoint_callback(self, callback: Any) -> None:
        """Set callback for breakpoint commands from backend."""
        self._breakpoint_callback = callback

    def is_connected(self) -> bool:
        """Check if connected and authenticated."""
        return self._connected and self._authenticated

    def _send(self, msg_type: str, payload: dict[str, Any]) -> None:
        """Queue a message for sending."""
        message = {
            'type': msg_type,
            'payload': payload,
            'timestamp': int(time.time() * 1000),
        }

        json_msg = json.dumps(message)

        if self._connected and self._authenticated and self._ws:
            try:
                self._ws.send(json_msg)
            except Exception as e:
                if self.config.debug:
                    print(f'[AIVory Monitor] Failed to send message: {e}')
                # Queue for later
                try:
                    self._message_queue.put_nowait(json_msg)
                except queue.Full:
                    # Drop oldest message
                    try:
                        self._message_queue.get_nowait()
                        self._message_queue.put_nowait(json_msg)
                    except queue.Empty:
                        pass
        else:
            # Queue for later
            try:
                self._message_queue.put_nowait(json_msg)
            except queue.Full:
                try:
                    self._message_queue.get_nowait()
                    self._message_queue.put_nowait(json_msg)
                except queue.Empty:
                    pass

    def _connection_loop(self) -> None:
        """Main connection loop running in background thread."""
        while not self._shutdown.is_set():
            try:
                self._connect_and_run()
            except Exception as e:
                if self.config.debug:
                    print(f'[AIVory Monitor] Connection error: {e}')

            if self._shutdown.is_set():
                break

            # Reconnect with exponential backoff
            self._reconnect_attempts += 1
            if self._reconnect_attempts > self._max_reconnect_attempts:
                print('[AIVory Monitor] Max reconnect attempts reached')
                break

            delay = min(self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)), 60.0)
            if self.config.debug:
                print(f'[AIVory Monitor] Reconnecting in {delay}s (attempt {self._reconnect_attempts})')

            self._shutdown.wait(delay)

    def _connect_and_run(self) -> None:
        """Connect and run message loop."""
        if self.config.debug:
            print(f'[AIVory Monitor] Connecting to {self.config.backend_url}')

        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
        }

        self._ws = ws_connect(
            self.config.backend_url,
            additional_headers=headers,
        )

        self._connected = True
        self._reconnect_attempts = 0

        if self.config.debug:
            print('[AIVory Monitor] WebSocket connected')

        # Authenticate
        self._authenticate()

        # Start heartbeat
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        # Message receive loop
        try:
            while not self._shutdown.is_set() and self._connected:
                try:
                    self._ws.socket.settimeout(1.0)
                    message = self._ws.recv()
                    self._handle_message(message)
                except TimeoutError:
                    continue
                except Exception as e:
                    if not self._shutdown.is_set():
                        if self.config.debug:
                            print(f'[AIVory Monitor] Receive error: {e}')
                    break
        finally:
            self._connected = False
            self._authenticated = False

    def _authenticate(self) -> None:
        """Send authentication message."""
        payload = {
            'api_key': self.config.api_key,
            'agent_id': self.config.agent_id,
            'hostname': self.config.hostname,
            'environment': self.config.environment,
            'agent_version': '1.0.0',
            **self.config.get_runtime_info(),
        }

        message = {
            'type': 'register',
            'payload': payload,
            'timestamp': int(time.time() * 1000),
        }

        self._ws.send(json.dumps(message))

    def _handle_message(self, data: str) -> None:
        """Handle incoming message from backend."""
        try:
            message = json.loads(data)
            msg_type = message.get('type')

            if self.config.debug:
                print(f'[AIVory Monitor] Received: {msg_type}')

            if msg_type == 'registered':
                self._handle_registered()
            elif msg_type == 'error':
                self._handle_error(message.get('payload', {}))
            elif msg_type == 'set_breakpoint':
                self._handle_set_breakpoint(message.get('payload', {}))
            elif msg_type == 'remove_breakpoint':
                self._handle_remove_breakpoint(message.get('payload', {}))
            elif self.config.debug:
                print(f'[AIVory Monitor] Unhandled message type: {msg_type}')

        except json.JSONDecodeError as e:
            if self.config.debug:
                print(f'[AIVory Monitor] Error parsing message: {e}')

    def _handle_registered(self) -> None:
        """Handle successful registration."""
        self._authenticated = True

        if self.config.debug:
            print('[AIVory Monitor] Agent registered')

        # Send queued messages
        while not self._message_queue.empty():
            try:
                msg = self._message_queue.get_nowait()
                if self._ws and self._connected:
                    self._ws.send(msg)
            except queue.Empty:
                break
            except Exception as e:
                if self.config.debug:
                    print(f'[AIVory Monitor] Error sending queued message: {e}')

    def _handle_error(self, payload: dict[str, Any]) -> None:
        """Handle error from backend."""
        code = payload.get('code', 'unknown')
        message = payload.get('message', 'Unknown error')

        print(f'[AIVory Monitor] Backend error: {code} - {message}')

        if code in ('auth_error', 'invalid_api_key'):
            print('[AIVory Monitor] Authentication failed, disabling reconnect')
            self._max_reconnect_attempts = 0
            self.disconnect()

    def _handle_set_breakpoint(self, payload: dict[str, Any]) -> None:
        """Handle set breakpoint command."""
        if self._breakpoint_callback:
            self._breakpoint_callback('set', payload)

    def _handle_remove_breakpoint(self, payload: dict[str, Any]) -> None:
        """Handle remove breakpoint command."""
        if self._breakpoint_callback:
            self._breakpoint_callback('remove', payload)

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while not self._shutdown.is_set() and self._connected:
            if self._authenticated:
                self._send('heartbeat', {
                    'timestamp': int(time.time() * 1000),
                    'agent_id': self.config.agent_id,
                })

            # Wait 30 seconds between heartbeats
            self._shutdown.wait(30.0)
