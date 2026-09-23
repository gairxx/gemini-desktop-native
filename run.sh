#!/usr/bin/env bash
# Run the app from the source tree (requires python3-gi, gtk4, libadwaita, webkitgtk-4.1/6.0).
set -euo pipefail
cd "$(dirname "$0")"
exec env PYTHONPATH="$PWD/src" python3 -m main "$@"