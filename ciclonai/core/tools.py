"""Herramientas rápidas: nivel de carga, densidad/% sólidos y recuperación."""
from __future__ import annotations

from .pulp import ValidationError, check_pct, check_positive, require


def mill_charge_level(height: float, diameter: float) -> tuple[float, str | None]:
    """Nivel de carga (%) a partir de la altura libre H y el diámetro efectivo D.

    Devuelve (nivel, advertencia_o_None).
    """
    check_positive(height, "La altura libre")
    check_positive(diameter, "El diámetro")
    require(height < diameter, "La altura libre debe ser menor que el diámetro.")
    level = (1.13 - 1.23 * (height / diameter)) * 100
    warning = None
    if not 0 <= level <= 100:
        warning = "El resultado está fuera del rango normal (0–100 %)."
    return level, warning


def solids_to_density(sg: float, pct_solids: float) -> float:
    """Densidad de pulpa (t/m³) a partir del % sólidos en peso."""
    check_positive(sg, "La gravedad específica")
    check_pct(pct_solids, "El % de sólidos")
    cw = pct_solids / 100
    return 1 / (cw / sg + 1 - cw)


def density_to_solids(sg: float, pulp_density: float) -> float:
    """% sólidos en peso a partir de la densidad de pulpa (t/m³)."""
    check_positive(sg, "La gravedad específica")
    require(sg > 1, "La gravedad específica debe ser mayor que 1.")
    require(1 < pulp_density < sg, "La densidad de pulpa debe estar entre 1 y la gravedad específica.")
    return (1 / pulp_density - 1) / (1 / sg - 1) * 100


def recovery(feed_grade: float, conc_grade: float, tail_grade: float) -> float:
    """Recuperación (%) por la fórmula de dos productos: R = c(f-t) / f(c-t)."""
    check_positive(feed_grade, "La ley de alimentación")
    require(tail_grade >= 0, "La ley de cola no puede ser negativa.")
    if not tail_grade < feed_grade < conc_grade:
        raise ValidationError("Debe cumplirse: ley de cola < ley de alimentación < ley de concentrado.")
    return 100 * conc_grade * (feed_grade - tail_grade) / (feed_grade * (conc_grade - tail_grade))
