import inspect
import logging

from mcp.server.fastmcp import FastMCP

from mcp_server import DataToolOutput
from mcp_server.repo import get_repo_metadata

log = logging.getLogger(__name__)


class PluginsRegistry:
    """Root registry: owns the FastMCP server and the set of all plugins.

    ``server.py`` builds exactly one of these, then calls ``for_plugin()`` once
    per plugin to hand each a namespaced :class:`Plugin`. After every
    plugin has loaded, ``build_instructions()`` composes the server's MCP
    ``instructions`` field from each plugin's self-description.
    """

    def __init__(self, mcp: FastMCP):
        self._mcp = mcp
        self._plugins: dict[str, dict] = {}

    def for_plugin(self, package_name: str) -> "Plugin":
        """Return a per-plugin :class:`Plugin` that namespaces everything
        it registers under ``package_name`` while sharing this FastMCP server.
        """
        metadata = self._plugins.get(package_name)
        if metadata is None:
            metadata = get_repo_metadata(package_name) or {}
            self._plugins[package_name] = metadata
        return Plugin(self._mcp, namespace=package_name, plugin_metadata=metadata)

    def build_instructions(self) -> str:
        """Compose the server's MCP ``instructions`` string from the metadata
        each plugin self-declares via ``Plugin.set_plugin_info``.
        """
        blocks = []
        for namespace, meta in self._plugins.items():
            if not meta:
                continue
            lines = []
            # The plugin's own persona/doctrine, injected verbatim and first so
            # it frames everything below (scope, units caveats, off-topic rule).
            instructions = meta.get("instructions")
            if instructions:
                lines.append(instructions.strip())
            description = meta.get("description")
            if description:
                lines.append(description.strip())
            questions = meta.get("sample_questions") or []
            if questions:
                lines.append("Example questions it can answer:")
                lines.extend(f"- {q}" for q in questions)
            if lines:
                blocks.append("\n".join(lines))

        if not blocks:
            return ""

        # Tool names are namespaced per plugin, so the fallback tool surfaces as
        # ``<plugin>_no_tool_disponible``. Reference it by suffix, not exact name.
        preamble = (
            "You are a data assistant. Answer every question using at least "
            "one of the available tools; never answer factual questions from "
            "your own knowledge. If no tool fits, call the fallback tool whose "
            "name ends in `no_tool_disponible` with a short reason. The "
            "available tools cover these domains:"
        )
        return preamble + "\n\n" + "\n\n".join(blocks)


class Plugin:
    """Per-plugin registry: namespaces one plugin's tools/resources and enforces
    the ToolOutput contract.
    """

    def __init__(self, mcp: FastMCP, namespace: str, plugin_metadata: dict):
        self._mcp = mcp
        self._namespace = namespace
        self._plugin_metadata = plugin_metadata

    def set_plugin_info(
        self,
        description: str | None = None,
        sample_questions: list[str] | None = None,
        instructions: str | None = None,
    ) -> None:
        """Self-describe the plugin so MCP clients can render a richer catalog.
        """
        if description is not None:
            self._plugin_metadata["description"] = description
        else:
            log.warning(f"Plugin {self._namespace} did not provide a description")
        if sample_questions is not None:
            self._plugin_metadata["sample_questions"] = list(sample_questions)
        else:
            log.warning(f"Plugin {self._namespace} did not provide sample questions")
        if instructions is not None:
            self._plugin_metadata["instructions"] = instructions
        else:
            log.warning(f"Plugin {self._namespace} did not provide instructions")

    def tool(self):
        """Decorator that registers a function with FastMCP after validating its
        return type annotation.

        If the return annotation is not ``ToolOutput``, logs a warning and returns
        the original function **without** registering it with FastMCP.

        The function's ``__name__`` is prefixed with the plugin namespace before
        being handed to FastMCP, so we avoid name collisions.
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
