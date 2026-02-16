# Contributing to AIVory Monitor Python Agent

Thank you for your interest in contributing to the AIVory Monitor Python Agent. Contributions of all kinds are welcome -- bug reports, feature requests, documentation improvements, and code changes.

## How to Contribute

- **Bug reports**: Open an issue at [GitHub Issues](https://github.com/aivorynet/agent-python/issues) with a clear description, steps to reproduce, and your environment details (Python version, OS, framework).
- **Feature requests**: Open an issue describing the use case and proposed behavior.
- **Pull requests**: See the Pull Request Process below.

## Development Setup

### Prerequisites

- Python 3.8 or later
- pip

### Build and Test

```bash
cd monitor-agents/agent-python
pip install -e ".[dev]"
pytest
```

### Running the Agent

```bash
AIVORY_API_KEY=your-key python -c "import aivory_monitor; aivory_monitor.init()" app.py
```

## Coding Standards

- Follow the existing code style in the repository.
- Write tests for all new features and bug fixes.
- Use type hints throughout.
- Keep `sys.settrace` and `sys.excepthook` usage minimal and well-documented.
- Ensure compatibility across Python 3.8+.

## Pull Request Process

1. Fork the repository and create a feature branch from `main`.
2. Make your changes and write tests.
3. Ensure all tests pass (`pytest`).
4. Submit a pull request on [GitHub](https://github.com/aivorynet/agent-python) or GitLab.
5. All pull requests require at least one review before merge.

## Reporting Bugs

Use [GitHub Issues](https://github.com/aivorynet/agent-python/issues). Include:

- Python version and OS
- Agent version
- Framework (Django, Flask, FastAPI, etc.) if applicable
- Error output or stack traces
- Minimal reproduction steps

## Security

Do not open public issues for security vulnerabilities. Report them to **security@aivory.net**. See [SECURITY.md](SECURITY.md) for details.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
