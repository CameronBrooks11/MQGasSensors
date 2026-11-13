#!/usr/bin/env bash
# Compile every example sketch against the library in this working tree.
#
#   scripts/examples.sh check   compile; exit 1 on any failure
#   scripts/examples.sh setup   install the board cores and libraries the examples need
#
# Outside CI, a sketch whose board core or library is not installed is reported
# as SKIP. With CI set, a skip is a failure: the gate must build everything.
set -euo pipefail
cd "$(dirname "$0")/.."

AVR=arduino:avr:mega
ESP32=esp32:esp32:esp32
ESP8266=esp8266:esp8266:nodemcuv2
BOARD_INDEXES=https://espressif.github.io/arduino-esp32/package_esp32_index.json,https://arduino.esp8266.com/stable/package_esp8266com_index.json

# The board a sketch is built for. Sketches are written for an AVR board unless
# they sit in one of the ESP folders.
board_for() {
  case "$1" in
    examples/ESP32 | examples/ESP32/*) echo "$ESP32" ;;
    examples/ESP8266) echo "$ESP8266" ;;
    *) echo "$AVR" ;;
  esac
}

# Third-party libraries a sketch includes, one per line.
libs_for() {
  case "$(basename "$1")" in
    MQ135-ADS1115) echo "Adafruit ADS1X15" ;;
    MQ-135-CorrectionFactorDHT11) printf '%s\n' "Adafruit Unified Sensor" "DHT sensor library" ;;
    UnitTesting) echo "ArduinoUnit" ;;
  esac
}

sketches() {
  find examples -name '*.ino' -printf '%h\n' | sort -u
}

has_core() {
  arduino-cli core list --json | jq -e --arg id "${1%:*}" '(.platforms // []) | any(.id == $id)' >/dev/null
}

has_lib() {
  arduino-cli lib list --json | jq -e --arg n "$1" '(.installed_libraries // []) | any(.library.name == $n)' >/dev/null
}

setup() {
  arduino-cli core update-index --additional-urls "$BOARD_INDEXES"
  for fqbn in "$AVR" "$ESP32" "$ESP8266"; do
    arduino-cli core install --additional-urls "$BOARD_INDEXES" "${fqbn%:*}"
  done
  arduino-cli lib update-index
  while IFS= read -r sketch; do
    while IFS= read -r lib; do
      arduino-cli lib install "$lib"
    done < <(libs_for "$sketch")
  done < <(sketches)
}

check() {
  local build="${TMPDIR:-/tmp}/mqgassensors-build" pass=0 fail=0 skip=0
  local sketch fqbn lib missing log
  while IFS= read -r sketch; do
    fqbn=$(board_for "$sketch")
    missing=""
    has_core "$fqbn" || missing="core ${fqbn%:*}"
    while IFS= read -r lib; do
      [ -z "$lib" ] || has_lib "$lib" || missing="${missing:+$missing, }library $lib"
    done < <(libs_for "$sketch")

    if [ -n "$missing" ]; then
      skip=$((skip + 1))
      echo "SKIP $sketch ($fqbn): not installed: $missing"
    elif log=$(arduino-cli compile --fqbn "$fqbn" --library . --build-path "$build/$sketch" "$sketch" 2>&1); then
      pass=$((pass + 1))
      echo "PASS $sketch ($fqbn)"
    else
      fail=$((fail + 1))
      echo "FAIL $sketch ($fqbn)"
      echo "$log" | sed 's/^/    /'
    fi
  done < <(sketches)

  echo "pass=$pass fail=$fail skip=$skip"
  if [ "$fail" -gt 0 ]; then exit 1; fi
  if [ "$pass" -eq 0 ]; then
    echo "error: no sketch was compiled" >&2
    exit 1
  fi
  if [ -n "${CI:-}" ] && [ "$skip" -gt 0 ]; then
    echo "error: $skip sketch(es) skipped in CI; run 'just setup' first" >&2
    exit 1
  fi
}

case "${1:-}" in
  check) check ;;
  setup) setup ;;
  *)
    echo "usage: $0 check|setup" >&2
    exit 2
    ;;
esac
