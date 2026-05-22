import inspect
import logging

from mcp.server.fastmcp import FastMCP

from mcp_server import DataToolOutput
from mcp_server.repo import get_repo_metadata

log = logging.getLogger(__name__)


class ToolRegistry:
    """Controls tool registration and enforces the ToolOutput contract.

    Wraps a FastMCP instance and intercepts every ``tool()`` call to verify that
    the function declares ``-> DataToolOutput`` in its return annotation.  Validation
    happens at registration time (server startup).

    Tools that do not declare the correct return annotation are **not registered**
    and a warning is logged instead.  This allows the server to start and serve
    only its valid tools.

    Plugins and engines must use this registry instead of calling ``mcp.tool()``
    directly.  The ``tool()`` method returns the same decorator API so existing
    patterns (``@registry.tool()`` and ``registry.tool()(fn)``) work unchanged.
    Use ``for_plugin()`` so every tool that plugin registers is automatically namespaced.
    """

    def __init__(self, mcp: FastMCP, namespace: str | None = None, plugin_metadata: dict | None = None):
        self._mcp = mcp
        self._namespace = namespace
        self._plugin_metadata = plugin_metadata

    def for_plugin(self, package_name: str) -> "ToolRegistry":
        """Return a sub-registry that namespaces tools under the plugin package.

        The returned registry shares the same FastMCP instance, so all tools
        end up on the same server, but their names are prefixed with the
        namespace derived from ``package_name``.
        Allow using metadata from the remote repo
        """
        return ToolRegistry(
            self._mcp,
            namespace=package_name,
            plugin_metadata=get_repo_metadata(package_name),
        )

    def set_plugin_info(self, description: str | None = None, sample_questions: list[str] | None = None) -> None:
        """Self-describe the plugin so MCP clients can render a richer catalog.

        Plugins call this from ``register_tools()`` before declaring their tools.
        The values are merged into ``_meta.plugin_metadata`` alongside the URLs
        already read from ``[project.urls]`` — the server stays agnostic; only
        the plugin knows what its description and sample questions are.

        Call this BEFORE any ``@registry.tool()`` decorators so every tool's
        meta payload picks up the new fields.
        """
        if self._plugin_metadata is None:
            self._plugin_metadata = {}
        if description is not None:
            self._plugin_metadata["description"] = description
        if sample_questions is not None:
            self._plugin_metadata["sample_questions"] = list(sample_questions)

    def tool(self):
        """Decorator that registers a function with FastMCP after validating its
        return type annotation.

        If the return annotation is not ``ToolOutput``, logs a warning and returns
        the original function **without** registering it with FastMCP.

        When this registry was obtained via ``for_plugin``, the
        function's ``__name__`` is prefixed with the plugin namespace before
        being handed to FastMCP, so we avoind name collisions.
        """
        def decorator(fn):
            sig = inspect.signature(fn)
            return_annotation = sig.return_annotation
            if return_annotation is inspect.Parameter.empty or return_annotation is not DataToolOutput:
                got = (
                    "none"
                    if return_annotation is inspect.Parameter.empty
                    else return_annotation.__name__
                )
                log.warning(
                    "Skipping tool '%s': return annotation must be DataToolOutput, got %s",
                    fn.__name__,
                    got,
                )
                return fn
            # If defined, apply the plugin namespace
            if self._namespace and not fn.__name__.startswith(self._namespace + "_"):
                fn.__name__ = f"{self._namespace}_{fn.__name__}"

            # Use the internal mcp "meta" to preserve metadata
            # and eventually use it in chat gateway or other remote clients
            tool_meta = None
            if self._namespace:
                tool_meta = {"plugin": self._namespace}
                if self._plugin_metadata:
                    tool_meta["plugin_metadata"] = self._plugin_metadata

            log.info(f" - Registered: [{fn.__name__}]")
            return self._mcp.tool(meta=tool_meta)(fn)
        return decorator

    def _resource_uri(self, uri: str) -> str:
        """Normalize a plugin-supplied URI to ``mcp://<plugin>/<path>``.

        Plugins pass a short path (``"ben/libro-2024.pdf"``); the registry
        builds the full URI so namespacing is automatic and consistent across
        plugins. A pre-built ``mcp://`` URI is accepted as-is for callers that
        want explicit control.
        """
        if uri.startswith("mcp://") or "://" in uri:
            return uri
        if self._namespace is None:
            return f"mcp://core/{uri.lstrip('/')}"
        return f"mcp://{self._namespace}/{uri.lstrip('/')}"

    def resource(
        self,
        uri: str,
        *,
        name: str | None = None,
        description: str | None = None,
        mime_type: str | None = None,
        annotations: dict | None = None,
    ):
        """Decorator that registers a resource with FastMCP, namespaced by plugin.

        Resources are static (or lazily computed) content addressed by URI:
        documents, methodology PDFs, reference datasets, etc. Unlike tools,
        the LLM does NOT autodiscover them - UI tools will be able list them.
        Plugins declare resources from a top-level ``register_resources(registry)``
        function.

        The decorated function is the lazy loader: it returns ``str`` for
        text content or ``bytes`` for binary (PDF, image, etc.). It runs
        only when a client calls ``resources/read``.

        Args:
            uri: Short path under the plugin namespace, e.g. ``"ben/libro-2024.pdf"``.
                Becomes ``mcp://<plugin>/ben/libro-2024.pdf`` on the wire.
            name: Human-readable label shown in the gateway sidebar.
            description: One/two sentences describing what the resource is.
            mime_type: e.g. ``"application/pdf"``, ``"text/markdown"``, ``"text/csv"``.
            annotations: Free-form metadata persisted in the resource's ``_meta``
                so the gateway can render an "Open original" link, publisher
                badge, etc. Conventional keys: ``source_url``, ``publisher``,
                ``year``, ``language``.
        """
        def decorator(fn):
            full_uri = self._resource_uri(uri)

            if self._namespace and not fn.__name__.startswith(self._namespace + "_"):
                fn.__name__ = f"{self._namespace}_{fn.__name__}"

            res_meta: dict = {}
            if self._namespace:
                res_meta["plugin"] = self._namespace
            if self._plugin_metadata:
                res_meta["plugin_metadata"] = self._plugin_metadata
            if annotations:
                res_meta["annotations"] = annotations

            log.info(f" - Registered resource: [{full_uri}]")
            return self._mcp.resource(
                uri=full_uri,
                name=name,
                description=description,
                mime_type=mime_type,
                meta=res_meta or None,
            )(fn)
        return decorator
