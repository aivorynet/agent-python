# AIVory Monitor Python Agent

Python agent using sys.settrace for breakpoint support and sys.excepthook for exception capture.

## Requirements

- Python 3.8+
- pip or pip3

## Installation

```bash
pip install aivory-monitor
```

## Usage

### Option 1: Import and Initialize

```python
import aivory_monitor

# Initialize with environment variables
aivory_monitor.init()

# Or pass configuration directly
aivory_monitor.init(
    api_key='your-api-key',
    environment='production'
)

# Your application code
```

### Option 2: Automatic Initialization via Environment

Set environment variables before importing your application:

```bash
export AIVORY_API_KEY=your_api_key
python app.py
```

Then initialize in your application entry point:

```python
import aivory_monitor
aivory_monitor.init()

# Rest of your application
```

### Option 3: Framework Middleware

**Django:**

Add to your `settings.py`:

```python
MIDDLEWARE = [
    'aivory_monitor.integrations.django.DjangoIntegration',
    # ... other middleware
]

# Initialize agent
import aivory_monitor
aivory_monitor.init(api_key='your-api-key')
```

**Flask:**

```python
from flask import Flask
from aivory_monitor.integrations.flask import init_app
import aivory_monitor

app = Flask(__name__)

# Initialize agent
aivory_monitor.init(api_key='your-api-key')

# Add Flask integration
init_app(app)
```

**FastAPI:**

```python
from fastapi import FastAPI
from aivory_monitor.integrations.fastapi import init_app
import aivory_monitor

app = FastAPI()

# Initialize agent
aivory_monitor.init(api_key='your-api-key')

# Add FastAPI integration
init_app(app)
```

### Manual Exception Capture

```python
import aivory_monitor

try:
    risky_operation()
except Exception as e:
    # Capture exception with additional context
    aivory_monitor.capture_exception(e, context={
        'user_id': '12345',
        'operation': 'payment_processing'
    })
    raise
```

### Setting Context and User Information

```python
import aivory_monitor

# Set custom context (included in all captures)
aivory_monitor.set_context({
    'feature_flags': {'new_ui': True},
    'tenant_id': 'acme-corp'
})

# Set user information
aivory_monitor.set_user(
    user_id='user-123',
    email='user@example.com',
    username='john_doe'
)
```

## Configuration

All configuration options can be set via environment variables or passed to `init()`:

| Parameter | Environment Variable | Default | Description |
|-----------|---------------------|---------|-------------|
| `api_key` | `AIVORY_API_KEY` | Required | AIVory API key for authentication |
| `backend_url` | `AIVORY_BACKEND_URL` | `wss://api.aivory.net/ws/agent` | Backend WebSocket URL |
| `environment` | `AIVORY_ENVIRONMENT` | `production` | Environment name (production, staging, etc.) |
| `sampling_rate` | `AIVORY_SAMPLING_RATE` | `1.0` | Exception sampling rate (0.0 - 1.0) |
| `max_capture_depth` | `AIVORY_MAX_DEPTH` | `10` | Maximum depth for variable capture |
| `max_string_length` | `AIVORY_MAX_STRING_LENGTH` | `1000` | Maximum string length to capture |
| `max_collection_size` | `AIVORY_MAX_COLLECTION_SIZE` | `100` | Maximum collection elements to capture |
| `enable_breakpoints` | `AIVORY_ENABLE_BREAKPOINTS` | `true` | Enable non-breaking breakpoint support |
| `debug` | `AIVORY_DEBUG` | `false` | Enable debug logging |

### Configuration Examples

**Environment Variables:**

```bash
export AIVORY_API_KEY=your_api_key
export AIVORY_BACKEND_URL=wss://api.aivory.net/ws/agent
export AIVORY_ENVIRONMENT=production
export AIVORY_SAMPLING_RATE=0.5
export AIVORY_MAX_DEPTH=5
export AIVORY_DEBUG=false
```

**Programmatic:**

```python
import aivory_monitor

aivory_monitor.init(
    api_key='your-api-key',
    backend_url='wss://api.aivory.net/ws/agent',
    environment='production',
    sampling_rate=0.5,
    max_capture_depth=5,
    max_string_length=500,
    max_collection_size=50,
    enable_breakpoints=True,
    debug=False
)
```

## Building from Source

```bash
cd monitor-agents/agent-python
pip install -e .

# Or build distribution packages
pip install build
python -m build
```

## How It Works

1. **sys.excepthook**: Automatically captures uncaught exceptions with full stack traces and local variables
2. **sys.settrace**: Implements non-breaking breakpoints by hooking into Python's trace mechanism
3. **Asyncio Integration**: Uses WebSocket client with asyncio for real-time communication with backend
4. **Context Preservation**: Captures thread-local and request context at the time of exception

**Key Features:**

- Non-breaking breakpoints that don't pause execution
- Full stack trace with local variables at each frame
- Request context correlation for web frameworks
- Configurable variable capture depth and sampling
- Minimal performance overhead (uses sampling and conditional capture)

## Framework Support

### Django

The Django integration provides:

- Automatic request context capture (method, path, headers, user)
- Exception handling in views and middleware
- Optional logging handler integration

```python
# settings.py
MIDDLEWARE = [
    'aivory_monitor.integrations.django.DjangoIntegration',
    # ... other middleware
]

import aivory_monitor
aivory_monitor.init(api_key='your-api-key')

# Optional: Configure logging integration
from aivory_monitor.integrations.django import configure_django_logging
LOGGING = configure_django_logging()
```

### Flask

The Flask integration provides:

- Before-request context setup
- Automatic exception handling
- Request timing information

```python
from flask import Flask
from aivory_monitor.integrations.flask import init_app
import aivory_monitor

app = Flask(__name__)
aivory_monitor.init(api_key='your-api-key')
init_app(app)
```

### FastAPI

The FastAPI integration provides:

- ASGI middleware for request/response tracking
- Async exception handling
- Path and query parameter capture

```python
from fastapi import FastAPI
from aivory_monitor.integrations.fastapi import init_app
import aivory_monitor

app = FastAPI()
aivory_monitor.init(api_key='your-api-key')
init_app(app)
```

For generic ASGI applications, use `AIVoryMiddleware`:

```python
from aivory_monitor.integrations.fastapi import AIVoryMiddleware

app = AIVoryMiddleware(app)
```

## Local Development Testing

### Quick Test Script

Create a test script to trigger exceptions:

```python
# test-app.py
import aivory_monitor
import time

aivory_monitor.init(
    api_key='ilscipio-dev-2024',
    backend_url='ws://localhost:19999/ws/monitor/agent',
    environment='development',
    debug=True
)

print("Agent initialized, waiting 2s for connection...")
time.sleep(2)

# Test 1: Simple exception
try:
    raise ValueError("Test exception from Python agent")
except Exception as e:
    aivory_monitor.capture_exception(e)

# Test 2: Null reference
try:
    x = None
    x.some_method()
except Exception as e:
    aivory_monitor.capture_exception(e)

# Test 3: With context
try:
    result = 10 / 0
except Exception as e:
    aivory_monitor.capture_exception(e, context={
        'operation': 'divide',
        'user_id': 'test-user'
    })

print("Test exceptions sent. Check backend logs.")
time.sleep(2)
aivory_monitor.shutdown()
```

Run with:

```bash
python test-app.py
```

### Flask Test Server

```python
# test-server.py
from flask import Flask
from aivory_monitor.integrations.flask import init_app
import aivory_monitor

app = Flask(__name__)

aivory_monitor.init(
    api_key='ilscipio-dev-2024',
    backend_url='ws://localhost:19999/ws/monitor/agent',
    environment='development',
    debug=True
)

init_app(app)

@app.route('/error')
def trigger_error():
    raise ValueError("Test sync error")

@app.route('/null')
def trigger_null():
    x = None
    return x.some_attribute

@app.route('/divide')
def trigger_divide():
    return 10 / 0

@app.route('/')
def index():
    return 'Endpoints: /error, /null, /divide'

if __name__ == '__main__':
    print("Test server: http://localhost:5000")
    app.run(port=5000, debug=False)
```

**Test URLs:**
- http://localhost:5000/error - Raises ValueError
- http://localhost:5000/null - Raises AttributeError
- http://localhost:5000/divide - Raises ZeroDivisionError

### Prerequisites for Local Testing

1. Backend running on `localhost:19999`
2. Dev token bypass enabled (uses `ilscipio-dev-2024`)
3. Org schema `org_test_20` exists in database

## Troubleshooting

**Breakpoints not working:**
- Ensure `enable_breakpoints=True` in configuration
- Check that sys.settrace is not being overridden by debuggers or profilers
- Only one trace function can be active at a time

**High memory usage:**
- Reduce `max_capture_depth` (default: 10)
- Reduce `max_string_length` (default: 1000)
- Reduce `max_collection_size` (default: 100)
- Use `sampling_rate` to capture only a percentage of exceptions

**Agent not connecting:**
- Check backend is running: `curl http://localhost:19999/health`
- Check WebSocket endpoint: `ws://localhost:19999/ws/monitor/agent`
- Verify API key is set correctly
- Enable debug mode: `debug=True` or `AIVORY_DEBUG=true`

**Exceptions not captured in Django:**
- Ensure middleware is added to `MIDDLEWARE` in settings.py
- Ensure `aivory_monitor.init()` is called before Django starts
- Check that `DEBUG=False` in production (Django only logs exceptions when DEBUG=False)

**Threading issues:**
- The agent uses thread-safe mechanisms for context storage
- Each thread maintains its own trace function for breakpoints
- WebSocket connection runs in a separate background thread

**Import errors:**
- Ensure `websockets>=11.0` is installed: `pip install websockets`
- For framework integrations, install optional dependencies:
  - Django: `pip install aivory-monitor[django]`
  - Flask: `pip install aivory-monitor[flask]`
  - FastAPI: `pip install aivory-monitor[fastapi]`
