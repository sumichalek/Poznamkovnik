#!/usr/bin/env bash
set -Eeuo pipefail
PN_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PN_PLAN_ONLY=0
case "${1:-}" in
  --help|-h)
    printf '%s\n' 'Použitie: bash scripts/install.sh [--plan]' \
      'Slovenský sprievodca: inštalácia, aktualizácia, stav/diagnostika, obnova a odinštalovanie Poznámkovníka.' \
      '--plan: iba otázky a plán; žiadne sťahovanie, sudo ani zmeny služby.'
    exit 0 ;;
  --plan) PN_PLAN_ONLY=1 ;;
  '') ;;
  *) printf 'Neznámy prepínač. Použi --help.\n' >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { printf 'Priveľa argumentov. Použi --help.\n' >&2; exit 2; }
if (( PN_PLAN_ONLY == 0 )) && { [[ ! -t 0 ]] || [[ ! -t 1 ]]; }; then
  printf 'Sprievodcu spusti osobne v interaktívnom termináli. Na vypísanie plánu môžeš použiť --plan.\n' >&2; exit 2
fi
if (( EUID == 0 && PN_PLAN_ONLY == 0 )); then
  printf 'Spusti sprievodcu pod bežným účtom. Sudo patrí iba samostatne potvrdeným systémovým krokom.\n' >&2; exit 2
fi
if [[ "$(uname -s)" != Linux ]] || ! command -v python3 >/dev/null; then
  printf 'Potrebný je Linux a Python 3.11+. Úvodný návod: docs/private-git-access.md.\n' >&2; exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || {
  printf 'Potrebný je Python 3.11 alebo novší. Systémový Python sa naslepo nenahrádza.\n' >&2; exit 1;
}
trap 'printf "\nKrok zlyhal. Ďalšie kroky sa nevykonajú; už schválené systémové zmeny môžu zostať. Pozri docs/server-operations.md.\n" >&2' ERR
trap 'printf "\nPrerušené používateľom. Skontroluj posledný výpis a stav; už dokončené kroky sa automaticky nemažú.\n" >&2; exit 130' INT TERM

pn_support() { python3 -B "$PN_SCRIPT_DIR/install_support.py" "$@"; }
pn_ask() {
  local variable="$1" prompt="$2" default="$3" value
  printf '%s [%s]: ' "$prompt" "$default"
  IFS= read -r value || { printf '\nZrušené.\n'; exit 130; }
  printf -v "$variable" '%s' "${value:-$default}"
}
pn_confirm() {
  local answer
  while true; do
    printf '%s [a/N]: ' "$1"
    IFS= read -r answer || return 1
    case "${answer,,}" in
      a|ano|áno) return 0 ;;
      ''|n|nie) return 1 ;;
      *) printf 'Odpovedz a (áno) alebo n (nie). Enter znamená nie.\n' ;;
    esac
  done
}
pn_command() { printf '  '; printf '%q ' "$@"; printf '\n'; }
pn_choice() {
  while true; do
    pn_ask "$1" "$2" "$3"
    [[ "${!1}" =~ $4 ]] && return 0
    printf 'Neplatná voľba, skús to znova.\n'
  done
}
pn_root() {
  while true; do
    pn_ask PN_ROOT 'Inštalačný priečinok' "$1"
    if PN_NORMALIZED="$(pn_support validate-root "$PN_ROOT")"; then
      PN_ROOT="$PN_NORMALIZED"; return 0
    fi
    printf 'Vyber bezpečný samostatný priečinok.\n'
  done
}
pn_port() {
  while true; do
    pn_ask PN_PORT 'Port aplikácie' "$1"
    if [[ "$PN_PORT" =~ ^[0-9]{1,5}$ ]] && (( 10#$PN_PORT >= 1 && 10#$PN_PORT <= 65535 )); then
      PN_PORT=$((10#$PN_PORT)); return 0
    fi
    printf 'Port musí byť číslo od 1 do 65535.\n'
  done
}

PN_DEFAULT_ROOT="$(pn_support default-root "$PN_SCRIPT_DIR")"
PN_DEFAULT_SERVICE=poznamkovnik.service
PN_DEFAULT_PORT=1111
printf '\nPoznámkovník – inštalácia a správa\nPočítač: %s\nPoužívateľ: %s\n' "$(hostname)" "$(id -un)"
pn_support overview "$PN_DEFAULT_ROOT"
printf '\n%s\n' '1) Nainštalovať Poznámkovník alebo samostatnú skúšobnú inštanciu' \
  '2) Aktualizovať existujúcu inštaláciu' '3) Zobraziť stav a diagnostiku (bez zmien)' \
  '4) Obnoviť Poznámkovník zo zálohy (dáta, nastavenia a vydanie, nie celý Linux)' \
  '5) Odinštalovať Poznámkovník (predvolene zachovať dáta a zálohy)' '0) Skončiť'
pn_choice PN_ACTION 'Voľba' '0' '^[0-5]$'
[[ "$PN_ACTION" == 0 ]] && exit 0
if [[ "$PN_ACTION" == 1 && -f "$PN_DEFAULT_ROOT/shared/server.json" ]]; then
  printf 'Inštalácia už existuje. Pre novú skúšku navrhujem iný priečinok, službu a port.\n'
  PN_DEFAULT_ROOT="${PN_DEFAULT_ROOT}-skuska"
  PN_DEFAULT_SERVICE=poznamkovnik-skuska.service
  PN_DEFAULT_PORT=1112
fi
while true; do
  pn_root "$PN_DEFAULT_ROOT"
  if [[ "$PN_ACTION" == 1 && -e "$PN_ROOT/shared/server.json" ]]; then
    printf 'Tu už je inštalácia. Nič sa neprepíše; zvoľ iný priečinok alebo skonči cez Ctrl+C.\n'
  elif [[ "$PN_ACTION" == 2 || "$PN_ACTION" == 4 || "$PN_ACTION" == 5 ]] && [[ ! -f "$PN_ROOT/shared/server.json" ]]; then
    printf 'Tu nie je konfigurácia inštalácie. Vyber jej skutočný priečinok.\n'
  else
    break
  fi
done
if [[ "$PN_ACTION" == 5 ]]; then
  PN_UNINSTALL=(bash "$PN_SCRIPT_DIR/uninstall.sh" --root "$PN_ROOT")
  (( PN_PLAN_ONLY == 0 )) || PN_UNINSTALL+=(--plan)
  exec "${PN_UNINSTALL[@]}"
fi
if [[ "$PN_ACTION" == 3 ]]; then
  pn_support diagnose "$PN_ROOT"
  if (( PN_PLAN_ONLY == 0 )) && pn_confirm 'Overiť aj sieťové čítanie Git repozitára? (Bez fetch, push alebo zmeny DNS.)'; then
    if [[ -d "$PN_ROOT/repository" ]]; then
      PN_REPOSITORY="$(pn_support repository "$PN_ROOT/repository")"
    else
      PN_REPOSITORY="$(pn_support default-repository "$PN_SCRIPT_DIR/..")"
    fi
    pn_support check-git "$PN_REPOSITORY"
  fi
  exit 0
fi

PN_COMMAND=(python3 "$PN_SCRIPT_DIR/server_manage.py" --root "$PN_ROOT")
PN_OCR=0
PN_AUTOSTART=0
PN_HOST=127.0.0.1
PN_PORT="$PN_DEFAULT_PORT"
PN_SERVICE="$PN_DEFAULT_SERVICE"
PN_REPOSITORY="$(pn_support default-repository "$PN_SCRIPT_DIR/..")"
if [[ "$PN_ACTION" == 2 || "$PN_ACTION" == 4 ]]; then
  PN_CONFIG="$(pn_support config "$PN_ROOT")"
  mapfile -t PN_EXISTING <<< "$PN_CONFIG"
  PN_HOST="${PN_EXISTING[0]}"; PN_PORT="${PN_EXISTING[1]}"; PN_SERVICE="${PN_EXISTING[2]}"
  if [[ "$PN_ACTION" == 2 ]]; then PN_REPOSITORY="$(pn_support repository "$PN_ROOT/repository")"; fi
fi

if [[ "$PN_ACTION" == 4 ]]; then
  PN_ROWS="$(pn_support backups "$PN_ROOT")"
  if [[ -z "$PN_ROWS" ]]; then
    printf 'V tejto inštalácii nie sú zálohy so značkou overenia. Nič sa nezmenilo.\n'; exit 0
  fi
  mapfile -t PN_BACKUPS <<< "$PN_ROWS"
  printf '\nZálohy (pred obnovou sa znovu overí celý obsah):\n'
  for PN_INDEX in "${!PN_BACKUPS[@]}"; do
    printf '%s) %s\n' "$((PN_INDEX + 1))" "${PN_BACKUPS[$PN_INDEX]}"
  done
  printf '0) Skončiť bez obnovy\n'
  while true; do
    pn_choice PN_SELECTION 'Číslo zálohy' '0' '^[0-9]{1,5}$'
    PN_SELECTION=$((10#$PN_SELECTION))
    (( PN_SELECTION == 0 )) && exit 0
    (( PN_SELECTION <= ${#PN_BACKUPS[@]} )) && break
    printf 'Vyber číslo z uvedeného zoznamu.\n'
  done
  IFS=$'\t' read -r PN_BACKUP_NAME PN_BACKUP_TIME PN_PREVIOUS <<< "${PN_BACKUPS[$((PN_SELECTION - 1))]}"
  PN_BACKUP="$PN_ROOT/shared/update-backups/$PN_BACKUP_NAME"
  PN_ACTION_LABEL='Obnova Poznámkovníka zo zálohy'
  PN_TARGET="${PN_PREVIOUS} (dáta z ${PN_BACKUP_TIME})"
  PN_COMMAND+=(recover "$PN_BACKUP")
  printf '\nObnova vráti dáta aj nastavenia do času zálohy. Novšie zápisy sa nezlúčia.\nNajprv vznikne nová overená záloha aktuálneho stavu. DNS, Python ani Pi-hole sa neobnovujú.\n'
else
  pn_choice PN_TAG 'Git tag vydania (musí byť zverejnený)' "v$(tr -d '\r\n' < "$PN_SCRIPT_DIR/../VERSION")" '^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$'
  PN_TARGET="$PN_TAG"
  if [[ "$PN_ACTION" == 1 ]]; then
    PN_ACTION_LABEL='Nová inštalácia'
    pn_port "$PN_PORT"
    printf '%s\n' '1) Prístup iba z tohto počítača (aj pre proxy alebo SSH tunel)' '2) Prístup z domácej siete (všetky IPv4 rozhrania; firewall nastavíme samostatne)'
    pn_choice PN_NETWORK 'Sieťový prístup' '1' '^[12]$'
    [[ "$PN_NETWORK" == 1 ]] || PN_HOST=0.0.0.0
    if pn_confirm 'Povoliť automatické spúšťanie? Pre beh bez prihlásenia potom samostatne potvrdíš linger.'; then PN_AUTOSTART=1; fi
    if pn_confirm 'Pripraviť aj OCRmyPDF, slovenské/anglické OCR a PDF náhľady?'; then PN_OCR=1; fi
    if pn_confirm 'Otvoriť rozšírené nastavenia (Git adresa a názov služby)?'; then
      while true; do
        pn_ask PN_REPOSITORY 'Git repozitár (bez hesla/tokenu v adrese)' "$PN_REPOSITORY"
        if pn_support validate-repository "$PN_REPOSITORY"; then break; fi
      done
      pn_choice PN_SERVICE 'Názov používateľskej systemd služby' "$PN_SERVICE" '^[A-Za-z0-9_-]+\.service$'
    fi
    if [[ -d "$PN_ROOT/shared/data" ]] && [[ -n "$(find "$PN_ROOT/shared/data" -mindepth 1 -print -quit)" ]]; then
      printf 'V cieli už sú dáta. Pôvodná aplikácia musí byť zastavená; dve inštancie ich nesmú používať naraz.\n'
      pn_confirm 'Zachovať a použiť existujúce dáta? Pred prvým spustením sa zálohujú.' || exit 0
    fi
    PN_COMMAND+=(init "$PN_TAG" --repository "$PN_REPOSITORY" --host "$PN_HOST" --port "$PN_PORT" --service "$PN_SERVICE")
    (( PN_AUTOSTART == 1 )) || PN_COMMAND+=(--no-autostart)
  else
    PN_ACTION_LABEL='Aktualizácia'
    PN_COMMAND+=(update "$PN_TAG")
  fi
fi

printf '\nPlán\n  Počítač: %s\n  Operácia: %s\n  Cieľový stav: %s\n  Kód a vydania: %s/releases\n  Dáta a účty: %s/shared/data\n  Zálohy: %s/shared/update-backups\n  Služba: %s\n  Adresa: %s, port %s\n' \
  "$(hostname)" "$PN_ACTION_LABEL" "$PN_TARGET" "$PN_ROOT" "$PN_ROOT" "$PN_ROOT" "$PN_SERVICE" "$PN_HOST" "$PN_PORT"
if [[ "$PN_ACTION" != 4 ]]; then
  printf '  Git repozitár: %s\n' "$PN_REPOSITORY"
  printf '  Privátny Git vyžaduje tvoje oprávnenie na čítanie; nenastavuje sa prístup agenta na server.\n'
fi
if [[ "$PN_ACTION" == 1 ]]; then
  PN_AUTOSTART_LABEL=nie; PN_OCR_LABEL=nie
  (( PN_AUTOSTART == 0 )) || PN_AUTOSTART_LABEL=áno
  (( PN_OCR == 0 )) || PN_OCR_LABEL=áno
  printf '  Automatické spúšťanie: %s\n  Voliteľné OCR nástroje: %s\n' "$PN_AUTOSTART_LABEL" "$PN_OCR_LABEL"
  printf '  Systémové balíky: podľa kontroly Git/Python venv, prípadne OCR. Pred sudo uvidíš konkrétny návrh.\n'
fi
printf '%s\n' '  Pred aktiváciou vždy vznikne nová overená záloha dát aj nastavení.' \
  '  Prípravu, zastavenie so zálohou aj aktiváciu potvrdíš osobitne.' \
  '  DNS, Pi-hole ani nastavenia routera sa nemenia. Dáta sa neposielajú do Gitu.' 'Príkaz správy aplikácie:'
pn_command "${PN_COMMAND[@]}"
if (( PN_PLAN_ONLY == 1 )); then
  printf '\nIba plán: nič sa nesťahovalo, služba ani systémové nastavenia sa nezmenili. Dostupnosť Gitu, miesto a port sa overia pred vykonaním.\n'; exit 0
fi
pn_confirm 'Súhlasíš s týmto plánom a chceš pokračovať ku kontrolám a potvrdzovaným krokom?' || exit 0

PN_CHECK=(preflight "$PN_ROOT" --host "$PN_HOST" --port "$PN_PORT" --service "$PN_SERVICE")
[[ "$PN_ACTION" != 1 ]] || PN_CHECK+=(--new)
pn_support "${PN_CHECK[@]}"
command -v systemctl >/dev/null && systemctl --user show --property=Version >/dev/null || {
  printf 'Používateľský systemd nie je dostupný. Spusti sprievodcu v riadnej SSH relácii, nie cez sudo. Aplikácia sa nemenila.\n' >&2; exit 1;
}
PN_MISSING=()
command -v git >/dev/null || PN_MISSING+=(git)
python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || PN_MISSING+=(python3-venv)
if (( PN_OCR == 1 )); then
  command -v ocrmypdf >/dev/null || PN_MISSING+=(ocrmypdf)
  command -v pdftoppm >/dev/null || PN_MISSING+=(poppler-utils)
  if command -v tesseract >/dev/null; then
    tesseract --list-langs 2>/dev/null | grep -qx slk || PN_MISSING+=(tesseract-ocr-slk)
    tesseract --list-langs 2>/dev/null | grep -qx eng || PN_MISSING+=(tesseract-ocr-eng)
  else
    PN_MISSING+=(tesseract-ocr-slk tesseract-ocr-eng)
  fi
fi
if [[ "$PN_ACTION" != 4 ]] && command -v git >/dev/null; then pn_support check-git "$PN_REPOSITORY" --tag "$PN_TAG"; fi
if (( ${#PN_MISSING[@]} > 0 )); then
  if [[ "$PN_ACTION" != 1 ]]; then
    printf 'Chýbajú systémové predpoklady: %s. Priprav ich osobitne; služba sa nemenila.\n' "${PN_MISSING[*]}" >&2; exit 1
  fi
  PN_SYSTEM=(sudo bash "$PN_SCRIPT_DIR/server-system.sh" packages)
  (( PN_OCR == 0 )) || PN_SYSTEM+=(--ocr)
  printf 'Chýbajúce nástroje/balíky: %s\nSamostatný administrátorský krok:\n' "${PN_MISSING[*]}"
  pn_command "${PN_SYSTEM[@]}"
  printf 'Najprv sa zálohujú systémové nastavenia a ukáže návrh APT. DNS a Pi-hole sa nemenia.\n'
  pn_confirm 'Spustiť tento systémový krok cez sudo?' || exit 0
  "${PN_SYSTEM[@]}"
  [[ "$PN_ACTION" == 4 ]] || pn_support check-git "$PN_REPOSITORY" --tag "$PN_TAG"
fi
PN_RESULT=0
"${PN_COMMAND[@]}" || PN_RESULT=$?
if (( PN_RESULT == 130 )); then
  printf '\nOperácia bola zrušená. Ďalšie systémové kroky sa nespustia. Pripravené súbory alebo schválené balíky môžu zostať.\n'; exit 0
elif (( PN_RESULT != 0 )); then
  printf 'Správa aplikácie zlyhala. Pozri posledný výpis a docs/server-operations.md; nič nemaž ani neopakuj naslepo.\n' >&2; exit "$PN_RESULT"
fi

if [[ "$PN_ACTION" == 1 ]] && (( PN_AUTOSTART == 1 )); then
  PN_LINGER="$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null || true)"
  if [[ "$PN_LINGER" != yes ]]; then
    printf 'Beh aj po odhlásení a pri štarte servera vyžaduje linger. Týka sa používateľského správcu služieb, nielen tejto aplikácie.\n'
    pn_command sudo bash "$PN_SCRIPT_DIR/server-system.sh" linger "$PN_ROOT"
    if pn_confirm 'Povoliť tento beh cez sudo?'; then
      sudo bash "$PN_SCRIPT_DIR/server-system.sh" linger "$PN_ROOT"
    else
      printf 'Automatické spúšťanie pri relácii je povolené, ale beh bez prihlásenia nebol zabezpečený.\n'
    fi
  fi
fi
if [[ "$PN_ACTION" == 1 && "$PN_HOST" == 0.0.0.0 ]] && [[ -x /usr/sbin/ufw ]]; then
  if systemctl is-active --quiet ufw; then
    printf 'UFW je aktívny. Pravidlo sa môže pridať samostatne iba pre vybranú IPv4 sieť.\n'
    if pn_confirm 'Chceš pripraviť pravidlo pre túto aplikáciu?'; then
      while true; do
        pn_ask PN_CIDR 'Zdrojová sieť v CIDR, napríklad 192.168.0.0/24' ''
        if python3 -c 'import ipaddress, sys; value=ipaddress.ip_network(sys.argv[1]); sys.exit(0 if value.version == 4 and value.prefixlen > 0 else 1)' "$PN_CIDR" 2>/dev/null; then break; fi
        printf 'Zadaj platnú konkrétnu IPv4 sieť, nie celý internet (0.0.0.0/0).\n'
      done
      pn_command sudo bash "$PN_SCRIPT_DIR/server-system.sh" firewall "$PN_ROOT" "$PN_CIDR"
      printf 'Pred zmenou sa zálohuje UFW. Ostatné pravidlá vrátane Pi-hole sa nemenia.\n'
      if pn_confirm 'Pridať toto pravidlo cez sudo?'; then sudo bash "$PN_SCRIPT_DIR/server-system.sh" firewall "$PN_ROOT" "$PN_CIDR"; fi
    fi
  fi
fi
printf '\nHotovo. Výsledok:\n'
pn_support diagnose "$PN_ROOT"
PN_NEXT="$PN_SCRIPT_DIR/install.sh"
[[ ! -f "$PN_ROOT/current/scripts/install.sh" ]] || PN_NEXT="$PN_ROOT/current/scripts/install.sh"
printf '\nSprievodcu znovu otvoríš:\n'
pn_command bash "$PN_NEXT"
if [[ -f "$PN_ROOT/current/server.py" ]]; then
  printf 'Účet vytváraš v prehliadači; predvolené prihlasovacie heslo sa nevytvára. Ak už účty existujú, zostávajú zachované.\n'
else
  printf 'Aktívne vydanie teraz nie je dostupné. Po obnove stavu pred prvou inštaláciou použiješ Aktualizáciu na vybrané vydanie; služba zatiaľ nebeží.\n'
fi
printf 'Návod na samostatnú obsluhu: docs/server-operations.md.\n'
