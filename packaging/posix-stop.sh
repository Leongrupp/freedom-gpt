#!/bin/sh
set -eu
APP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$APP_ROOT/runtime/python/bin/python3" -B -s "$APP_ROOT/stop.py" "$@"
