"""Exception handler installation and management."""

from __future__ import annotations

import sys
from types import TracebackType
from typing import TYPE_CHECKING, Callable

from .capture import ExceptionCaptureBuilder

if TYPE_CHECKING:
    from ..config import AgentConfig
    from ..transport.connection import BackendConnection


ExceptHookType = Callable[[type[BaseException], BaseException, TracebackType | None], None]


class ExceptionHandler:
    """Handles exception capture and reporting."""

    def __init__(self, config: 'AgentConfig', connection: 'BackendConnection') -> None:
        self.config = config
        self.connection = connection
        self._capture_builder = ExceptionCaptureBuilder(config)
        self._installed = False
        self._original_excepthook: ExceptHookType | None = None
        self._original_unraisablehook: Callable | None = None

    def install(self) -> None:
        """Install exception hooks."""
        if self._installed:
            return

        # Save original hooks
        self._original_excepthook = sys.excepthook
        if hasattr(sys, 'unraisablehook'):
            self._original_unraisablehook = sys.unraisablehook

        # Install our hooks
        sys.excepthook = self._excepthook
        if hasattr(sys, 'unraisablehook'):
            sys.unraisablehook = self._unraisablehook

        self._installed = True

        if self.config.debug:
            print('[AIVory Monitor] Exception handlers installed')

    def uninstall(self) -> None:
        """Uninstall exception hooks."""
        if not self._installed:
            return

        # Restore original hooks
        if self._original_excepthook:
            sys.excepthook = self._original_excepthook

        if self._original_unraisablehook and hasattr(sys, 'unraisablehook'):
            sys.unraisablehook = self._original_unraisablehook

        self._installed = False

    def capture(
        self,
        exception: BaseException,
        context: dict | None = None,
    ) -> None:
        """Manually capture an exception."""
        if not self.config.should_sample():
            return

        # Get the frame where the exception occurred
        frame = None
        tb = exception.__traceback__
        while tb is not None:
            frame = tb.tb_frame
            tb = tb.tb_next

        capture = self._capture_builder.capture(exception, context, frame)
        self.connection.send_exception(capture)

    def _excepthook(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        """Handle uncaught exceptions."""
        try:
            if self.config.should_sample():
                # Create exception with traceback attached
                if exc_tb is not None:
                    exc_value.__traceback__ = exc_tb

                frame = None
                tb = exc_tb
                while tb is not None:
                    frame = tb.tb_frame
                    tb = tb.tb_next

                capture = self._capture_builder.capture(
                    exc_value,
                    context={'origin': 'uncaught'},
                    frame=frame,
                )
                self.connection.send_exception(capture)
        except Exception as e:
            if self.config.debug:
                print(f'[AIVory Monitor] Error capturing exception: {e}')

        # Call original hook
        if self._original_excepthook:
            self._original_excepthook(exc_type, exc_value, exc_tb)

    def _unraisablehook(self, unraisable: object) -> None:
        """Handle unraisable exceptions (e.g., in __del__)."""
        try:
            if self.config.should_sample() and hasattr(unraisable, 'exc_value'):
                exc_value = getattr(unraisable, 'exc_value')
                if exc_value is not None:
                    capture = self._capture_builder.capture(
                        exc_value,
                        context={
                            'origin': 'unraisable',
                            'err_msg': getattr(unraisable, 'err_msg', None),
                            'object': str(getattr(unraisable, 'object', None)),
                        },
                    )
                    self.connection.send_exception(capture)
        except Exception as e:
            if self.config.debug:
                print(f'[AIVory Monitor] Error capturing unraisable: {e}')

        # Call original hook
        if self._original_unraisablehook:
            self._original_unraisablehook(unraisable)
