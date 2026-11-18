"""Escribe los resultados de un balance sobre el diagrama del circuito (PNG)."""
from __future__ import annotations

import base64
import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .circuits import CircuitResult

IMG_DIR = Path(__file__).resolve().parent.parent / "static" / "img"
SPACING = 6

# Por diagrama: imagen, tamaño de letra, posiciones de las corrientes (mineral t/h, pulpa m³/h,
# % sólidos), posiciones de las corrientes de agua (m³/h) y de las cargas circulantes (en el
# mismo orden que CircuitResult.circulating_loads).
LAYOUTS = {
    "hydrocyclone": {
        "image": "hydrocyclon_mass_balance.png", "font": 12,
        "streams": {"feed": (190, 207), "of": (190, 90), "uf": (190, 325)},
        "water": {}, "loads": [(90, 360)],
    },
    "direct": {
        "image": "direct_circuit.png", "font": 14,
        "streams": {"fresh": (90, 405), "uf": (170, 195), "mill_feed": (325, 405), "mill_dis": (725, 425),
                    "cyc_feed": (805, 110), "of": (565, 70)},
        "water": {"mill_water": (485, 530), "sump_water": (805, 320)}, "loads": [(815, 215)],
    },
    "reverse": {
        "image": "reverse_circuit.png", "font": 14,
        "streams": {"fresh": (85, 195), "uf": (965, 195), "mill_feed": (725, 195), "mill_dis": (405, 195),
                    "cyc_feed": (725, 445), "of": (565, 65)},
        "water": {"mill_water": (890, 340), "sump_water": (85, 360)}, "loads": [(490, 445)],
    },
    "dsag": {
        "image": "d_sag_circuit.png", "font": 16,
        "streams": {"fresh": (35, 200), "sag_dis": (305, 200), "pebbles": (490, 200), "undersize": (490, 343),
                    "mill_dis": (670, 200), "of": (853, 54), "mill_feed": (853, 200), "uf": (1125, 200),
                    "cyc_feed": (1125, 510)},
        "water": {"sag_water": (35, 465), "mill_water": (1035, 415), "sump_water": (490, 585)},
        "loads": [(400, 440), (945, 485)],
    },
}


@lru_cache(maxsize=None)
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def blank_diagram_url(kind: str) -> str:
    return f"img/{LAYOUTS[kind]['image']}"


def draw(kind: str, result: CircuitResult) -> str:
    """Devuelve el diagrama con los valores como data URI PNG (listo para <img src>)."""
    layout = LAYOUTS[kind]
    image = Image.open(IMG_DIR / layout["image"]).convert("RGB")
    canvas = ImageDraw.Draw(image)
    font = _font(layout["font"])

    for key, xy in layout["streams"].items():
        s = result.streams[key]
        text = f"{s.solids:,.2f}\n{s.pulp_m3:,.2f}\n{s.sol_ww:.2f}"
        canvas.multiline_text(xy, text, font=font, fill="black", align="right", spacing=SPACING)
    for key, xy in layout["water"].items():
        canvas.text(xy, f"{result.streams[key].water:,.2f}", font=font, fill="black")
    for xy, value in zip(layout["loads"], result.circulating_loads.values()):
        canvas.text(xy, f"{value:.3f}", font=font, fill="black")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
