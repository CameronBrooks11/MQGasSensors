"""Isolate one curve of a log-log datasheet figure and turn it into data points.

The method: starting from a marked pixel on the curve, collect every connected
pixel whose colour is within a tolerance of that pixel's colour (a fixed-range
flood fill). Average the collected pixels column by column to get the centre of
the stroke, then convert pixel positions to data values through the axis
calibration.

The calibration is two marked positions per axis with their known values. It
does not depend on where the curve starts or ends, so a curve that covers only
part of the plot is read correctly.
"""
from dataclasses import dataclass

import numpy as np


# Columns left out either side of one that exceeds a recipe's max_thickness.
MARKER_MARGIN = 3


@dataclass(frozen=True)
class Axis:
    """A logarithmic axis fixed by two pixel positions with known values."""

    pixel_a: float
    value_a: float
    pixel_b: float
    value_b: float

    def __post_init__(self):
        if self.pixel_a == self.pixel_b:
            raise ValueError("axis reference pixels must differ")
        if self.value_a <= 0 or self.value_b <= 0 or self.value_a == self.value_b:
            raise ValueError("axis reference values must be positive and differ")

    def to_log10(self, pixel):
        la, lb = np.log10(self.value_a), np.log10(self.value_b)
        return la + (np.asarray(pixel, dtype=float) - self.pixel_a) * (lb - la) / (self.pixel_b - self.pixel_a)

    def to_pixel(self, value):
        la, lb = np.log10(self.value_a), np.log10(self.value_b)
        return self.pixel_a + (np.log10(np.asarray(value, dtype=float)) - la) * (self.pixel_b - self.pixel_a) / (lb - la)


def flood(image, seed, lo, up, connectivity=8):
    """Mask of the pixels connected to `seed` whose colour is within range of it.

    A pixel qualifies when every channel c satisfies
    seed[c] - lo <= pixel[c] <= seed[c] + up. `image` is HxWx3 uint8 and `seed`
    is (x, y).
    """
    if connectivity not in (4, 8):
        raise ValueError("connectivity must be 4 or 8")
    h, w = image.shape[:2]
    sx, sy = seed
    if not (0 <= sx < w and 0 <= sy < h):
        raise ValueError(f"seed {seed} is outside the {w}x{h} image")
    px = image.astype(np.int16)
    ref = px[sy, sx]
    candidate = np.all((px >= ref - lo) & (px <= ref + up), axis=2)

    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if connectivity == 8:
        steps += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
    mask = np.zeros((h, w), dtype=bool)
    mask[sy, sx] = True
    stack = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        for dx, dy in steps:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and candidate[ny, nx] and not mask[ny, nx]:
                mask[ny, nx] = True
                stack.append((nx, ny))
    return mask


def centreline(mask, bin_width=1, max_thickness=None):
    """Mean row of the masked pixels in each `bin_width`-pixel-wide column band.

    Returns (x, y) pixel arrays: band centres and the stroke's mean row there.

    A marker drawn on the line has the line's colour, so the fill takes it too,
    and an asymmetric one (a triangle) pulls the mean row away from the line.
    With `max_thickness`, pixel columns where the trace is taller than that many
    pixels are left out: the line is a few pixels thick, a marker much more.
    So are the MARKER_MARGIN columns either side of them, where the marker
    tapers to within the limit but still sits off the line's centre.
    """
    if max_thickness is not None:
        thick = mask.sum(axis=0) > max_thickness
        near = np.convolve(thick, np.ones(2 * MARKER_MARGIN + 1), mode="same") > 0
        mask = mask & ~near[None, :]
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        raise ValueError("the trace is empty")
    x0 = xs.min()
    band = (xs - x0) // bin_width
    count = np.bincount(band)
    keep = count > 0
    cx = np.bincount(band, weights=xs)[keep] / count[keep]
    cy = np.bincount(band, weights=ys)[keep] / count[keep]
    return cx, cy


def trace(image, seed, x_axis, y_axis, lo=20, up=20, bin_width=1, connectivity=8, max_thickness=None):
    """Trace the curve through `seed` and return (ppm, ratio, pixel_x, pixel_y)."""
    mask = flood(image, seed, lo, up, connectivity)
    px, py = centreline(mask, bin_width, max_thickness)
    ppm = 10 ** x_axis.to_log10(px)
    ratio = 10 ** y_axis.to_log10(py)
    return ppm, ratio, px, py


@dataclass(frozen=True)
class Fit:
    """Power-law fits to the same points, in both directions.

    ratio = A * ppm**B   regression of log10(ratio) on log10(ppm): how the
                         datasheet draws the curve.
    ppm = a * ratio**b   regression of log10(ppm) on log10(ratio): the form the
                         library evaluates, passed to setA and setB.

    The two are not exact inverses of each other unless the points lie on a
    perfect line; r_squared says how close to one they are.

    max_ppm_error is the largest relative difference, over the fitted points,
    between a * ratio**b and the point's own ppm: how far the library's answer
    can be from the datasheet's curve within the fitted range.
    """

    A: float
    B: float
    a: float
    b: float
    r_squared: float
    n: int
    ppm_min: float
    ppm_max: float
    ratio_min: float
    ratio_max: float
    max_ppm_error: float


def fit(ppm, ratio):
    ppm, ratio = np.asarray(ppm, dtype=float), np.asarray(ratio, dtype=float)
    if ppm.size < 2:
        raise ValueError("at least two points are needed for a fit")
    if np.any(ppm <= 0) or np.any(ratio <= 0):
        raise ValueError("ppm and ratio must be positive")
    lx, ly = np.log10(ppm), np.log10(ratio)
    B, logA = np.polyfit(lx, ly, 1)
    b, loga = np.polyfit(ly, lx, 1)
    r = np.corrcoef(lx, ly)[0, 1]
    a = 10**loga
    max_ppm_error = float(np.max(np.abs(a * ratio**b / ppm - 1)))
    return Fit(
        A=float(10**logA), B=float(B), a=float(10**loga), b=float(b),
        r_squared=float(r * r), n=int(ppm.size),
        ppm_min=float(ppm.min()), ppm_max=float(ppm.max()),
        ratio_min=float(ratio.min()), ratio_max=float(ratio.max()),
        max_ppm_error=max_ppm_error,
    )
