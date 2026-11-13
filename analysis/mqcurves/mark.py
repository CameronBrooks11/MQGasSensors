"""Mark a figure by hand: click the axis references and a point on the curve.

Opens the figure in a matplotlib window. For each axis, click two positions
whose values you know (gridlines or tick marks) and type each value in the
terminal. Then click the curve. The recipe is written, traced and shown back
as an overlay so the result can be judged before it is kept.

Needs the `interactive` extra: uv sync --extra interactive
"""
from pathlib import Path

from . import figure, recipe


def source_for(args):
    """The [source] table for a recipe, and the figure's pixels."""
    if args.image:
        image = Path(args.image).resolve()
        rel = image.relative_to(Path(args.recipe).resolve().parent, walk_up=True)
        return {"image": rel.as_posix()}, figure.from_image(image)
    if not (args.page and args.pixels_sha256):
        raise ValueError("--datasheet needs --page and --pixels-sha256 (see `mqcurves figures`)")
    pdf = Path(args.datasheets) / f"{args.datasheet}.pdf"
    pixels = figure.from_datasheet(pdf, args.page, args.pixels_sha256)
    return {"datasheet": args.datasheet, "page": args.page, "pixels_sha256": args.pixels_sha256}, pixels


def write(args, source, clicks, values):
    """Write the recipe from five clicks: x ref 1 and 2, y ref 1 and 2, the curve."""
    (x1, _), (x2, _), (_, y1), (_, y2), (sx, sy) = clicks
    recipe.dump(
        args.recipe, id=args.id, sensor=args.sensor, gas=args.gas, source=source,
        x=((round(x1, 1), values[0]), (round(x2, 1), values[1])),
        y=((round(y1, 1), values[2]), (round(y2, 1), values[3])),
        seed=(round(sx), round(sy)),
    )


def run(args):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ValueError("marking needs matplotlib: uv sync --extra interactive") from None
    from .cli import report, run_recipe
    from .overlay import draw

    source, pixels = source_for(args)
    fig, ax = plt.subplots(figsize=(10, 7.6))
    ax.imshow(pixels, interpolation="nearest")
    prompts = ("a position on the ppm axis", "a second position on the ppm axis",
               "a position on the Rs/R0 axis", "a second position on the Rs/R0 axis")
    clicks, values = [], []
    for prompt in prompts:
        ax.set_title(f"Click {prompt}, then type its value in the terminal")
        fig.canvas.draw()
        clicks.append(plt.ginput(1, timeout=0)[0])
        values.append(float(input(f"Value at {prompt}: ")))
    ax.set_title("Click a point on the curve to trace")
    fig.canvas.draw()
    clicks.append(plt.ginput(1, timeout=0)[0])
    plt.close(fig)

    write(args, source, clicks, values)
    r = recipe.load(args.recipe)
    pixels, _, _, px, py, f = run_recipe(r, args.datasheets)
    report(r.id, f)
    print(f"recipe written to {args.recipe}")
    plt.imshow(draw(pixels, r.x, r.y, r.seed, px, py, f))
    plt.title("Trace (red), fit (black), axis references (magenta). Close to finish.")
    plt.axis("off")
    plt.show()
    return 0
