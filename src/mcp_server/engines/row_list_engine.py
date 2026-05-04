"""
Row List engine

Generates an MCP tool that returns a list of rows from a CSV, formatted
per-row using a configurable columns list. Supports optional filters.

YAML config example:

    engine: row_list
    dataset:
      name: prestamos-bcie
      source:
        csv: https://example.org/data.csv
        url: https://example.org/dataset
        # optional separator. Pandas will try to guess if not provided.
        separator: ","
    tool:
      name: lista_prestamos_bcie
      description: "Get list of loans approved by BCIE"
      columns:
        - column: ANIO_APROBACION
          label: Año
        - column: PAIS
          label: País
        - column: MONTO_BRUTO_USD
          label: Monto
          format: "${result:,.2f}"
        - column: SECTOR
          label: Sector
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
            same: "en {year_from}"
      limit: 20        # optional, default 20. Use 0 for no limit.
      sort:
        column: ANIO_APROBACION
        order: asc     # asc (default) or desc
      response: |
        El BCIE ha aprobado {count} préstamos {filter_label}:
        {list}
        Fuente: {source}
"""

import inspect
import pandas as pd
from mcp_server import DataToolOutput
from mcp_server.engines.filters import build_filter_params, apply_filters, build_filter_doc
from mcp_server.results import text_result, force_result


def load_row_list_dataset(mcp, config, yaml_path):
    source = config["dataset"]["source"]
    csv_url = source["csv"]
    source_url = source.get("url", "")
    separator = source.get("separator")

    tool_cfg = config["tool"]
    tool_name = tool_cfg["name"]
    tool_desc = tool_cfg["description"]
    columns = tool_cfg.get("columns", [])
    limit = tool_cfg.get("limit", 20)
    sort_cfg = tool_cfg.get("sort")
    response_template = tool_cfg.get("response")

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

        rows_lines = []
        total = len(df)
        if sort_cfg:
            df = df.sort_values(
                by=sort_cfg["column"],
                ascending=sort_cfg.get("order", "asc") == "asc",
            )
        display_df = df if not limit else df.head(limit)

        header = [f.get("label", f["column"]) for f in columns]
        table_data = []
        for _, row in display_df.iterrows():
            parts = []
            row_cells = []
            for field in columns:
                label = field.get("label", field["column"])
                field_fmt = field.get("format", "{result}")
                value = field_fmt.format(result=row[field["column"]])
                parts.append(f"{label}: {value}")
                row_cells.append(value)
            rows_lines.append("  - " + " | ".join(parts))
            table_data.append(row_cells)

        if limit and total > limit:
            rows_lines.append(f"  ... y {total - limit} más.")

        list_str = "\n".join(rows_lines)

        context = {
            "count": total,
            "list": list_str,
            "filter_label": filter_label,
            "source": source_url,
        }

        if response_template:
            text = response_template.format(**context)
        else:
            text = f"{total} resultados {filter_label}:\n{list_str}"

        table = [header] + table_data if header else None
        return text_result(text, source_url, table=table)

    tool_fn.__signature__ = inspect.Signature(filter_params, return_annotation=DataToolOutput)
    tool_fn.__annotations__["return"] = DataToolOutput
    tool_fn.__name__ = tool_name
    tool_fn.__doc__ = build_filter_doc(tool_cfg, tool_desc)
    mcp.tool()(tool_fn)

    return 1
