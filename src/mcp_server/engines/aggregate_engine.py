"""
Aggregate engine

Generates an MCP tool that computes a single aggregate value (sum, avg,
count) from one column in a CSV file. Supports optional filters to
narrow the rows before aggregating.

YAML config example:

    engine: aggregate
    dataset:
      name: total-prestamos-bcie
      source:
        csv: https://example.org/data.csv
        url: https://example.org/dataset
        # optional separator. Pandas will try to guess if not provided.
        separator: ","
    tool:
      name: total_prestamos_bcie
      description: "Get total approved loans from BCIE in USD"
      column: MONTO_BRUTO_USD
      aggregation: sum
      format: "${result:,.2f}"
      filters:
        - column: PAIS
          param: country
          description: "Country name, e.g. Honduras, Costa Rica"
          label: "para {value}"
        - column: ANIO_APROBACION
          param: year
          type: int_range
          description: "Year of approval"
          label:
            both: "entre {year_from} y {year_to}"
            from_only: "desde {year_from}"
            to_only: "hasta {year_to}"
      response: |
        El monto total de préstamos aprobados por el BCIE {filter_label} es {result}.
        Fuente: {source}
"""

import inspect

import pandas as pd

from mcp_server import DataToolOutput
from mcp_server.engines.filters import build_filter_params, apply_filters, build_filter_doc
from mcp_server.results import text_result, force_result


AGGREGATIONS = {
    "sum": lambda s: s.sum(),
    "avg": lambda s: s.mean(),
    "count": lambda s: len(s),
}


def load_aggregate_dataset(mcp, config, yaml_path):
    source = config["dataset"]["source"]
    csv_url = source["csv"]
    source_url = source.get("url", "")
    separator = source.get("separator")

    tool_cfg = config["tool"]
    tool_name = tool_cfg["name"]
    tool_desc = tool_cfg["description"]
    column = tool_cfg["column"]
    aggregation = tool_cfg.get("aggregation", "sum")
    fmt = tool_cfg.get("format", "{result}")
    response_template = tool_cfg.get("response")

    agg_fn = AGGREGATIONS.get(aggregation)
    if not agg_fn:
        raise ValueError(f"Unknown aggregation '{aggregation}'. Available: {list(AGGREGATIONS.keys())}")
    filter_params = build_filter_params(tool_cfg)

    encoding = source.get("encoding")

    def tool_fn(**kwargs):
        read_kwargs = {"sep": separator} if separator else {}
        if encoding:
            read_kwargs["encoding"] = encoding
        df = pd.read_csv(csv_url, **read_kwargs)
        try:
            df, filter_label = apply_filters(df, tool_cfg, kwargs)
        except ValueError as e:
            return force_result(f"Error en los parámetros: {e}", source_url)

        if df.empty:
            label = f" {filter_label}" if filter_label else ""
            return force_result(f"No se encontraron resultados{label}.", source_url)

        value = agg_fn(df[column].dropna())
        result = fmt.format(result=value)

        context = {
            "result": result,
            "filter_label": filter_label,
            "source": source_url,
        }

        if response_template:
            text = response_template.format(**context)
        else:
            text = f"Result {filter_label}: {result}"
        return text_result(text, source_url)

    tool_fn.__signature__ = inspect.Signature(filter_params, return_annotation=DataToolOutput)
    tool_fn.__annotations__["return"] = DataToolOutput
    tool_fn.__name__ = tool_name
    tool_fn.__doc__ = build_filter_doc(tool_cfg, tool_desc)
    mcp.tool()(tool_fn)

    return 1
