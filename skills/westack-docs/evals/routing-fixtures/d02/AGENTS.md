# Agent notes

- Python 3.11. Install with `pip install -e .[dev]`.
- Payments code lives in `payments/`. Its tests are in `payments/tests/`; run them with `pytest payments/tests`.
- Never call the live card provider from tests: use the fakes in `payments/fakes.py`.
- Lint with `ruff check .` before committing.
