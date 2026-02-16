"""Django integration for AIVory Monitor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


class DjangoIntegration:
    """Django middleware for capturing request context and exceptions."""

    def __init__(self, get_response: Callable[['HttpRequest'], 'HttpResponse']) -> None:
        self.get_response = get_response

    def __call__(self, request: 'HttpRequest') -> 'HttpResponse':
        """Process the request and capture exceptions."""
        import aivory_monitor

        # Set request context
        context = self._build_request_context(request)
        aivory_monitor.set_context({'request': context})

        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            # Capture the exception with request context
            aivory_monitor.capture_exception(e, {'request': context})
            raise

    def process_exception(
        self,
        request: 'HttpRequest',
        exception: Exception,
    ) -> None:
        """Process exceptions caught by Django's exception handling."""
        import aivory_monitor

        context = self._build_request_context(request)
        aivory_monitor.capture_exception(exception, {'request': context})

    def _build_request_context(self, request: 'HttpRequest') -> dict[str, Any]:
        """Build context dictionary from request."""
        context: dict[str, Any] = {
            'method': request.method,
            'path': request.path,
            'path_info': request.path_info,
            'query_string': request.META.get('QUERY_STRING', ''),
        }

        # Headers (sanitized)
        headers: dict[str, str] = {}
        for key, value in request.META.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').title()
                if header_name.lower() not in ('authorization', 'cookie', 'x-api-key'):
                    headers[header_name] = str(value)

        context['headers'] = headers

        # User info if available
        if hasattr(request, 'user') and request.user.is_authenticated:
            context['user'] = {
                'id': str(request.user.pk) if hasattr(request.user, 'pk') else None,
                'username': getattr(request.user, 'username', None),
                'email': getattr(request.user, 'email', None),
            }

        # GET/POST data (limited)
        if request.GET:
            context['query_params'] = dict(request.GET.lists())

        return context


def configure_django_logging() -> dict[str, Any]:
    """
    Returns a Django LOGGING configuration that integrates with AIVory Monitor.

    Usage in settings.py:
        from aivory_monitor.integrations.django import configure_django_logging

        LOGGING = configure_django_logging()
        # Or merge with existing config:
        # LOGGING['handlers'].update(configure_django_logging()['handlers'])
    """
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'aivory': {
                'class': 'aivory_monitor.integrations.django.AIVoryLoggingHandler',
                'level': 'ERROR',
            },
        },
        'root': {
            'handlers': ['aivory'],
            'level': 'ERROR',
        },
    }


class AIVoryLoggingHandler:
    """Python logging handler that sends errors to AIVory Monitor."""

    def __init__(self, level: int = 40) -> None:  # 40 = ERROR
        self.level = level

    def emit(self, record: Any) -> None:
        """Emit a log record."""
        import aivory_monitor

        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            if exc_value is not None:
                aivory_monitor.capture_exception(exc_value, {
                    'logger': record.name,
                    'level': record.levelname,
                    'message': record.getMessage(),
                })
