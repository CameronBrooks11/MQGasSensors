# Datasheets

The calibration coefficients in this library are fitted to the sensitivity curves printed in manufacturer datasheets. Those PDFs are copyrighted, so they are not stored in this repository. [`manifest.toml`](manifest.toml) identifies each one exactly, and one command downloads them:

```
just datasheets
```

The files land in `datasheets/files/`, which git ignores. Python 3.11 or newer is the only requirement.

## How a download is accepted

Every entry records the file's size and SHA-256 and an ordered list of mirrors. A download is kept only if its bytes match. Anything else is discarded and the next mirror is tried: an error page served with status 200, a truncated copy, or a different edition of the same sheet. A mirror that fails with a server error is retried before moving on.

## Mirror order

| Kind | What it is | Why it is in this position |
|---|---|---|
| `wayback` | An Internet Archive snapshot, in the form that returns the original bytes | A snapshot never changes |
| `swh` | Software Heritage, addressed by the file's own SHA-256 | Also immutable, and independent of the Internet Archive |
| `live` | A distributor's or manufacturer's own URL | Works today, but these move and disappear |
| `github` | A copy in a third-party repository, pinned to a commit | Last resort only |

## Editions

Two documents for the same sensor from different makers are different datasheets with different curves. The manifest keeps them as separate entries and never lists one as a mirror of the other.

- **Hanwei** sheets, dated 2004 to 2009, are the ones the coefficients in `examples/` were derived from.
- **Winsen** manuals (Zhengzhou Winsen Electronics), versions 1.3 and 1.4 from 2014 and 2015, are a later maker's documents for parts sold under the same names.

## Checking the mirrors

```
scripts/datasheets.py verify
```

tests every mirror of every entry, not only the first that works, and reports each one that is unreachable or serves different bytes.

The `Datasheet mirrors` workflow runs the same command on the 3rd of each month, on demand from the Actions tab, and on any pull request that changes the manifest or the fetch script. It fails when a datasheet has no working mirror left, and raises a warning for each mirror that fails while another still works. The pull request gate itself never downloads datasheets.

## Adding a datasheet

Add an entry with the file's size and SHA-256, at least one `wayback` mirror first, and any `github` mirror last. Then run `scripts/datasheets.py verify --only <id>`; every mirror listed must pass.
