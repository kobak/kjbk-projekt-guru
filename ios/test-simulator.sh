#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
device=${1:?Add meg egy iPhone- vagy iPad-szimulátor UUID-ját.}
python=${GURU_TEST_PYTHON:-.venv/bin/python}
"$python" ios/Tests/simulator_server.py "$device" &
server=$!
trap 'kill "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true' EXIT
for attempt in $(seq 1 40); do
    kill -0 "$server"
    if curl --silent --fail http://127.0.0.1:8021/health/ >/dev/null; then break; fi
    sleep 1
done
xcodebuild -project ios/Guru.xcodeproj -scheme Guru -configuration Debug \
    -destination "platform=iOS Simulator,id=$device" -parallel-testing-enabled NO \
    -derivedDataPath "${GURU_DERIVED_DATA:-ios/build-tests}" test
