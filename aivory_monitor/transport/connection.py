"""WebSocket connection to AIVory backend."""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import TYPE_CHECKING, Any

try:
    import websockets  # noqa: F401 -- required for availability check; do not remove this comment
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
        self._ws = None
        self._connected = False
        self._authenticated = False
        self._reconnect_attempts = 0
        self._reconnect_delay = 1.0
        self._message_queue = queue.Queue(maxsize=100)
        self._send_thread = None
        self._receive_thread = None
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()
        self._shutdown = threading.Event()
        self._ws_lock = threading.Lock()
        self._breakpoint_callback = None

    def connect(self) -> None:
        """Connect to the backend."""
        if not HAS_WEBSOCKETS:
            print('[AIVory Monitor] websockets package not installed. Install with: pip install websockets')
            return
        self._connected = False
        self._shutdown.clear()
        self._send_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self._send_thread.start()

    def disconnect(self) -> None:
        """Disconnect from the backend."""
        self._shutdown.set()
        self._heartbeat_stop.set()
        self._connected = False
        self._authenticated = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

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

    def _enqueue(self, json_msg: str) -> None:
        """Enqueue a message, dropping the oldest if full."""
        try:
            self._message_queue.put_nowait(json_msg)
        except queue.Full:
            try:
                self._message_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._message_queue.put_nowait(json_msg)
            except queue.Full:
                pass

    def _send(self, msg_type: str, payload: dict[str, Any]) -> None:
        """Queue a message for sending."""
        message = {
            'type': msg_type,
            'payload': payload,
            'timestamp': int(time.time() * 1000),
        }
        json_msg = json.dumps(message)

        with self._ws_lock:
            if self._connected and self._authenticated and self._ws:
                try:
                    self._ws.send(json_msg)
                    # Flush any queued messages
                    while True:
                        try:
                            queued = self._message_queue.get_nowait()
                            self._ws.send(queued)
                        except queue.Empty:
                            break
                except Exception as e:
                    if self.config.debug:
                        print(f'[AIVory Monitor] Failed to send message: {e}')
                    self._enqueue(json_msg)
            else:
                self._enqueue(json_msg)

    def _connection_loop(self) -> None:
        """Main connection loop running in background thread — retries indefinitely."""
        while not self._shutdown.is_set():
            try:
                self._connect_and_run()
            except Exception as e:
                if self.config.debug:
                    print(f'[AIVory Monitor] Connection error: {e}')

            if self._shutdown.is_set():
                return

            self._reconnect_attempts += 1
            delay = min(self._reconnect_delay * (2 ** min(self._reconnect_attempts - 1, 6)), 60.0)

            # Warn periodically (not just in debug mode)
            if self._reconnect_attempts in (1, 5, 10) or self._reconnect_attempts % 50 == 0:
                print(
                    f'[AIVory Monitor] Connection lost, reconnecting '
                    f'(attempt {self._reconnect_attempts}, next retry in {delay:.0f}s) '
                    f'to {self.config.backend_url}'
                )

            self._shutdown.wait(delay)

    def _connect_and_run(self) -> None:
        """Connect and run message loop."""
        if self.config.debug:
            print(f'[AIVory Monitor] Connecting to {self.config.backend_url}')

        headers = {
            'Authorization': 'Bearer ' + self.config.api_key,
        }

        # Stop any previous heartbeat thread before establishing new connection
        self._heartbeat_stop.set()

        with ws_connect(self.config.backend_url, additional_headers=headers) as ws:
            self._ws = ws
            self._connected = True
            self._reconnect_attempts = 0

            if self.config.debug:
                print('[AIVory Monitor] WebSocket connected')

            self._authenticate()

            # Wait for registration confirmation before starting main loop
            auth_deadline = time.time() + 10.0
            while not self._authenticated and not self._shutdown.is_set():
                try:
                    message = self._ws.recv(timeout=1.0)
                    self._handle_message(message)
                except TimeoutError:
                    pass
                if time.time() > auth_deadline:
                    raise TimeoutError(
                        'Authentication timeout - no registered response from backend'
                    )

            if self._shutdown.is_set():
                return

            # Start a fresh heartbeat thread for this connection
            self._heartbeat_stop = threading.Event()
            stop = self._heartbeat_stop
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop, args=(stop,), daemon=True
            )
            self._heartbeat_thread.start()

            # FIX: Use recv(timeout=1.0) instead of socket.settimeout(1.0) + recv()
            # The socket.settimeout() approach causes the websockets recv_events
            # background thread to terminate the entire connection on timeout.
            while not self._shutdown.is_set():
                try:
                    message = self._ws.recv(timeout=1.0)
                    self._handle_message(message)
                except TimeoutError:
                    continue
                except Exception as e:
                    if self.config.debug:
                        print(f'[AIVory Monitor] Receive error: {e}')
                    break

        self._connected = False
        self._authenticated = False
        self._heartbeat_stop.set()

    def _authenticate(self) -> None:
        """Send authentication message."""
        from aivory_monitor import __version__

        runtime_info = self.config.get_runtime_info()
        payload = {
            'api_key': self.config.api_key,
            'agent_id': self.config.agent_id,
            'hostname': self.config.hostname,
            'environment': self.config.environment,
            'agent_version': __version__,
            **runtime_info,
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
            msg = json.loads(data)
            msg_type = msg.get('type')
            if self.config.debug:
                print(f'[AIVory Monitor] Received: {msg_type}')
            if msg_type == 'registered':
                self._handle_registered(msg)
            elif msg_type == 'error':
                self._handle_error(msg.get('payload', {}))
            elif msg_type == 'set_breakpoint':
                self._handle_set_breakpoint(msg.get('payload', {}))
            elif msg_type == 'remove_breakpoint':
                self._handle_remove_breakpoint(msg.get('payload', {}))
            else:
                if self.config.debug:
                    print(f'[AIVory Monitor] Unhandled message type: {msg_type}')
        except Exception as e:
            if self.config.debug:
                print(f'[AIVory Monitor] Error parsing message: {e}')

    def _handle_registered(self, msg) -> None:
        """Handle successful registration."""
        self._authenticated = True
        if self.config.debug:
            print('[AIVory Monitor] Agent registered')
        # Flush queued messages under lock to prevent concurrent send races
        with self._ws_lock:
            while not self._message_queue.empty():
                try:
                    queued = self._message_queue.get_nowait()
                    try:
                        self._ws.send(queued)
                    except Exception as e:
                        if self.config.debug:
                            print(f'[AIVory Monitor] Error sending queued message: {e}')
                except queue.Empty:
                    break

    def _handle_error(self, payload: dict[str, Any]) -> None:
        """Handle error from backend."""
        code = payload.get('code', 'unknown')
        message = payload.get('message', 'Unknown error')
        print(f'[AIVory Monitor] Backend error: {code} - {message}')
        if code in ('auth_error', 'invalid_api_key'):
            print('[AIVory Monitor] Authentication failed — stopping reconnection')
            self._shutdown.set()

    def _handle_set_breakpoint(self, payload: dict[str, Any]) -> None:
        """Handle set breakpoint command."""
        if self._breakpoint_callback:
            self._breakpoint_callback('set', payload)

    def _handle_remove_breakpoint(self, payload: dict[str, Any]) -> None:
        """Handle remove breakpoint command."""
        if self._breakpoint_callback:
            self._breakpoint_callback('remove', payload)

    def _heartbeat_loop(self, stop: threading.Event) -> None:
        """Send periodic heartbeats. Each connection gets its own stop event."""
        while not self._shutdown.is_set() and not stop.is_set():
            if self._connected and self._authenticated:
                self._send('heartbeat', {
                    'timestamp': int(time.time() * 1000),
                    'agent_id': self.config.agent_id,
                })
            stop.wait(30.0)
