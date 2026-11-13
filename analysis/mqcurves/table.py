"""Generate docs/coefficients.md: every fitted curve, and every value the examples use.

The first table is one row per curve in analysis/curves.toml, fitted from its
committed points. The second lists each distinct setA/setB pair found in
examples/ beside the curve it comes from, or says that none matches.
"""
import math
import re
import tomllib
from pathlib import Path

import numpy as np

from . import points
from .trace import fit

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis"
OUTPUT = ROOT / "docs" / "coefficients.md"

SET_PAIR = re.compile(r"\b(MQ\w+?)\s*\.\s*setA\(\s*([-+0-9.eE]+)\s*\)\s*;\s*MQ\w+?\s*\.\s*setB\(\s*([-+0-9.eE]+)\s*\)")


def sig(x, digits=5):
    """`x` to `digits` significant figures, without an exponent for ordinary sizes."""
    if x == 0:
        return "0"
    x = round_sig(x, digits)
    if 1e-3 <= abs(x) < 1e6:
        decimals = max(digits - 1 - math.floor(math.log10(abs(x))), 0)
        return f"{x:.{decimals}f}"
    return f"{x:.{digits - 1}e}"


def significant_digits(text):
    """How many significant figures a number was written with, e.g. '1012.7' -> 5."""
    mantissa = re.split("[eE]", text.strip().lstrip("+-"))[0]
    digits = mantissa.replace(".", "").lstrip("0")
    if "." not in mantissa:
        digits = digits.rstrip("0") or "0"
    return max(len(digits), 1)


def round_sig(x, digits):
    return float(f"{x:.{digits - 1}e}")


def load_curves(analysis=ANALYSIS, manifest=None):
    manifest = manifest or ROOT / "datasheets" / "manifest.toml"
    with open(manifest, "rb") as f:
        sheets = {d["id"]: d for d in tomllib.load(f)["datasheet"]}
    with open(Path(analysis) / "curves.toml", "rb") as f:
        curves = tomllib.load(f)["curve"]
    seen = set()
    for c in curves:
        if c["id"] in seen:
            raise ValueError(f"curves.toml: duplicate id {c['id']}")
        seen.add(c["id"])
        if c["datasheet"] not in sheets:
            raise ValueError(f"{c['id']}: datasheet '{c['datasheet']}' is not in the manifest")
        if c["origin"] not in ("upstream", "traced", "extracted", "located"):
            raise ValueError(f"{c['id']}: origin must be 'upstream', 'traced', 'extracted' or 'located'")
        if c["origin"] != "upstream" and not (Path(analysis) / c.get("recipe", "")).is_file():
            raise ValueError(f"{c['id']}: a {c['origin']} curve needs a 'recipe' file")
        c["sheet"] = sheets[c["datasheet"]]
        c.setdefault("unit", "ppm")
        c["points_data"] = points.read(Path(analysis) / c["points"])
        c["fit"] = fit(*c["points_data"])
    by_id = {c["id"]: c for c in curves}
    for c in curves:
        if "hand_read" in c:
            other = by_id.get(c["hand_read"])
            if other is None or other["origin"] != "upstream" or other["datasheet"] != c["datasheet"]:
                raise ValueError(f"{c['id']}: hand_read must name a curve read by hand upstream from the same datasheet")
            c["hand_read"] = other
    return curves


def offsets(hand_ppm, hand_ratio, ppm, ratio):
    """How far each hand-read point lies from a re-derived line, in Rs/R0 at the point's own concentration.

    The line is the re-derived points joined by straight segments on log-log
    axes, extended along its end segments for a point just past either end.
    """
    order = np.argsort(ppm)
    lx, ly = np.log10(np.asarray(ppm, dtype=float)[order]), np.log10(np.asarray(ratio, dtype=float)[order])
    out = []
    for p, q in zip(hand_ppm, hand_ratio, strict=True):
        x = math.log10(p)
        i = int(np.clip(np.searchsorted(lx, x) - 1, 0, len(lx) - 2))
        y = ly[i] + (x - lx[i]) * (ly[i + 1] - ly[i]) / (lx[i + 1] - lx[i])
        out.append(q / 10**y - 1)
    return out


def sensor_of(variable):
    """The sensor an example's object is for, from its name: MQ4 -> MQ-4, MQ303 -> MQ-303A."""
    m = re.fullmatch(r"MQ(\d+)[A-Za-z]?", variable)
    if not m:
        return None
    number = m.group(1)
    return f"MQ-{number}A" if number in ("303", "309") else f"MQ-{number}"


def example_pairs(examples=None):
    """{(sensor, a text, b text): sorted sketch names} for every setA/setB pair in examples/."""
    found = {}
    for ino in sorted((examples or ROOT / "examples").rglob("*.ino")):
        for var, a, b in SET_PAIR.findall(ino.read_text(errors="replace")):
            sensor = sensor_of(var)
            if sensor:
                found.setdefault((sensor, a, b), set()).add(ino.parent.name)
    return {k: sorted(v) for k, v in found.items()}


def judge(a_text, b_text, f):
    """How an example's pair relates to a fitted curve: (verdict, relative error in a, error in b)."""
    a, b = float(a_text), float(b_text)
    err_a, err_b = abs(a / f.a - 1), abs(b - f.b)
    same_a = round_sig(f.a, significant_digits(a_text)) == a
    same_b = round_sig(f.b, significant_digits(b_text)) == b
    if same_a and same_b:
        # Equal as written. A value written to one or two figures can still be far off.
        return ("same" if err_a < 0.005 else "rounded"), err_a, err_b
    if err_a < 0.05 and err_b < 0.05:
        return "near", err_a, err_b
    return "different", err_a, err_b


def audit(curves, pairs):
    """One row per example pair: its closest curve for that sensor and the verdict.

    The examples were written from Hanwei-era datasheets, so only curves from
    those are candidates. A Winsen manual for the same sensor is a different
    document with a different curve, and comparing against it would mislead.
    """
    curves = [c for c in curves if c.get("sheet", {}).get("maker", "Hanwei").startswith("Hanwei")]
    # A curve re-derived beside hand-read points is compared below, not here,
    # until one of the two is chosen as the source of the fit.
    curves = [c for c in curves if "hand_read" not in c]
    rows = []
    for (sensor, a_text, b_text), sketches in sorted(pairs.items(), key=lambda kv: (sensor_key(kv[0][0]), float(kv[0][1]))):
        candidates = [c for c in curves if c["sensor"] == sensor]
        if float(a_text) <= 0:
            rows.append((sensor, a_text, b_text, sketches, None, "not a power law", None, None))
            continue
        if not candidates:
            rows.append((sensor, a_text, b_text, sketches, None, "no points", None, None))
            continue
        a, b = float(a_text), float(b_text)
        best = min(candidates, key=lambda c: abs(c["fit"].b - b) / abs(b) + abs(math.log10(c["fit"].a / a)))
        verdict, err_a, err_b = judge(a_text, b_text, best["fit"])
        rows.append((sensor, a_text, b_text, sketches, best, verdict, err_a, err_b))
    return rows


def sensor_key(sensor):
    m = re.match(r"MQ-(\d+)(.*)", sensor)
    return (int(m.group(1)), m.group(2))


VERDICT = {
    "same": "same as the fit",
    "rounded": "the fit, rounded coarsely",
    "near": "near the fit, not equal",
    "different": "does not match any curve",
    "no points": "no digitised points from a Hanwei-era datasheet",
    "not a power law": "linear-model example",
}


def compared(curves):
    """A section comparing each re-derived curve with the hand-read points it re-derives."""
    pairs = [c for c in curves if "hand_read" in c]
    if not pairs:
        return []
    out = [
        "## Hand-read points against the datasheet",
        "",
        "Curves re-derived from a datasheet that also has hand-read points for the same gas. Both fits are in the table above; this compares them, and says how far each hand-read point lies from the re-derived line, in Rs/R0 at the concentration the point was read at.",
        "",
        "| Sensor | Gas | Datasheet | Hand-read a | Re-derived a | Hand-read b | Re-derived b | Hand-read points off the re-derived line |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in sorted(pairs, key=lambda c: (sensor_key(c["sensor"]), c["gas"].lower())):
        h = c["hand_read"]
        hp, hr = h["points_data"]
        off = offsets(hp, hr, *c["points_data"])
        cells = ", ".join(f"{d * 100:+.1f} % at {sig(p, 3)}" for p, d in zip(hp, off, strict=True))
        out.append(f"| {c['sensor']} | {c['gas']} | `{c['datasheet']}` | {sig(h['fit'].a)} | {sig(c['fit'].a)} "
                   f"| {sig(h['fit'].b, 4)} | {sig(c['fit'].b, 4)} | {cells} {c['unit']} |")
    out += [
        "",
        "Re-derived curves are not used in the comparison with the examples below until one source is chosen per curve.",
        "",
    ]
    return out


def render(curves, rows):
    out = [
        "# Calibration coefficients",
        "",
        "<!-- Generated by `just coefficients` from analysis/curves.toml. Do not edit by hand. -->",
        "",
        "The library computes a gas concentration as `ppm = a * (Rs/R0)^b`. The values of `a` and `b` are passed to `setA` and `setB`. This page lists every pair fitted from a datasheet curve, and then every pair the example sketches use.",
        "",
        "Each fit is a straight line through digitised points on log-log axes. It describes the datasheet's typical curve over the range of the points, not an individual sensor, and should not be used outside that range. None has been validated against hardware.",
        "",
        "## Fitted curves",
        "",
        "| Sensor | Gas | a | b | Concentration range | Rs/R0 range | Points | r² | Largest error | Datasheet | Points from |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in sorted(curves, key=lambda c: (sensor_key(c["sensor"]), c["sheet"]["maker"], c["gas"].lower())):
        f = c["fit"]
        origin = "read by hand upstream" if c["origin"] == "upstream" else f"[{c['origin']}](../analysis/{c['recipe']})"
        out.append(
            f"| {c['sensor']} | {c['gas']} | {sig(f.a)} | {sig(f.b, 4)} | {sig(f.ppm_min, 3)} to {sig(f.ppm_max, 3)} {c['unit']} "
            f"| {sig(f.ratio_min, 3)} to {sig(f.ratio_max, 3)} | {f.n} | {f.r_squared:.4f} | {f.max_ppm_error * 100:.0f} % | `{c['datasheet']}` | {origin} |"
        )
    notes = [c for c in curves if c.get("note")]
    if notes:
        out += ["", "Notes:", ""]
        out += [f"- **{c['sensor']} {c['gas']}** (`{c['datasheet']}`): {c['note']}" for c in notes]
    out += [
        "",
        "The concentration is in the unit of the datasheet figure's horizontal axis. Where that is not ppm, the value the library returns is in that unit too, whatever the sketch calls it: the MQ-3 curves are drawn against mg/L.",
        "",
        "`Datasheet` is an id in [`datasheets/manifest.toml`](../datasheets/manifest.toml), which records the document's maker, edition and SHA-256. Datasheets from different makers for the same sensor have different curves.",
        "",
        "**Largest error** is the biggest relative difference, over the fitted points, between the concentration the fit returns and the concentration the datasheet plots at that Rs/R0. It is what approximating the curve by a power law costs, before any error in the sensor itself.",
        "",
        "**Read by hand upstream** means a few marker positions per curve, digitised by the authors of MQSensorsLib and copied from `miguel5612/MQSensorsLib_Docs` (MIT). **Traced** means every pixel column of the line, by the tool in [`analysis/`](../analysis/README.md). **Extracted** means the marker positions the PDF draws the figure with, read from its drawing commands by the same tool. **Located** means the centres of a line's hollow markers in a figure stored as an image, found by the same tool. For all three, the link is the recipe that reproduces the points.",
        "",
    ]
    out += compared(curves)
    out += [
        "## Values used in the examples",
        "",
        "Every distinct `setA`/`setB` pair in `examples/`, beside the closest fitted curve for the same sensor. The examples were written from the Hanwei-era datasheets, so only curves from those are compared; a Winsen manual for the same sensor is a different document with a different curve.",
        "",
        "| Sensor | setA | setB | Closest curve | Fitted a | Fitted b | Difference in a | Verdict | Sketches |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    counts = {}
    for sensor, a, b, sketches, best, verdict, err_a, _ in rows:
        counts[verdict] = counts.get(verdict, 0) + 1
        if best:
            f = best["fit"]
            cells = f"{best['gas']} | {sig(f.a)} | {sig(f.b, 4)} | {err_a * 100:.1f} %"
        else:
            cells = " | | | "
        out.append(f"| {sensor} | {a} | {b} | {cells} | {VERDICT[verdict]} | {', '.join(sketches)} |")
    out += ["", "| Verdict | Pairs |", "|---|---|"]
    out += [f"| {VERDICT[v]} | {counts[v]} |" for v in VERDICT if v in counts]
    out += [
        "",
        "- **Same as the fit**: the example's value equals the fitted value at the precision the example writes it.",
        "- **The fit, rounded coarsely**: equal at the precision written, but written to so few figures that `a` is off by the amount shown. The computed concentration is off by the same proportion.",
        "- **Near the fit, not equal**: within 5 % in `a` and 0.05 in `b` of a curve, without being that curve's fit. Its origin is not recorded.",
        "- **Does not match any curve**: no digitised curve for the sensor gives this pair.",
        "",
    ]
    return "\n".join(out)


def generate():
    curves = load_curves()
    return render(curves, audit(curves, example_pairs()))


def run(check=False, output=OUTPUT):
    text = generate()
    name = output.relative_to(ROOT) if output.is_relative_to(ROOT) else output
    if check:
        if not output.exists() or output.read_text() != text:
            print(f"error: {name} is out of date: run `just coefficients`")
            return 1
        print(f"{name} is up to date")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    print(f"wrote {name}")
    return 0
