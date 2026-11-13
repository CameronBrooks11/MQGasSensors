"""Read a line's plotted values from the hollow markers of a figure stored as an image.

A datasheet figure plots a few values per gas as markers and joins them with
lines. Where the markers are hollow outlines (squares, triangles, circles),
each encloses a small patch of background, and the centre of that patch is the
centre of the marker. Finding the patches rather than the outline keeps two
markers apart when one is drawn on top of the other, and keeps the line out,
since a line through the marker does not change what the outline encloses.

    id = "mq-303a-hanwei-2006-ethanol-located"
    sensor = "MQ-303A"
    gas = "ethanol"

    [source]                         # the figure: as for a traced curve
    datasheet = "mq-303a-hanwei-2006"
    page = 2
    pixels_sha256 = "..."

    [x]                              # ppm axis: two pixel columns and their values
    pixels = [358.4, 610.4]
    values = [1, 10000]

    [y]                              # Rs/R0 axis: two pixel rows and their values
    pixels = [17, 272]
    values = [10, 0.001]

    [markers]
    colour = [254, 0, 0]             # the outline's colour
    tolerance = 0                    # allowed difference per channel
    box = [359, 17, 611, 272]        # the plot area in pixels: [x0, y0, x1, y1]
    exclude = [[365, 200, 470, 270]] # optional: boxes to ignore, e.g. the legend
    area = [8, 20]                   # pixels a marker's hole may have
    fill = [0.9, 1.0]                # the hole's share of its bounding box: about 1
                                     # for a square, less for a triangle or circle
    count = 7                        # how many the figure plots
    # close = 1                      # optional: thicken the outline by this many
                                     # pixels first, to close gaps in it

`box` should reach a marker's width past the plot area, so that a marker on the
frame encloses its hole inside the box.

A hole is a 4-connected patch of pixels that are not the outline's colour and
do not reach the edge of `box`. Its centre is the centre of its bounding box.
Gaps between lines that enclose background are holes too; they are much larger
than a marker's, and `area` leaves them out.

Where a marker's outline has a one-pixel gap, its hole leaks out and is not
found. `close` thickens the outline by that many pixels in every direction
before holes are found. Every hole shrinks from every side, so a symmetric
hole's centre does not move; where the outline is uneven it can move by half a
pixel. `area` must then allow for the smaller holes.
"""
import tomllib
from collections import deque
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
    colour: tuple
    tolerance: int
    box: tuple
    exclude: tuple
    area: tuple
    fill: tuple
    count: int
    close: int
    path: Path

    def pixels(self, datasheets=DATASHEETS):
        if "image" in self.source:
            return figure.from_image(self.path.parent / self.source["image"])
        pdf = Path(datasheets) / f"{self.source['datasheet']}.pdf"
        return figure.from_datasheet(pdf, self.source["page"], self.source["pixels_sha256"])


def _range(table, key, kind):
    v = table[key]
    if len(v) != 2 or not v[0] <= v[1]:
        raise RecipeError(f"[markers] {key} must be [low, high]")
    return kind(v[0]), kind(v[1])


def load(path):
    path = Path(path)
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    try:
        source, m = doc["source"], doc["markers"]
        if "image" not in source:
            for key in ("datasheet", "page", "pixels_sha256"):
                if key not in source:
                    raise RecipeError(f"[source] needs 'image', or 'datasheet', 'page' and 'pixels_sha256' (missing '{key}')")
        colour = tuple(int(c) for c in m["colour"])
        if len(colour) != 3:
            raise RecipeError("[markers] colour must be [r, g, b]")
        box = tuple(int(v) for v in m["box"])
        exclude = tuple(tuple(int(v) for v in b) for b in m.get("exclude", []))
        if len(box) != 4 or any(len(b) != 4 for b in exclude):
            raise RecipeError("[markers] box and each exclude box must be [x0, y0, x1, y1]")
        return Recipe(
            id=doc["id"], sensor=doc["sensor"], gas=doc["gas"], source=source,
            x=_axis(doc["x"], "x"), y=_axis(doc["y"], "y"), colour=colour,
            tolerance=int(m.get("tolerance", 0)), box=box, exclude=exclude,
            area=_range(m, "area", int), fill=_range(m, "fill", float), count=int(m["count"]),
            close=int(m.get("close", 0)), path=path,
        )
    except KeyError as err:
        raise RecipeError(f"{path}: missing {err}") from err


def holes(mask):
    """Bounding boxes and sizes of the 4-connected False patches that do not touch the edge.

    Returns a list of (x0, y0, x1, y1, pixels), inclusive, in `mask` coordinates.
    """
    h, w = mask.shape
    seen = mask.copy()
    out = []
    for sy, sx in zip(*np.nonzero(~seen), strict=True):
        if seen[sy, sx]:
            continue
        seen[sy, sx] = True
        queue, n, edge = deque([(sx, sy)]), 0, False
        x0, y0, x1, y1 = sx, sy, sx, sy
        while queue:
            x, y = queue.popleft()
            n += 1
            x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
            edge |= x in (0, w - 1) or y in (0, h - 1)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((nx, ny))
        if not edge:
            out.append((int(x0), int(y0), int(x1), int(y1), n))
    return out


def find(pixels, r):
    """Centres of the recipe's markers, in pixel coordinates of the whole image."""
    bx0, by0, bx1, by1 = r.box
    region = pixels[by0:by1 + 1, bx0:bx1 + 1].astype(np.int16)
    mask = np.all(np.abs(region - np.array(r.colour)) <= r.tolerance, axis=2)
    for _ in range(r.close):
        grown = np.pad(mask, 1)
        mask = np.any([grown[1 + dy:grown.shape[0] - 1 + dy, 1 + dx:grown.shape[1] - 1 + dx]
                       for dy in (-1, 0, 1) for dx in (-1, 0, 1)], axis=0)
    centres = []
    for x0, y0, x1, y1, n in holes(mask):
        fill = n / ((x1 - x0 + 1) * (y1 - y0 + 1))
        cx, cy = bx0 + (x0 + x1) / 2, by0 + (y0 + y1) / 2
        if not (r.area[0] <= n <= r.area[1] and r.fill[0] <= fill <= r.fill[1]):
            continue
        if any(ex0 <= cx <= ex1 and ey0 <= cy <= ey1 for ex0, ey0, ex1, ey1 in r.exclude):
            continue
        centres.append((cx, cy))
    if len(centres) != r.count:
        raise RecipeError(f"{r.id}: expected {r.count} markers, found {len(centres)} at "
                          f"{[(round(x, 1), round(y, 1)) for x, y in sorted(centres)]}")
    return np.array([c[0] for c in centres]), np.array([c[1] for c in centres])


def locate(r, datasheets=DATASHEETS):
    """(pixels, ppm, ratio, x, y), sorted by concentration."""
    pixels = r.pixels(datasheets)
    x, y = find(pixels, r)
    ppm, ratio = 10 ** r.x.to_log10(x), 10 ** r.y.to_log10(y)
    order = np.argsort(ppm)
    return pixels, ppm[order], ratio[order], x[order], y[order]
