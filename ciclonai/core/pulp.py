"""Modelo de corriente de pulpa y utilidades comunes.

Una corriente se define solo por dos magnitudes independientes: el mineral seco
(t/h) y el agua (m3/h, equivalente a t/h). Todo lo demás (pulpa, densidad,
% sólidos) se deriva, así los balances siempre cierran por construcción.
"""
from __future__ import annotations

from dataclasses import dataclass


class ValidationError(ValueError):
    """Error de datos de entrada con un mensaje apto para mostrar al usuario."""


# Filas que se muestran en las tablas de balance de pulpa (orden de la app original).
PULP_ROWS = [
    ("solids", "Mineral (t/h)"),
    ("water", "Agua (m³/h)"),
    ("pulp_t", "Pulpa (t/h)"),
    ("pulp_m3", "Pulpa (m³/h)"),
    ("density", "Densidad (t/m³)"),
    ("sol_vv", "% Sólidos (v/v)"),
    ("sol_ww", "% Sólidos (w/w)"),
]


@dataclass(frozen=True)
class Stream:
    name: str
    solids: float  # t/h de mineral seco
    water: float  # m3/h de agua
    sg: float  # gravedad específica del mineral

    @classmethod
    def from_solids_pct(cls, name: str, solids: float, pct_solids: float, sg: float) -> "Stream":
        """Corriente a partir del mineral seco y su % sólidos en peso."""
        pulp = solids / pct_solids * 100
        return cls(name, solids, pulp - solids, sg)

    @classmethod
    def from_wet(cls, name: str, wet_tonnage: float, moisture: float, sg: float) -> "Stream":
        """Corriente a partir del tonelaje húmedo y la humedad (%)."""
        solids = wet_tonnage * (100 - moisture) / 100
        return cls(name, solids, wet_tonnage - solids, sg)

    @classmethod
    def water_only(cls, name: str, water: float, sg: float) -> "Stream":
        return cls(name, 0.0, water, sg)

    def __add__(self, other: "Stream") -> "Stream":
        return Stream(self.name, self.solids + other.solids, self.water + other.water, self.sg)

    def renamed(self, name: str) -> "Stream":
        return Stream(name, self.solids, self.water, self.sg)

    @property
    def pulp_t(self) -> float:
        return self.solids + self.water

    @property
    def pulp_m3(self) -> float:
        return self.solids / self.sg + self.water

    @property
    def density(self) -> float:
        return self.pulp_t / self.pulp_m3 if self.pulp_m3 else 0.0

    @property
    def sol_vv(self) -> float:
        return self.solids / self.sg / self.pulp_m3 * 100 if self.pulp_m3 else 0.0

    @property
    def sol_ww(self) -> float:
        return self.solids / self.pulp_t * 100 if self.pulp_t else 0.0

    def as_dict(self) -> dict:
        return {key: getattr(self, key) for key, _ in PULP_ROWS}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def check_pct(value: float, label: str) -> None:
    require(0 < value < 100, f"{label} debe estar entre 0 y 100 %.")


def check_positive(value: float, label: str) -> None:
    require(value > 0, f"{label} debe ser mayor que 0.")


def circulating_load(sol_over: float, sol_under: float, sol_feed: float) -> float:
    """Carga circulante (fracción UF/OF) por el método de las razones de dilución."""
    check_pct(sol_over, "% sólidos del rebose")
    check_pct(sol_under, "% sólidos de la descarga")
    check_pct(sol_feed, "% sólidos de la alimentación al ciclón")
    require(
        sol_over < sol_feed < sol_under,
        "Debe cumplirse: % sól. rebose < % sól. alimentación ciclón < % sól. descarga ciclón.",
    )
    return (1 / sol_over - 1 / sol_feed) / (1 / sol_feed - 1 / sol_under)
