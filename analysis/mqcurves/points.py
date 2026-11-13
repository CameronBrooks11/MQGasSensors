"""Digitised points as CSV: one `ppm,ratio` pair per line under a header."""
import csv

import numpy as np

HEADER = ("ppm", "ratio")


def write(path, ppm, ratio):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        for p, r in zip(ppm, ratio, strict=True):
            w.writerow((f"{p:.6g}", f"{r:.6g}"))


def read(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    if not rows or tuple(rows[0]) != HEADER:
        raise ValueError(f"{path}: expected a '{','.join(HEADER)}' header")
    data = np.array([[float(v) for v in row] for row in rows[1:] if row], dtype=float)
    if data.size == 0:
        raise ValueError(f"{path}: no points")
    return data[:, 0], data[:, 1]
