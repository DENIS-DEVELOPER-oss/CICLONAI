"""Balance metalúrgico de N concentrados y N elementos (más una cola).

Resuelve el sistema lineal  A·x = b  donde x son las fracciones en peso de cada
producto respecto a la alimentación:
    Σ x_j          = 1
    Σ x_j · ley_ij = ley_alim_i     (para cada elemento i)
Para N = 1 equivale a la fórmula clásica de dos productos (f - t)/(c - t).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .pulp import ValidationError, check_positive, require

ELEMENTS = ["Cu", "Au", "Ag", "Pb", "Zn", "Sn", "Mo", "Fe"]
UNITS = ["%", "g/t", "Oz/Tn"]
# Unidad del contenido metálico según la unidad de ley.
CONTENT_UNIT = {"%": "t", "g/t": "g", "Oz/Tn": "Oz"}


def _content(mass_t: float, grade: float, unit: str) -> float:
    return mass_t * grade / 100 if unit == "%" else mass_t * grade


@dataclass
class Product:
    name: str
    mass: float  # t secas
    weight_pct: float
    grades: list[float]
    contents: list[float]
    distributions: list[float]
    ratio: float | None  # razón de concentración F/C (solo concentrados)


@dataclass
class MetallurgicalResult:
    elements: list[str]
    units: list[str]
    products: list[Product]  # alimentación, concentrados..., cola

    @property
    def recoveries(self) -> list[float]:
        """Recuperación del elemento i en su concentrado i."""
        return [self.products[i + 1].distributions[i] for i in range(len(self.elements))]


def metallurgical_balance(feed_tonnage: float, moisture: float, elements: list[str], units: list[str],
                          feed_grades: list[float], conc_grades: list[list[float]],
                          tail_grades: list[float]) -> MetallurgicalResult:
    """conc_grades[j][i] = ley del elemento i en el concentrado j."""
    n = len(elements)
    require(len(set(elements)) == n, "Los elementos seleccionados deben ser distintos.")
    require(len(conc_grades) == n and len(feed_grades) == n and len(tail_grades) == n,
            "Número de leyes inconsistente.")
    check_positive(feed_tonnage, "La alimentación")
    require(0 <= moisture < 100, "La humedad debe estar entre 0 y 100 %.")
    all_grades = [*feed_grades, *tail_grades, *(g for row in conc_grades for g in row)]
    require(all(g >= 0 for g in all_grades), "Las leyes no pueden ser negativas.")

    columns = [*conc_grades, tail_grades]  # una columna por producto
    a = np.array([[1.0] * (n + 1)] + [[col[i] for col in columns] for i in range(n)])
    b = np.array([1.0, *feed_grades])
    if not np.isfinite(np.linalg.cond(a)) or np.linalg.cond(a) > 1e12:
        raise ValidationError("El sistema no tiene solución única: revise que las leyes de los "
                              "productos no sean iguales o proporcionales entre sí.")
    x = np.linalg.solve(a, b)
    if (x < -1e-9).any():
        raise ValidationError("El balance da masas negativas para algún producto: las leyes "
                              "ingresadas no son consistentes con la alimentación.")

    dry_feed = feed_tonnage * (100 - moisture) / 100
    names = ["Alimentación", *(f"Concentrado {e}" if n > 1 else "Concentrado" for e in elements), "Cola"]
    masses = [dry_feed, *(float(xi) * dry_feed for xi in x)]
    grades = [list(feed_grades), *columns]
    feed_contents = [_content(dry_feed, feed_grades[i], units[i]) for i in range(n)]

    products = []
    for k, (name, mass, g) in enumerate(zip(names, masses, grades)):
        contents = [_content(mass, g[i], units[i]) for i in range(n)]
        dist = [c / fc * 100 if fc else 0.0 for c, fc in zip(contents, feed_contents)]
        is_conc = 0 < k < len(names) - 1
        ratio = dry_feed / mass if is_conc and mass > 0 else None
        products.append(Product(name, mass, mass / dry_feed * 100, g, contents, dist, ratio))
    return MetallurgicalResult(list(elements), list(units), products)
