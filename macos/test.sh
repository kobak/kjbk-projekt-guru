#!/bin/sh
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
task_temp=$(mktemp -d -t guru-mac-tests)
trap 'rm -rf "$task_temp"' EXIT
xcrun swiftc -swift-version 5 -module-cache-path "$task_temp/cache" "$task_root/Sources/Protocol.swift" "$task_root/Tests/main.swift" -o "$task_temp/protocol-tests"
"$task_temp/protocol-tests"
