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

# Run the unit tests on a simulated Mega 2560 (needs simavr)
test:
    scripts/test.sh
