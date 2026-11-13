"""Command line: python -m mqcurves <command>

    figures <datasheet.pdf> [--page N] [--save DIR]   list a PDF's embedded images
    trace <recipe.toml> [--points CSV] [--overlay PNG] trace a curve from its recipe
    fit <points.csv>                                   fit points already digitised
    mark <recipe.toml> ...                             mark a new figure by hand
    table [--check]                                    write docs/coefficients.md
"""
import argparse
import sys
from pathlib import Path

from . import figure, overlay, points, recipe
from .trace import fit, trace


def report(label, f):
    print(f"{label}: {f.n} points, {f.ppm_min:.4g} to {f.ppm_max:.4g} ppm, Rs/R0 {f.ratio_min:.4g} to {f.ratio_max:.4g}")
    print(f"  ratio = A * ppm^B     A = {f.A:.5g}   B = {f.B:.5g}")
    print(f"  ppm = a * ratio^b     a = {f.a:.5g}   b = {f.b:.5g}    (setA, setB)")
    print(f"  r^2 = {f.r_squared:.5f}")


def cmd_figures(args):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(args.pdf))
    pages = [args.page] if args.page else range(1, len(pdf) + 1)
    pdf.close()
    for page in pages:
        for n, px in enumerate(figure.embedded_images(args.pdf, page)):
            digest = figure.pixel_hash(px)
            print(f"page {page} image {n}: {px.shape[1]}x{px.shape[0]}  pixels_sha256 = {digest}")
            if args.save:
                from PIL import Image

                args.save.mkdir(parents=True, exist_ok=True)
                Image.fromarray(px).save(args.save / f"{args.pdf.stem}-p{page}-{digest[:12]}.png")
    return 0


def run_recipe(r, datasheets=recipe.DATASHEETS):
    pixels = r.pixels(datasheets)
    ppm, ratio, px, py = trace(pixels, r.seed, r.x, r.y, r.lo, r.up, r.bin_width, r.connectivity)
    return pixels, ppm, ratio, px, py, fit(ppm, ratio)


def cmd_trace(args):
    r = recipe.load(args.recipe)
    pixels, ppm, ratio, px, py, f = run_recipe(r, args.datasheets)
    report(r.id, f)
    if args.points:
        points.write(args.points, ppm, ratio)
        print(f"  points written to {args.points}")
    if args.overlay:
        args.overlay.parent.mkdir(parents=True, exist_ok=True)
        overlay.draw(pixels, r.x, r.y, r.seed, px, py, f).save(args.overlay)
        print(f"  overlay written to {args.overlay} (contains the datasheet figure: do not commit)")
    return 0


def cmd_fit(args):
    report(str(args.points), fit(*points.read(args.points)))
    return 0


def cmd_mark(args):
    from . import mark

    return mark.run(args)


def cmd_table(args):
    from . import table

    return table.run(check=args.check)


def main(argv=None):
    p = argparse.ArgumentParser(prog="mqcurves", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("figures", help="list the images embedded in a datasheet PDF")
    s.add_argument("pdf", type=Path)
    s.add_argument("--page", type=int)
    s.add_argument("--save", type=Path, metavar="DIR", help="also save each image as PNG (local use only)")
    s.set_defaults(func=cmd_figures)

    s = sub.add_parser("trace", help="trace a curve from its recipe and fit it")
    s.add_argument("recipe", type=Path)
    s.add_argument("--points", type=Path, metavar="CSV", help="write the digitised points here")
    s.add_argument("--overlay", type=Path, metavar="PNG", help="write a picture of the trace over the figure")
    s.add_argument("--datasheets", type=Path, default=recipe.DATASHEETS, help="directory of downloaded datasheets")
    s.set_defaults(func=cmd_trace)

    s = sub.add_parser("fit", help="fit points that are already digitised")
    s.add_argument("points", type=Path)
    s.set_defaults(func=cmd_fit)

    s = sub.add_parser("mark", help="mark a new figure by hand and write its recipe (needs matplotlib)")
    s.add_argument("recipe", type=Path, help="recipe file to write")
    s.add_argument("--id", required=True)
    s.add_argument("--sensor", required=True)
    s.add_argument("--gas", required=True)
    src = s.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", type=Path, help="an image file")
    src.add_argument("--datasheet", help="a manifest id; with --page and --pixels-sha256")
    s.add_argument("--page", type=int)
    s.add_argument("--pixels-sha256")
    s.add_argument("--datasheets", type=Path, default=recipe.DATASHEETS)
    s.set_defaults(func=cmd_mark)

    s = sub.add_parser("table", help="write docs/coefficients.md from analysis/curves.toml")
    s.add_argument("--check", action="store_true", help="fail if the committed file is out of date")
    s.set_defaults(func=cmd_table)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (recipe.RecipeError, figure.FigureError, ValueError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
