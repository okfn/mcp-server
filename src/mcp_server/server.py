"""
MCP Server with dynamic tool loading

This server automatically discovers and loads tools from installed python packages.
Each package should have an `mcp_server` entrypoint with a register_tools(registry) function.
"""
import importlib
import logging
import pkgutil

from mcp.server.fastmcp import FastMCP

from mcp_server.engines import load_dataset
from mcp_server.registry import PluginsRegistry
from mcp_server.settings import MCP_TRANSPORT, MCP_HOST, MCP_PORT

log = logging.getLogger(__name__)


def load_python_plugins(registry):
    """Load Python tools defined in plugins.
    Each plugin defines a namespaced sub-registry so we avoid name colition
    """
    for entry_point in importlib.metadata.entry_points():
        if entry_point.group == "mcp_server":
            log.info(f"[{entry_point.module}] - python tools.")
            register_tools = entry_point.load()
            plugin_registry = registry.for_plugin(entry_point.module)
            register_tools(plugin_registry)


def load_python_resources(registry):
    """Load Python resources defined in plugins.

    Optional sibling of ``load_python_plugins``: if the plugin's top-level
    module exposes a ``register_resources(registry)`` callable, the server
    invokes it with the same namespaced sub-registry used for tools. Plugins
    with no documents/PDFs to expose simply don't define the function.
    """
    for entry_point in importlib.metadata.entry_points():
        if entry_point.group != "mcp_server":
            continue
        module = importlib.import_module(entry_point.module)
        register_resources = getattr(module, "register_resources", None)
        if not callable(register_resources):
            continue
        log.info(f"[{entry_point.module}] - python resources.")
        plugin_registry = registry.for_plugin(entry_point.module)
        register_resources(plugin_registry)


def load_yaml_plugins(registry):
    """Load YAML tools defined in plugins.

    The YAML tools are based on our engines. It will use a name-convention look for plugin
    packages (like Flask).

    https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-naming-convention
    Each plugin's YAMLs are loaded against a namespaced sub-registry,
    so YAML-declared tool names get the same prefix as Python ones.
    """
    discovered_plugins = [name for _, name, _ in pkgutil.iter_modules() if name.startswith('mcp_server_')]
    for plugin in discovered_plugins:
        resources = importlib.resources.files(plugin)
        plugin_registry = registry.for_plugin(plugin)
        for resource in resources.rglob('*.yaml'):
            log.info(f"[{plugin}] - {resource.name}")
            load_dataset(plugin_registry, resource)


def create_mcp_server(host, port):
    """Create MCP server with settings from environment variables"""
    mcp = FastMCP("Demo", host=host, port=port, streamable_http_path="/")
    registry = PluginsRegistry(mcp)
    load_python_plugins(registry)
    load_python_resources(registry)
    load_yaml_plugins(registry)
    # Publish the composed doctrine on the standard MCP `instructions` field
    mcp._mcp_server.instructions = registry.build_instructions()
    return mcp


# Create server instance
mcp = create_mcp_server(MCP_HOST, MCP_PORT)


def main():
    log.info("=" * 60)
    log.info(f"Settings: host={MCP_HOST}, port={MCP_PORT} transport={MCP_TRANSPORT}")
    log.info("=" * 60)

    if MCP_TRANSPORT == "http":
        # HTTP mode for infrastructure deployment
        mcp.run(transport="streamable-http")
    else:
        # stdio mode (default) for local development
        mcp.run(transport="stdio")
