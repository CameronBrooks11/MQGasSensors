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

## Figures drawn as vectors

Some datasheets draw the figure with PDF drawing commands instead of embedding an image: the gridlines, lines and markers are path objects with coordinates. There the plotted values are in the file, and

```
uv run python -m mqcurves extract recipes/<curve>.toml --points points.csv --overlay out/curve.png
```

reads them without any pixels. Each value the manufacturer plotted is a marker, and its centre is the value; the segments between markers are the drawing program's smoothing and are not read. A recipe names the plot frame and the markers' colours:

```toml
id = "mq-4-hanwei-2007-ch4-extracted"
sensor = "MQ-4"
gas = "CH4"

[source]
datasheet = "mq-4-hanwei-2007"
page = 2

[frame]                          # the plot area, a rectangle drawn on the page
x = [85.2, 353.04]               # its left and right edges, in PDF points
y = [427.2, 651.36]              # its bottom and top edges
ppm = [100, 10000]               # the concentration at the left and right edges
ratio = [0.1, 10]                # Rs/R0 at the bottom and top edges

[markers]                        # the gas's markers, by outline and fill colour
stroke = [0, 0, 128]
fill = [255, 0, 255]
count = 4                        # how many the figure plots
exclude = [[98.64, 433.44, 169.68, 536.64]]   # optional: boxes to ignore, e.g. the legend
```

Nothing is read unless the PDF matches the SHA-256 in the manifest, the page draws a rectangle at the frame's coordinates, and exactly `count` markers of those colours are found. A path of the marker colours larger than a marker is refused as a line. A marker drawn as several strokes, such as a cross, is joined into one.

## Commands

| Command | What it does |
|---|---|
| `figures <pdf> [--page N] [--save DIR]` | List a PDF's embedded images with their size and `pixels_sha256` |
| `trace <recipe> [--points CSV] [--overlay PNG]` | Trace and fit a curve from its recipe |
| `extract <recipe> [--points CSV] [--overlay PNG]` | Read a curve's markers from a figure drawn as vectors, and fit it |
| `fit <points.csv>` | Fit points that are already digitised |
| `mark <recipe> --id … --sensor … --gas … (--image F \| --datasheet ID --page N --pixels-sha256 H)` | Mark a new figure by clicking, and write its recipe |
| `table [--check]` | Write `docs/coefficients.md`, or fail if it is out of date |
| `reproduce` | Re-derive every traced or extracted curve from its datasheet and compare with the committed points |

`mark` opens a window and needs matplotlib: `uv sync --extra interactive`.

An overlay shows the traced points, the fitted line and the axis reference positions on top of the figure. It contains the datasheet's figure, so keep it local; `analysis/out/` is ignored by git.

## Points and the coefficients page

[`curves.toml`](curves.toml) lists every curve that has digitised points: its sensor, gas, datasheet and the CSV under `points/` that holds them. A curve's points are read by hand by the authors of MQSensorsLib (a few marker positions each), traced from the figure's pixels by this tool, or extracted from the figure's drawing commands by this tool. A curve re-derived from a datasheet that also has hand-read points names them in `hand_read`, and the coefficients page compares the two.

```
just coefficients
```

fits every curve and writes [`docs/coefficients.md`](../docs/coefficients.md). For a traced or extracted curve, the recipe is in `recipes/` and

```
just reproduce
```

downloads the datasheets, derives each such curve again and expects the committed points back byte for byte. The `Datasheet mirrors` workflow runs it monthly and on pull requests that touch a recipe, the points or the tracer.

The coefficients page also lists every `setA`/`setB` pair used in `examples/` beside the curve it comes from. `just check` fails when the page no longer matches the points or the examples, so a coefficient cannot change without the page changing with it.

## Limits

- **Resolution.** A figure is only as precise as its pixels. In a 400 by 305 pixel figure spanning two decades vertically, one pixel is about 1.8 % in Rs/R0. A vector figure is as precise as its coordinates: the MQ-4 figure is drawn on a 0.24 pt grid. Its markers are plotted at 200, 1000, 5000 and 10000 ppm, and their centres sit up to 0.49 pt from where the frame puts those concentrations, 0.83 % in concentration. Rs/R0 is drawn to the same grid.
- **A power law is an approximation.** Some datasheet curves bend on log-log axes, and several are drawn as straight segments between a handful of plotted values. The fit is then a best straight line over the traced range. The coefficients page gives, for each curve, the largest difference between the fit and the points: up to 20 % in concentration for the curves traced so far. Coefficients should not be used outside the range of the points.
- **Markers.** Where a line carries markers, their pixels are part of the trace. A symmetric marker does not move the centre of the stroke; a triangle shifts it slightly over the few columns it covers.
- **A datasheet curve is typical, not individual.** It describes a nominal sensor under the conditions the datasheet states. No fit here has been validated against hardware.

## Tests

```
just test
```

The tracer's tests draw a figure with a known curve that covers only part of the plot, trace it, and check that both coefficients come back. The extractor's tests write a PDF that draws a figure with known values, a legend and a marker made of strokes, and read the values back. Neither needs a datasheet. Further tests read real datasheets and run only where `just datasheets` has been run.
