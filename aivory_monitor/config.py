"""Agent configuration management."""

from __future__ import annotations

import os
import platform
import random
import secrets
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentConfig:
    """Configuration for the AIVory Monitor agent."""

    api_key: str | None = None
    backend_url: str | None = None
    environment: str | None = None
    sampling_rate: float | None = None
    max_capture_depth: int | None = None
    max_string_length: int | None = None
    max_collection_size: int | None = None
    enable_breakpoints: bool | None = None
    debug: bool | None = None

    # Generated fields
    hostname: str = field(default_factory=socket.gethostname)
    agent_id: str = field(default_factory=lambda: f"agent-{hex(int(time.time()))[2:]}-{secrets.token_hex(4)}")

    # Custom context
    _custom_context: dict = field(default_factory=dict, repr=False)
    _user: dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Apply defaults from environment variables."""
        self.api_key = self.api_key or os.environ.get('AIVORY_API_KEY', '')
        self.backend_url = self.backend_url or os.environ.get(
            'AIVORY_BACKEND_URL', 'wss://api.aivory.net/monitor/agent'
        )
        self.environment = self.environment or os.environ.get('AIVORY_ENVIRONMENT', 'production')
        self.sampling_rate = self.sampling_rate if self.sampling_rate is not None else float(
            os.environ.get('AIVORY_SAMPLING_RATE', '1.0')
        )
        self.max_capture_depth = self.max_capture_depth if self.max_capture_depth is not None else int(
            os.environ.get('AIVORY_MAX_DEPTH', '10')
        )
        self.max_string_length = self.max_string_length if self.max_string_length is not None else int(
            os.environ.get('AIVORY_MAX_STRING_LENGTH', '1000')
        )
        self.max_collection_size = self.max_collection_size if self.max_collection_size is not None else int(
            os.environ.get('AIVORY_MAX_COLLECTION_SIZE', '100')
        )
        self.enable_breakpoints = self.enable_breakpoints if self.enable_breakpoints is not None else (
            os.environ.get('AIVORY_ENABLE_BREAKPOINTS', 'true').lower() != 'false'
        )
        self.debug = self.debug if self.debug is not None else (
            os.environ.get('AIVORY_DEBUG', 'false').lower() == 'true'
        )

    def should_sample(self) -> bool:
        """Determine if current event should be sampled."""
        if self.sampling_rate >= 1.0:
            return True
        if self.sampling_rate <= 0.0:
            return False
        return random.random() < self.sampling_rate

    def set_custom_context(self, context: dict) -> None:
        """Set custom context data."""
        self._custom_context = dict(context)

    def get_custom_context(self) -> dict:
        """Get custom context data."""
        return dict(self._custom_context)

    def set_user(
        self,
        user_id: str | None = None,
        email: str | None = None,
        username: str | None = None,
    ) -> None:
        """Set current user information."""
        self._user = {}
        if user_id:
            self._user['id'] = user_id
        if email:
            self._user['email'] = email
        if username:
            self._user['username'] = username

    def get_user(self) -> dict:
        """Get current user information."""
        return dict(self._user)

    def get_runtime_info(self) -> dict[str, Any]:
        """Get Python runtime information."""
        return {
            'runtime': 'python',
            'runtime_version': platform.python_version(),
            'platform': sys.platform,
            'arch': platform.machine(),
            'implementation': platform.python_implementation(),
        }
