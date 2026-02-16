"""Trace manager for breakpoint support using sys.settrace."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable

from ..exceptions.capture import CapturedVariable, ExceptionCaptureBuilder

if TYPE_CHECKING:
    from ..config import AgentConfig
    from ..transport.connection import BackendConnection


class Breakpoint:
    """Represents a single breakpoint."""

    def __init__(
        self,
        backend_id: str,
        file_path: str,
        line_number: int,
        condition: str | None = None,
        max_hits: int = 1,
    ) -> None:
        self.backend_id = backend_id
        self.file_path = file_path
        self.line_number = line_number
        self.condition = condition
        self.max_hits = max_hits  # Default: capture only once
        self.hit_count = 0

        # Normalize file path for comparison
        self.normalized_path = os.path.normpath(file_path).lower()


class TraceManager:
    """Manages tracing for breakpoint support."""

    def __init__(self, config: 'AgentConfig', connection: 'BackendConnection') -> None:
        self.config = config
        self.connection = connection
        self._enabled = False
        self._breakpoints: dict[str, Breakpoint] = {}
        self._breakpoints_by_file: dict[str, list[Breakpoint]] = {}
        self._capture_builder = ExceptionCaptureBuilder(config)
        self._original_trace: Callable | None = None

        # Register for breakpoint commands
        connection.set_breakpoint_callback(self._handle_breakpoint_command)

    def enable(self) -> None:
        """Enable tracing."""
        if self._enabled:
            return

        self._original_trace = sys.gettrace()
        sys.settrace(self._trace_callback)

        self._enabled = True

        if self.config.debug:
            print('[AIVory Monitor] Trace manager enabled')

    def disable(self) -> None:
        """Disable tracing."""
        if not self._enabled:
            return

        sys.settrace(self._original_trace)
        self._original_trace = None
        self._breakpoints.clear()
        self._breakpoints_by_file.clear()

        self._enabled = False

        if self.config.debug:
            print('[AIVory Monitor] Trace manager disabled')

    def set_breakpoint(
        self,
        backend_id: str,
        file_path: str,
        line_number: int,
        condition: str | None = None,
        max_hits: int = 1,
    ) -> None:
        """Set a breakpoint."""
        # Cap max_hits at 50
        max_hits = min(max(max_hits, 1), 50)
        breakpoint = Breakpoint(backend_id, file_path, line_number, condition, max_hits)
        self._breakpoints[backend_id] = breakpoint

        # Index by file for fast lookup
        if breakpoint.normalized_path not in self._breakpoints_by_file:
            self._breakpoints_by_file[breakpoint.normalized_path] = []
        self._breakpoints_by_file[breakpoint.normalized_path].append(breakpoint)

        if self.config.debug:
            print(f'[AIVory Monitor] Breakpoint set: {backend_id} at {file_path}:{line_number}')

    def remove_breakpoint(self, backend_id: str) -> None:
        """Remove a breakpoint."""
        breakpoint = self._breakpoints.pop(backend_id, None)
        if breakpoint:
            file_breakpoints = self._breakpoints_by_file.get(breakpoint.normalized_path, [])
            self._breakpoints_by_file[breakpoint.normalized_path] = [
                bp for bp in file_breakpoints if bp.backend_id != backend_id
            ]

            if self.config.debug:
                print(f'[AIVory Monitor] Breakpoint removed: {backend_id}')

    def _handle_breakpoint_command(self, command: str, payload: dict[str, Any]) -> None:
        """Handle breakpoint commands from backend."""
        if command == 'set':
            self.set_breakpoint(
                backend_id=payload.get('id', ''),
                file_path=payload.get('file_path', ''),
                line_number=payload.get('line_number', 0),
                condition=payload.get('condition'),
                max_hits=payload.get('max_hits', 1),
            )
        elif command == 'remove':
            self.remove_breakpoint(payload.get('id', ''))

    def _trace_callback(self, frame: FrameType, event: str, arg: Any) -> Callable | None:
        """Trace callback called for each line execution."""
        # Only interested in line events
        if event != 'line':
            return self._trace_callback

        # Skip if no breakpoints
        if not self._breakpoints_by_file:
            return self._trace_callback

        # Get normalized file path
        code = frame.f_code
        file_path = code.co_filename
        if not file_path:
            return self._trace_callback

        normalized_path = os.path.normpath(file_path).lower()

        # Check if we have breakpoints in this file
        # First try exact match, then suffix match (for relative paths in breakpoints)
        file_breakpoints = self._breakpoints_by_file.get(normalized_path)
        if not file_breakpoints:
            # Try suffix matching - breakpoint might have relative path
            for bp_path, bps in self._breakpoints_by_file.items():
                if normalized_path.endswith(bp_path) or bp_path.endswith(normalized_path):
                    file_breakpoints = bps
                    break
        if not file_breakpoints:
            return self._trace_callback

        # Check each breakpoint
        line_number = frame.f_lineno
        for breakpoint in file_breakpoints:
            if breakpoint.line_number == line_number:
                self._handle_breakpoint_hit(breakpoint, frame)

        return self._trace_callback

    def _handle_breakpoint_hit(self, breakpoint: Breakpoint, frame: FrameType) -> None:
        """Handle a breakpoint being hit."""
        # Check if max hits reached
        if breakpoint.hit_count >= breakpoint.max_hits:
            return

        # Check condition if present
        if breakpoint.condition:
            try:
                result = eval(breakpoint.condition, frame.f_globals, frame.f_locals)
                if not result:
                    return
            except Exception as e:
                if self.config.debug:
                    print(f'[AIVory Monitor] Condition eval error: {e}')
                return

        breakpoint.hit_count += 1

        if self.config.debug:
            print(f'[AIVory Monitor] Breakpoint hit: {breakpoint.backend_id}')

        # Capture local variables
        local_variables = self._capture_local_variables(frame)

        # Build stack trace
        stack_trace = self._build_stack_trace(frame)

        # Send to backend
        self.connection.send_breakpoint_hit(breakpoint.backend_id, {
            'captured_at': datetime.utcnow().isoformat() + 'Z',
            'file_path': breakpoint.file_path,
            'line_number': breakpoint.line_number,
            'stack_trace': stack_trace,
            'local_variables': {k: v.to_dict() for k, v in local_variables.items()},
            'hit_count': breakpoint.hit_count,
        })

    def _capture_local_variables(self, frame: FrameType) -> dict[str, CapturedVariable]:
        """Capture local variables from frame."""
        variables: dict[str, CapturedVariable] = {}

        for name, value in frame.f_locals.items():
            if name.startswith('_'):
                continue

            try:
                captured = self._capture_value(name, value, depth=0)
                if captured:
                    variables[name] = captured
            except Exception:
                pass

        return variables

    def _capture_value(
        self,
        name: str,
        value: Any,
        depth: int,
    ) -> CapturedVariable | None:
        """Recursively capture a value."""
        if depth > self.config.max_capture_depth:
            return CapturedVariable(
                name=name,
                type=type(value).__name__,
                value='<max depth exceeded>',
                is_truncated=True,
            )

        if value is None:
            return CapturedVariable(
                name=name,
                type='NoneType',
                value='None',
                is_null=True,
            )

        type_name = type(value).__name__

        # Primitive types
        if isinstance(value, (bool, int, float)):
            return CapturedVariable(
                name=name,
                type=type_name,
                value=str(value),
            )

        if isinstance(value, str):
            truncated = len(value) > self.config.max_string_length
            display_value = value[:self.config.max_string_length] if truncated else value
            return CapturedVariable(
                name=name,
                type='str',
                value=display_value,
                is_truncated=truncated,
            )

        if isinstance(value, bytes):
            truncated = len(value) > self.config.max_string_length
            display_value = value[:self.config.max_string_length].hex() if truncated else value.hex()
            return CapturedVariable(
                name=name,
                type='bytes',
                value=display_value,
                is_truncated=truncated,
            )

        # Collections
        if isinstance(value, (list, tuple)):
            elements: list[CapturedVariable] = []
            total_length = len(value)

            for i, item in enumerate(value):
                if i >= self.config.max_collection_size:
                    break
                captured = self._capture_value(f'[{i}]', item, depth + 1)
                if captured:
                    elements.append(captured)

            return CapturedVariable(
                name=name,
                type=type_name,
                value=f'{type_name}[{total_length}]',
                array_elements=elements,
                array_length=total_length,
                is_truncated=total_length > self.config.max_collection_size,
            )

        if isinstance(value, dict):
            children: dict[str, CapturedVariable] = {}
            total_length = len(value)
            count = 0

            for k, v in value.items():
                if count >= self.config.max_collection_size:
                    break
                key_str = str(k)[:100]
                captured = self._capture_value(key_str, v, depth + 1)
                if captured:
                    children[key_str] = captured
                count += 1

            return CapturedVariable(
                name=name,
                type='dict',
                value=f'dict[{total_length}]',
                children=children,
                is_truncated=total_length > self.config.max_collection_size,
            )

        # Objects - just show type
        return CapturedVariable(
            name=name,
            type=type_name,
            value=f'<{type_name}>',
        )

    def _build_stack_trace(self, frame: FrameType) -> list[dict[str, Any]]:
        """Build stack trace from frame."""
        stack: list[dict[str, Any]] = []
        current = frame

        while current is not None and len(stack) < 50:
            code = current.f_code
            file_path = code.co_filename
            file_name = os.path.basename(file_path) if file_path else None
            is_native = file_path.startswith('<') if file_path else True

            stack.append({
                'method_name': code.co_name,
                'file_name': file_name,
                'file_path': file_path,
                'line_number': current.f_lineno,
                'class_name': self._get_class_name(current),
                'is_native': is_native,
                'source_available': not is_native and file_path and 'site-packages' not in file_path,
            })

            current = current.f_back

        return stack

    def _get_class_name(self, frame: FrameType) -> str | None:
        """Try to extract class name from frame."""
        local_self = frame.f_locals.get('self')
        if local_self is not None:
            return type(local_self).__name__
        return None
