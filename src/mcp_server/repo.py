"""Look up package metadata for an installed Python distribution.

Used by the registry to attach a plugin's metadata to every tool it
registers, so MCP clients (e.g. the chat gateway) can render labelled
links and — in the future — surface other useful information like the
package version, summary, authors, or license.

Today only ``[project.urls]`` is read.  The module returns a dict so
new fields can be added without changing the call sites.
"""

import importlib.metadata


def _find_distribution(package_name: str) -> importlib.metadata.Distribution | None:
    """Locate a distribution by either the import name or the
    PEP 503-normalised distribution name (``foo_bar`` ↔ ``foo-bar``)."""
    for candidate in (package_name, package_name.replace("_", "-")):
        try:
            return importlib.metadata.distribution(candidate)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def _project_urls(dist: importlib.metadata.Distribution) -> list[dict] | None:
    """Parse ``Project-URL`` entries into a list of ``{label, url}`` dicts."""
    declared: list[dict] = []
    for entry in dist.metadata.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        label, url = label.strip(), url.strip()
        if label and url:
            declared.append({"label": label, "url": url})
    return declared or None


def get_repo_metadata(package_name: str) -> dict | None:
    """Return metadata for an installed Python distribution.

    Returns ``None`` when the package is not installed.  Otherwise a dict
    whose currently-defined keys are:

        - ``urls``: list of ``{"label": str, "url": str}`` from
          ``[project.urls]``, or ``None`` when the package declares none.

    The dict shape is intentionally open-ended so future fields (version,
    summary, license, authors, …) can be added without breaking callers.
    Callers should use ``meta.get("urls")`` rather than positional access.
    """
    dist = _find_distribution(package_name)
    if dist is None:
        return None
    return {
        # TODO add more metadata in the future (version, license, author, etc)
        "urls": _project_urls(dist)
    }
