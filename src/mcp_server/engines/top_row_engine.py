"""
Top Row engine

Generates an MCP tool that finds the row with the highest or lowest value
in a column and returns details from that row. Supports optional filters
to narrow the rows before finding the top/bottom.

YAML config example:

    engine: top_row
    dataset:
      name: mayor-prestamo-bcie
      source:
        csv: https://example.org/data.csv
        url: https://example.org/dataset
        # optional separator. Pandas will try to guess if not provided.
        separator: ","
    tool:
      name: mayor_prestamo_bcie
      description: "Get the largest approved loan from BCIE with details"
      column: MONTO_BRUTO_USD
      order: max
      format: "{result:,.0f}"
      # Show will generate an option "details" section with this values
      # This details are a list of " - label: value"
      show:
        - column: PAIS
          label: País
        - column: ANIO_APROBACION
          label: Año
        - column: MONTO_BRUTO_USD
          label: Monto
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
        El mayor préstamo aprobado por el BCIE {filter_label} es de {result} dólares:
        {details}. Fue entregado a {row[PAIS]} en {row[ANIO_APROBACION]}.
        Fuente: {source}
"""

import inspect

import pandas as pd

from mcp_server import DataToolOutput
from mcp_server.engines.filters import build_filter_params, apply_filters, build_filter_doc
from mcp_server.results import text_result, force_result


def load_top_row_dataset(mcp, config, yaml_path):
    source = config["dataset"]["source"]
    csv_url = source["csv"]
    source_url = source.get("url", "")
    separator = source.get("separator")

    tool_cfg = config["tool"]
    tool_name = tool_cfg["name"]
    tool_desc = tool_cfg["description"]
    column = tool_cfg["column"]
    order = tool_cfg.get("order", "max")
    fmt = tool_cfg.get("format", "{result}")
    show = tool_cfg.get("show", [])
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

        col = df[column].dropna()
        idx = col.idxmax() if order == "max" else col.idxmin()
        row = df.loc[idx]

        result = fmt.format(result=row[column])

        details_lines = []
        header = []
        values = []
        for field in show:
            label = field.get("label", field["column"])
            field_fmt = field.get("format", "{result}")
            value = field_fmt.format(result=row[field["column"]])
            details_lines.append(f"  - {label}: {value}")
            header.append(label)
            values.append(value)
        details = "\n".join(details_lines)

        context = {
            "result": result,
            "details": details,
            "filter_label": filter_label,
            "source": source_url,
            "row": row.to_dict(),
        }

        if response_template:
            text = response_template.format(**context)
        else:
            text = f"Top result {filter_label}: {result}\n{details}"

        table = [header, values] if header else None
        return text_result(text, source_url, table=table)

    tool_fn.__signature__ = inspect.Signature(filter_params, return_annotation=DataToolOutput)
    tool_fn.__annotations__["return"] = DataToolOutput
    tool_fn.__name__ = tool_name
    tool_fn.__doc__ = build_filter_doc(tool_cfg, tool_desc)
    mcp.tool()(tool_fn)

    return 1
