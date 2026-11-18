"""Convierte resultados del núcleo en tablas para HTML y Excel."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .core.circuits import CircuitResult
from .core.metallurgical import CONTENT_UNIT, MetallurgicalResult
from .core.pulp import PULP_ROWS


@dataclass
class Table:
    headers: list[str]
    rows: list[list]  # primera celda = etiqueta, resto números (o None)
    highlight_rows: set[int] = field(default_factory=set)


def circuit_table(result: CircuitResult) -> Table:
    streams = list(result.streams.values())
    rows = [[label, *(getattr(s, key) for s in streams)] for key, label in PULP_ROWS]
    return Table(["Característica", *(s.name for s in streams)], rows)


def metallurgical_table(result: MetallurgicalResult) -> Table:
    els, units = result.elements, result.units
    headers = ["Producto", "Masa (t)", "% Peso",
               *(f"Ley {e} ({u})" for e, u in zip(els, units)),
               *(f"Contenido {e} ({CONTENT_UNIT[u]})" for e, u in zip(els, units)),
               *(f"Distribución {e} (%)" for e in els),
               "Razón de conc."]
    rows = [[p.name, p.mass, p.weight_pct, *p.grades, *p.contents, *p.distributions, p.ratio]
            for p in result.products]
    return Table(headers, rows, highlight_rows={0})


def to_excel(title: str, inputs: list[tuple[str, float, str]], table: Table,
             extras: list[tuple[str, float]] = ()) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Resultados"
    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="0F9D58")

    ws.append([f"CiclonAI — {title}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([f"Generado: {datetime.now():%Y-%m-%d %H:%M}"])
    ws.append([])
    ws.append(["Datos de entrada"])
    ws.cell(ws.max_row, 1).font = bold
    for label, value, unit in inputs:
        ws.append([label, value, unit])
    ws.append([])

    ws.append(table.headers)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(wrap_text=True, horizontal="center")
    for row in table.rows:
        ws.append(row)
        for cell in ws[ws.max_row][1:]:
            cell.number_format = "#,##0.000"
    for label, value in extras:
        ws.append([label, value])
        ws.cell(ws.max_row, 1).font = bold
        ws.cell(ws.max_row, 2).number_format = "0.000"

    ws.column_dimensions["A"].width = 28
    for col in range(2, len(table.headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 16

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
