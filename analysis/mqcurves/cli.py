"""Command line: python -m mqcurves <command>

    figures <datasheet.pdf> [--page N] [--save DIR]   list a PDF's embedded images
    trace <recipe.toml> [--points CSV] [--overlay PNG] trace a curve from its recipe
    fit <points.csv>                                   fit points already digitised
    mark <recipe.toml> ...                             mark a new figure by hand
    table [--check]                                    write docs/coefficients.md
    reproduce                                          re-trace every traced curve and compare
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
    print(f"  r^2 = {f.r_squared:.5f}   largest error against the points: {f.max_ppm_error * 100:.1f} % in ppm")


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
    ppm, ratio, px, py = trace(pixels, r.seed, r.x, r.y, r.lo, r.up, r.bin_width, r.connectivity, r.max_thickness)
    if r.ppm is not None:
        keep = (ppm >= r.ppm[0]) & (ppm <= r.ppm[1])
        ppm, ratio, px, py = ppm[keep], ratio[keep], px[keep], py[keep]
    return pixels, ppm, ratio, px, py, fit(ppm, ratio)


def run_checks(r, ppm, ratio):
    """Compare the trace with each value read off the figure by eye. Returns (lines, all passed).

    Inside the traced range the trace is interpolated. A value read at the end
    of a line sits on a marker, whose columns a recipe may leave out, so up to a
    factor of 1.5 beyond the range the nearest 20 points are extended as a
    straight line on log-log axes.
    """
    import numpy as np

    order = np.argsort(ppm)
    lx, ly = np.log10(ppm[order]), np.log10(ratio[order])
    lines, ok = [], True
    for at, expected, within in r.checks:
        la = np.log10(at)
        if lx[0] <= la <= lx[-1]:
            traced, how = 10 ** float(np.interp(la, lx, ly)), "traced"
        elif ppm.min() / 1.5 <= at <= ppm.max() * 1.5:
            near = slice(0, 20) if la < lx[0] else slice(-20, None)
            slope, intercept = np.polyfit(lx[near], ly[near], 1)
            traced, how = 10 ** float(intercept + slope * la), "extended"
        else:
            lines.append(f"  check at {at:g} ppm: outside the traced range  FAILED")
            ok = False
            continue
        apart = abs(traced / expected - 1)
        passed = apart <= within
        ok &= passed
        lines.append(f"  check at {at:g} ppm: {how} {traced:.4g}, read by eye {expected:g} ({apart * 100:.1f} % apart, limit {within * 100:.0f} %)"
                     f"{'' if passed else '  FAILED'}")
    return lines, ok


def cmd_trace(args):
    r = recipe.load(args.recipe)
    pixels, ppm, ratio, px, py, f = run_recipe(r, args.datasheets)
    report(r.id, f)
    lines, ok = run_checks(r, ppm, ratio)
    print("\n".join(lines)) if lines else None
    if args.points:
        points.write(args.points, ppm, ratio)
        print(f"  points written to {args.points}")
    if args.overlay:
        args.overlay.parent.mkdir(parents=True, exist_ok=True)
        overlay.draw(pixels, r.x, r.y, r.seed, px, py, f).save(args.overlay)
        print(f"  overlay written to {args.overlay} (contains the datasheet figure: do not commit)")
    return 0 if ok else 1


def cmd_reproduce(args):
    """Re-trace every traced curve from its datasheet and compare with the committed points."""
    import tempfile
    import tomllib

    from . import table

    with open(table.ANALYSIS / "curves.toml", "rb") as fh:
        traced = [c for c in tomllib.load(fh)["curve"] if c["origin"] == "traced"]
    failed = 0
    for c in traced:
        r = recipe.load(table.ANALYSIS / c["recipe"])
        _, ppm, ratio, _, _, _ = run_recipe(r, args.datasheets)
        with tempfile.TemporaryDirectory() as d:
            fresh = Path(d) / "points.csv"
            points.write(fresh, ppm, ratio)
            same = fresh.read_bytes() == (table.ANALYSIS / c["points"]).read_bytes()
        lines, ok = run_checks(r, ppm, ratio)
        failed += not (same and ok)
        print(f"{'ok      ' if same and ok else 'FAILED  '}{c['id']}: {len(ppm)} points "
              f"{'identical to' if same else 'DIFFER from'} {c['points']}, {len(lines)} checks {'pass' if ok else 'FAIL'}")
        if not ok:
            print("\n".join(lines))
    print(f"{len(traced) - failed} of {len(traced)} traced curves reproduced from their datasheets")
    return 1 if failed else 0


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

    s = sub.add_parser("reproduce", help="re-trace every traced curve from its datasheet; fail on any difference")
    s.add_argument("--datasheets", type=Path, default=recipe.DATASHEETS)
    s.set_defaults(func=cmd_reproduce)

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
