# Changelog

All notable changes to the AIVory Monitor Python Agent will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-02-16

### Added
- sys.excepthook integration for automatic uncaught exception capture
- sys.settrace hooks for non-breaking breakpoint support
- Local variable capture at each stack frame
- Django, Flask, and FastAPI framework integrations
- Manual exception capture via `aivory_monitor.capture_exception()`
- User and custom context enrichment
- WebSocket connection to AIVory backend with automatic reconnection
- Configurable sampling rate, capture depth, and string/collection limits
- asyncio integration for async application support
- Python 3.8 through 3.12 support
