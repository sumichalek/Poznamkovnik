#!/usr/bin/env bash
set -euo pipefail
PN_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$PN_SCRIPT_DIR/server_manage.py" "$@"
