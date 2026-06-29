"""
Initial MCP Server integration tests.

Inspired on the official documentation: https://py.sdk.modelcontextprotocol.io/testing/

"""
from collections.abc import AsyncGenerator

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import EmptyResult

from mcp_server.server import mcp


@pytest.fixture
async def client_session() -> AsyncGenerator[ClientSession]:
    async with create_connected_server_and_client_session(mcp, raise_exceptions=True) as _session:
        yield _session


@pytest.mark.anyio
async def test_server_runs(client_session: ClientSession):
    result = await client_session.send_ping()
    assert isinstance(result, EmptyResult)
