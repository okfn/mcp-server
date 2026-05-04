"""
Unique Values engine

Generates an MCP tool that returns the unique values from a single column
in a CSV file. Supports optional filters to narrow the rows before
extracting unique values.

YAML config example:

    engine: unique_values
    dataset:
      name: paises-prestamos-bcie
      source:
        csv: https://example.org/data.csv
        url: https://example.org/dataset
        # optional separator. Pandas will try to guess if not provided.
        separator: ";"
    tool:
      name: paises_con_prestamos_bcie
      description: "Get list of all countries that receive loans from BCIE"
      column: PAIS
      limit: 15
      filters:
        - column: ANIO_APROBACION
          param: year
          type: int_range
          description: "Year of approval"
          label:
            both: "entre {year_from} y {year_to}"
            from_only: "desde {year_from}"
            to_only: "hasta {year_to}"
      response: |
        El BCIE otorgó préstamos a {count} países {filter_label}:
        {list}
        Fuente: {source}
"""

import inspect

import pandas as pd

from mcp_server import DataToolOutput
from mcp_server.engines.filters import build_filter_params, apply_filters, build_filter_doc
from mcp_server.results import text_result


def load_unique_values_dataset(mcp, config, yaml_path):
    source = config["dataset"]["source"]
    csv_url = source["csv"]
    source_url = source.get("url", "")
    separator = source.get("separator")

    tool_cfg = config["tool"]
    tool_name = tool_cfg["name"]
    tool_desc = tool_cfg["description"]
    column = tool_cfg["column"]
    limit = tool_cfg.get("limit", 0)
    response_template = tool_cfg.get("response")

    filter_params = build_filter_params(tool_cfg)

    encoding = source.get("encoding")

    def tool_fn(**kwargs):
        read_kwargs = {"sep": separator} if separator else {}
        if encoding:
            read_kwargs["encoding"] = encoding
        df = pd.read_csv(csv_url, **read_kwargs)
        df, filter_label = apply_filters(df, tool_cfg, kwargs)

        values = sorted(df[column].dropna().unique())
        list_values = values[:limit] + ["..."] if limit > 0 and len(values) > limit else values
        list_str = "\n".join(f"  - {v}" for v in list_values)

        context = {
            "count": len(values),
            "list": list_str,
            "filter_label": filter_label,
            "source": source_url,
        }

        if response_template:
            text = response_template.format(**context)
        else:
            text = f"Found {len(values)} unique values {filter_label}:\n{list_str}"

        table = [[column]] + [[v] for v in list_values]
        return text_result(text, source_url, table=table)

    tool_fn.__signature__ = inspect.Signature(filter_params, return_annotation=DataToolOutput)
    tool_fn.__annotations__["return"] = DataToolOutput
    tool_fn.__name__ = tool_name
    tool_fn.__doc__ = build_filter_doc(tool_cfg, tool_desc)
    mcp.tool()(tool_fn)

    return 1
