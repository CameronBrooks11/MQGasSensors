# How a datasheet curve becomes a coefficient

The library computes a gas concentration from a sensor's resistance as

```
ppm = a * (Rs/R0)^b
```

`a` and `b` are set per gas with `setA` and `setB`. They are not measured by this project. They come from the sensitivity figure in the sensor's datasheet, which plots Rs/R0 against concentration on log-log axes, one line per gas. This page describes how a line in that figure becomes a pair of numbers, and how anyone can repeat it.

## The chain

| Step | What | Where | Checked by |
|---|---|---|---|
| 1 | The datasheet, named by size and SHA-256 | [`datasheets/manifest.toml`](../datasheets/manifest.toml) | A download is accepted only if its bytes match |
| 2 | The figure, named by a SHA-256 of its pixels | the curve's recipe in [`analysis/recipes/`](../analysis/recipes) | The tracer refuses a figure whose pixels differ |
| 3 | The line, as digitised points | [`analysis/points/`](../analysis/points) | `just reproduce` traces it again and expects the same file |
| 4 | The fit | [`coefficients.md`](coefficients.md) | `just check` fails if the page does not match the points |
| 5 | The values in a sketch | `examples/` | The same page lists each one beside its curve |

```
just datasheets     # 1: download the PDFs
just reproduce      # 2 and 3: re-trace every traced curve from them
just coefficients   # 4 and 5: fit every curve and write the page
```

The datasheets are copyrighted and are not stored in this repository, and neither are figures cut from them. The digitised points, which are numbers read off a figure, are.

## Two ways the points were obtained

**Read by hand upstream.** The coefficients the example sketches use were derived by the authors of [MQSensorsLib](https://github.com/miguel5612/MQSensorsLib), who read a few marker positions per line off each figure. Their points are kept here unchanged, and fitting them gives back the values in the sketches. For these curves the chain starts at step 3: which figure the points were read from is recorded, but the reading cannot be repeated.

**Traced.** Newer curves are read by the tool in [`analysis/`](../analysis/README.md). It takes the figure's pixels straight from the PDF, collects the connected pixels of the line's colour starting from a marked point, and averages them column by column. Pixel positions become values through an axis calibration fitted to the figure's gridlines. Every input is in a recipe file, so the whole chain from step 1 is repeatable.

## Two editions of the datasheets

Two makers publish datasheets for sensors with the same names, and their curves differ.

- **Hanwei**, 2004 to 2009. The example sketches' values come from these.
- **Zhengzhou Winsen**, manuals from 2014 and 2015. The traced curves so far come from these.

A coefficient pair is only meaningful together with the datasheet it came from, so the page names the datasheet in every row and never mixes editions. Which edition describes a sensor you have bought depends on who made it.

## The fit

A straight line is fitted, by least squares, to the points on log-log axes: log of concentration against log of Rs/R0. Its slope is `b` and its intercept gives `a`.

The page reports three things about each fit that say how far to trust it:

- **Range.** The concentrations and Rs/R0 values the points cover. The fit says nothing outside them.
- **r².** How close the points are to a straight line on log-log axes.
- **Largest error.** The biggest relative difference, over the points, between the concentration the fit returns and the one the datasheet plots at the same Rs/R0.

## Limits

- **One power law is an approximation.** Several curves bend, and some are drawn as straight segments with different slopes. The largest error in the table is the cost: up to 20 % in concentration for the curves traced so far.
- **A figure is only as precise as its pixels.** In a 400 by 305 pixel figure spanning two decades vertically, one pixel is about 1.8 % in Rs/R0.
- **A datasheet curve is typical.** It describes a nominal sensor at the temperature, humidity and load resistance the datasheet states. An individual sensor differs, and drifts.
- **Units follow the figure.** Most figures are drawn against ppm. The Hanwei MQ-3 figure is drawn against mg/L, so its coefficients return mg/L.
- **Nothing here has been validated against hardware.** These are the manufacturer's curves, reproduced faithfully. Whether a sensor on a bench follows them is a separate question.
