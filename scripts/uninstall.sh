#!/usr/bin/env bash
# The final exec lets a running release safely remove its own code.
set -euo pipefail
PN_UNINSTALL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
case "${1:-}" in
  -h|--help)
    printf '%s\n' 'Použitie: bash scripts/uninstall.sh [--plan] [--root CESTA] [--delete-data]' \
      'Predvolene odstráni službu a kód, zachová shared/. --delete-data vymaže aj dáta a všetky aplikačné zálohy.'
    exit 0 ;;
esac
exec python3 -B "$PN_UNINSTALL_DIR/server_uninstall.py" "$@"
