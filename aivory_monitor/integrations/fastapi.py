"""FastAPI integration for AIVory Monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Awaitable

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.requests import Request
    from starlette.responses import Response


class FastAPIIntegration:
    """FastAPI middleware for AIVory Monitor."""

    def __init__(self, app: 'FastAPI' | None = None) -> None:
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app: 'FastAPI') -> None:
        """Initialize FastAPI application with AIVory Monitor."""
        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=self._dispatch)

        # Register exception handler
        @app.exception_handler(Exception)
        async def exception_handler(request: 'Request', exc: Exception) -> 'Response':
            import aivory_monitor
            from starlette.responses import JSONResponse

            context = await self._build_request_context(request)
            aivory_monitor.capture_exception(exc, {'request': context})

            return JSONResponse(
                status_code=500,
                content={'detail': 'Internal Server Error'},
            )

    async def _dispatch(
        self,
        request: 'Request',
        call_next: Callable[['Request'], Awaitable['Response']],
    ) -> 'Response':
        """Process the request and capture context."""
        import aivory_monitor

        context = await self._build_request_context(request)
        aivory_monitor.set_context({'request': context})

        try:
            response = await call_next(request)
            return response
        except Exception as e:
            aivory_monitor.capture_exception(e, {'request': context})
            raise

    async def _build_request_context(self, request: 'Request') -> dict[str, Any]:
        """Build context dictionary from Starlette request."""
        context: dict[str, Any] = {
            'method': request.method,
            'path': request.url.path,
            'url': str(request.url),
            'client_host': request.client.host if request.client else None,
        }

        # Headers (sanitized)
        headers: dict[str, str] = {}
        for key, value in request.headers.items():
            if key.lower() not in ('authorization', 'cookie', 'x-api-key'):
                headers[key] = value
        context['headers'] = headers

        # Query params
        if request.query_params:
            context['query_params'] = dict(request.query_params.multi_items())

        # Path params
        if request.path_params:
            context['path_params'] = dict(request.path_params)

        return context


def init_app(app: 'FastAPI') -> FastAPIIntegration:
    """
    Initialize FastAPI app with AIVory Monitor.

    Usage:
        from fastapi import FastAPI
        from aivory_monitor.integrations.fastapi import init_app

        app = FastAPI()
        init_app(app)

        # Or using the middleware directly:
        from aivory_monitor.integrations.fastapi import FastAPIIntegration
        FastAPIIntegration(app)
    """
    return FastAPIIntegration(app)


class AIVoryMiddleware:
    """
    ASGI middleware for AIVory Monitor.

    Can be used with any ASGI framework.

    Usage:
        from aivory_monitor.integrations.fastapi import AIVoryMiddleware

        app = AIVoryMiddleware(app)
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Process ASGI request."""
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        import aivory_monitor

        context = self._build_scope_context(scope)
        aivory_monitor.set_context({'request': context})

        try:
            await self.app(scope, receive, send)
        except Exception as e:
            aivory_monitor.capture_exception(e, {'request': context})
            raise

    def _build_scope_context(self, scope: dict[str, Any]) -> dict[str, Any]:
        """Build context from ASGI scope."""
        context: dict[str, Any] = {
            'method': scope.get('method', ''),
            'path': scope.get('path', ''),
            'type': scope.get('type', ''),
        }

        # Parse query string
        query_string = scope.get('query_string', b'')
        if query_string:
            context['query_string'] = query_string.decode('utf-8', errors='replace')

        # Headers (sanitized)
        headers: dict[str, str] = {}
        for name, value in scope.get('headers', []):
            name_str = name.decode('utf-8', errors='replace').lower()
            if name_str not in ('authorization', 'cookie', 'x-api-key'):
                headers[name_str] = value.decode('utf-8', errors='replace')
        context['headers'] = headers

        # Client info
        client = scope.get('client')
        if client:
            context['client'] = {'host': client[0], 'port': client[1]}

        return context
