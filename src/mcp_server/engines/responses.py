"""Shared CallToolResult builders for engines.

All engine return paths should go through these helpers so every YAML-defined
tool produces a CallToolResult whose structuredContent satisfies ValidationModel
(at minimum, `sources` is always populated).
"""
from mcp.types import CallToolResult, TextContent


def force_result(text, source_url=""):
    """Canned message that should bypass the LLM and be shown verbatim."""
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent={
            "sources": [source_url] if source_url else [],
            "force": text,
        },
    )
