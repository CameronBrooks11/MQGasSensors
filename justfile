# Project task runner

set dotenv-load := false

# Default: show available recipes
default:
    @just --list

# Install the Arduino board cores and libraries the examples need (CI runs this)
setup:
    scripts/examples.sh setup

# Check tracked assets and the coefficients page, then compile every example; skips what is not installed
check:
    scripts/check-assets.sh
    cd analysis && uv run --locked python -m mqcurves table --check
    scripts/examples.sh check

# Run the tests: the library on a simulated Mega 2560 (needs simavr), the scripts, the curve tracer (needs uv)
test:
    scripts/test.sh
    python3 -m unittest discover -s tests
    cd analysis && uv run --locked python -m unittest discover -s tests

# Regenerate docs/coefficients.md from the digitised points and the examples
coefficients:
    cd analysis && uv run --locked python -m mqcurves table

# Download the datasheets in datasheets/manifest.toml, verifying each by SHA-256
datasheets:
    scripts/datasheets.py fetch

# Download the datasheets, then re-derive every traced or extracted curve and compare with the committed points
reproduce: datasheets
    cd analysis && uv run --locked python -m mqcurves reproduce
