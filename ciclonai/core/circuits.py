"""Balances de pulpa: hidrociclón y circuitos de molienda (directo, inverso, D-SAG)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .pulp import Stream, check_pct, check_positive, circulating_load, require


@dataclass
class CircuitResult:
    streams: dict[str, Stream]  # clave -> corriente, en el orden de la tabla
    circulating_loads: dict[str, float]  # etiqueta -> valor (fracción)
    warnings: list[str] = field(default_factory=list)


def _check_water(result: CircuitResult) -> CircuitResult:
    """Un agua de reposición negativa indica datos de % sólidos incompatibles."""
    for stream in result.streams.values():
        if stream.solids == 0 and stream.water < 0:
            result.warnings.append(
                f"'{stream.name}' resulta negativa ({stream.water:,.2f} m³/h): "
                "revise los % de sólidos ingresados."
            )
    return result


def hydrocyclone(feed_solids: float, sg: float, sol_feed: float, sol_uf: float, sol_of: float) -> CircuitResult:
    check_positive(feed_solids, "La alimentación seca")
    check_positive(sg, "La gravedad específica")
    cc = circulating_load(sol_of, sol_uf, sol_feed)
    of = Stream.from_solids_pct("Rebose (O/F)", feed_solids / (1 + cc), sol_of, sg)
    uf = Stream.from_solids_pct("Descarga (U/F)", of.solids * cc, sol_uf, sg)
    feed = (uf + of).renamed("Alimentación")
    return CircuitResult({"feed": feed, "of": of, "uf": uf}, {"Carga circulante": cc})


def _ball_mill_circuit(circuit_feed: Stream, sg: float, sol_of: float, sol_uf: float,
                       sol_cyc_feed: float, sol_mill_dis: float, reverse: bool) -> dict[str, Stream]:
    """Molino de bolas en circuito cerrado con hidrociclón.

    Directo: la alimentación al circuito entra al molino.
    Inverso: la alimentación al circuito entra al cajón del ciclón.
    """
    check_pct(sol_mill_dis, "% sólidos de la descarga del molino")
    cc = circulating_load(sol_of, sol_uf, sol_cyc_feed)
    of = Stream.from_solids_pct("Rebose Ciclón", circuit_feed.solids, sol_of, sg)
    uf = Stream.from_solids_pct("Descarga Ciclón", of.solids * cc, sol_uf, sg)
    mill_feed = (uf + circuit_feed if not reverse else uf).renamed("Alimentación Molino")
    mill_dis = Stream.from_solids_pct("Descarga Molino", mill_feed.solids, sol_mill_dis, sg)
    mill_water = Stream.water_only("Agua al Molino", mill_dis.water - mill_feed.water, sg)
    cyc_feed = (uf + of).renamed("Alimentación Ciclón")
    sump_in = mill_dis.water + (circuit_feed.water if reverse else 0.0)
    sump_water = Stream.water_only("Agua a Descarga", cyc_feed.water - sump_in, sg)
    return {
        "mill_feed": mill_feed, "mill_water": mill_water, "mill_dis": mill_dis,
        "sump_water": sump_water, "cyc_feed": cyc_feed, "uf": uf, "of": of,
    }


def grinding_circuit(fresh_feed: float, moisture: float, sg: float, sol_of: float, sol_uf: float,
                     sol_cyc_feed: float, sol_mill_dis: float, reverse: bool = False) -> CircuitResult:
    check_positive(fresh_feed, "La carga fresca")
    check_positive(sg, "La gravedad específica")
    require(0 <= moisture < 100, "La humedad debe estar entre 0 y 100 %.")
    fresh = Stream.from_wet("Alimentación Fresca", fresh_feed, moisture, sg)
    ball = _ball_mill_circuit(fresh, sg, sol_of, sol_uf, sol_cyc_feed, sol_mill_dis, reverse)
    streams = {"fresh": fresh, **ball}
    return _check_water(CircuitResult(streams, {"Carga circulante": ball["uf"].solids / ball["of"].solids}))


def dsag_circuit(fresh_feed: float, moisture: float, sg: float, sol_sag_dis: float, cc_pebbles: float,
                 moisture_pebbles: float, sol_of: float, sol_uf: float, sol_cyc_feed: float,
                 sol_mill_dis: float) -> CircuitResult:
    """Molino SAG con trommel y chancado de pebbles + molino de bolas en circuito inverso."""
    check_positive(fresh_feed, "La carga fresca")
    check_positive(sg, "La gravedad específica")
    require(0 <= moisture < 100, "La humedad debe estar entre 0 y 100 %.")
    require(cc_pebbles >= 0, "La carga circulante de pebbles no puede ser negativa.")
    require(0 <= moisture_pebbles < 100, "La humedad de pebbles debe estar entre 0 y 100 %.")
    check_pct(sol_sag_dis, "% sólidos de la descarga SAG")

    fresh = Stream.from_wet("Alimentación Fresca", fresh_feed, moisture, sg)
    peb_solids = fresh.solids * cc_pebbles / 100
    pebbles = Stream("Sobre Trommel", peb_solids, peb_solids * moisture_pebbles / (100 - moisture_pebbles), sg)
    sag_dis = Stream.from_solids_pct("Desc. SAG", fresh.solids + pebbles.solids, sol_sag_dis, sg)
    sag_water = Stream.water_only("Agua a SAG", sag_dis.water - fresh.water - pebbles.water, sg)
    undersize = Stream("Bajo Trommel", sag_dis.solids - pebbles.solids, sag_dis.water - pebbles.water, sg)

    ball = _ball_mill_circuit(undersize, sg, sol_of, sol_uf, sol_cyc_feed, sol_mill_dis, reverse=True)
    streams = {"fresh": fresh, "sag_water": sag_water, "sag_dis": sag_dis, "pebbles": pebbles,
               "undersize": undersize, **ball}
    loads = {
        "Carga circulante SAG (pebbles)": pebbles.solids / undersize.solids,
        "Carga circulante molino de bolas": ball["uf"].solids / ball["of"].solids,
    }
    return _check_water(CircuitResult(streams, loads))
