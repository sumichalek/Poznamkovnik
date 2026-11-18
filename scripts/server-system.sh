#!/usr/bin/env bash
# Explicit, separately confirmed administrative steps used by install.sh.
set -euo pipefail
PN_SYSTEM_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ "${1:-}" == --help ]]; then
  printf '%s\n' 'Systémové kroky: packages [--ocr], linger INSTALACNY_KOREN, firewall INSTALACNY_KOREN CIDR, firewall-remove INSTALACNY_KOREN [--plan].' \
    'Pred zmenami vznikne súkromná záloha v /var/backups/. Linger/UFW majú root doklad vlastníctva. DNS sa nemení.'
  exit 0
fi
[[ "${EUID}" == 0 ]] || { printf 'Tento samostatný systémový krok vyžaduje sudo.\n' >&2; exit 1; }
PN_ACTION="${1:-}"
case "$PN_ACTION" in
  packages)
    [[ $# == 1 || ( $# == 2 && "$2" == --ocr ) ]] || exit 2
    command -v apt-get >/dev/null || { printf 'Balíkový krok podporuje systémy s apt-get.\n' >&2; exit 1; }
    [[ -f /etc/debian_version ]] || { printf 'Automatické balíky podporujú Debian/Ubuntu; inak ich priprav ručne.\n' >&2; exit 1; }
    PN_PACKAGES=(git python3-venv)
    if [[ "${2:-}" == --ocr ]]; then
      PN_PACKAGES+=(ocrmypdf tesseract-ocr-slk tesseract-ocr-eng poppler-utils)
    fi ;;
  linger)
    [[ $# == 2 ]] || exit 2
    exec python3 -B "$PN_SYSTEM_DIR/system_changes.py" apply-linger --root "$2" ;;
  firewall)
    [[ $# == 3 ]] || exit 2
    exec python3 -B "$PN_SYSTEM_DIR/system_changes.py" apply-firewall --root "$2" --network "$3" ;;
  firewall-remove)
    [[ $# == 2 || ( $# == 3 && "$3" == --plan ) ]] || exit 2
    PN_REMOVE=(python3 -B "$PN_SYSTEM_DIR/system_changes.py" remove-firewall --root "$2")
    [[ $# == 2 ]] || PN_REMOVE+=(--plan)
    exec "${PN_REMOVE[@]}" ;;
  *) printf 'Neplatný systémový krok.\n' >&2; exit 2 ;;
esac
umask 077
PN_BACKUP="$(mktemp -d /var/backups/poznamkovnik-system-XXXXXXXX)"
printf 'Pôvodné systémové nastavenia: %s\n' "$PN_BACKUP"
case "$PN_ACTION" in
  packages)
    cp -a -- /etc/apt "$PN_BACKUP/"
    dpkg-query -W > "$PN_BACKUP/packages-before.txt"
    apt-get update
    apt-get --simulate install --no-install-recommends "${PN_PACKAGES[@]}"
    printf 'Nasleduje APT s vlastným potvrdením. Skontroluj aj prípadné aktualizácie systémových závislostí.\n'
    apt-get install --no-install-recommends "${PN_PACKAGES[@]}" ;;
esac
