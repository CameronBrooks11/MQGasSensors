# Curve tracing

A datasheet gives a sensor's response as a figure: Rs/R0 against gas concentration on log-log axes, one line per gas. This tool reads one of those lines off the figure and fits the power law the library evaluates.

```
cd analysis
uv run python -m mqcurves trace recipes/<curve>.toml --points points.csv --overlay out/curve.png
```

[uv](https://docs.astral.sh/uv/) creates the environment on first use. The dependencies are numpy, Pillow and pypdfium2.

## Method

1. **Take the figure's pixels.** For a datasheet, the figure is the image object embedded in the PDF, extracted as stored. The page is not rendered, so the pixels do not depend on a renderer or a resolution.
2. **Isolate the line.** From a marked pixel on the line, collect every connected pixel whose colour is within a tolerance of that pixel's colour.
3. **Find its centre.** Average the collected pixels' rows in each pixel column.
4. **Convert to values.** Each axis is fixed by two marked positions with known values, interpolated in log space. The mapping does not depend on where the line starts or ends.
5. **Fit** a straight line to the points in log-log space, in both directions:

| Form | Regression | Use |
|---|---|---|
| `ratio = A * ppm^B` | log ratio on log ppm | How the datasheet draws the curve |
| `ppm = a * ratio^b` | log ppm on log ratio | What the library evaluates: `setA(a)`, `setB(b)` |

The two are exact inverses only when the points lie on a perfect line. `r^2` says how close they are to one.

## Recipes

A recipe holds every input to a trace, so the trace can be repeated without a person:

```toml
id = "mq-8-winsen-v1.3-h2"
sensor = "MQ-8"
gas = "H2"

[source]                      # a figure embedded in a manifest datasheet ...
datasheet = "mq-8-winsen-v1.3"
page = 4
pixels_sha256 = "..."
# image = "figure.png"        # ... or an image file, relative to the recipe

[x]                           # ppm axis: two pixel columns and their values
pixels = [50, 380]
values = [100, 10000]

[y]                           # Rs/R0 axis: two pixel rows and their values
pixels = [15, 270]
values = [1, 0.01]

[trace]
seed = [210, 140]             # a pixel on the line, as [x, y]
lo = 20                       # colour tolerance below and above the seed's
up = 20
bin_width = 1                 # columns averaged into one point
connectivity = 8
ppm = [100, 10000]            # optional: keep only points in this range

[[check]]                     # optional, repeatable: a value read off the
at = 1000                     # figure by eye, which the trace must pass
ratio = 0.09                  # within 10 % of (or `within = ...`)
```

`ppm` matters where a line ends in a marker: the marker's outer half has the line's colour and would otherwise be read as points beyond the last value the datasheet plots. A `check` guards against a wrong calibration or seed: the trace fails if it does not pass near a value a person read off the figure.

`datasheet` is an id from [`datasheets/manifest.toml`](../datasheets/manifest.toml); run `just datasheets` first. `pixels_sha256` identifies the figure by its content, which also proves the figure being traced is the one the recipe was written for.

## Commands

| Command | What it does |
|---|---|
| `figures <pdf> [--page N] [--save DIR]` | List a PDF's embedded images with their size and `pixels_sha256` |
| `trace <recipe> [--points CSV] [--overlay PNG]` | Trace and fit a curve from its recipe |
| `fit <points.csv>` | Fit points that are already digitised |
| `mark <recipe> --id … --sensor … --gas … (--image F \| --datasheet ID --page N --pixels-sha256 H)` | Mark a new figure by clicking, and write its recipe |
| `table [--check]` | Write `docs/coefficients.md`, or fail if it is out of date |
| `reproduce` | Re-trace every traced curve from its datasheet and compare with the committed points |

`mark` opens a window and needs matplotlib: `uv sync --extra interactive`.

An overlay shows the traced points, the fitted line and the axis reference positions on top of the figure. It contains the datasheet's figure, so keep it local; `analysis/out/` is ignored by git.

## Points and the coefficients page

[`curves.toml`](curves.toml) lists every curve that has digitised points: its sensor, gas, datasheet and the CSV under `points/` that holds them. A curve's points are either read by hand by the authors of MQSensorsLib (a few marker positions each) or traced from the figure by this tool.

```
just coefficients
```

fits every curve and writes [`docs/coefficients.md`](../docs/coefficients.md). For a traced curve, the recipe is in `recipes/` and

```
just reproduce
```

downloads the datasheets, traces each such curve again and expects the committed points back byte for byte. The `Datasheet mirrors` workflow runs it monthly and on pull requests that touch a recipe, the points or the tracer.

The coefficients page also lists every `setA`/`setB` pair used in `examples/` beside the curve it comes from. `just check` fails when the page no longer matches the points or the examples, so a coefficient cannot change without the page changing with it.

## Limits

- **Resolution.** A figure is only as precise as its pixels. In a 400 by 305 pixel figure spanning two decades vertically, one pixel is about 1.8 % in Rs/R0.
- **A power law is an approximation.** Some datasheet curves bend on log-log axes, and several are drawn as straight segments between a handful of plotted values. The fit is then a best straight line over the traced range. The coefficients page gives, for each curve, the largest difference between the fit and the points: up to 20 % in concentration for the curves traced so far. Coefficients should not be used outside the range of the points.
- **Markers.** Where a line carries markers, their pixels are part of the trace. A symmetric marker does not move the centre of the stroke; a triangle shifts it slightly over the few columns it covers.
- **A datasheet curve is typical, not individual.** It describes a nominal sensor under the conditions the datasheet states. No fit here has been validated against hardware.

## Tests

```
just test
```

The tracer's tests draw a figure with a known curve that covers only part of the plot, trace it, and check that both coefficients come back. They need no datasheet. One further test reads a real datasheet's figure and runs only where `just datasheets` has been run.
