"""
Tests for PluginRegistry.build_instructions() - the composition of the MCP
`instructions` field (initialize result) from each plugin's self-declared
metadata (ToolRegistry.set_plugin_info).

Spec: https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle
"""
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp_server.registry import PluginRegistry


class TestBuildInstructions:
    def test_empty_when_no_plugins(self):
        pr = PluginRegistry(FastMCP("test"))
        assert pr.build_instructions() == ""

    def test_skips_plugins_without_self_description(self):
        # A plugin that never calls set_plugin_info contributes nothing to the
        # prompt (repo urls alone are not persona/doctrine).
        root = PluginRegistry(FastMCP("test"))
        root.for_plugin("mcp_server_silent")
        assert root.build_instructions() == ""

    def test_composes_persona_description_and_questions(self):
        root = PluginRegistry(FastMCP("test"))
        sub = root.for_plugin("mcp_server_demo")
        sub.set_plugin_info(
            description="Demo datasets.",
            instructions="You only answer about demo data.",
            sample_questions=["What is X?", "How many Y?"],
        )

        out = root.build_instructions()

        assert "You only answer about demo data." in out
        assert "Demo datasets." in out
        assert "What is X?" in out
        assert "How many Y?" in out
        # Persona is injected before the catalog description so it frames it.
        assert out.index("You only answer about demo data.") < out.index("Demo datasets.")

    def test_composes_multiple_plugins(self):
        root = PluginRegistry(FastMCP("test"))
        root.for_plugin("mcp_server_a").set_plugin_info(instructions="Scope A.")
        root.for_plugin("mcp_server_b").set_plugin_info(instructions="Scope B.")

        out = root.build_instructions()

        assert "Scope A." in out
        assert "Scope B." in out

    def test_for_plugin_is_idempotent(self):
        """Regression: a plugin that registers tools AND resources is handed a
        sub-registry more than once (load_python_plugins then
        load_python_resources). The later for_plugin() call must reuse the same
        metadata dict, not clobber what set_plugin_info() populated on the first
        pass - otherwise build_instructions() comes back empty.
        """
        root = PluginRegistry(FastMCP("test"))

        # First pass: self-describe + (would) register tools.
        first = root.for_plugin("mcp_server_dual")
        first.set_plugin_info(description="Dual.", instructions="Scope: dual only.")

        # Second pass: same plugin again (as the resources loader does).
        second = root.for_plugin("mcp_server_dual")

        # Same underlying metadata object is reused, not replaced.
        assert first._plugin_metadata is second._plugin_metadata

        out = root.build_instructions()
        assert "Scope: dual only." in out
        assert "Dual." in out


@pytest.mark.anyio
async def test_instructions_travel_in_initialize_result():
    """End-to-end: what build_instructions() produces is what an MCP client
    receives in the `instructions` field of the initialize handshake."""
    mcp = FastMCP("test")
    root = PluginRegistry(mcp)
    root.for_plugin("mcp_server_demo").set_plugin_info(instructions="Only demo data.")
    mcp._mcp_server.instructions = root.build_instructions()

    async with create_connected_server_and_client_session(mcp._mcp_server) as client:
        init = await client.initialize()

    assert "Only demo data." in (init.instructions or "")
