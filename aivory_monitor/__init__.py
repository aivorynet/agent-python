"""
AIVory Monitor Python Agent

Remote debugging with AI-powered fix generation.

Usage:
    import aivory_monitor

    aivory_monitor.init(
        api_key='your-api-key',
        environment='production'
    )

    # Manually capture an exception
    try:
        risky_operation()
    except Exception as e:
        aivory_monitor.capture_exception(e)
"""

from .config import AgentConfig
from .agent import AIVoryAgent

__version__ = '1.0.2'
__all__ = [
    'init',
    'shutdown',
    'capture_exception',
    'set_context',
    'set_user',
    'is_initialized',
]

_agent: AIVoryAgent | None = None


def init(
    api_key: str | None = None,
    backend_url: str | None = None,
    environment: str | None = None,
    sampling_rate: float | None = None,
    max_capture_depth: int | None = None,
    max_string_length: int | None = None,
    max_collection_size: int | None = None,
    enable_breakpoints: bool | None = None,
    debug: bool | None = None,
) -> None:
    """
    Initialize the AIVory Monitor agent.

    Args:
        api_key: AIVory API key (or set AIVORY_API_KEY env var)
        backend_url: Backend WebSocket URL (default: wss://api.aivory.net/monitor/agent)
        environment: Environment name (default: production)
        sampling_rate: Exception sampling rate 0.0-1.0 (default: 1.0)
        max_capture_depth: Maximum depth for variable capture (default: 3)
        max_string_length: Maximum string length to capture (default: 1000)
        max_collection_size: Maximum collection elements to capture (default: 100)
        enable_breakpoints: Enable breakpoint support (default: True)
        debug: Enable debug logging (default: False)
    """
    global _agent

    if _agent is not None:
        print('[AIVory Monitor] Agent already initialized')
        return

    config = AgentConfig(
        api_key=api_key,
        backend_url=backend_url,
        environment=environment,
        sampling_rate=sampling_rate,
        max_capture_depth=max_capture_depth,
        max_string_length=max_string_length,
        max_collection_size=max_collection_size,
        enable_breakpoints=enable_breakpoints,
        debug=debug,
    )

    if not config.api_key:
        print('[AIVory Monitor] API key is required. Set AIVORY_API_KEY or pass api_key parameter.')
        return

    _agent = AIVoryAgent(config)
    _agent.start()

    print(f'[AIVory Monitor] Agent v{__version__} initialized')
    print(f'[AIVory Monitor] Environment: {config.environment}')


def shutdown() -> None:
    """Shutdown the AIVory Monitor agent."""
    global _agent

    if _agent is None:
        return

    print('[AIVory Monitor] Shutting down agent')
    _agent.stop()
    _agent = None


def capture_exception(
    exception: BaseException,
    context: dict | None = None,
) -> None:
    """
    Manually capture an exception.

    Args:
        exception: The exception to capture
        context: Additional context to include with the capture
    """
    if _agent is None:
        print('[AIVory Monitor] Agent not initialized')
        return

    _agent.capture_exception(exception, context)


def set_context(context: dict) -> None:
    """
    Set custom context that will be sent with all captures.

    Args:
        context: Dictionary of context data
    """
    if _agent is None:
        print('[AIVory Monitor] Agent not initialized')
        return

    _agent.config.set_custom_context(context)


def set_user(
    user_id: str | None = None,
    email: str | None = None,
    username: str | None = None,
) -> None:
    """
    Set the current user for context.

    Args:
        user_id: User ID
        email: User email
        username: Username
    """
    if _agent is None:
        print('[AIVory Monitor] Agent not initialized')
        return

    _agent.config.set_user(user_id=user_id, email=email, username=username)


def is_initialized() -> bool:
    """Check if the agent is initialized."""
    return _agent is not None
