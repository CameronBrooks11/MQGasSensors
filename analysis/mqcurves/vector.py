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
    # shape = "x"                    # optional: "outline", "polygon", "round", "x", "star" or "plus"

The datasheet must match the SHA-256 the manifest records, and the page must
draw a rectangle at the frame's coordinates; otherwise nothing is read.

A marker is drawn either as one outline (a square, a circle), centred on its
bounding box, or as straight strokes out from its centre (a cross), drawn one
after another. Both are read as subpaths, so it does not matter whether the PDF
puts each marker in its own path object or all of a line's markers in one. Consecutive strokes that start at the same point are one
marker, centred on that point. That stays right when the frame clips some of
the strokes away, and keeps apart two markers that sit at the same place.
Markers that share colours are told apart by `shape`. An "outline" is a single
outline of any kind: a "polygon" one has only straight sides (a square, a
triangle), a "round" one is drawn with curves (a circle). Of markers drawn as
strokes, an "x" has only diagonal strokes, a "star" adds vertical ones, and a
"plus" has none.
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
    start: tuple = (0.0, 0.0)
    end: tuple = (0.0, 0.0)
    points: int = 0
    curved: bool = False

    @property
    def is_stroke(self):
        return self.points == 2


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
    shape: str | None
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
        shape = m.get("shape")
        if shape not in (None, *SHAPES):
            raise VectorError(f"[markers] shape must be one of {', '.join(SHAPES)}")
        return Recipe(
            id=doc["id"], sensor=doc["sensor"], gas=doc["gas"],
            datasheet=doc["source"]["datasheet"], page=int(doc["source"]["page"]),
            frame=(x0, y0, x1, y1), x=Axis(x0, pa, x1, pb), y=Axis(y0, ra, y1, rb),
            stroke=_colour(m, "stroke"), fill=_colour(m, "fill"), count=int(m["count"]),
            exclude=exclude, shape=shape, path=path,
        )
    except KeyError as err:
        raise VectorError(f"{path}: missing {err}") from err


def page_paths(pdf_path, page):
    """Every subpath of every top-level path object on a page (numbered from 1), in drawing order.

    A subpath starts at each move. Some PDF writers draw one marker per path
    object, others all of a line's markers as the subpaths of one.
    """
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
            subpaths = []
            for i in range(raw.FPDFPath_CountSegments(h)):
                seg = raw.FPDFPath_GetPathSegment(h, i)
                x, y = ctypes.c_float(), ctypes.c_float()
                raw.FPDFPathSegment_GetPoint(seg, x, y)
                kind = raw.FPDFPathSegment_GetType(seg)
                if kind == raw.FPDF_SEGMENT_MOVETO or not subpaths:
                    subpaths.append(([], [False]))
                subpaths[-1][0].append((m.a * x.value + m.c * y.value + m.e, m.b * x.value + m.d * y.value + m.f))
                subpaths[-1][1][0] |= kind == raw.FPDF_SEGMENT_BEZIERTO
            colours = []
            for get in (raw.FPDFPageObj_GetStrokeColor, raw.FPDFPageObj_GetFillColor):
                r, g, b, a = (ctypes.c_uint() for _ in range(4))
                get(h, r, g, b, a)
                colours.append((r.value, g.value, b.value))
            for pts, (curved,) in subpaths:
                xs, ys = [q[0] for q in pts], [q[1] for q in pts]
                out.append(Shape(colours[0], colours[1], min(xs), min(ys), max(xs), max(ys), pts[0], pts[-1], len(pts),
                                 curved))
        return out
    finally:
        pdf.close()


def _inside(p, box):
    x0, y0, x1, y1 = box
    return x0 <= p.x0 and p.x1 <= x1 and y0 <= p.y0 and p.y1 <= y1


SHAPES = ("outline", "polygon", "round", "x", "star", "plus")


def _shape(strokes):
    """"x", "star" or "plus" for a marker's strokes, by the directions they point in."""
    kinds = set()
    for p in strokes:
        dx, dy = abs(p.end[0] - p.start[0]), abs(p.end[1] - p.start[1])
        kinds.add("vertical" if dx < 0.25 * dy else "horizontal" if dy < 0.25 * dx else "diagonal")
    if kinds == {"diagonal"}:
        return "x"
    if "diagonal" in kinds and "vertical" in kinds:
        return "star"
    if "diagonal" not in kinds:
        return "plus"
    return None


def _same(a, b):
    return all(abs(u - v) <= TOLERANCE for u, v in zip(a, b, strict=True))


def _kind(group):
    """The shape of one marker: "polygon" or "round" for an outline, else that of its strokes."""
    if group[0].is_stroke:
        return _shape(group)
    return "round" if group[0].curved else "polygon"


def _group(paths):
    """Split subpaths, in drawing order, into markers: each a list of subpaths.

    Consecutive strokes from the same point are one marker, and so are
    consecutive outlines with the same bounding box: one marker drawn twice,
    once filled and once stroked.
    """
    groups = []
    for p in paths:
        q = groups[-1][-1] if groups else None
        if q and p.is_stroke and q.is_stroke and _same(p.start, q.start):
            groups[-1].append(p)
        elif q and not p.is_stroke and not q.is_stroke and _same((p.x0, p.y0, p.x1, p.y1), (q.x0, q.y0, q.x1, q.y1)):
            groups[-1].append(p)
        else:
            groups.append([p])
    return groups


def _centre(group):
    if group[0].is_stroke:
        return group[0].start
    p = group[0]
    return ((p.x0 + p.x1) / 2, (p.y0 + p.y1) / 2)


def markers(paths, r):
    """Centres of the recipe's markers inside its frame, sorted by x, in points."""
    if not any(_same((p.x0, p.y0, p.x1, p.y1), r.frame) for p in paths):
        raise VectorError(f"{r.id}: no rectangle drawn at the frame {list(r.frame)} on page {r.page}")
    frame = (r.frame[0] - MAX_MARKER, r.frame[1] - MAX_MARKER, r.frame[2] + MAX_MARKER, r.frame[3] + MAX_MARKER)
    # A subpath larger than a marker is a line, a legend sample or a box, whatever its colours.
    chosen = [p for p in paths if p.stroke == r.stroke and p.fill == r.fill
              and p.x1 - p.x0 <= MAX_MARKER and p.y1 - p.y0 <= MAX_MARKER
              and _inside(p, frame) and not any(_inside(p, box) for box in r.exclude)]
    groups = _group(chosen)
    if r.shape is not None:
        groups = [g for g in groups if _kind(g) == r.shape or (r.shape == "outline" and not g[0].is_stroke)]
    centres = sorted(_centre(g) for g in groups)
    if len(centres) != r.count:
        raise VectorError(f"{r.id}: expected {r.count} markers, found {len(centres)} at x "
                          f"{[round(x, 2) for x, _ in centres]}")
    return np.array([c[0] for c in centres]), np.array([c[1] for c in centres])


def extract(r, pdf_path):
    """(ppm, ratio, x, y): the plotted values, and the marker centres they come from."""
    x, y = markers(page_paths(pdf_path, r.page), r)
    return 10 ** r.x.to_log10(x), 10 ** r.y.to_log10(y), x, y
