"""Flask integration for AIVory Monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask import Flask


class FlaskIntegration:
    """Flask extension for AIVory Monitor."""

    def __init__(self, app: 'Flask' | None = None) -> None:
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app: 'Flask') -> None:
        """Initialize the Flask application with AIVory Monitor."""
        from flask import g, request

        # Register error handler
        @app.errorhandler(Exception)
        def handle_exception(error: Exception) -> Any:
            import aivory_monitor

            context = self._build_request_context()
            aivory_monitor.capture_exception(error, {'request': context})

            # Re-raise to let Flask handle the response
            raise error

        # Set context before each request
        @app.before_request
        def before_request() -> None:
            import aivory_monitor

            context = self._build_request_context()
            aivory_monitor.set_context({'request': context})

            # Store start time for timing
            g.aivory_start_time = self._get_time()

        # Store extensions reference
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['aivory_monitor'] = self

    def _build_request_context(self) -> dict[str, Any]:
        """Build context dictionary from Flask request."""
        from flask import request

        context: dict[str, Any] = {
            'method': request.method,
            'path': request.path,
            'url': request.url,
            'endpoint': request.endpoint,
        }

        # Headers (sanitized)
        headers: dict[str, str] = {}
        for key, value in request.headers:
            if key.lower() not in ('authorization', 'cookie', 'x-api-key'):
                headers[key] = str(value)
        context['headers'] = headers

        # Query params
        if request.args:
            context['query_params'] = dict(request.args.lists())

        # Form data keys (not values for security)
        if request.form:
            context['form_keys'] = list(request.form.keys())

        # JSON body keys (not values)
        if request.is_json and request.json:
            context['json_keys'] = list(request.json.keys()) if isinstance(request.json, dict) else None

        return context

    def _get_time(self) -> float:
        """Get current time in seconds."""
        import time
        return time.time()


def init_app(app: 'Flask') -> FlaskIntegration:
    """
    Initialize Flask app with AIVory Monitor.

    Usage:
        from flask import Flask
        from aivory_monitor.integrations.flask import init_app

        app = Flask(__name__)
        init_app(app)
    """
    return FlaskIntegration(app)
