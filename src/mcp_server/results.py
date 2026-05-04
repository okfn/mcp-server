"""Shared CallToolResult builders for tool responses.

Helpers to build MCP responses that produces a CallToolResult whose structuredContent
satisfies the ValidationModel (at minimum, `sources` is always populated)

When developing engines, their return paths should go through these helpers so every
YAML-defined tool produces a correct return value.
"""
from mcp.types import CallToolResult, TextContent


def text_result(text, source_url="", table=None, charts=None, force=None):
    """Successful response: text content plus structured sources/table/charts."""
    # TODO: If validation model field is array, source_url should be an array as well.
    structured = {"sources": [source_url] if source_url else []}
    if table is not None:
        structured["table"] = table
    if charts:
        structured["charts"] = charts
    if force:
        structured["force"] = force
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent=structured,
    )


def force_result(text, source_url=""):
    """Canned message that should bypass the LLM and be shown verbatim."""
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent={
            "sources": [source_url] if source_url else [],
            "force": text,
        },
    )
