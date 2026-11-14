"""Marker positions read by eye: recorded in pixels, converted through the axes."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from mqcurves import cli, figure, marked, points
from mqcurves.recipe import RecipeError

ROOT = Path(__file__).resolve().parents[2]


def recipe_text(markers="[[20, 120], [120, 70], [220, 20]]", source='image = "figure.png"'):
    # 100 px a decade both ways: 10 ppm at x 20, Rs/R0 10 at y 20, y growing downwards.
    return f"""id = "synthetic-h2-marked"
sensor = "MQ-0"
gas = "H2"
markers = {markers}

[source]
{source}

[x]
pixels = [20, 220]
values = [10, 1000]

[y]
pixels = [20, 220]
values = [10, 0.1]
"""


class MarkedTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        Image.new("RGB", (240, 240), (255, 255, 255)).save(self.dir / "figure.png")

    def load(self, **kw):
        path = self.dir / "curve.toml"
        path.write_text(recipe_text(**kw))
        return marked.load(path)

    def test_positions_convert_through_the_axes_sorted_by_concentration(self):
        _, ppm, ratio, x, _ = marked.read(self.load(markers="[[220, 20], [20, 120], [120, 70]]"))
        np.testing.assert_allclose(ppm, [10, 100, 1000])
        np.testing.assert_allclose(ratio, [1, 10 ** 0.5, 10])
        np.testing.assert_allclose(x, [20, 120, 220])

    def test_position_outside_the_figure_is_refused(self):
        with self.assertRaisesRegex(RecipeError, "outside the 240x240 figure"):
            marked.read(self.load(markers="[[20, 120], [260, 70]]"))

    def test_fewer_than_two_positions_or_a_bad_one_is_refused(self):
        for bad in ("[[20, 120]]", "[[20, 120], [120]]", "[[20, 120], [120, 70, 3]]"):
            with self.assertRaisesRegex(RecipeError, "at least two"):
                self.load(markers=bad)

    def test_figure_must_match_the_recorded_pixels(self):
        pdf = self.dir / "sheet.pdf"
        Image.new("RGB", (240, 240), (255, 255, 255)).save(pdf)
        r = self.load(source='datasheet = "sheet"\npage = 1\npixels_sha256 = "' + "0" * 64 + '"')
        with self.assertRaises(figure.FigureError):
            marked.read(r, datasheets=self.dir)


@unittest.skipUnless((ROOT / "datasheets" / "files" / "mq-136-hanwei-2004.pdf").exists(),
                     "datasheets not downloaded (run `just datasheets`)")
class RealDatasheetTests(unittest.TestCase):
    def test_mq136_h2s_positions_give_the_committed_points(self):
        recipe = ROOT / "analysis" / "recipes" / "mq-136-hanwei-2004-h2s-marked.toml"
        committed = ROOT / "analysis" / "points" / "mq-136-hanwei-2004" / "h2s-marked.csv"
        with tempfile.TemporaryDirectory() as d:
            csv = Path(d) / "points.csv"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["marked", str(recipe), "--points", str(csv)]), 0)
            self.assertEqual(csv.read_bytes(), committed.read_bytes())
        self.assertEqual(len(points.read(committed)[0]), 3)


if __name__ == "__main__":
    unittest.main()
