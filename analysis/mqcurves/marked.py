"""Marker centres read by eye from a figure's pixels, written down so they can be checked.

Where neither tracing nor marker finding can follow a figure, a person reads
each marker's centre off the pixels. The recipe records those positions in the
pixel coordinates of the figure as stored, together with the figure's pixel
hash and the axis calibration, so anyone can see on an overlay exactly where
each value was read, and the conversion to values repeats exactly.

    id = "mq-136-hanwei-2004-h2s-marked"
    sensor = "MQ-136"
    gas = "H2S"
    # Marker centres as [x, y] pixels of the image as stored, x right, y down.
    # Written before the first table, or TOML puts it inside that table.
    markers = [[55, 183.5], [226, 152.5], [277, 140.5]]

    [source]                         # the figure: as for a traced curve
    datasheet = "mq-136-hanwei-2004"
    page = 2
    pixels_sha256 = "..."

    [x]                              # ppm axis: two pixel columns and their values
    pixels = [54.58, 396.0]
    values = [10, 1000]

    [y]                              # Rs/R0 axis: two pixel rows and their values
    pixels = [51.98, 279.06]
    values = [0.1, 10]

The reading is a person's, so it is no more precise than one pixel; what the
recipe adds is that it can be checked against the figure and repeated.
"""
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import figure
from .recipe import DATASHEETS, RecipeError, _axis
from .trace import Axis


@dataclass(frozen=True)
class Recipe:
    id: str
    sensor: str
    gas: str
    source: dict
    x: Axis
    y: Axis
    markers: tuple
    path: Path

    def pixels(self, datasheets=DATASHEETS):
        if "image" in self.source:
            return figure.from_image(self.path.parent / self.source["image"])
        pdf = Path(datasheets) / f"{self.source['datasheet']}.pdf"
        return figure.from_datasheet(pdf, self.source["page"], self.source["pixels_sha256"])


def load(path):
    path = Path(path)
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    try:
        source = doc["source"]
        if "image" not in source:
            for key in ("datasheet", "page", "pixels_sha256"):
                if key not in source:
                    raise RecipeError(f"[source] needs 'image', or 'datasheet', 'page' and 'pixels_sha256' (missing '{key}')")
        if len(doc["markers"]) < 2 or any(len(m) != 2 for m in doc["markers"]):
            raise RecipeError("markers must be at least two [x, y] pixel positions")
        markers = tuple((float(m[0]), float(m[1])) for m in doc["markers"])
        return Recipe(id=doc["id"], sensor=doc["sensor"], gas=doc["gas"], source=source,
                      x=_axis(doc["x"], "x"), y=_axis(doc["y"], "y"), markers=markers, path=path)
    except KeyError as err:
        raise RecipeError(f"{path}: missing {err}") from err


def read(r, datasheets=DATASHEETS):
    """(pixels, ppm, ratio, x, y), sorted by concentration. The figure must match the recipe's hash."""
    pixels = r.pixels(datasheets)
    h, w = pixels.shape[:2]
    x, y = np.array([m[0] for m in r.markers]), np.array([m[1] for m in r.markers])
    if np.any((x < 0) | (x > w - 1) | (y < 0) | (y > h - 1)):
        raise RecipeError(f"{r.id}: a marker lies outside the {w}x{h} figure")
    ppm, ratio = 10 ** r.x.to_log10(x), 10 ** r.y.to_log10(y)
    order = np.argsort(ppm)
    return pixels, ppm[order], ratio[order], x[order], y[order]
