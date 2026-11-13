"""Finding the hollow markers of one line in a figure stored as an image."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from mqcurves import cli, markers, points
from mqcurves.recipe import RecipeError

ROOT = Path(__file__).resolve().parents[2]
RED, GREY, WHITE = (254, 0, 0), (128, 128, 128), (254, 254, 254)

# 100 px a decade both ways: 10 to 10000 ppm across, Rs/R0 10 down to 0.01.
LEFT, RIGHT, TOP, BOTTOM = 20, 320, 20, 320
SQUARES = ((70, 120), (170, 170), (270, 220))   # pixel centres
TRIANGLES = ((70, 100), (170, 140), (270, 180))
LEGEND = (40, 280)


# Markers are filled with the background, as in the datasheets, so a line
# through one does not show inside it.
def square(d, x, y):
    d.rectangle([x - 3, y - 3, x + 3, y + 3], outline=RED, fill=WHITE)


def triangle(d, x, y):
    d.polygon([(x, y - 4), (x + 4, y + 3), (x - 4, y + 3)], outline=RED, fill=WHITE)


def figure(gap=False, overlap=False):
    """Two red lines, one with squares and one with triangles; grey gridlines drawn over the lines; a legend."""
    im = Image.new("RGB", (340, 340), WHITE)
    d = ImageDraw.Draw(im)
    d.line(SQUARES, fill=RED)
    d.line(TRIANGLES, fill=RED)
    for x in range(LEFT, RIGHT + 1, 25):
        d.line([(x, TOP), (x, BOTTOM)], fill=GREY)
    for x, y in SQUARES:
        square(d, x, y)
    for x, y in TRIANGLES:
        triangle(d, x, y)
    if overlap:
        # A triangle drawn over the top of the middle square, as two markers at one place.
        x, y = SQUARES[1]
        triangle(d, x, y - 6)
    square(d, *LEGEND)
    if gap:
        x, y = SQUARES[2]
        d.point((x, y - 3), fill=WHITE)
    return im


def recipe_text(fill="[0.9, 1.0]", area="[10, 40]", count=3, exclude=True, close=0):
    return f"""id = "synthetic-h2-located"
sensor = "MQ-0"
gas = "H2"

[source]
image = "figure.png"

[x]
pixels = [{LEFT}, {RIGHT}]
values = [10, 10000]

[y]
pixels = [{TOP}, {BOTTOM}]
values = [10, 0.01]

[markers]
colour = [254, 0, 0]
box = [10, 10, 330, 330]
{"exclude = [[30, 270, 50, 290]]" if exclude else ""}
area = {area}
fill = {fill}
count = {count}
close = {close}
"""


class MarkerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        figure().save(self.dir / "figure.png")

    def find(self, **kw):
        path = self.dir / "curve.toml"
        path.write_text(recipe_text(**kw))
        r = markers.load(path)
        return markers.find(r.pixels(), r)

    def test_square_centres_come_back_exactly(self):
        x, y = self.find()
        self.assertEqual(sorted(zip(x.tolist(), y.tolist())), sorted(SQUARES))

    def test_squares_and_triangles_of_one_colour_are_told_apart_by_fill(self):
        x, y = self.find(fill="[0.3, 0.8]", area="[5, 40]")
        np.testing.assert_allclose(sorted(zip(x, y)), sorted(TRIANGLES), atol=0.5)

    def test_square_under_a_triangle_is_still_found(self):
        figure(overlap=True).save(self.dir / "figure.png")
        x, y = self.find(area="[5, 40]")
        found = sorted(zip(x.tolist(), y.tolist()))
        self.assertEqual(len(found), 3)
        # Its hole is cut short at the top, so its centre moves down by at most 2 px.
        self.assertAlmostEqual(found[1][0], SQUARES[1][0])
        self.assertLessEqual(abs(found[1][1] - SQUARES[1][1]), 2)

    def test_legend_marker_is_counted_unless_excluded(self):
        with self.assertRaisesRegex(RecipeError, "expected 3 markers, found 4"):
            self.find(exclude=False)

    def test_patch_enclosed_between_two_lines_is_not_a_marker(self):
        # Two lines that meet at both ends enclose the space between them: a patch far
        # larger than a marker's hole, and as square as one.
        im = Image.new("RGB", (340, 340), WHITE)
        d = ImageDraw.Draw(im)
        d.line([(100, 100), (200, 100), (200, 140), (100, 140), (100, 100)], fill=RED)
        square(d, *SQUARES[2])
        im.save(self.dir / "figure.png")
        with self.assertRaisesRegex(RecipeError, "expected 1 markers, found 2"):
            self.find(area="[10, 100000]", count=1, exclude=False)
        x, y = self.find(count=1, exclude=False)
        self.assertEqual((x[0], y[0]), SQUARES[2])

    def test_outline_with_a_gap_is_found_only_when_closed(self):
        figure(gap=True).save(self.dir / "figure.png")
        with self.assertRaisesRegex(RecipeError, "found 2"):
            self.find()
        x, y = self.find(close=1, area="[5, 15]")
        self.assertEqual(sorted(zip(x.tolist(), y.tolist())), sorted(SQUARES))

    def test_locate_converts_centres_through_the_axes(self):
        path = self.dir / "curve.toml"
        path.write_text(recipe_text())
        _, ppm, ratio, _, _ = markers.locate(markers.load(path))
        np.testing.assert_allclose(ppm, [10 ** (1 + (x - LEFT) / 100) for x, _ in SQUARES])
        np.testing.assert_allclose(ratio, [10 ** (1 - (y - TOP) / 100) for _, y in SQUARES])


@unittest.skipUnless((ROOT / "datasheets" / "files" / "mq-303a-hanwei-2006.pdf").exists(),
                     "datasheets not downloaded (run `just datasheets`)")
class RealDatasheetTests(unittest.TestCase):
    def test_mq303a_ethanol_markers_match_the_committed_points(self):
        recipe = ROOT / "analysis" / "recipes" / "mq-303a-hanwei-2006-ethanol-located.toml"
        committed = ROOT / "analysis" / "points" / "mq-303a-hanwei-2006" / "ethanol-located.csv"
        with tempfile.TemporaryDirectory() as d:
            csv = Path(d) / "points.csv"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["locate", str(recipe), "--points", str(csv)]), 0)
            self.assertEqual(csv.read_bytes(), committed.read_bytes())
        ppm, _ = points.read(committed)
        self.assertEqual(len(ppm), 7)


if __name__ == "__main__":
    unittest.main()
