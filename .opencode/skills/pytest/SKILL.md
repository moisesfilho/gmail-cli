---
name: pytest
description: This skill should be used when the user asks to "write pytest tests", "set up pytest best practices", "configure pytest", "write fixtures", or needs guidance on pytest testing patterns and project structure.
---

# pytest Best Practices

Comprehensive guidance for writing maintainable, efficient test suites with pytest, grounded in the official pytest documentation.

## Project Layout

Use the `src` layout with tests outside the application package:

```
pyproject.toml
src/
    mypkg/
        __init__.py
        app.py
tests/
    conftest.py
    test_app.py
```

Configure `importlib` import mode in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = ["--import-mode=importlib"]
testpaths = ["tests"]
```

Install the package in editable mode so tests run against the local source:

```bash
pip install -e .
```

## Test Discovery Conventions

- Name test files `test_*.py` or `*_test.py`
- Name test functions and methods with a `test_` prefix
- Use `Test`-prefixed classes (no `__init__` method) to group related tests
- Place shared fixtures and plugins in `conftest.py`

## Assertions

Use plain `assert` statements:

```python
def test_addition():
    assert 1 + 1 == 2

def test_with_message():
    result = compute()
    assert result > 0, f"Expected positive, got {result}"
```

**Floating-point comparisons** — use `pytest.approx`:

```python
def test_floats():
    assert 0.1 + 0.2 == pytest.approx(0.3)
```

**Exception assertions** — use `pytest.raises`:

```python
def test_zero_division():
    with pytest.raises(ZeroDivisionError):
        1 / 0

def test_exception_message():
    with pytest.raises(ValueError, match=r"invalid value"):
        parse_value("bad")
```

## Fixtures

### Basic fixture

```python
import pytest

@pytest.fixture
def user():
    return {"name": "Alice", "role": "admin"}

def test_user_role(user):
    assert user["role"] == "admin"
```

### Yield fixtures for teardown

```python
@pytest.fixture
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()
```

### Fixture scope

| Scope | Lifetime | Use case |
|-------|----------|----------|
| `function` | Per test (default) | Mutable state, cheap to create |
| `class` | Per test class | Shared state within a class |
| `module` | Per test file | Expensive setup shared across a module |
| `session` | Entire test run | Database connections, containers |

### Factory fixtures

```python
@pytest.fixture
def make_order():
    orders = []
    def _make(product, qty):
        order = Order(product=product, qty=qty)
        orders.append(order)
        return order
    yield _make
    for o in orders: o.cancel()

def test_two_orders(make_order):
    o1 = make_order("book", 1)
    o2 = make_order("pen", 5)
    assert o1.product != o2.product
```

## Parametrization

```python
@pytest.mark.parametrize("value,expected", [
    (2, 4),
    (3, 9),
    (-1, 1),
])
def test_square(value, expected):
    assert square(value) == expected
```

## Markers

Register all custom markers in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow",
    "integration: requires external services",
    "unit: fast, isolated tests",
]
```

## Quick Reference

| Goal | Tool |
|------|------|
| Assert equality | `assert a == b` |
| Assert float equality | `pytest.approx` |
| Assert exception raised | `pytest.raises()` |
| Skip conditionally | `@pytest.mark.skipif` |
| Document known failure | `@pytest.mark.xfail` |
| Run test N times with data | `@pytest.mark.parametrize` |
| Shared setup/teardown | `@pytest.fixture` |
| Patch objects/env | `monkeypatch` |
| Temp files | `tmp_path` |
