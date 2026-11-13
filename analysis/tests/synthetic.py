"""Draw a log-log sensitivity figure with known curves, like a datasheet's."""
import numpy as np
from PIL import Image, ImageDraw

from mqcurves.trace import Axis

WIDTH, HEIGHT = 400, 305
# Plot area in pixels, and the values at its edges: 100 to 10000 ppm across,
# Rs/R0 of 1 at the top down to 0.01 at the bottom.
LEFT, RIGHT, TOP, BOTTOM = 50, 380, 15, 270
X_AXIS = Axis(LEFT, 100.0, RIGHT, 10000.0)
Y_AXIS = Axis(TOP, 1.0, BOTTOM, 0.01)

BLUE = (68, 114, 196)
GREEN = (155, 187, 89)
GRID = (191, 191, 191)


def polyline(curve_a, curve_b, ppm_from, ppm_to):
    """Pixel vertices of ratio = curve_a * ppm**curve_b between two ppm values."""
    ppm = np.logspace(np.log10(ppm_from), np.log10(ppm_to), 60)
    ratio = curve_a * ppm**curve_b
    return list(zip(X_AXIS.to_pixel(ppm).tolist(), Y_AXIS.to_pixel(ratio).tolist(), strict=True))


def figure(curve_a, curve_b, ppm_from, ppm_to):
    """A figure whose blue curve is ratio = curve_a * ppm**curve_b over part of the plot.

    Also drawn: grey gridlines the curve crosses, a second curve in another
    colour, and a legend sample in the curve's own colour that does not touch it.
    Returns (HxWx3 uint8 array, a seed pixel on the blue curve).
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    d = ImageDraw.Draw(img)
    for decade in (100, 1000, 10000):
        for m in range(1, 10):
            x = float(X_AXIS.to_pixel(decade * m))
            if LEFT <= x <= RIGHT:
                d.line([(x, TOP), (x, BOTTOM)], fill=GRID, width=1)
    for decade in (0.01, 0.1, 1):
        for m in range(1, 10):
            y = float(Y_AXIS.to_pixel(decade * m))
            if TOP <= y <= BOTTOM:
                d.line([(LEFT, y), (RIGHT, y)], fill=GRID, width=1)
    d.rectangle([LEFT, TOP, RIGHT, BOTTOM], outline=(0, 0, 0))

    d.line(polyline(0.9, -0.05, 100, 10000), fill=GREEN, width=3)
    pts = polyline(curve_a, curve_b, ppm_from, ppm_to)
    d.line(pts, fill=BLUE, width=3, joint="curve")
    d.line([(70, 235), (100, 235)], fill=BLUE, width=3)  # legend sample
    d.text((106, 229), "H2", fill=(0, 0, 0))

    mid = pts[len(pts) // 2]
    return np.asarray(img), (round(mid[0]), round(mid[1]))
