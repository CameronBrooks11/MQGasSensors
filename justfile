# Project task runner

set dotenv-load := false

# Default: show available recipes
default:
    @just --list

# Install the Arduino board cores and libraries the examples need (CI runs this)
setup:
    scripts/examples.sh setup

# Check tracked assets, then compile every example; skips what is not installed
check:
    scripts/check-assets.sh
    scripts/examples.sh check

# Run the library's unit tests on a simulated Mega 2560 (needs simavr), then the tooling's
test:
    scripts/test.sh
    python3 -m unittest discover -s tests

# Download the datasheets in datasheets/manifest.toml, verifying each by SHA-256
datasheets:
    scripts/datasheets.py fetch
