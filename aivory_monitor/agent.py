"""Main AIVory Monitor agent."""

from __future__ import annotations

import atexit
import signal
import sys
from typing import TYPE_CHECKING

from .config import AgentConfig
from .exceptions.handler import ExceptionHandler
from .tracer.trace_manager import TraceManager
from .transport.connection import BackendConnection

if TYPE_CHECKING:
    pass


class AIVoryAgent:
    """Main agent that coordinates all monitoring components."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._started = False

        # Initialize components
        self._connection = BackendConnection(config)
        self._exception_handler = ExceptionHandler(config, self._connection)
        self._trace_manager = TraceManager(config, self._connection) if config.enable_breakpoints else None

    def start(self) -> None:
        """Start the agent and all its components."""
        if self._started:
            return

        # Connect to backend
        self._connection.connect()

        # Install exception handlers
        self._exception_handler.install()

        # Enable tracing for breakpoints
        if self._trace_manager:
            self._trace_manager.enable()

        # Register cleanup handlers
        atexit.register(self._cleanup)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self._started = True

        if self.config.debug:
            print('[AIVory Monitor] Agent started')

    def stop(self) -> None:
        """Stop the agent and cleanup all resources."""
        if not self._started:
            return

        self._cleanup()
        self._started = False

    def capture_exception(
        self,
        exception: BaseException,
        context: dict | None = None,
    ) -> None:
        """Manually capture an exception."""
        if not self._started:
            return

        self._exception_handler.capture(exception, context)

    def _cleanup(self) -> None:
        """Cleanup all resources."""
        if self._trace_manager:
            self._trace_manager.disable()

        self._exception_handler.uninstall()
        self._connection.disconnect()

        if self.config.debug:
            print('[AIVory Monitor] Agent stopped')

    def _signal_handler(self, signum: int, frame: object) -> None:
        """Handle shutdown signals."""
        self.stop()
        sys.exit(0)
