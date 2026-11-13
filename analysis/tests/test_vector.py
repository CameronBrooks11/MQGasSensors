"""Reading plotted values out of a figure drawn with PDF vector commands."""
import contextlib
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np

from mqcurves import cli, points, vector
from mqcurves.trace import Axis, fit

ROOT = Path(__file__).resolve().parents[2]

# The synthetic figure: a 300 by 200 pt frame, 100 to 10000 ppm across and
# Rs/R0 0.1 to 10 up, on a 400 by 300 pt page.
FRAME = (50.0, 50.0, 350.0, 250.0)
X = Axis(50.0, 100.0, 350.0, 10000.0)
Y = Axis(50.0, 0.1, 250.0, 10.0)
A, B = 4.0, -0.3
PPM = (200.0, 1000.0, 5000.0)
LEGEND = (60.0, 60.0, 120.0, 100.0)


def pdf_bytes(content):
    """A one-page PDF whose page draws `content`, a content stream."""
    stream = content.encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 300] /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def square(x, y):
    """A filled 4 pt square marker: blue outline, magenta fill."""
    return f"0 0 1 RG 1 0 1 rg {x - 2:.4f} {y - 2:.4f} 4 4 re B\n"


def cross(x, y):
    """A cross marker drawn as four strokes out from its centre: red, with a yellow fill set but unused."""
    return "".join(f"1 0 0 RG 1 1 0 rg {x:.4f} {y:.4f} m {x + dx:.4f} {y + dy:.4f} l S\n"
                   for dx, dy in ((2, 2), (-2, 2), (2, -2), (-2, -2)))


def figure(line_colours="0 0 1 RG 1 1 1 rg"):
    """The frame, a legend, a blue line with square markers at A*ppm^B, and a red line with crosses at half that."""
    xs = [float(X.to_pixel(p)) for p in PPM]
    ys = [float(Y.to_pixel(A * p**B)) for p in PPM]
    yc = [float(Y.to_pixel(A * p**B / 2)) for p in PPM]
    s = "0 0 0 RG 1 1 1 rg 50 50 300 200 re S\n"
    s += "0 0 0 RG 1 1 1 rg 60 60 60 40 re S\n" + square(80, 80) + cross(80, 70)
    s += f"{line_colours} {xs[0]:.4f} {ys[0]:.4f} m " + " ".join(f"{x:.4f} {y:.4f} l" for x, y in zip(xs[1:], ys[1:])) + " S\n"
    s += "".join(square(x, y) for x, y in zip(xs, ys))
    s += "".join(cross(x, y) for x, y in zip(xs, yc))
    return s


def recipe_text(stroke="[0, 0, 255]", fill="[255, 0, 255]", count=3, exclude=True, frame_x="[50, 350]"):
    return f"""id = "synthetic-h2-extracted"
sensor = "MQ-0"
gas = "H2"

[source]
datasheet = "synthetic"
page = 1

[frame]
x = {frame_x}
y = [50, 250]
ppm = [100, 10000]
ratio = [0.1, 10]

[markers]
stroke = {stroke}
fill = {fill}
count = {count}
{"exclude = [[60, 60, 120, 100]]" if exclude else ""}
"""


class VectorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.write_pdf(figure())

    def write_pdf(self, content):
        self.pdf = self.dir / "synthetic.pdf"
        self.pdf.write_bytes(pdf_bytes(content))
        digest = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.manifest = self.dir / "manifest.toml"
        self.manifest.write_text(f'[[datasheet]]\nid = "synthetic"\nsha256 = "{digest}"\n')

    def recipe(self, **kw):
        path = self.dir / "curve.toml"
        path.write_text(recipe_text(**kw))
        return vector.load(path)

    def extract(self, r):
        return vector.extract(r, r.pdf(self.dir, self.manifest))

    def test_plotted_values_come_back_from_the_drawing(self):
        ppm, ratio, _, _ = self.extract(self.recipe())
        np.testing.assert_allclose(ppm, PPM, rtol=1e-4)
        np.testing.assert_allclose(ratio, [A * p**B for p in PPM], rtol=1e-4)
        f = fit(ppm, ratio)
        self.assertAlmostEqual(f.B, B, places=4)
        self.assertAlmostEqual(f.A, A, delta=A * 1e-3)

    def test_marker_drawn_as_several_strokes_is_one_marker_at_their_centre(self):
        ppm, ratio, _, _ = self.extract(self.recipe(stroke="[255, 0, 0]", fill="[255, 255, 0]"))
        np.testing.assert_allclose(ppm, PPM, rtol=1e-4)
        np.testing.assert_allclose(ratio, [A * p**B / 2 for p in PPM], rtol=1e-4)

    def test_legend_marker_is_counted_unless_excluded(self):
        with self.assertRaisesRegex(vector.VectorError, "expected 3 markers, found 4"):
            self.extract(self.recipe(exclude=False))

    def test_frame_not_drawn_on_the_page_is_refused(self):
        with self.assertRaisesRegex(vector.VectorError, "no rectangle drawn at the frame"):
            self.extract(self.recipe(frame_x="[50, 351]"))

    def test_line_in_the_marker_colours_is_not_a_marker(self):
        self.write_pdf(figure(line_colours="0 0 1 RG 1 0 1 rg"))
        ppm, ratio, _, _ = self.extract(self.recipe())
        np.testing.assert_allclose(ppm, PPM, rtol=1e-4)
        np.testing.assert_allclose(ratio, [A * p**B for p in PPM], rtol=1e-4)

    def test_datasheet_must_match_the_manifest(self):
        r = self.recipe()
        self.pdf.write_bytes(self.pdf.read_bytes() + b"\n")
        with self.assertRaisesRegex(vector.VectorError, "is not the manifest's"):
            r.pdf(self.dir, self.manifest)
        self.pdf.unlink()
        with self.assertRaisesRegex(vector.VectorError, "just datasheets"):
            r.pdf(self.dir, self.manifest)
        self.manifest.write_text("datasheet = []\n")
        with self.assertRaisesRegex(vector.VectorError, "not in"):
            r.pdf(self.dir, self.manifest)

    def test_markers_drawn_as_subpaths_of_one_path_are_read_one_by_one(self):
        xs = [float(X.to_pixel(p)) for p in PPM]
        ys = [float(Y.to_pixel(A * p**B)) for p in PPM]
        crosses = " ".join(f"{x:.4f} {y:.4f} m {x + dx:.4f} {y + dy:.4f} l"
                           for x, y in zip(xs, ys) for dx, dy in ((2, 2), (-2, 2), (2, -2), (-2, -2)))
        self.write_pdf("0 0 0 RG 1 1 1 rg 50 50 300 200 re S\n1 0 0 RG 1 1 0 rg " + crosses + " S\n")
        ppm, ratio, _, _ = self.extract(self.recipe(stroke="[255, 0, 0]", fill="[255, 255, 0]", exclude=False))
        np.testing.assert_allclose(ppm, PPM, rtol=1e-4)
        np.testing.assert_allclose(ratio, [A * p**B for p in PPM], rtol=1e-4)

    def test_cross_clipped_at_the_frame_is_centred_on_its_strokes_start(self):
        # Only the two strokes pointing into the plot are drawn, as at a frame edge.
        y = float(Y.to_pixel(1.0))
        self.write_pdf("0 0 0 RG 1 1 1 rg 50 50 300 200 re S\n"
                       + "".join(f"1 0 0 RG 1 1 0 rg 50 {y:.4f} m 52 {y + dy:.4f} l S\n" for dy in (2, -2)))
        ppm, ratio, _, _ = self.extract(self.recipe(stroke="[255, 0, 0]", fill="[255, 255, 0]", count=1, exclude=False))
        np.testing.assert_allclose([ppm[0], ratio[0]], [100.0, 1.0], rtol=1e-4)

    def test_shape_tells_apart_markers_that_share_colours(self):
        # Crosses, then stars, then triangles, all in the same colours, as one line's
        # markers after another's. A cross and a star sit at the same place.
        def strokes(x, y, ends):
            return "".join(f"0 0 0 RG 1 1 0 rg {x:.4f} {y:.4f} m {x + dx:.4f} {y + dy:.4f} l S\n" for dx, dy in ends)

        diagonals = ((2, 2), (-2, 2), (2, -2), (-2, -2))
        at = {"x": ((1000.0, 2.0), (5000.0, 1.0)), "star": ((1000.0, 2.0), (3000.0, 4.0)), "outline": ((300.0, 0.5), (3000.0, 0.5))}
        content = "0 0 0 RG 1 1 1 rg 50 50 300 200 re S\n"
        for ppm, ratio in at["x"]:
            content += strokes(float(X.to_pixel(ppm)), float(Y.to_pixel(ratio)), diagonals)
        for ppm, ratio in at["star"]:
            content += strokes(float(X.to_pixel(ppm)), float(Y.to_pixel(ratio)), diagonals + ((0, 2), (0, -2)))
        for ppm, ratio in at["outline"]:
            x, y = float(X.to_pixel(ppm)), float(Y.to_pixel(ratio))
            content += f"0 0 0 RG 1 1 0 rg {x:.4f} {y + 2:.4f} m {x + 2:.4f} {y - 2:.4f} l {x - 2:.4f} {y - 2:.4f} l h B\n"
        self.write_pdf(content)
        for shape, expected in at.items():
            r = self.recipe(stroke="[0, 0, 0]", fill="[255, 255, 0]", count=2, exclude=False)
            ppm, ratio, _, _ = self.extract(vector.Recipe(**{**r.__dict__, "shape": shape}))
            np.testing.assert_allclose(np.column_stack([ppm, ratio]), expected, rtol=1e-4, err_msg=shape)

    def test_outline_drawn_twice_is_one_marker(self):
        x, y = float(X.to_pixel(1000.0)), float(Y.to_pixel(A * 1000.0**B))
        self.write_pdf(figure().replace(square(x, y), square(x, y) * 2))
        ppm, _, _, _ = self.extract(self.recipe())
        np.testing.assert_allclose(ppm, PPM, rtol=1e-4)

    def test_recipe_with_a_bad_colour_is_refused(self):
        with self.assertRaisesRegex(vector.VectorError, "r, g, b"):
            self.recipe(stroke="[0, 0, 256]")


@unittest.skipUnless((ROOT / "datasheets" / "files" / "mq-4-hanwei-2007.pdf").exists(),
                     "datasheets not downloaded (run `just datasheets`)")
class RealDatasheetTests(unittest.TestCase):
    def test_mq4_ch4_markers_match_the_committed_points(self):
        recipe = ROOT / "analysis" / "recipes" / "mq-4-hanwei-2007-ch4-extracted.toml"
        with tempfile.TemporaryDirectory() as d:
            csv = Path(d) / "points.csv"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["extract", str(recipe), "--points", str(csv)]), 0)
            committed = ROOT / "analysis" / "points" / "mq-4-hanwei-2007" / "ch4-extracted.csv"
            self.assertEqual(csv.read_bytes(), committed.read_bytes())
        ppm, _ = points.read(committed)
        # Plotted at 200, 1000, 5000 and 10000 ppm, on a 0.24 pt grid.
        np.testing.assert_allclose(ppm, [200, 1000, 5000, 10000], rtol=0.01)


if __name__ == "__main__":
    unittest.main()
