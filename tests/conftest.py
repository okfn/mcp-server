"""
Shared pytest fixtures for the mcp-server test suite.

Fixtures defined here are auto-discovered by pytest for every test under
``tests/`` - no import needed.
"""
import pytest


@pytest.fixture
def anyio_backend():
    """Pin anyio-based async tests (those marked ``@pytest.mark.anyio``) to the
    asyncio backend. Without this, anyio also tries the trio backend, which is
    not installed. Consumed implicitly by the anyio plugin, not by name.
    """
    return "asyncio"
