"""Pruebas de humo de las páginas web."""
import pytest

from ciclonai import create_app
from ciclonai.routes import METALLURGICAL_DEFAULTS, PULP_PAGES, TOOLS, _metallurgical_fields
from ciclonai.forms import all_fields, defaults


@pytest.fixture()
def client():
    return create_app({"TESTING": True}).test_client()


def test_index(client):
    html = client.get("/").get_data(as_text=True)
    assert "Bienvenido a Ciclon IA" in html
    for slug in PULP_PAGES:
        assert f"/balance/{slug}" in html


@pytest.mark.parametrize("slug", list(PULP_PAGES))
def test_pulp_pages_compute_and_export(client, slug):
    assert client.get(f"/balance/{slug}").status_code == 200
    form = defaults(all_fields(PULP_PAGES[slug]["groups"]))
    html = client.post(f"/balance/{slug}", data=form).get_data(as_text=True)
    assert "Resultados del balance" in html and "data:image/png;base64," in html
    xlsx = client.post(f"/balance/{slug}", data={**form, "action": "excel"})
    assert xlsx.status_code == 200 and xlsx.data[:2] == b"PK"


@pytest.mark.parametrize("n", list(METALLURGICAL_DEFAULTS))
def test_metallurgical_pages(client, n):
    d = METALLURGICAL_DEFAULTS[n]
    form = defaults(_metallurgical_fields(n, d))
    form.update({f"el_{i}": e for i, e in enumerate(d["elements"])})
    form.update({f"unit_{i}": "%" for i in range(n)})
    html = client.post(f"/metalurgico/{n}", data=form).get_data(as_text=True)
    assert "Recuperación" in html and "Resultados del balance" in html
    assert client.post(f"/metalurgico/{n}", data={**form, "action": "excel"}).data[:2] == b"PK"


@pytest.mark.parametrize("key", list(TOOLS))
def test_tools(client, key):
    form = {"tool": key, **defaults(TOOLS[key]["fields"])}
    html = client.post("/herramientas", data=form).get_data(as_text=True)
    assert TOOLS[key]["result"] in html


def test_invalid_input_shows_error(client):
    form = defaults(all_fields(PULP_PAGES["hidrociclon"]["groups"]))
    form["sol_of"] = "abc"
    html = client.post("/balance/hidrociclon", data=form).get_data(as_text=True)
    assert "debe ser un número" in html


def test_unknown_page_404(client):
    assert client.get("/balance/no-existe").status_code == 404
    assert client.get("/metalurgico/9").status_code == 404
