"""Pruebas del núcleo de cálculo.

Los valores de referencia se obtuvieron ejecutando la app Streamlit original con los
mismos datos por defecto; donde la original tenía un error se indica explícitamente.
"""
import pytest

from ciclonai.core import tools
from ciclonai.core.circuits import dsag_circuit, grinding_circuit, hydrocyclone
from ciclonai.core.metallurgical import metallurgical_balance
from ciclonai.core.pulp import ValidationError, circulating_load

approx = lambda v: pytest.approx(v, rel=1e-4)  # noqa: E731


# ---------------------------------------------------------------- herramientas
def test_tools_match_original():
    assert tools.mill_charge_level(2.1, 3.4)[0] == approx(37.0294)
    assert tools.solids_to_density(2.7, 30) == approx(1.2328767)
    assert tools.density_to_solids(2.7, 1.23) == approx(29.6987)
    assert tools.recovery(2.09, 20.0, 0.1) == approx(95.6938)


@pytest.mark.parametrize("call", [
    lambda: tools.mill_charge_level(4, 3),
    lambda: tools.solids_to_density(2.7, 0),
    lambda: tools.density_to_solids(2.7, 3.0),
    lambda: tools.recovery(25, 20, 0.1),
])
def test_tools_reject_invalid_input(call):
    with pytest.raises(ValidationError):
        call()


def test_circulating_load_requires_ordered_solids():
    with pytest.raises(ValidationError):
        circulating_load(60, 76, 40)  # rebose más denso que la alimentación


# ---------------------------------------------------------------- hidrociclón
def test_hydrocyclone_matches_original():
    r = hydrocyclone(1622.8, 2.8, 62.2, 76.0, 40.0)
    s = r.streams
    assert s["of"].solids == approx(400.0472)
    assert s["uf"].solids == approx(1222.7528)
    assert s["feed"].water == approx(986.2032)
    assert s["feed"].pulp_m3 == approx(1565.7746)
    assert s["uf"].density == approx(1.9553)
    assert s["feed"].sol_ww == approx(62.2)


# ---------------------------------------------------------------- circuitos de molienda
def _closes(r):
    """Agua y mineral se conservan en el cajón y en el molino."""
    s = r.streams
    assert s["cyc_feed"].solids == approx(s["uf"].solids + s["of"].solids)
    assert s["mill_dis"].water == approx(s["mill_feed"].water + s["mill_water"].water)


def test_direct_circuit_matches_original():
    r = grinding_circuit(421.10, 5.0, 2.8, 40.0, 76.0, 62.2, 72.0, reverse=False)
    s = r.streams
    assert s["fresh"].solids == approx(400.045)
    assert s["mill_feed"].solids == approx(1622.791)
    assert s["mill_water"].water == approx(223.900)
    assert s["sump_water"].water == approx(355.112)
    assert s["cyc_feed"].sol_ww == approx(62.2)
    assert s["cyc_feed"].water == approx(s["mill_dis"].water + s["sump_water"].water)
    _closes(r)


def test_reverse_circuit_matches_original():
    r = grinding_circuit(421.053, 5.0, 2.8, 40.0, 76.0, 64.1, 72.0, reverse=True)
    s = r.streams
    assert s["uf"].solids == approx(1539.1610)
    assert s["mill_water"].water == approx(112.5118)
    assert s["sump_water"].water == approx(466.4361)
    assert s["cyc_feed"].pulp_m3 == approx(1778.6090)
    assert s["cyc_feed"].water == approx(s["mill_dis"].water + s["sump_water"].water + s["fresh"].water)
    _closes(r)


def test_dsag_circuit_closes_water_balance():
    r = dsag_circuit(421.053, 5.0, 2.8, 82.43, 30, 2.5, 40.0, 76.0, 64.1, 72.0)
    s = r.streams
    # Igual que la original:
    assert s["sag_dis"].solids == approx(520.0)
    assert s["sag_water"].water == pytest.approx(86.71, abs=0.01)
    assert s["undersize"].water == pytest.approx(107.76, abs=0.01)
    assert s["mill_water"].water == pytest.approx(112.51, abs=0.01)
    # CORREGIDO: la original restaba el agua de la carga fresca (21.05) en vez del agua del
    # bajo trommel (107.76) y daba 466.44 m3/h; el balance del cajón no cerraba.
    assert s["sump_water"].water == pytest.approx(379.73, abs=0.01)
    assert s["cyc_feed"].water == approx(s["mill_dis"].water + s["sump_water"].water + s["undersize"].water)
    assert r.circulating_loads["Carga circulante SAG (pebbles)"] == approx(0.30)
    _closes(r)


def test_inconsistent_solids_produce_warning():
    # % sólidos descarga del molino muy alto → agua al molino negativa
    r = grinding_circuit(421.1, 5.0, 2.8, 40.0, 76.0, 62.2, 90.0)
    assert any("Agua al Molino" in w for w in r.warnings)


# ---------------------------------------------------------------- balance metalúrgico
def test_one_concentrate_mass_closes():
    r = metallurgical_balance(150, 2, ["Cu"], ["%"], [0.3], [[20.3]], [0.2])
    feed, conc, tail = r.products
    assert feed.mass == approx(147.0)
    assert conc.mass == approx(0.731343)
    # CORREGIDO: la original calculaba la cola como alimentación − razón (146.995 t).
    assert tail.mass == approx(147.0 - 0.731343)
    assert conc.mass + tail.mass == approx(feed.mass)
    assert r.recoveries[0] == approx(tools.recovery(0.3, 20.3, 0.2))
    assert conc.ratio == approx(201.0)  # razón de concentración F/C


def test_two_concentrates_match_original():
    r = metallurgical_balance(1330.84, 0, ["Cu", "Pb"], ["%", "%"], [1.5, 1.8],
                              [[29.6, 1.7], [1.7, 62.3]], [0.1, 0.11])
    _, cu, pb, tail = r.products
    assert cu.mass == approx(61.281979)
    assert pb.mass == approx(34.598509)
    assert tail.mass == approx(1234.959512)
    assert cu.distributions[0] == approx(90.867251)
    assert pb.distributions[1] == approx(89.980225)
    assert cu.ratio == approx(21.716662)


def test_three_concentrates_match_original():
    r = metallurgical_balance(4000, 0, ["Cu", "Pb", "Zn"], ["%"] * 3, [0.89, 1.83, 5.66],
                              [[24.29, 7.45, 6.99], [0.85, 60.97, 8.90], [2.74, 0.82, 56.14]],
                              [0.11, 0.17, 0.66])
    masses = [p.mass for p in r.products]
    assert masses[1:] == [approx(89.562925), approx(94.892537), approx(336.177941), approx(3479.366596)]
    assert r.recoveries == [approx(61.109086), approx(79.038224), approx(83.361438)]


def test_content_units():
    r = metallurgical_balance(100, 0, ["Au"], ["g/t"], [2.0], [[50.0]], [0.5])
    assert r.products[0].contents[0] == approx(200.0)  # gramos, sin dividir entre 100


def test_singular_system_is_reported():
    with pytest.raises(ValidationError, match="solución única"):
        metallurgical_balance(100, 0, ["Cu", "Pb"], ["%", "%"], [1, 1], [[2, 2], [2, 2]], [0, 0])


def test_negative_mass_is_reported():
    with pytest.raises(ValidationError, match="negativas"):
        metallurgical_balance(100, 0, ["Cu"], ["%"], [25], [[20]], [0.1])
