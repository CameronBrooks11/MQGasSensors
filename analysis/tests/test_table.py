"""The coefficients page: its numbers, its verdicts and its staleness check."""
import contextlib
import io
import re
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
        curves = [{"sensor": "MQ-4", "gas": "CH4", "origin": "upstream", "fit": fitted(1012.687, -2.78594)}]
        rows = table.audit(curves, {("MQ-4", "-0.318", "1.133"): ["x"], ("MQ-136", "36.737", "-3.536"): ["y"],
                                    ("MQ-4", "1012.7", "-2.786"): ["z"]})
        self.assertEqual({(r[0], r[5]) for r in rows},
                         {("MQ-4", "not a power law"), ("MQ-136", "no points"), ("MQ-4", "same")})


class EditionTests(unittest.TestCase):
    def test_example_values_are_not_compared_with_another_makers_curve(self):
        hanwei = {"sensor": "MQ-136", "gas": "H2S", "origin": "upstream", "fit": fitted(36.737, -3.536), "sheet": {"maker": "Hanwei"}}
        winsen = {"sensor": "MQ-136", "gas": "H2S", "origin": "traced", "fit": fitted(0.13543, -3.7705), "sheet": {"maker": "Winsen"}}
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

    def re_derived(self):
        hand = {"id": "hand", "sensor": "MQ-4", "gas": "CH4", "origin": "upstream", "fit": fitted(1012.687, -2.78594)}
        again = {"id": "again", "sensor": "MQ-4", "gas": "CH4", "origin": "extracted", "fit": fitted(990.22, -2.8257),
                 "hand_read": hand}
        hand["superseded_by"] = again
        return hand, again

    def test_re_derived_curve_is_the_source_and_its_hand_read_one_is_not(self):
        hand, again = self.re_derived()
        other = {"id": "other", "sensor": "MQ-2", "gas": "H2", "origin": "upstream", "fit": fitted(982.04, -2.131)}
        self.assertEqual([c["id"] for c in table.source_curves([hand, again, other])], ["again", "other"])

    def test_example_is_matched_to_its_hand_read_fit_and_measured_against_the_re_derived_one(self):
        hand, again = self.re_derived()
        row = table.audit([again, hand], {("MQ-4", "1012.7", "-2.786"): ["MQ-4"]})[0]
        self.assertIs(row[4], hand)
        self.assertEqual(row[5], "same")
        self.assertIs(row[8], again)
        self.assertAlmostEqual(row[9], table.difference_from(1012.7, -2.786, again["fit"]))
        self.assertGreater(row[9], 0.01)

    def test_example_written_from_the_re_derived_fit_is_matched_to_it(self):
        hand, again = self.re_derived()
        row = table.audit([hand, again], {("MQ-4", "990.22", "-2.826"): ["MQ-4"]})[0]
        self.assertIs(row[4], again)
        self.assertEqual(row[5], "same")
        self.assertAlmostEqual(row[9], 0, places=3)

    def test_sensor_without_hand_read_points_is_matched_to_its_source_curve(self):
        marked = {"id": "m", "sensor": "MQ-136", "gas": "H2S", "origin": "marked", "fit": fitted(36.716, -3.481)}
        row = table.audit([marked], {("MQ-136", "36.737", "-3.536"): ["MQ-136"]})[0]
        self.assertIs(row[4], marked)
        self.assertIs(row[8], marked)

    def test_provenance_tells_confirmed_partly_checked_and_unchecked_sensors_apart(self):
        def hand(ident, sensor):
            return {"id": ident, "sensor": sensor, "gas": ident, "datasheet": "sheet", "origin": "upstream",
                    "points_data": ([100, 1000], [2.0, 1.0])}
        a, b, c, d = hand("a", "MQ-1"), hand("b", "MQ-1"), hand("c", "MQ-2"), hand("d", "MQ-3")
        for h in (a, c):
            h["superseded_by"] = {"id": h["id"] + "-again", "sensor": h["sensor"], "origin": "marked",
                                  "points_data": ([100, 1000], [2.2, 1.0]), "hand_read": h}
        text = "\n".join(table.provenance([a, b, c, d, a["superseded_by"], c["superseded_by"]]))
        self.assertIn("| MQ-1 | `sheet` | 2 | 1 | 9.1 % in Rs/R0 | read from this datasheet, where checked |", text)
        self.assertIn("| MQ-2 | `sheet` | 1 | 1 | 9.1 % in Rs/R0 | read from this datasheet |", text)
        self.assertIn("| MQ-3 | `sheet` | 1 | 0 |  | not checked |", text)

    def test_difference_from_a_fit_is_the_largest_over_its_range(self):
        f = fitted(100.0, -2.0)
        self.assertAlmostEqual(table.difference_from(100.0, -2.0, f), 0.0, places=9)
        self.assertAlmostEqual(table.difference_from(110.0, -2.0, f), 0.1, places=9)
        # A different slope differs most at an end of the Rs/R0 range, 0.2 to 2.
        self.assertAlmostEqual(table.difference_from(100.0, -2.1, f), 0.2 ** -0.1 - 1, places=9)

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


class CleanAirTests(unittest.TestCase):
    def test_air_line_is_its_one_ratio_and_one_that_slopes_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "r.toml").write_text("")
            (d / "manifest.toml").write_text('[[datasheet]]\nid = "s1"\nmaker = "Hanwei"\n')
            (d / "curves.toml").write_text('curve = []\n\n[[air]]\nid = "a"\nsensor = "MQ-0"\ndatasheet = "s1"\n'
                                           'points = "p.csv"\norigin = "marked"\nrecipe = "r.toml"\n')
            (d / "p.csv").write_text("ppm,ratio\n100,9.5\n1000,9.5\n")
            [air] = table.load_air(d, d / "manifest.toml")
            self.assertEqual((air["value"], air["axis"]), (9.5, "Rs/R0"))
            (d / "p.csv").write_text("ppm,ratio\n100,9.5\n1000,9.4\n")
            with self.assertRaisesRegex(ValueError, "share one Rs/R0"):
                table.load_air(d, d / "manifest.toml")

    def test_defines_are_read_in_every_form_the_examples_write(self):
        with tempfile.TemporaryDirectory() as d:
            sketch = Path(d) / "S" / "S.ino"
            sketch.parent.mkdir()
            sketch.write_text("#define         RatioMQ2CleanAir        (9.51) // note\n"
                              "#define RatioMQ135CleanAir 3.60// note\n"
                              "//#define RatioMQ309CleanAir 11.1 // note\n"
                              "#define RatioMQ131CleanAir (1.0 / 12.0) // note\n")
            self.assertEqual(table.example_air(Path(d)), {("MQ-2", "9.51"): ["S"], ("MQ-135", "3.60"): ["S"],
                                                          ("MQ-309A", "11.1"): ["S"], ("MQ-131", "1.0 / 12.0"): ["S"]})
        self.assertAlmostEqual(table.air_number("1.0 / 12.0"), 1 / 12)

    def test_expected_value_is_three_figures_inverted_for_r0_over_rs_or_as_defined(self):
        self.assertEqual(table.air_expected({"value": 9.5073, "axis": "Rs/R0"}), 9.51)
        self.assertEqual(table.air_expected({"value": 12.048, "axis": "R0/Rs"}), 1 / 12.0)
        self.assertEqual(table.air_expected({"value": 0.991, "axis": "Rs/Rs(air)", "defined": 1.0}), 1.0)


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
        self.assertEqual(sum(c["origin"] == "marked" for c in self.curves), 18)
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

    def test_page_lists_each_curve_once(self):
        page = table.OUTPUT.read_text()
        fitted_rows = page.split("## Fitted curves")[1].split("Notes:")[0]
        keys = [tuple(cell.strip() for cell in line.split("|")[1:3]) + (line.split("`")[1],)
                for line in fitted_rows.splitlines() if line.startswith("| MQ")]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), len(table.source_curves(self.curves)))

    def test_provenance_says_which_hand_read_points_were_confirmed(self):
        text = "\n".join(table.provenance(self.curves))
        self.assertIn("| MQ-4 | `mq-4-hanwei-2007` | 6 | 6 | 2.1 % in Rs/R0 | read from this datasheet |", text)
        self.assertIn("| MQ-2 | `mq-2-hanwei-2009` | 6 | 6 | 3.7 % in Rs/R0 | read from this datasheet |", text)
        self.assertIn("| MQ-303A | `mq-303a-hanwei-2006` | 3 | 2 | 2.9 % in Rs/R0 | read from this datasheet, where checked |", text)

    def hanwei_sources(self):
        return {(c["sensor"], c["gas"]): c for c in table.source_curves(self.curves)
                if c.get("sheet", {}).get("maker", "Hanwei").startswith("Hanwei")}

    def test_every_example_pair_is_its_gas_datasheet_fit(self):
        exceptions = {("MQ-303A", "1", "1")}  # a placeholder in UnitTesting's voltage offset test
        checked = 0
        for sensor, a, b, sketches, best, *_, source, _ in table.audit(self.curves, table.example_pairs()):
            if best is None or (sensor, a, b) in exceptions:
                continue
            want = (table.sig(source["fit"].a), table.sig(source["fit"].b, 4))
            self.assertEqual((a, b), want, f"{sensor} {source['gas']} in {', '.join(sketches)}")
            checked += 1
        self.assertGreater(checked, 25)

    def test_every_example_clean_air_ratio_is_its_datasheet_value(self):
        airs = {e["sensor"]: e for e in table.load_air()}
        defines = table.example_air()
        self.assertGreater(len(defines), 10)
        for (sensor, text), sketches in defines.items():
            self.assertIn(sensor, airs, f"{sensor} has no clean-air reading, used in {', '.join(sketches)}")
            self.assertAlmostEqual(table.air_number(text), table.air_expected(airs[sensor]), places=9,
                                   msg=f"{sensor} {text} in {', '.join(sketches)}")

    def test_every_example_coefficient_table_lists_its_sensors_datasheet_fits(self):
        head = re.compile(r"^\s*(?:Gas|GAS)\s*\|\s*a\s*\|\s*b\s*$")
        row = re.compile(r"^\s*(\S[^|]*?)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*$")
        sources = self.hanwei_sources()
        tables = 0
        for ino in sorted((table.ROOT / "examples").rglob("*.ino")):
            lines = ino.read_text().splitlines()
            for i, line in enumerate(lines):
                if not head.match(line):
                    continue
                sensor = next(table.sensor_of(v) for v, *_ in table.SET_PAIR.findall("\n".join(lines))
                              if table.sensor_of(v))
                found = {}
                for r in lines[i + 1:]:
                    m = row.match(r)
                    if not m:
                        break
                    found[m.group(1)] = (m.group(2), m.group(3))
                want = {gas: (table.sig(c["fit"].a), table.sig(c["fit"].b, 4))
                        for (s, gas), c in sources.items() if s == sensor}
                self.assertEqual(found, want, ino.relative_to(table.ROOT))
                tables += 1
        self.assertGreater(tables, 20)

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
        self.assertIn("80 of 80 recipes", out.getvalue())

    def test_check_passes_on_the_committed_page(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(table.run(check=True), 0)


if __name__ == "__main__":
    unittest.main()
