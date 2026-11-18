"""Definición declarativa de campos numéricos y su lectura desde request.form."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    default: float
    unit: str = ""
    help: str = ""


@dataclass(frozen=True)
class Group:
    title: str
    fields: tuple[Field, ...]
    note: str = ""


def all_fields(groups: list[Group]) -> list[Field]:
    return [f for g in groups for f in g.fields]


def to_float(raw: str | None) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw.strip().replace(",", "."))
    except ValueError:
        return None


def parse(fields: list[Field], form) -> tuple[dict[str, float], dict[str, str], list[str]]:
    """Devuelve (valores numéricos, valores crudos para re-llenar el formulario, errores)."""
    values, raw, errors = {}, {}, []
    for f in fields:
        text = form.get(f.name, "")
        raw[f.name] = text
        number = to_float(text)
        if number is None:
            errors.append(f"«{f.label}» debe ser un número.")
        else:
            values[f.name] = number
    return values, raw, errors


def defaults(fields: list[Field]) -> dict[str, str]:
    return {f.name: f"{f.default:g}" for f in fields}
