"""The tracer recovers known coefficients from a synthetic figure."""
import unittest

import numpy as np
import synthetic

from mqcurves.trace import Axis, centreline, fit, flood, trace

# A curve like a datasheet's hydrogen line: it starts a quarter of the way up
# the plot and covers only part of the ppm range.
A, B = 4.0, -0.6
PPM_FROM, PPM_TO = 200.0, 5000.0


class TraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image, cls.seed = synthetic.figure(A, B, PPM_FROM, PPM_TO)

    def traced(self, **kw):
        return trace(self.image, self.seed, synthetic.X_AXIS, synthetic.Y_AXIS, **kw)

    def test_recovers_the_curve_it_was_drawn_from(self):
        ppm, ratio, _, _ = self.traced()
        f = fit(ppm, ratio)
        self.assertAlmostEqual(f.B, B, delta=0.01)
        # One pixel is about 1.8 % in Rs/R0 here, so this also catches a trace that
        # follows an edge of the 3-pixel stroke instead of its centre.
        self.assertAlmostEqual(f.A / A, 1.0, delta=0.012)
        self.assertGreater(f.r_squared, 0.999)

    def test_reads_the_curve_at_a_known_point(self):
        ppm, ratio, _, _ = self.traced()
        f = fit(ppm, ratio)
        for at in (300.0, 1000.0, 4000.0):
            self.assertAlmostEqual(f.A * at**f.B / (A * at**B), 1.0, delta=0.012, msg=f"at {at} ppm")

    def test_covers_the_curves_own_range_not_the_axis_range(self):
        ppm, _, _, _ = self.traced()
        self.assertAlmostEqual(ppm.min() / PPM_FROM, 1.0, delta=0.05)
        self.assertAlmostEqual(ppm.max() / PPM_TO, 1.0, delta=0.05)

    def test_library_form_is_the_inverse_relation(self):
        ppm, ratio, _, _ = self.traced()
        f = fit(ppm, ratio)
        # ppm = a * ratio**b with b = 1/B and a = A**(-1/B), for a clean curve.
        self.assertAlmostEqual(f.b, 1 / B, delta=0.03)
        self.assertAlmostEqual(f.a / A ** (-1 / B), 1.0, delta=0.08)

    def test_does_not_leak_into_other_marks(self):
        mask = flood(self.image, self.seed, 20, 20)
        ys, xs = np.nonzero(mask)
        # The legend sample has the curve's colour but does not touch it.
        self.assertFalse(mask[235, 85])
        # Nothing outside the span the curve was drawn over, give or take the stroke.
        self.assertGreaterEqual(xs.min(), synthetic.X_AXIS.to_pixel(PPM_FROM) - 3)
        self.assertLessEqual(xs.max(), synthetic.X_AXIS.to_pixel(PPM_TO) + 3)

    def test_wider_bins_give_fewer_points_and_the_same_fit(self):
        fine = fit(*self.traced(bin_width=1)[:2])
        coarse_ppm, coarse_ratio, _, _ = self.traced(bin_width=5)
        coarse = fit(coarse_ppm, coarse_ratio)
        self.assertLess(coarse.n, fine.n / 3)
        self.assertAlmostEqual(coarse.B, fine.B, delta=0.01)

    def test_seed_off_the_curve_does_not_return_the_curve(self):
        # A white pixel: the fill takes the background, which is nothing like a line.
        mask = flood(self.image, (200, 290), 5, 5)
        cx, _ = centreline(mask)
        self.assertGreater(cx.max() - cx.min(), 300)


class MarkerTests(unittest.TestCase):
    """A triangle marker on the line has the line's colour and is not symmetric about it."""

    @classmethod
    def setUpClass(cls):
        cls.image, cls.seed = synthetic.figure(A, B, PPM_FROM, PPM_TO, markers=(400.0, 1000.0, 3000.0))

    def worst(self, **kw):
        """Largest distance, in pixels, between a traced point and the drawn line."""
        ppm, ratio, _, py = trace(self.image, self.seed, synthetic.X_AXIS, synthetic.Y_AXIS, **kw)
        return float(np.max(np.abs(py - synthetic.Y_AXIS.to_pixel(A * ppm**B)))), ppm

    def test_markers_pull_the_trace_off_the_line(self):
        worst, _ = self.worst()
        self.assertGreater(worst, 1.5)

    def test_thickness_limit_keeps_the_trace_on_the_line(self):
        worst, ppm = self.worst(max_thickness=4)
        self.assertLess(worst, 1.0)
        # The columns under each marker are gone, the line between them is not.
        for at in (400.0, 1000.0, 3000.0):
            self.assertGreater(np.min(np.abs(np.log10(ppm / at))), 0.01, at)
        self.assertGreater(ppm.size, 150)

    def test_fit_is_right_with_the_limit(self):
        ppm, ratio, _, _ = trace(self.image, self.seed, synthetic.X_AXIS, synthetic.Y_AXIS, max_thickness=4)
        f = fit(ppm, ratio)
        self.assertAlmostEqual(f.B, B, delta=0.01)
        self.assertAlmostEqual(f.A / A, 1.0, delta=0.012)

    def test_limit_does_nothing_where_there_are_no_markers(self):
        plain, seed = synthetic.figure(A, B, PPM_FROM, PPM_TO)
        with_limit = trace(plain, seed, synthetic.X_AXIS, synthetic.Y_AXIS, max_thickness=4)[0]
        without = trace(plain, seed, synthetic.X_AXIS, synthetic.Y_AXIS)[0]
        np.testing.assert_array_equal(with_limit, without)


class AxisTests(unittest.TestCase):
    def test_round_trip(self):
        ax = Axis(50, 100.0, 380, 10000.0)
        for v in (100.0, 250.0, 1000.0, 9999.0):
            self.assertAlmostEqual(float(10 ** ax.to_log10(ax.to_pixel(v))), v, places=6)

    def test_reference_points_need_not_be_the_axis_ends(self):
        whole = Axis(50, 100.0, 380, 10000.0)
        inner = Axis(float(whole.to_pixel(1000.0)), 1000.0, 380, 10000.0)
        self.assertAlmostEqual(float(10 ** inner.to_log10(50)), 100.0, places=6)

    def test_degenerate_axis_is_refused(self):
        with self.assertRaises(ValueError):
            Axis(50, 100.0, 50, 10000.0)
        with self.assertRaises(ValueError):
            Axis(50, 100.0, 380, 100.0)
        with self.assertRaises(ValueError):
            Axis(50, 0.0, 380, 100.0)


class FitTests(unittest.TestCase):
    def test_exact_power_law(self):
        ppm = np.array([10.0, 100.0, 1000.0])
        f = fit(ppm, 3.0 * ppm**-0.5)
        self.assertAlmostEqual(f.A, 3.0, places=9)
        self.assertAlmostEqual(f.B, -0.5, places=9)
        self.assertAlmostEqual(f.b, -2.0, places=9)
        self.assertAlmostEqual(f.a, 9.0, places=9)
        self.assertAlmostEqual(f.r_squared, 1.0, places=9)

    def test_needs_two_positive_points(self):
        with self.assertRaises(ValueError):
            fit([100.0], [0.5])
        with self.assertRaises(ValueError):
            fit([100.0, -1.0], [0.5, 0.4])


if __name__ == "__main__":
    unittest.main()
