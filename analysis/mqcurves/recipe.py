"""A recipe: everything needed to trace one curve again without a human.

    id = "mq-8-winsen-v1.3-h2"
    sensor = "MQ-8"
    gas = "H2"

    [source]                      # a figure embedded in a manifest datasheet ...
    datasheet = "mq-8-winsen-v1.3"
    page = 4
    pixels_sha256 = "..."
    # image = "figure.png"        # ... or an image file, relative to the recipe

    [x]                           # ppm axis: two pixel columns and their values
    pixels = [50, 380]
    values = [100, 10000]

    [y]                           # Rs/R0 axis: two pixel rows and their values
    pixels = [15, 270]
    values = [1, 0.01]

    [trace]
    seed = [210, 140]             # a pixel on the curve, as [x, y]
    lo = 20                       # colour tolerance below and above the seed's
    up = 20
    bin_width = 1                 # columns averaged into one point
    connectivity = 8
    ppm = [100, 10000]            # optional: keep only points in this range
    max_thickness = 3             # optional: skip columns where the trace is
                                  # taller than this, i.e. where a marker sits

    [[check]]                     # optional, repeatable: a value read off the
    at = 1000                     # figure by eye, which the trace must pass
    ratio = 0.09                  # within `within` (relative, default 0.1) of
    within = 0.1

The range matters where a line ends in a marker: the marker's outer half is the
line's colour too, and would otherwise be read as points beyond the last value
the datasheet plots.
"""
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import figure
from .trace import Axis

DATASHEETS = Path(__file__).resolve().parents[2] / "datasheets" / "files"


class RecipeError(ValueError):
    pass


@dataclass(frozen=True)
class Recipe:
    id: str
    sensor: str
    gas: str
    source: dict
    x: Axis
    y: Axis
    seed: tuple
    lo: int
    up: int
    bin_width: int
    connectivity: int
    ppm: tuple | None
    max_thickness: int | None
    checks: tuple
    path: Path

    def pixels(self, datasheets=DATASHEETS):
        if "image" in self.source:
            return figure.from_image(self.path.parent / self.source["image"])
        pdf = Path(datasheets) / f"{self.source['datasheet']}.pdf"
        return figure.from_datasheet(pdf, self.source["page"], self.source["pixels_sha256"])


def _axis(table, name):
    try:
        (pa, pb), (va, vb) = table["pixels"], table["values"]
        return Axis(float(pa), float(va), float(pb), float(vb))
    except (KeyError, TypeError, ValueError) as err:
        raise RecipeError(f"[{name}] needs pixels = [a, b] and values = [a, b] that differ: {err}") from err


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
        t = doc["trace"]
        seed = tuple(int(v) for v in t["seed"])
        if len(seed) != 2:
            raise RecipeError("[trace] seed must be [x, y]")
        ppm = tuple(float(v) for v in t["ppm"]) if "ppm" in t else None
        if ppm is not None and not (len(ppm) == 2 and 0 < ppm[0] < ppm[1]):
            raise RecipeError("[trace] ppm must be [low, high] with 0 < low < high")
        return Recipe(
            id=doc["id"], sensor=doc["sensor"], gas=doc["gas"], source=source,
            x=_axis(doc["x"], "x"), y=_axis(doc["y"], "y"), seed=seed,
            lo=int(t.get("lo", 20)), up=int(t.get("up", 20)),
            bin_width=int(t.get("bin_width", 1)), connectivity=int(t.get("connectivity", 8)),
            ppm=ppm, path=path,
            max_thickness=int(t["max_thickness"]) if "max_thickness" in t else None,
            checks=tuple((float(c["at"]), float(c["ratio"]), float(c.get("within", 0.1))) for c in doc.get("check", [])),
        )
    except KeyError as err:
        raise RecipeError(f"{path}: missing {err}") from err


def dump(path, *, id, sensor, gas, source, x, y, seed, lo=20, up=20, bin_width=1, connectivity=8, ppm=None,
         max_thickness=None):
    """Write a recipe file. `x` and `y` are ((pixel, value), (pixel, value))."""

    def value(v):
        return f'"{v}"' if isinstance(v, str) else f"{v:g}" if isinstance(v, float) else str(v)

    lines = [f'id = "{id}"', f'sensor = "{sensor}"', f'gas = "{gas}"', "", "[source]"]
    lines += [f"{k} = {value(v)}" for k, v in source.items()]
    for name, ((pa, va), (pb, vb)) in (("x", x), ("y", y)):
        lines += ["", f"[{name}]", f"pixels = [{value(pa)}, {value(pb)}]", f"values = [{value(va)}, {value(vb)}]"]
    lines += ["", "[trace]", f"seed = [{seed[0]}, {seed[1]}]", f"lo = {lo}", f"up = {up}",
              f"bin_width = {bin_width}", f"connectivity = {connectivity}"]
    if ppm is not None:
        lines.append(f"ppm = [{value(ppm[0])}, {value(ppm[1])}]")
    if max_thickness is not None:
        lines.append(f"max_thickness = {max_thickness}")
    lines.append("")
    Path(path).write_text("\n".join(lines))
