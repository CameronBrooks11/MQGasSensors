"""Get a figure's pixels: from an image file, or straight out of a datasheet PDF.

Datasheet figures are taken as the image object embedded in the PDF, not by
rendering the page, so the pixels do not depend on a renderer or a resolution.
A recipe names the figure by a hash of its pixels, which also proves that the
figure being traced is the one the recipe was written for.
"""
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image


class FigureError(ValueError):
    pass


def pixel_hash(pixels):
    """SHA-256 over the image size and its RGB bytes."""
    h, w = pixels.shape[:2]
    return hashlib.sha256(f"{w}x{h}:".encode() + np.ascontiguousarray(pixels).tobytes()).hexdigest()


def from_image(path):
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))


def embedded_images(pdf_path, page):
    """The image objects on a page (numbered from 1), as RGB arrays, in document order."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        if not 1 <= page <= len(pdf):
            raise FigureError(f"{pdf_path}: no page {page} (the document has {len(pdf)})")
        objects = pdf[page - 1].get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE])
        return [np.asarray(o.get_bitmap(render=False).to_pil().convert("RGB")) for o in objects]
    finally:
        pdf.close()


def from_datasheet(pdf_path, page, pixels_sha256):
    """The embedded image on `page` whose pixels hash to `pixels_sha256`."""
    if not Path(pdf_path).exists():
        raise FigureError(f"{pdf_path} is missing: run `just datasheets` to download it")
    images = embedded_images(pdf_path, page)
    for pixels in images:
        if pixel_hash(pixels) == pixels_sha256:
            return pixels
    found = ", ".join(f"{p.shape[1]}x{p.shape[0]} {pixel_hash(p)[:12]}" for p in images) or "none"
    raise FigureError(f"{pdf_path} page {page}: no embedded image with pixels {pixels_sha256[:12]}; found {found}")
