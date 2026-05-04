# Simple MCP Server to answer questions with data

**Note:** This project is currently in early research phase. Breaking changes are expected.

MCP Server that allows admins to register custom tools, by installing python packages, to consistently and accurately answer user questions using data.

## Running locally

### Install the project using UV
Sync dependencies:
```bash
uv sync
```

Run the tests:
```bash
uv run pytest
```

Run the server:
```bash
uv run mcp-ckan
```

## Server Settings

This (and other settings) can be configured via the `settings.py` file (or environment variables if defined).

- Set `MCP_TRANSPORT=stdio` (default) for local development and Claude Desktop integration
- Set `MCP_TRANSPORT=http` for remote infrastructure deployment
- Set `MCP_HOST` and `MCP_PORT` to control the server's host and port (default: 127.0.0.1:8063).

## Testing the server

### Test in VSCode with GitHub Copilot

Create the file `.vscode/mcp.json`:

```json
{
  "servers": {
    "mybcie-server": {
      "url": "http://127.0.0.1:8063",
      "type": "http"
    }
  },
  "inputs": []
}
```

### Run MCP Inspector

This tool allows you to test tools locally without any AI model.

```bash
npx @modelcontextprotocol/inspector uv run mcp-ckan
```

## Fetching Remote Tools

To register remote tools just install a Python package that can register MCP tools for your particular datasets.
You can see an example at [https://github.com/okfn/mcp-ckan-examplepythontools](https://github.com/okfn/mcp-ckan-examplepythontools)

In a nutshell, you can extend by installing python plugins:

```bash
uv pip install "git+https://github.com/okfn/mcp-ckan"
uv pip install "git+https://github.com/okfn/mcp-ckan-examplepythontools"
uv run mcp-ckan
```

The MCP server is configured to load the tools at startup time by iterating throug all the installed python packages looking for `mcp_ckan` entrypoints.

# Tutorial: Developing a new MCP CKAN plugin

## Creating a new plugin

1. Create a new pip-installable package:

```bash
uv init --package mcp-ckan-exampleplugin
cd mcp-ckan-exampleplugin
```

2. Install the mcp-ckan dependency:

```bash
uv add https://github.com/okfn/mcp-ckan.git
```

3. Define a `register_tools(mcp)` function that register tools in a MCP Server registry:

**Note:** This MCP server enforces [structured output](https://github.com/modelcontextprotocol/python-sdk?tab=readme-ov-file#structured-output)
so the `DataToolOutput` annotation and the `CallToolResult` return value are mandatory. If the function does not have the type annotation `-> DataToolOutput`
it will not be registered in the MCP server.

```python
from mcp.types import CallToolResult, TextContent
from mcp_server import DataToolOutput

def register_tools(registry):

    @registry.tool()
    def greetings_from_examplepythontools() -> DataToolOutput:
        """Return a greetings message to the user."""
        source = "https://example.org/link/to/data"
        return CallToolResult(
            content=[TextContent(type="text", text="Hello from an Example Plugin!")],
            structuredContent={"sources": [source]},
        )
```

4. Register a new `mcp_ckan` entrypoint in the `pyproject.toml` file that calls the newly created `register_tools` function.

```toml
[project.entry-points.mcp_ckan]
mcp-ckan-examplepythontools = "mcp_ckan_examplepythontools:register_tools"
```

5. Run the mcp-ckan server (inside the newly created package folder)
```
MCP_TRANSPORT=http uv run mcp-ckan
```

6. Run MCP Inspector to test the tool
```
npx @modelcontextprotocol/inspector
```

7. Navigate to the MCP Inspector webpage and connect to `http://127.0.0.1:8063` (no `/mcp`) using `Streamable HTTP` transport type

## Tool return values

Using the `python-sdk` cannonical way of building results (this is, the `CallToolResult` object) can get quite verbose quite fast. For
that reason, the `mcp_server` provides an optional set of functions to use.

The two following tools and return values are possible:

```python
@registry.tool()
def hello_world() -> DataToolOutput:
    """Return a hello world value. """
    source = "https://example.org/link/to/data"
    return CallToolResult(
        content=[TextContent(type="text", text="Hello world!!")],
        structuredContent={"sources": [source]},
    )
```

```python
from mcp_server.results import text_result

@registry.tool()
def hello_world() -> DataToolOutput:
    """Return a hello world value. """
    source = "https://example.org/link/to/data"
    return text_result("Hello world!!", source=source)
```

## DataToolOutput

This MCP Server uses a `DataToolOutput` annotation and a `ValidationModel` to enforce a standardized contract between plugins and the server. The schema is still in development so changes are expected.

### How it works

`DataToolOutput` is defined as:

```python
DataToolOutput = Annotated[CallToolResult, ValidationModel]
```

This combines the MCP SDK's `CallToolResult` return type with a `ValidationModel` (a Pydantic model) using Python's `Annotated` generic. The MCP SDK uses this pattern to enable [structured output](https://github.com/modelcontextprotocol/python-sdk?tab=readme-ov-file#structured-output) — validating that the `structuredContent` field conforms to the `ValidationModel` schema.

The `ToolRegistry` enforces this annotation at startup time by inspecting each tool function's return type. Tools that do not declare `-> DataToolOutput` are **skipped** with a warning and will not be registered. Because Python is dynamically typed, the server cannot validate actual runtime return values, but enforcing annotations is a good-enough approach for early implementations.

### CallToolResult: `content` and `structuredContent`

Every tool must return a `CallToolResult` with two fields:

- **`content`** (`list[TextContent | ImageContent | ...]`): The human-readable output that the LLM uses to understand and respond to the user. This is always required.
- **`structuredContent`** (`dict conforming to ValidationModel`): A machine-parseable JSON payload that the chat interface uses to render structured elements like tables, charts, and source links. This is optional but recommended.

Both fields serve different consumers: `content` is for the **LLM**, while `structuredContent` is for the **UI**.

Providing both gives flexibility by ensuring the AI can answer the question and the developers can render it in a structured way.

For more information on `content`/`structuredContent`:

- [How Langchain uses this fields](https://forum.langchain.com/t/why-can-the-model-see-the-structured-content-returned-by-the-mcp-tool/3076).
- [User Guidance community discussion](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1624)

### ValidationModel fields

The `structuredContent` dict must conform to the following schema:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sources` | `list` | *required* | Information pointing to the original source of the data. |
| `table` | `list` | `[]` | Two-dimensional list (list of rows) representing tabular data. Each row should be a list of cell values. |
| `charts` | `list` | `[]` | *(in development)* Dictionaries containing data and configuration for rendering Chart.js charts. |
| `force` | `str` | `""` | Plain text message that bypasses LLM processing and is printed exactly as provided. |

### Examples

**Minimal — text with a data source:**

```python
from mcp.types import CallToolResult, TextContent
from mcp_server import DataToolOutput

def get_gdp() -> DataToolOutput:
    """Return the latest GDP value."""
    return CallToolResult(
        content=[TextContent(type="text", text="The GDP for 2024 is $1.2 trillion.")],
        structuredContent={"sources": ["https://example.org/gdp-data"]},
    )

def register_tools(registry):
    registry.tool()(get_gdp)
```

**Table data — returning tabular results:**

```python
from mcp.types import CallToolResult, TextContent
from mcp_server import DataToolOutput

def register_tools(registry):
    @registry.tool()
    def list_cities() -> DataToolOutput:
        """Return the top 3 cities by population."""
        return CallToolResult(
            content=[TextContent(type="text", text="Found 3 cities sorted by population.")],
            structuredContent={
                "sources": ["https://example.org/cities-data"],
                "table": [
                    ["City", "Population"],
                    ["Tokyo", "37400068"],
                    ["Delhi", "30290936"],
                    ["Shanghai", "27058479"],
                ],
            },
        )
```

You can check the [source code](./src/mcp_server/__init__.py) for more information on `DataToolOutput`.

