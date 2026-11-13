#!/usr/bin/env bash
# Run the ArduinoUnit tests in examples/UnitTesting on a simulated Mega 2560.
#
# Builds the sketch for arduino:avr:mega, runs the firmware in simavr and reads
# ArduinoUnit's summary line from the simulated serial port. Passes only when
# that line reports at least one test passed and none failed.
set -euo pipefail
cd "$(dirname "$0")/.."

SKETCH=examples/UnitTesting
TIMEOUT=${TEST_TIMEOUT:-60}
build="${TMPDIR:-/tmp}/mqgassensors-build/$SKETCH"
out="$build/simavr.out"

for tool in arduino-cli simavr; do
  command -v "$tool" >/dev/null || {
    echo "error: $tool is not installed" >&2
    exit 1
  }
done

arduino-cli compile --fqbn arduino:avr:mega --library . --build-path "$build" "$SKETCH" >/dev/null

# The firmware idles forever once the tests finish, so simavr never exits and
# never writes again: watch its output file and stop it from here.
: >"$out"
simavr -m atmega2560 -f 16000000 "$build/UnitTesting.ino.elf" >"$out" 2>&1 &
sim=$!
trap 'kill "$sim" 2>/dev/null || true' EXIT

# simavr colours the serial text and prints "." for a carriage return.
serial() { sed 's/\x1b\[[0-9;]*m//g' "$out"; }

summary=""
for ((i = 0; i < TIMEOUT * 5; i++)); do
  summary=$(serial | grep -m1 'Test summary:' || true)
  [ -n "$summary" ] && break
  kill -0 "$sim" 2>/dev/null || break
  sleep 0.2
done
kill "$sim" 2>/dev/null || true

serial | grep -E '^Test .* (passed|failed|skipped)\.' || true
if [ -z "$summary" ]; then
  echo "error: no test summary within ${TIMEOUT}s; simulator output:" >&2
  serial >&2
  exit 1
fi
echo "$summary"

if [[ "$summary" =~ Test\ summary:\ ([0-9]+)\ passed,\ ([0-9]+)\ failed ]]; then
  if [ "${BASH_REMATCH[1]}" -gt 0 ] && [ "${BASH_REMATCH[2]}" -eq 0 ]; then
    exit 0
  fi
fi
exit 1
