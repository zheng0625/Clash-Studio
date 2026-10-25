#!/bin/bash
set -euo pipefail
package=$(realpath "$1")
data=$(mktemp -d -t clash-native-XXXXXX)
"$package/Start.sh" --data-dir "$data" > "$data/desktop.log" 2>&1 &
pid=$!
trap 'if kill -0 "$pid" 2>/dev/null; then kill "$pid"; fi' EXIT
for attempt in $(seq 1 150); do
    if grep -q frontend_ready "$data/startup.log" 2>/dev/null; then break; fi
    if ! kill -0 "$pid" 2>/dev/null; then cat "$data/desktop.log"; exit 1; fi
    sleep .2
done
cat "$data/startup.log"
if ! grep -q frontend_ready "$data/startup.log"; then cat "$data/desktop.log"; exit 1; fi
"$package/Stop.sh" --data-dir "$data"
for attempt in $(seq 1 50); do
    if ! kill -0 "$pid" 2>/dev/null; then wait "$pid"; echo "Native desktop, frontend IPC and single-instance quit passed; logs: $data"; exit 0; fi
    sleep .2
done
echo 'Desktop quit timed out'; exit 1
