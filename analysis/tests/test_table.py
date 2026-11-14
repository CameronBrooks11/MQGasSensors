"""The coefficients page: its numbers, its verdicts and its staleness check."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np

from mqcurves import table
from mqcurves.trace import fit


def fitted(a, b):
    """A fit whose library-form coefficients are exactly a and b."""
    ratio = [0.2, 0.5, 1.0, 2.0]
    return fit([a * r**b for r in ratio], ratio)


class FormattingTests(unittest.TestCase):
    def test_sig_rounds_to_significant_figures(self):
        self.assertEqual(table.sig(1012.687), "1012.7")
        self.assertEqual(table.sig(-2.78594, 4), "-2.786")
        self.assertEqual(table.sig(0.393394), "0.39339")
        self.assertEqual(table.sig(521853.4), "521850")
        self.assertEqual(table.sig(2.7663e7), "2.7663e+07")
        self.assertEqual(table.sig(102.2), "102.20")

    def test_significant_digits_as_written(self):
        for text, n in (("1012.7", 5), ("-2.786", 4), ("0.3934", 4), ("30000000", 1), ("1000000", 1),
                        ("102.2", 4), ("-3.18", 3), ("-8.310", 4), ("6e10", 1), ("1", 1)):
            self.assertEqual(table.significant_digits(text), n, text)


class JudgeTests(unittest.TestCase):
    def test_value_equal_at_written_precision_is_the_same(self):
        self.assertEqual(table.judge("1012.7", "-2.786", fitted(1012.687, -2.78594))[0], "same")

    def test_value_written_to_one_figure_is_flagged_as_rounded(self):
        verdict, err_a, _ = table.judge("1000000", "-4.01", fitted(1.4136e6, -4.0096))
        self.assertEqual(verdict, "rounded")
        self.assertAlmostEqual(err_a, 0.2926, places=3)

    def test_close_but_unequal_value_is_near(self):
        self.assertEqual(table.judge("1000.5", "-2.186", fitted(993.68, -2.1474))[0], "near")

    def test_unrelated_value_is_different(self):
        self.assertEqual(table.judge("97124", "-4.918", fitted(68091.0, -4.5507))[0], "different")

    def test_same_a_with_another_slope_is_not_the_same(self):
        self.assertNotEqual(table.judge("1012.7", "-2.286", fitted(1012.687, -2.78594))[0], "same")


class ExampleScanTests(unittest.TestCase):
    def test_pairs_are_read_from_sketch_source(self):
        with tempfile.TemporaryDirectory() as d:
            sketch = Path(d) / "MQ-4" / "MQ-4.ino"
            sketch.parent.mkdir()
            sketch.write_text(
                "MQ4.setA(1012.7); MQ4.setB(-2.786); // CH4\n"
                "  MQ303.setA( 6.2144 ) ;  MQ303.setB(-2.894);\n"
                "MQ4.setA(-0.318); MQ4.setB(1.133);\n"
                "MQ4.setR0(10);\n"
            )
            pairs = table.example_pairs(Path(d))
        self.assertEqual(set(pairs), {("MQ-4", "1012.7", "-2.786"), ("MQ-303A", "6.2144", "-2.894"), ("MQ-4", "-0.318", "1.133")})
        self.assertEqual(pairs[("MQ-4", "1012.7", "-2.786")], ["MQ-4"])

    def test_sensor_is_taken_from_the_object_name(self):
        for var, sensor in (("MQ4", "MQ-4"), ("MQ135", "MQ-135"), ("MQ303", "MQ-303A"), ("MQ303A", "MQ-303A"),
                            ("MQ309", "MQ-309A"), ("MQ309A", "MQ-309A")):
            self.assertEqual(table.sensor_of(var), sensor)
        self.assertIsNone(table.sensor_of("sensor"))

    def test_linear_and_unknown_sensors_get_their_own_verdicts(self):
        curves = [{"sensor": "MQ-4", "gas": "CH4", "fit": fitted(1012.687, -2.78594)}]
        rows = table.audit(curves, {("MQ-4", "-0.318", "1.133"): ["x"], ("MQ-136", "36.737", "-3.536"): ["y"],
                                    ("MQ-4", "1012.7", "-2.786"): ["z"]})
        self.assertEqual({(r[0], r[5]) for r in rows},
                         {("MQ-4", "not a power law"), ("MQ-136", "no points"), ("MQ-4", "same")})


class EditionTests(unittest.TestCase):
    def test_example_values_are_not_compared_with_another_makers_curve(self):
        hanwei = {"sensor": "MQ-136", "gas": "H2S", "fit": fitted(36.737, -3.536), "sheet": {"maker": "Hanwei"}}
        winsen = {"sensor": "MQ-136", "gas": "H2S", "fit": fitted(0.13543, -3.7705), "sheet": {"maker": "Winsen"}}
        pair = {("MQ-136", "36.737", "-3.536"): ["MQ-136"]}
        self.assertEqual(table.audit([winsen], pair)[0][5], "no points")
        self.assertEqual(table.audit([winsen, hanwei], pair)[0][5], "same")


class ComparisonTests(unittest.TestCase):
    def test_offset_is_measured_in_ratio_at_the_hand_read_concentration(self):
        ppm, ratio = [100, 1000, 10000], [4.0, 2.0, 1.0]
        off = table.offsets([100, 1000, 10**2.5, 10000], [4.0, 2.2, 2 * 2**0.5, 0.9], ppm, ratio)
        np.testing.assert_allclose(off, [0, 0.1, 0, -0.1], atol=1e-12)

    def test_offset_just_past_an_end_follows_the_end_segment(self):
        off = table.offsets([10**4.5, 10**1.5], [2**-0.5, 4 * 2**0.5], [100, 1000, 10000], [4.0, 2.0, 1.0])
        np.testing.assert_allclose(off, [0, 0], atol=1e-12)

    def test_re_derived_curve_is_left_out_of_the_example_audit(self):
        hand = {"sensor": "MQ-4", "gas": "CH4", "fit": fitted(1012.687, -2.78594)}
        again = {"sensor": "MQ-4", "gas": "CH4", "fit": fitted(1012.7, -2.786), "hand_read": hand}
        rows = table.audit([again, hand], {("MQ-4", "1012.7", "-2.786"): ["MQ-4"]})
        self.assertIs(rows[0][4], hand)

    def test_hand_read_must_name_a_hand_read_curve_of_the_same_datasheet(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "p.csv").write_text("ppm,ratio\n100,2\n1000,1\n")
            (d / "r.toml").write_text("")
            (d / "manifest.toml").write_text('[[datasheet]]\nid = "s1"\n\n[[datasheet]]\nid = "s2"\n')
            base = ('[[curve]]\nid = "hand"\nsensor = "MQ-0"\ngas = "H2"\ndatasheet = "s1"\npoints = "p.csv"\n'
                    'origin = "upstream"\n\n[[curve]]\nid = "pdf"\nsensor = "MQ-0"\ngas = "H2"\npoints = "p.csv"\n'
                    'origin = "extracted"\nrecipe = "r.toml"\n')
            (d / "curves.toml").write_text(base + 'datasheet = "s1"\nhand_read = "hand"\n')
            curves = table.load_curves(d, d / "manifest.toml")
            self.assertEqual(curves[1]["hand_read"]["id"], "hand")
            for tail in ('datasheet = "s2"\nhand_read = "hand"\n', 'datasheet = "s1"\nhand_read = "nothing"\n',
                         'datasheet = "s1"\nhand_read = "pdf"\n'):
                (d / "curves.toml").write_text(base + tail)
                with self.assertRaisesRegex(ValueError, "hand_read"):
                    table.load_curves(d, d / "manifest.toml")


class RepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.curves = table.load_curves()

    def curve(self, ident):
        return next(c for c in self.curves if c["id"] == ident)["fit"]

    def test_every_curve_names_a_manifest_datasheet_and_fits(self):
        self.assertEqual(sum(c["origin"] == "upstream" for c in self.curves), 57)
        self.assertEqual(sum(c["origin"] == "traced" for c in self.curves), 5)
        self.assertEqual(sum(c["origin"] == "extracted" for c in self.curves), 38)
        self.assertEqual(sum(c["origin"] == "located" for c in self.curves), 6)
        self.assertEqual(sum(c["origin"] == "marked" for c in self.curves), 6)
        for c in self.curves:
            self.assertGreaterEqual(c["fit"].n, 3, c["id"])
            self.assertLess(c["fit"].b, 0, c["id"])

    def test_points_reproduce_the_values_the_library_has_always_used(self):
        for ident, a, b in (("mq-4-hanwei-2007-ch4", 1012.7, -2.786), ("mq-7-hanwei-2007-co", 99.042, -1.518),
                            ("mq-8-hanwei-2009-h2", 976.97, -0.688), ("mq-135-hanwei-co2", 110.47, -2.862),
                            ("mq-131-2009-o3", 23.943, -1.11)):
            f = self.curve(ident)
            self.assertAlmostEqual(f.a / a, 1.0, delta=6e-5, msg=ident)  # half a unit in the fifth figure
            self.assertAlmostEqual(f.b, b, delta=5e-4, msg=ident)

    def test_committed_page_is_up_to_date(self):
        self.assertEqual(table.OUTPUT.read_text(), table.generate(),
                         "docs/coefficients.md is stale: run `just coefficients`")

    def test_check_fails_on_a_stale_page(self):
        with tempfile.TemporaryDirectory() as d:
            page = table.ROOT / "docs" / "coefficients.md"
            stale = Path(d) / "coefficients.md"
            stale.write_text(page.read_text().replace("1012.7", "1012.8", 1))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(table.run(check=True, output=stale), 1)
                self.assertEqual(table.run(check=True, output=Path(d) / "missing.md"), 1)
            self.assertIn("out of date", out.getvalue())
            with contextlib.redirect_stdout(out):
                self.assertEqual(table.run(output=stale), 0)
                self.assertEqual(table.run(check=True, output=stale), 0)

    @unittest.skipUnless((table.ROOT / "datasheets" / "files" / "mq-8-winsen-v1.3.pdf").exists(),
                         "datasheets not downloaded (run `just datasheets`)")
    def test_traced_points_come_back_out_of_the_datasheets(self):
        from mqcurves import cli

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["reproduce"])
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("55 of 55", out.getvalue())

    def test_check_passes_on_the_committed_page(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(table.run(check=True), 0)


if __name__ == "__main__":
    unittest.main()
