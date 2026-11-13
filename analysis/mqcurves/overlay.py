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

    # The traced centreline, one dot per point, and the seed. Without a seed the
    # points are marker centres: a ring and a dot each.
    for x, y in zip(px, py, strict=True):
        cx, cy = at(float(x), float(y))
        d.ellipse([cx - 1.5, cy - 1.5, cx + 1.5, cy + 1.5], fill=(255, 0, 0))
        if seed is None:
            d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=(255, 128, 0), width=2)
    if seed is not None:
        sx, sy = at(*seed)
        d.ellipse([sx - 6, sy - 6, sx + 6, sy + 6], outline=(255, 128, 0), width=2)
    return img


def draw_page(pdf_path, page, frame, x_axis, y_axis, xs, ys, fit, scale=4, margin=30):
    """The page rendered around a vector figure's frame, with the markers found and the fit.

    `frame`, `xs` and `ys` are in PDF points, y upwards.
    """
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        p = pdf[page - 1]
        height = p.get_height()
        img = p.render(scale=scale).to_pil().convert("RGB")
    finally:
        pdf.close()
    d = ImageDraw.Draw(img)

    def at(x, y):
        return (x * scale, (height - y) * scale)

    ppm = np.logspace(np.log10(fit.ppm_min), np.log10(fit.ppm_max), 200)
    line = [at(float(x), float(y)) for x, y in zip(x_axis.to_pixel(ppm), y_axis.to_pixel(fit.A * ppm**fit.B), strict=True)]
    d.line(line, fill=(0, 0, 0), width=2)
    for x, y in zip(xs, ys, strict=True):
        cx, cy = at(float(x), float(y))
        d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], outline=(255, 128, 0), width=2)
        d.line([cx - 14, cy, cx + 14, cy], fill=(255, 0, 0), width=1)
        d.line([cx, cy - 14, cx, cy + 14], fill=(255, 0, 0), width=1)
    left, top = at(frame[0] - margin, frame[3] + margin)
    right, bottom = at(frame[2] + margin, frame[1] - margin)
    return img.crop((int(max(left, 0)), int(max(top, 0)), int(min(right, img.width)), int(min(bottom, img.height))))
