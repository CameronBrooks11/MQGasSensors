# Project task runner

set dotenv-load := false

# Default: show available recipes
default:
    @just --list

# Install the Arduino board cores and libraries the examples need (CI runs this)
setup:
    scripts/examples.sh setup

# Compile every example against this working tree; skips what is not installed
check:
    scripts/examples.sh check
