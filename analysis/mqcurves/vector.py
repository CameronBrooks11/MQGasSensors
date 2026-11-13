"""Read a curve's plotted values out of a figure drawn with PDF vector commands.

Some datasheet figures are not images but drawings: lines, markers and
gridlines as path objects with coordinates. There the values the manufacturer
plotted are in the file, and no pixels are involved. Each plotted value is a
marker; its centre is the value. The segments between markers are the drawing
program's smoothing, not data, and are not read.

    id = "mq-4-hanwei-2007-ch4-extracted"
    sensor = "MQ-4"
    gas = "CH4"

    [source]
    datasheet = "mq-4-hanwei-2007"   # an id in datasheets/manifest.toml
    page = 2

    [frame]                          # the plot area, a rectangle drawn on the page
    x = [85.2, 353.04]               # its left and right edges, in PDF points
    y = [427.2, 651.36]              # its bottom and top edges
    ppm = [100, 10000]               # the concentration at the left and right edges
    ratio = [0.1, 10]                # Rs/R0 at the bottom and top edges

    [markers]                        # the gas's markers, by their colours
    stroke = [0, 0, 128]
    fill = [255, 0, 255]
    count = 4                        # how many the figure plots
    exclude = [[98.64, 433.44, 169.68, 536.64]]   # optional: boxes to ignore, e.g. the legend

The datasheet must match the SHA-256 the manifest records, and the page must
draw a rectangle at the frame's coordinates; otherwise nothing is read. A
marker is one or more paths of the marker colours whose bounding boxes touch,
and its centre is the centre of their joint bounding box.
"""
import ctypes
import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .trace import Axis

ROOT = Path(__file__).resolve().parents[2]
DATASHEETS = ROOT / "datasheets" / "files"
MANIFEST = ROOT / "datasheets" / "manifest.toml"

# Coordinates are compared within this many points: well under the 0.24 pt
# grid the figures checked so far are drawn on.
TOLERANCE = 0.01
# Paths of one marker touch; markers of one line are tens of points apart.
TOUCH = 0.5
# A path larger than this in either direction is a line, not a marker.
MAX_MARKER = 12.0


class VectorError(ValueError):
    pass


@dataclass(frozen=True)
class Shape:
    """A path object's colours and its bounding box on the page, in points."""

    stroke: tuple
    fill: tuple
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class Recipe:
    id: str
    sensor: str
    gas: str
    datasheet: str
    page: int
    frame: tuple
    x: Axis
    y: Axis
    stroke: tuple
    fill: tuple
    count: int
    exclude: tuple
    path: Path

    def pdf(self, datasheets=DATASHEETS, manifest=MANIFEST):
        """The datasheet's file, after checking it is the one the manifest names."""
        with open(manifest, "rb") as f:
            sheets = {d["id"]: d for d in tomllib.load(f)["datasheet"]}
        if self.datasheet not in sheets:
            raise VectorError(f"{self.path}: datasheet '{self.datasheet}' is not in {manifest}")
        pdf = Path(datasheets) / f"{self.datasheet}.pdf"
        if not pdf.exists():
            raise VectorError(f"{pdf} is missing: run `just datasheets` to download it")
        digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
        if digest != sheets[self.datasheet]["sha256"]:
            raise VectorError(f"{pdf}: SHA-256 {digest[:12]} is not the manifest's {sheets[self.datasheet]['sha256'][:12]}")
        return pdf


def _pair(table, key, name):
    v = table[key]
    if len(v) != 2:
        raise VectorError(f"[{name}] {key} must be [a, b]")
    return float(v[0]), float(v[1])


def _colour(table, key):
    v = tuple(int(c) for c in table[key])
    if len(v) != 3 or not all(0 <= c <= 255 for c in v):
        raise VectorError(f"[markers] {key} must be [r, g, b], each 0 to 255")
    return v


def load(path):
    path = Path(path)
    with open(path, "rb") as f:
        doc = tomllib.load(f)
    try:
        fr, m = doc["frame"], doc["markers"]
        (x0, x1), (y0, y1) = _pair(fr, "x", "frame"), _pair(fr, "y", "frame")
        (pa, pb), (ra, rb) = _pair(fr, "ppm", "frame"), _pair(fr, "ratio", "frame")
        exclude = tuple(tuple(float(v) for v in box) for box in m.get("exclude", []))
        if any(len(box) != 4 for box in exclude):
            raise VectorError("[markers] exclude must be a list of [x0, y0, x1, y1]")
        return Recipe(
            id=doc["id"], sensor=doc["sensor"], gas=doc["gas"],
            datasheet=doc["source"]["datasheet"], page=int(doc["source"]["page"]),
            frame=(x0, y0, x1, y1), x=Axis(x0, pa, x1, pb), y=Axis(y0, ra, y1, rb),
            stroke=_colour(m, "stroke"), fill=_colour(m, "fill"), count=int(m["count"]),
            exclude=exclude, path=path,
        )
    except KeyError as err:
        raise VectorError(f"{path}: missing {err}") from err


def page_paths(pdf_path, page):
    """Every top-level path object on a page (numbered from 1)."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        if not 1 <= page <= len(pdf):
            raise VectorError(f"{pdf_path}: no page {page} (the document has {len(pdf)})")
        out = []
        for obj in pdf[page - 1].get_objects(filter=[raw.FPDF_PAGEOBJ_PATH], max_depth=0):
            h = obj.raw
            m = raw.FS_MATRIX()
            raw.FPDFPageObj_GetMatrix(h, m)
            xs, ys = [], []
            for i in range(raw.FPDFPath_CountSegments(h)):
                x, y = ctypes.c_float(), ctypes.c_float()
                raw.FPDFPathSegment_GetPoint(raw.FPDFPath_GetPathSegment(h, i), x, y)
                xs.append(m.a * x.value + m.c * y.value + m.e)
                ys.append(m.b * x.value + m.d * y.value + m.f)
            if not xs:
                continue
            colours = []
            for get in (raw.FPDFPageObj_GetStrokeColor, raw.FPDFPageObj_GetFillColor):
                r, g, b, a = (ctypes.c_uint() for _ in range(4))
                get(h, r, g, b, a)
                colours.append((r.value, g.value, b.value))
            out.append(Shape(colours[0], colours[1], min(xs), min(ys), max(xs), max(ys)))
        return out
    finally:
        pdf.close()


def _inside(p, box):
    x0, y0, x1, y1 = box
    return x0 <= p.x0 and p.x1 <= x1 and y0 <= p.y0 and p.y1 <= y1


def markers(paths, r):
    """Centres of the recipe's markers inside its frame, sorted by x, in points."""
    if not any(all(abs(a - b) <= TOLERANCE for a, b in zip((p.x0, p.y0, p.x1, p.y1), r.frame, strict=True))
               for p in paths):
        raise VectorError(f"{r.id}: no rectangle drawn at the frame {list(r.frame)} on page {r.page}")
    frame = (r.frame[0] - MAX_MARKER, r.frame[1] - MAX_MARKER, r.frame[2] + MAX_MARKER, r.frame[3] + MAX_MARKER)
    chosen = [p for p in paths if p.stroke == r.stroke and p.fill == r.fill
              and _inside(p, frame) and not any(_inside(p, box) for box in r.exclude)]
    for p in chosen:
        if p.x1 - p.x0 > MAX_MARKER or p.y1 - p.y0 > MAX_MARKER:
            raise VectorError(f"{r.id}: a path of the marker colours spans {p.x1 - p.x0:.1f} by {p.y1 - p.y0:.1f} pt "
                              f"at x {p.x0:.2f}; that is a line, not a marker")

    # Join paths whose boxes touch: one marker can be drawn as several strokes.
    group = list(range(len(chosen)))

    def root(i):
        while group[i] != i:
            group[i] = group[group[i]]
            i = group[i]
        return i

    for i, a in enumerate(chosen):
        for j in range(i):
            b = chosen[j]
            if a.x0 <= b.x1 + TOUCH and b.x0 <= a.x1 + TOUCH and a.y0 <= b.y1 + TOUCH and b.y0 <= a.y1 + TOUCH:
                group[root(i)] = root(j)
    boxes = {}
    for i, p in enumerate(chosen):
        x0, y0, x1, y1 = boxes.get(root(i), (p.x0, p.y0, p.x1, p.y1))
        boxes[root(i)] = (min(x0, p.x0), min(y0, p.y0), max(x1, p.x1), max(y1, p.y1))
    centres = sorted(((x0 + x1) / 2, (y0 + y1) / 2) for x0, y0, x1, y1 in boxes.values())
    if len(centres) != r.count:
        raise VectorError(f"{r.id}: expected {r.count} markers, found {len(centres)} at x "
                          f"{[round(x, 2) for x, _ in centres]}")
    return np.array([c[0] for c in centres]), np.array([c[1] for c in centres])


def extract(r, pdf_path):
    """(ppm, ratio, x, y): the plotted values, and the marker centres they come from."""
    x, y = markers(page_paths(pdf_path, r.page), r)
    return 10 ** r.x.to_log10(x), 10 ** r.y.to_log10(y), x, y
