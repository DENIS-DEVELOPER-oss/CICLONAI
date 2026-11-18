"""Rutas web de CiclonAI."""
from __future__ import annotations

from flask import Blueprint, abort, render_template, request, send_file, url_for

from .core import diagrams, tools
from .core.circuits import dsag_circuit, grinding_circuit, hydrocyclone
from .core.metallurgical import ELEMENTS, UNITS, metallurgical_balance
from .core.pulp import ValidationError
from .forms import Field, Group, all_fields, defaults, parse
from .tables import circuit_table, metallurgical_table, to_excel

bp = Blueprint("main", __name__)


# --------------------------------------------------------------------------- páginas de pulpa
def _mineral(fresh: float) -> Group:
    return Group("Mineral", (
        Field("fresh_feed", "Carga fresca", fresh, "t/h húmedas"),
        Field("moisture", "Humedad", 5.0, "%"),
        Field("sg", "Gravedad específica", 2.80),
    ))


def _ball_mill(cyc_feed: float) -> Group:
    return Group("Molino de bolas y ciclón", (
        Field("sol_of", "% Sólidos rebose ciclón", 40.0, "%"),
        Field("sol_uf", "% Sólidos descarga ciclón", 76.0, "%"),
        Field("sol_cyc_feed", "% Sólidos alimentación ciclón", cyc_feed, "%"),
        Field("sol_mill_dis", "% Sólidos descarga molino", 72.0, "%"),
    ))


PULP_PAGES = {
    "hidrociclon": {
        "title": "Balance de Masas de Hidrociclón", "icon": "🌪️", "diagram": "hydrocyclone",
        "groups": [
            Group("Alimentación", (
                Field("feed_solids", "Alimentación seca", 1622.8, "t/h"),
                Field("sg", "Gravedad específica", 2.80),
            )),
            Group("% Sólidos en las corrientes", (
                Field("sol_feed", "Alimentación ciclón", 62.2, "%"),
                Field("sol_uf", "Descarga (U/F)", 76.0, "%"),
                Field("sol_of", "Rebose (O/F)", 40.0, "%"),
            )),
        ],
        "compute": lambda v: hydrocyclone(**v),
        "note": "Determina los flujos de mineral, agua y pulpa en la alimentación, el rebose y la "
                "descarga del hidrociclón a partir de los % de sólidos (método de razones de dilución).",
    },
    "molienda-directa": {
        "title": "Circuito de Molienda Directo", "icon": "➡️", "diagram": "direct",
        "groups": [_mineral(421.10), _ball_mill(62.2)],
        "compute": lambda v: grinding_circuit(**v, reverse=False),
        "note": "La carga fresca entra al molino junto con la descarga del ciclón.",
    },
    "molienda-inversa": {
        "title": "Circuito de Molienda Inverso", "icon": "⬅️", "diagram": "reverse",
        "groups": [_mineral(421.053), _ball_mill(64.1)],
        "compute": lambda v: grinding_circuit(**v, reverse=True),
        "note": "La carga fresca entra al cajón del ciclón; el molino recibe solo la descarga del ciclón.",
    },
    "molienda-dsag": {
        "title": "Circuito de Molienda D-SAG", "icon": "↪️", "diagram": "dsag",
        "groups": [
            _mineral(421.053),
            Group("Molino SAG", (
                Field("sol_sag_dis", "% Sólidos descarga SAG", 82.43, "%"),
                Field("cc_pebbles", "Carga circulante de pebbles", 30.0, "% de la carga fresca"),
                Field("moisture_pebbles", "Humedad de pebbles", 2.5, "%"),
            )),
            _ball_mill(64.1),
        ],
        "compute": lambda v: dsag_circuit(**v),
        "note": "Molino SAG con trommel y retorno de pebbles; el bajo trommel alimenta un molino de "
                "bolas en circuito inverso con hidrociclones.",
    },
}

METALLURGICAL_DEFAULTS = {
    1: {"title": "Dos productos", "feed_t": 150.0, "moisture": 2.0, "elements": ["Cu"],
        "feed": [0.3], "conc": [[20.3]], "tail": [0.2]},
    2: {"title": "Tres productos", "feed_t": 1330.84, "moisture": 0.0, "elements": ["Cu", "Pb"],
        "feed": [1.5, 1.8], "conc": [[29.6, 1.7], [1.7, 62.3]], "tail": [0.1, 0.11]},
    3: {"title": "Cuatro productos", "feed_t": 4000.0, "moisture": 0.0, "elements": ["Cu", "Pb", "Zn"],
        "feed": [0.89, 1.83, 5.66], "conc": [[24.29, 7.45, 6.99], [0.85, 60.97, 8.90], [2.74, 0.82, 56.14]],
        "tail": [0.11, 0.17, 0.66]},
}

TOOLS = {
    "mill": {
        "title": "Nivel de carga del molino", "num": "1",
        "note": "Nivel de carga según las dimensiones del molino.",
        "fields": (Field("diameter", "Diámetro efectivo D", 3.4, "m"), Field("height", "Altura libre H", 2.1, "m")),
        "compute": lambda v: tools.mill_charge_level(v["height"], v["diameter"]),
        "result": "Nivel de carga", "unit": "%",
    },
    "density": {
        "title": "% Sólidos → densidad de pulpa", "num": "2",
        "note": "Convierte % de sólidos en peso a densidad de pulpa.",
        "fields": (Field("sg", "Gravedad específica", 2.7), Field("pct", "% Sólidos (p/p)", 30.0, "%")),
        "compute": lambda v: (tools.solids_to_density(v["sg"], v["pct"]), None),
        "result": "Densidad de pulpa", "unit": "t/m³",
    },
    "solids": {
        "title": "Densidad de pulpa → % sólidos", "num": "3",
        "note": "Convierte densidad de pulpa a % de sólidos en peso.",
        "fields": (Field("sg", "Gravedad específica", 2.7), Field("density", "Densidad de pulpa", 1.23, "t/m³")),
        "compute": lambda v: (tools.density_to_solids(v["sg"], v["density"]), None),
        "result": "% Sólidos (p/p)", "unit": "%",
    },
    "recovery": {
        "title": "Recuperación metálica", "num": "4",
        "note": "Recuperación a partir de las leyes (fórmula de dos productos).",
        "fields": (Field("feed", "Ley de alimentación", 2.09), Field("conc", "Ley de concentrado", 20.0),
                   Field("tail", "Ley de cola", 0.1)),
        "compute": lambda v: (tools.recovery(v["feed"], v["conc"], v["tail"]), None),
        "result": "Recuperación", "unit": "%",
    },
}


def navigation() -> list[dict]:
    """Menú compartido por la portada y la barra lateral."""
    return [
        {"title": "Cálculos", "items": [
            {"url": url_for("main.tools_page"), "icon": "🧰", "label": "Herramientas rápidas",
             "detail": "Nivel de carga · % sólidos ↔ densidad · Recuperación"},
        ]},
        {"title": "Balance de pulpa", "items": [
            {"url": url_for("main.pulp_page", slug=slug), "icon": p["icon"], "label": p["title"],
             "detail": p["note"]} for slug, p in PULP_PAGES.items()
        ]},
        {"title": "Balance metalúrgico", "items": [
            {"url": url_for("main.metallurgical_page", n=n), "icon": "⚖️",
             "label": f"{d['title']} ({n} concentrado{'s' if n > 1 else ''} + cola)",
             "detail": f"{n} elemento{'s' if n > 1 else ''}: masas, contenidos, distribución y recuperación"}
            for n, d in METALLURGICAL_DEFAULTS.items()
        ]},
    ]


@bp.app_context_processor
def inject_navigation():
    return {"navigation": navigation}


def _wants_excel() -> bool:
    return request.method == "POST" and request.form.get("action") == "excel"


def _excel_response(title: str, filename: str, inputs, table, extras=()):
    buffer = to_excel(title, inputs, table, extras)
    return send_file(buffer, as_attachment=True, download_name=f"ciclonai_{filename}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# --------------------------------------------------------------------------- vistas
@bp.get("/")
def index():
    return render_template("index.html")


@bp.route("/herramientas", methods=["GET", "POST"])
def tools_page():
    values = {key: defaults(tool["fields"]) for key, tool in TOOLS.items()}
    results = {}
    active = request.form.get("tool") if request.method == "POST" else None
    if active in TOOLS:
        tool = TOOLS[active]
        numbers, values[active], errors = parse(list(tool["fields"]), request.form)
        if errors:
            results[active] = {"errors": errors}
        else:
            try:
                value, warning = tool["compute"](numbers)
                results[active] = {"value": value, "warning": warning}
            except ValidationError as exc:
                results[active] = {"errors": [str(exc)]}
    return render_template("tools.html", tools=TOOLS, values=values, results=results)


@bp.route("/balance/<slug>", methods=["GET", "POST"])
def pulp_page(slug: str):
    page = PULP_PAGES.get(slug) or abort(404)
    fields = all_fields(page["groups"])
    values, errors, result = defaults(fields), [], None
    diagram = url_for("static", filename=diagrams.blank_diagram_url(page["diagram"]))

    if request.method == "POST":
        numbers, values, errors = parse(fields, request.form)
        if not errors:
            try:
                result = page["compute"](numbers)
            except ValidationError as exc:
                errors = [str(exc)]
        if result and _wants_excel():
            inputs = [(f.label, numbers[f.name], f.unit) for f in fields]
            extras = list(result.circulating_loads.items())
            return _excel_response(page["title"], slug, inputs, circuit_table(result), extras)
        if result:
            diagram = diagrams.draw(page["diagram"], result)

    return render_template("pulp.html", page=page, values=values, errors=errors, result=result,
                           table=circuit_table(result) if result else None, diagram=diagram)


def _metallurgical_fields(n: int, d: dict) -> list[Field]:
    fields = [Field("feed_t", "Alimentación", d["feed_t"], "t húmedas"),
              Field("moisture", "Humedad", d["moisture"], "%")]
    for i in range(n):
        fields.append(Field(f"feed_g_{i}", f"Ley alimentación elemento {i + 1}", d["feed"][i]))
        fields.append(Field(f"tail_g_{i}", f"Ley cola elemento {i + 1}", d["tail"][i]))
        for j in range(n):
            fields.append(Field(f"conc_{j}_g_{i}", f"Ley concentrado {j + 1} elemento {i + 1}", d["conc"][j][i]))
    return fields


def _with_element_names(label: str, elements: list[str]) -> str:
    for i, element in enumerate(elements):
        label = label.replace(f"elemento {i + 1}", element)
    return label


@bp.route("/metalurgico/<int:n>", methods=["GET", "POST"])
def metallurgical_page(n: int):
    d = METALLURGICAL_DEFAULTS.get(n) or abort(404)
    fields = _metallurgical_fields(n, d)
    values = defaults(fields)
    elements, units = list(d["elements"]), ["%"] * n
    errors, result = [], None

    if request.method == "POST":
        numbers, values, errors = parse(fields, request.form)
        elements = [request.form.get(f"el_{i}", elements[i]) for i in range(n)]
        units = [request.form.get(f"unit_{i}", "%") for i in range(n)]
        if any(e not in ELEMENTS for e in elements) or any(u not in UNITS for u in units):
            errors.append("Elemento o unidad no válidos.")
        if not errors:
            try:
                result = metallurgical_balance(
                    numbers["feed_t"], numbers["moisture"], elements, units,
                    [numbers[f"feed_g_{i}"] for i in range(n)],
                    [[numbers[f"conc_{j}_g_{i}"] for i in range(n)] for j in range(n)],
                    [numbers[f"tail_g_{i}"] for i in range(n)],
                )
            except ValidationError as exc:
                errors = [str(exc)]
        if result and _wants_excel():
            inputs = [(_with_element_names(f.label, elements), numbers[f.name], f.unit) for f in fields]
            extras = [(f"Recuperación {e} (%)", r) for e, r in zip(elements, result.recoveries)]
            return _excel_response(f"Balance metalúrgico — {d['title']}", f"metalurgico_{n}", inputs,
                                   metallurgical_table(result), extras)

    return render_template("metallurgical.html", n=n, title=d["title"], values=values, elements=elements,
                           units=units, all_elements=ELEMENTS, all_units=UNITS, errors=errors, result=result,
                           table=metallurgical_table(result) if result else None)


@bp.app_template_filter("num")
def format_number(value, decimals: int = 2) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, str):
        return value
    return f"{value:,.{decimals}f}"
