"""Exception capture data structures."""

from __future__ import annotations

import hashlib
import os
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from types import FrameType
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import AgentConfig


@dataclass
class CapturedVariable:
    """Represents a captured variable value."""

    name: str
    type: str
    value: str
    is_null: bool = False
    is_truncated: bool = False
    children: dict[str, 'CapturedVariable'] = field(default_factory=dict)
    array_elements: list['CapturedVariable'] = field(default_factory=list)
    array_length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            'name': self.name,
            'type': self.type,
            'value': self.value,
            'is_null': self.is_null,
            'is_truncated': self.is_truncated,
        }

        if self.children:
            result['children'] = {k: v.to_dict() for k, v in self.children.items()}

        if self.array_elements:
            result['array_elements'] = [e.to_dict() for e in self.array_elements]
            result['array_length'] = self.array_length

        return result


@dataclass
class StackFrameInfo:
    """Information about a single stack frame."""

    method_name: str
    file_name: str | None = None
    file_path: str | None = None
    line_number: int | None = None
    class_name: str | None = None
    is_native: bool = False
    source_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'method_name': self.method_name,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'class_name': self.class_name,
            'is_native': self.is_native,
            'source_available': self.source_available,
        }


@dataclass
class ExceptionCapture:
    """Complete exception capture data."""

    id: str
    exception_type: str
    message: str
    fingerprint: str
    stack_trace: list[StackFrameInfo]
    local_variables: dict[str, CapturedVariable]
    context: dict[str, Any]
    captured_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'exception_type': self.exception_type,
            'message': self.message,
            'fingerprint': self.fingerprint,
            'stack_trace': [f.to_dict() for f in self.stack_trace],
            'local_variables': {k: v.to_dict() for k, v in self.local_variables.items()},
            'context': self.context,
            'captured_at': self.captured_at,
        }


class ExceptionCaptureBuilder:
    """Builds exception capture from Python exception."""

    def __init__(self, config: 'AgentConfig') -> None:
        self.config = config

    def capture(
        self,
        exception: BaseException,
        context: dict | None = None,
        frame: FrameType | None = None,
    ) -> ExceptionCapture:
        """Capture exception with full context."""
        stack_trace = self._extract_stack_trace(exception)
        local_variables = self._capture_local_variables(frame) if frame else {}
        fingerprint = self._calculate_fingerprint(exception, stack_trace)

        return ExceptionCapture(
            id=str(uuid.uuid4()),
            exception_type=type(exception).__name__,
            message=str(exception),
            fingerprint=fingerprint,
            stack_trace=stack_trace,
            local_variables=local_variables,
            context={
                **self.config.get_custom_context(),
                **(context or {}),
                'user': self.config.get_user(),
            },
            captured_at=datetime.utcnow().isoformat() + 'Z',
        )

    def _extract_stack_trace(self, exception: BaseException) -> list[StackFrameInfo]:
        """Extract stack trace from exception."""
        frames: list[StackFrameInfo] = []
        tb = exception.__traceback__

        while tb is not None:
            frame = tb.tb_frame
            code = frame.f_code

            file_path = code.co_filename
            file_name = os.path.basename(file_path) if file_path else None
            is_native = file_path.startswith('<') if file_path else True
            source_available = (
                not is_native
                and file_path
                and not ('site-packages' in file_path or 'dist-packages' in file_path)
            )

            frames.append(StackFrameInfo(
                method_name=code.co_name,
                file_name=file_name,
                file_path=file_path,
                line_number=tb.tb_lineno,
                class_name=self._get_class_name(frame),
                is_native=is_native,
                source_available=source_available,
            ))

            tb = tb.tb_next

            if len(frames) >= 50:
                break

        return frames

    def _get_class_name(self, frame: FrameType) -> str | None:
        """Try to extract class name from frame."""
        local_self = frame.f_locals.get('self')
        if local_self is not None:
            return type(local_self).__name__

        local_cls = frame.f_locals.get('cls')
        if local_cls is not None and isinstance(local_cls, type):
            return local_cls.__name__

        return None

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
                # Skip variables that can't be captured
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

        if isinstance(value, set):
            elements = []
            total_length = len(value)
            count = 0

            for item in value:
                if count >= self.config.max_collection_size:
                    break
                captured = self._capture_value(f'[{count}]', item, depth + 1)
                if captured:
                    elements.append(captured)
                count += 1

            return CapturedVariable(
                name=name,
                type='set',
                value=f'set[{total_length}]',
                array_elements=elements,
                array_length=total_length,
                is_truncated=total_length > self.config.max_collection_size,
            )

        # Objects
        try:
            children = {}
            attrs = [a for a in dir(value) if not a.startswith('_')][:self.config.max_collection_size]

            for attr in attrs:
                try:
                    attr_value = getattr(value, attr)
                    if callable(attr_value):
                        continue
                    captured = self._capture_value(attr, attr_value, depth + 1)
                    if captured:
                        children[attr] = captured
                except Exception:
                    pass

            return CapturedVariable(
                name=name,
                type=type_name,
                value=f'<{type_name}>',
                children=children,
            )
        except Exception:
            return CapturedVariable(
                name=name,
                type=type_name,
                value=f'<{type_name}>',
            )

    def _calculate_fingerprint(
        self,
        exception: BaseException,
        stack_trace: list[StackFrameInfo],
    ) -> str:
        """Calculate unique fingerprint for exception grouping."""
        parts = [type(exception).__name__]

        # Add first few non-native stack frames
        added = 0
        for frame in stack_trace:
            if added >= 5:
                break
            if frame.is_native:
                continue
            parts.append(f'{frame.method_name}:{frame.line_number or 0}')
            added += 1

        hash_input = ':'.join(parts)
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
