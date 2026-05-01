"""Shared CallToolResult builders for engines.

All engine return paths should go through these helpers so every YAML-defined
tool produces a CallToolResult whose structuredContent satisfies ValidationModel
(at minimum, `sources` is always populated).
"""
from mcp.types import CallToolResult, TextContent


def text_result(text, source_url="", table=None, charts=None):
    """Successful response: text content plus structured sources/table/charts."""
    structured = {"sources": [source_url] if source_url else []}
    if table is not None:
        structured["table"] = table
    if charts:
        structured["charts"] = charts
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
