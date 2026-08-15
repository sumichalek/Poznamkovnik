#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="poznamkovnik.service"
HOST="127.0.0.1"
PORT="${POZNAMKOVNIK_PORT:-1111}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
UNIT_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
UNIT_PATH="${UNIT_DIR}/${SERVICE_NAME}"

unit_value() {
  local value="$1"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  printf '"%s"' "$value"
}

render_unit() {
  printf '%s\n' '[Unit]'
  printf '%s\n' 'Description=Poznamkovnik local web server'
  printf '%s\n\n' 'StartLimitIntervalSec=0'
  printf '%s\n' '[Service]'
  printf '%s\n' 'Type=simple'
  printf 'WorkingDirectory=%s\n' "$PROJECT_DIR"
  printf 'ExecStart=%s %s --host %s --port %s --data-dir %s\n' \
    "$(unit_value "$PYTHON_BIN")" \
    "$(unit_value "${PROJECT_DIR}/server.py")" \
    "$(unit_value "$HOST")" \
    "$PORT" \
    "$(unit_value "${PROJECT_DIR}/data")"
  printf '%s\n' 'Environment=PYTHONUNBUFFERED=1'
  printf '%s\n' 'Restart=always'
  printf '%s\n' 'RestartSec=10'
  printf '%s\n' 'TimeoutStopSec=20'
  printf '%s\n\n' 'KillSignal=SIGINT'
  printf '%s\n' '[Install]'
  printf '%s\n' 'WantedBy=default.target'
}

ensure_systemd() {
  if ! command -v systemctl >/dev/null 2>&1; then
    printf '%s\n' 'systemctl nie je k dispozicii.' >&2
    exit 1
  fi
}

warn_if_port_is_in_use() {
  if command -v ss >/dev/null 2>&1 && ss -ltnH "sport = :${PORT}" | grep -q .; then
    printf 'Port %s je uz obsadeny. Sluzba bude cakat, kym sa aktualny server uvolni.\n' "$PORT" >&2
  fi
}

install_service() {
  ensure_systemd
  mkdir -p "$UNIT_DIR"
  local temporary_unit
  temporary_unit="$(mktemp "${UNIT_DIR}/.${SERVICE_NAME}.XXXXXX")"
  render_unit > "$temporary_unit"
  mv "$temporary_unit" "$UNIT_PATH"
  systemctl --user daemon-reload
  warn_if_port_is_in_use
  systemctl --user enable --now "$SERVICE_NAME"
  printf 'Sluzba %s je nainstalovana.\n' "$SERVICE_NAME"
}

uninstall_service() {
  ensure_systemd
  systemctl --user disable --now "$SERVICE_NAME" 2>/dev/null || true
  rm -f "$UNIT_PATH"
  systemctl --user daemon-reload
  printf 'Sluzba %s bola odstranena.\n' "$SERVICE_NAME"
}

usage() {
  printf '%s\n' 'Pouzitie: scripts/poznamkovnik-daemon.sh {install|start|stop|restart|status|logs|print-unit|uninstall}'
}

command_name="${1:-}"
case "$command_name" in
  install)
    install_service
    ;;
  start|stop|restart)
    ensure_systemd
    systemctl --user "$command_name" "$SERVICE_NAME"
    ;;
  status)
    ensure_systemd
    systemctl --user status "$SERVICE_NAME" --no-pager
    ;;
  logs)
    ensure_systemd
    journalctl --user -u "$SERVICE_NAME" -n 100 --no-pager
    ;;
  print-unit)
    render_unit
    ;;
  uninstall)
    uninstall_service
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
