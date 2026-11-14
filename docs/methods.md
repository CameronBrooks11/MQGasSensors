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
| 2 | The figure: an image named by a SHA-256 of its pixels, or a drawing named by its page and plot frame | the curve's recipe in [`analysis/recipes/`](../analysis/recipes) | The tool refuses a figure whose pixels differ, or a page without that frame |
| 3 | The line, as digitised points | [`analysis/points/`](../analysis/points) | `just reproduce` traces it again and expects the same file |
| 4 | The fit | [`coefficients.md`](coefficients.md) | `just check` fails if the page does not match the points |
| 5 | The values in a sketch | `examples/` | The same page lists each one beside the fit it was written from and its difference from the datasheet fit |

```
just datasheets     # 1: download the PDFs
just reproduce      # 2 and 3: re-derive every curve that has a recipe from them
just coefficients   # 4 and 5: fit every curve and write the page
```

The datasheets are copyrighted and are not stored in this repository, and neither are figures cut from them. The digitised points, which are numbers read off a figure, are.

## Five ways the points were obtained

**Read by hand upstream.** The coefficients the example sketches use were derived by the authors of [MQSensorsLib](https://github.com/miguel5612/MQSensorsLib), who read a few marker positions per line off each figure. Their points are kept here unchanged, and fitting them gives back the values in the sketches. The reading cannot be repeated, so for a curve known only from these points the chain starts at step 3. Most have since been re-derived from the datasheet named for them, which also tests where the hand reading came from; see below.

**Traced.** Curves in figures stored as images are read by the tool in [`analysis/`](../analysis/README.md). It takes the figure's pixels straight from the PDF, collects the connected pixels of the line's colour starting from a marked point, and averages them column by column. Pixel positions become values through an axis calibration fitted to the figure's gridlines. Every input is in a recipe file, so the whole chain from step 1 is repeatable.

**Extracted.** Some datasheets draw the figure with PDF drawing commands, so the position of every marker is in the file. The same tool reads the centres of one gas's markers, picked out by their colours, and converts them through the plot frame's coordinates. These are the values the manufacturer plotted, to the precision of the drawing, with no pixels involved. A marker the legend is drawn over is still in the file and is read; on the MQ-3 sheet the legend covers three of the ten markers on three lines, which is why the hand-read points for those lines skip from about 1 to 6 mg/L. Where hand-read points exist for the same curve, the coefficients page compares the two.

**Located.** In a figure stored as an image whose markers are hollow outlines, the same tool finds each marker as the patch of background its outline encloses, and takes the centre of that patch. Markers of one colour are told apart by the shape of the patch. These are the plotted values to the precision of the image's pixels. Where a figure's markers cannot be found this way, they are read by eye as below, or the hand-read points are kept and the reason is recorded beside the curve.

**Marked.** Where neither method can follow a figure, the marker centres are read by eye and recorded as pixel positions in the recipe, with the figure's pixel hash and gridline calibration. This is still a person's reading, good to about a pixel, but each position can be checked against the exact figure on an overlay, which the hand-read points cannot.

## Which points a fit comes from

Where a curve has been re-derived from its datasheet, the re-derived points are the source of its fit, and the hand-read points for the same gas are kept as a comparison. Where it has not, the hand-read points remain the source. The coefficients page has one row per curve, says which source each uses, and lists every hand-read fit that a re-derived one replaced beside how far each hand-read point lies from the re-derived line.

For each sensor the page also says whether its hand-read points were confirmed to come from the datasheet named for them. A sensor counts as confirmed when its curves have been re-derived from that datasheet and the hand-read points lie on the re-derived lines, within a few percent in Rs/R0. Where some or none of its curves have been re-derived, the page says so.

The example sketches' values were written from the hand-read fits. The page matches each one to the hand-read fit it came from, and gives the largest difference in concentration between the example's pair and the datasheet fit for the same gas over that curve's range: what using the example costs, apart from the error of the power law itself.

## Two editions of the datasheets

Two makers publish datasheets for sensors with the same names, and their curves differ.

- **Hanwei**, 2004 to 2009. The example sketches' values come from these.
- **Zhengzhou Winsen**, manuals from 2014 and 2015. The traced curves so far come from these.

The extracted curves so far come from the Hanwei MQ-3, MQ-4, MQ-5, MQ-6, MQ-7, MQ-8 and MQ-135 datasheets, the located ones from the Hanwei MQ-303A and MQ-309A datasheets, and the marked ones from the Hanwei MQ-2 and MQ-9 datasheets, the 2009 MQ-131 datasheet, and the Hanwei MQ-136 and MQ-137 datasheets, which print the same figure with different legends. The MQ-131 figure plots R0/Rs rather than Rs/R0, so its curves' ratio is R0/Rs.

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
