# Changelog

All notable changes to the AIVory Monitor Python Agent will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.2] - 2026-02-27

### Fixed
- WebSocket connection stability: replaced `socket.settimeout()` with `recv(timeout=1.0)` to prevent the websockets internal thread from terminating on idle timeouts
- Restored `send_exception` payload construction (regression caused silent JSON serialization failure)
- Restored `send_breakpoint_hit` breakpoint ID and agent ID in payload
- Restored exponential backoff reconnect counter increment
- Restored auth error handling to correctly stop reconnection on `auth_error`/`invalid_api_key`

## [1.0.1] - 2026-02-27

### Changed
- Updated WebSocket endpoint to `wss://api.aivory.net/monitor/agent`

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
