"""Draw a trace and its fit over the figure, for checking by eye.

The result contains the datasheet's figure, so it is for local use only and is
never committed.
"""
import numpy as np
from PIL import Image, ImageDraw

SCALE = 3


def draw(pixels, x_axis, y_axis, seed, px, py, fit):
    img = Image.fromarray(pixels).resize((pixels.shape[1] * SCALE, pixels.shape[0] * SCALE), Image.NEAREST)
    d = ImageDraw.Draw(img)

    def at(x, y):
        return ((x + 0.5) * SCALE, (y + 0.5) * SCALE)

    # Axis reference positions: where the recipe says the known values sit.
    h, w = pixels.shape[:2]
    for p in (x_axis.pixel_a, x_axis.pixel_b):
        d.line([at(p, 0), at(p, h - 1)], fill=(255, 0, 255), width=1)
    for p in (y_axis.pixel_a, y_axis.pixel_b):
        d.line([at(0, p), at(w - 1, p)], fill=(255, 0, 255), width=1)

    # The fitted power law across the traced range.
    ppm = np.logspace(np.log10(fit.ppm_min), np.log10(fit.ppm_max), 200)
    line = [at(float(x), float(y)) for x, y in zip(x_axis.to_pixel(ppm), y_axis.to_pixel(fit.A * ppm**fit.B), strict=True)]
    d.line(line, fill=(0, 0, 0), width=2)

    # The traced centreline, one dot per point, and the seed.
    for x, y in zip(px, py, strict=True):
        cx, cy = at(float(x), float(y))
        d.ellipse([cx - 1.5, cy - 1.5, cx + 1.5, cy + 1.5], fill=(255, 0, 0))
    sx, sy = at(*seed)
    d.ellipse([sx - 6, sy - 6, sx + 6, sy + 6], outline=(255, 128, 0), width=2)
    return img
