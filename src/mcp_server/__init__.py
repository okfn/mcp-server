from typing import Annotated
from mcp.types import CallToolResult
from pydantic import BaseModel, Field


class ValidationModel(BaseModel):
    """Schema for all Structured Outputs of the MCP server.

    Every tool registered through the ToolRegistry must declare ``-> DataToolOutput``
    in its return annotation.  The registry checks this at startup; tools that
    don't comply are skipped with a warning.

    The serialized dict (via ``model_dump()``) is returned to the MCP client
    in the `structuredContent` field of the response.
    """
    sources: list = Field(
        description="URL(s) that users can nagivate to to download the data used for the analysis. E.g., landing page, feed, file endpoint, CKAN resource page, etc."
    )
    table: list = Field(
        default=[],
        description="Two-dimensional list (list of rows) representing tabular data, e.g., from CSV or TSV sources. Each row should be a list of cell values."
    )
    charts: list = Field(
        default=[],
        description="List of dictionaries containing data and configuration for rendering a Chart.js chart in the chat interface."
    )
    force: str = Field(
        default="",
        description="Plain text message that bypasses LLM processing and should be printed exactly as provided in the user interface."
    )


DataToolOutput = Annotated[CallToolResult, ValidationModel]
