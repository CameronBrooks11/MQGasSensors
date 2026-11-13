"""A recipe drives the whole run with no window: figure, trace, points, fit."""
import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
import synthetic
from PIL import Image

from mqcurves import cli, figure, mark, points, recipe
from mqcurves.trace import fit

A, B = 4.0, -0.6
ROOT = Path(__file__).resolve().parents[2]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.pixels, self.seed = synthetic.figure(A, B, 200.0, 5000.0)
        Image.fromarray(self.pixels).save(self.dir / "figure.png")
        self.recipe = self.dir / "curve.toml"
        recipe.dump(
            self.recipe, id="synthetic-h2", sensor="MQ-0", gas="H2", source={"image": "figure.png"},
            x=((synthetic.LEFT, 100.0), (synthetic.RIGHT, 10000.0)),
            y=((synthetic.TOP, 1.0), (synthetic.BOTTOM, 0.01)),
            seed=self.seed,
        )

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([str(a) for a in argv])
        return code, out.getvalue(), err.getvalue()

    def test_trace_from_recipe_writes_points_that_fit_the_drawn_curve(self):
        csv = self.dir / "points.csv"
        code, out, _ = self.run_cli("trace", self.recipe, "--points", csv)
        self.assertEqual(code, 0)
        self.assertIn("synthetic-h2", out)
        f = fit(*points.read(csv))
        self.assertAlmostEqual(f.B, B, delta=0.01)
        self.assertAlmostEqual(f.A / A, 1.0, delta=0.03)

    def test_same_recipe_gives_the_same_points_file(self):
        first, second = self.dir / "a.csv", self.dir / "b.csv"
        self.run_cli("trace", self.recipe, "--points", first)
        self.run_cli("trace", self.recipe, "--points", second)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_fit_command_reads_points_back(self):
        csv = self.dir / "points.csv"
        self.run_cli("trace", self.recipe, "--points", csv)
        code, out, _ = self.run_cli("fit", csv)
        self.assertEqual(code, 0)
        self.assertIn("setA, setB", out)

    def test_overlay_is_a_picture_of_the_figure(self):
        png = self.dir / "out" / "overlay.png"
        code, _, _ = self.run_cli("trace", self.recipe, "--overlay", png)
        self.assertEqual(code, 0)
        with Image.open(png) as im:
            self.assertEqual(im.size, (synthetic.WIDTH * 3, synthetic.HEIGHT * 3))

    def test_recipe_marked_at_inner_gridlines_gives_the_same_fit(self):
        # Reference positions need not be the ends of the axes.
        x_inner = ((float(synthetic.X_AXIS.to_pixel(1000.0)), 1000.0), (synthetic.RIGHT, 10000.0))
        y_inner = ((float(synthetic.Y_AXIS.to_pixel(0.1)), 0.1), (synthetic.TOP, 1.0))
        other = self.dir / "inner.toml"
        recipe.dump(other, id="inner", sensor="MQ-0", gas="H2", source={"image": "figure.png"},
                    x=x_inner, y=y_inner, seed=self.seed)
        _, _, _, _, _, f = cli.run_recipe(recipe.load(other))
        self.assertAlmostEqual(f.B, B, delta=0.01)
        self.assertAlmostEqual(f.A / A, 1.0, delta=0.03)

    def test_marking_clicks_become_a_working_recipe(self):
        args = argparse.Namespace(recipe=self.dir / "marked.toml", id="marked", sensor="MQ-0", gas="H2")
        clicks = [(synthetic.LEFT, 280.0), (synthetic.RIGHT, 281.0), (40.0, synthetic.TOP),
                  (41.0, synthetic.BOTTOM), (float(self.seed[0]), float(self.seed[1]))]
        mark.write(args, {"image": "figure.png"}, clicks, [100.0, 10000.0, 1.0, 0.01])
        _, _, _, _, _, f = cli.run_recipe(recipe.load(args.recipe))
        self.assertAlmostEqual(f.B, B, delta=0.01)

    def test_missing_axis_is_reported_not_raised(self):
        self.recipe.write_text(self.recipe.read_text().replace("[y]", "[z]"))
        code, _, err = self.run_cli("trace", self.recipe)
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_datasheet_says_how_to_get_it(self):
        recipe.dump(self.recipe, id="x", sensor="MQ-0", gas="H2",
                    source={"datasheet": "no-such-sheet", "page": 4, "pixels_sha256": "0" * 64},
                    x=((50, 100.0), (380, 10000.0)), y=((15, 1.0), (270, 0.01)), seed=(1, 1))
        code, _, err = self.run_cli("trace", self.recipe, "--datasheets", self.dir)
        self.assertEqual(code, 1)
        self.assertIn("just datasheets", err)


class PointsTests(unittest.TestCase):
    def test_round_trip_keeps_six_significant_figures(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "p.csv"
            points.write(path, [123.456789, 9876.54321], [0.123456789, 0.0123456789])
            ppm, ratio = points.read(path)
            np.testing.assert_allclose(ppm, [123.457, 9876.54])
            np.testing.assert_allclose(ratio, [0.123457, 0.0123457])
            self.assertEqual(path.read_text().splitlines()[0], "ppm,ratio")

    def test_file_without_header_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "p.csv"
            path.write_text("100,0.5\n200,0.4\n300,0.3\n")
            with self.assertRaises(ValueError):
                points.read(path)


class FigureTests(unittest.TestCase):
    def test_pixel_hash_depends_on_shape_as_well_as_bytes(self):
        flat = np.zeros((2, 6, 3), dtype=np.uint8)
        self.assertNotEqual(figure.pixel_hash(flat), figure.pixel_hash(flat.reshape(6, 2, 3)))

    def test_pixel_hash_changes_with_one_pixel(self):
        a = np.zeros((4, 4, 3), dtype=np.uint8)
        b = a.copy()
        b[2, 1, 0] = 1
        self.assertNotEqual(figure.pixel_hash(a), figure.pixel_hash(b))

    def pdf_with_two_figures(self, directory):
        """A PDF with one losslessly embedded figure per page, and the figures' pixels."""
        pages = []
        for a, b in ((4.0, -0.6), (2.0, -0.3)):
            pixels, seed = synthetic.figure(a, b, 200.0, 5000.0)
            pages.append((Image.fromarray(pixels).convert("P", palette=Image.ADAPTIVE, colors=64), seed))
        pdf = Path(directory) / "synthetic.pdf"
        pages[0][0].save(pdf, save_all=True, append_images=[pages[1][0]])
        return pdf, [(np.asarray(im.convert("RGB")), seed) for im, seed in pages]

    def test_figure_comes_out_of_a_pdf_pixel_for_pixel(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, figures = self.pdf_with_two_figures(d)
            for page, (pixels, _) in enumerate(figures, 1):
                got = figure.from_datasheet(pdf, page, figure.pixel_hash(pixels))
                np.testing.assert_array_equal(got, pixels)

    def test_figure_is_chosen_by_its_pixels_not_its_position(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, figures = self.pdf_with_two_figures(d)
            other_page = figure.pixel_hash(figures[1][0])
            with self.assertRaises(figure.FigureError) as ctx:
                figure.from_datasheet(pdf, 1, other_page)
            self.assertIn("found 400x305", str(ctx.exception))
            with self.assertRaises(figure.FigureError):
                figure.from_datasheet(pdf, 3, other_page)

    def test_recipe_traces_a_figure_embedded_in_a_datasheet(self):
        with tempfile.TemporaryDirectory() as d:
            pdf, figures = self.pdf_with_two_figures(d)
            pixels, seed = figures[0]
            path = Path(d) / "curve.toml"
            recipe.dump(path, id="from-pdf", sensor="MQ-0", gas="H2",
                        source={"datasheet": "synthetic", "page": 1, "pixels_sha256": figure.pixel_hash(pixels)},
                        x=((synthetic.LEFT, 100.0), (synthetic.RIGHT, 10000.0)),
                        y=((synthetic.TOP, 1.0), (synthetic.BOTTOM, 0.01)), seed=seed)
            _, _, _, _, _, f = cli.run_recipe(recipe.load(path), datasheets=d)
            self.assertAlmostEqual(f.B, -0.6, delta=0.01)

    # Needs a real datasheet, which the repository does not carry. Runs wherever
    # `just datasheets` has been run; skipped otherwise.
    SHEET = ROOT / "datasheets" / "files" / "mq-8-winsen-v1.3.pdf"
    FIGURE = "a7e8f9d7734e1595"

    @unittest.skipUnless(SHEET.exists(), "datasheets not downloaded (run `just datasheets`)")
    def test_embedded_figure_is_found_in_a_real_datasheet_by_its_pixels(self):
        hashes = [figure.pixel_hash(p) for p in figure.embedded_images(self.SHEET, 4)]
        match = [h for h in hashes if h.startswith(self.FIGURE)]
        self.assertEqual(len(match), 1, hashes)
        pixels = figure.from_datasheet(self.SHEET, 4, match[0])
        self.assertEqual(pixels.shape, (305, 400, 3))
        with self.assertRaises(figure.FigureError):
            figure.from_datasheet(self.SHEET, 4, "0" * 64)


if __name__ == "__main__":
    unittest.main()
