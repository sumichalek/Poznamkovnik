#!/usr/bin/env python3
"""Read-only checks and presentation for the interactive Bash installer."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys

# A plan must not create even an import cache in the bootstrap checkout.
sys.dont_write_bytecode = True
if __package__:
    from .server_manage import DEFAULT_REPOSITORY, Deployment, DeploymentError, TAG_PATTERN, validate_repository
else:
    from server_manage import DEFAULT_REPOSITORY, Deployment, DeploymentError, TAG_PATTERN, validate_repository


def command(*args: str, timeout: float = 5) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})


def safe_root(raw: str) -> Path:
    path = Path(raw).expanduser().absolute()
    Deployment(path)  # The same minimum restrictions as the actual manager.
    if path.resolve() != path or any(parent.is_symlink() for parent in (path, *path.parents)):
        raise DeploymentError("Inštalačná cesta ani jej nadradené priečinky nesmú byť symbolické odkazy.")
    if path.exists() and not path.is_dir():
        raise DeploymentError("Inštalačná cesta musí byť priečinok.")
    if any(ord(character) < 32 for character in str(path)):
        raise DeploymentError("Cesta nesmie obsahovať riadiace znaky.")
    return path


def default_root(script_dir: Path) -> Path:
    release = script_dir.resolve().parent
    root = release.parent.parent
    if release.parent.name == "releases" and (root / "shared/server.json").is_file():
        return root
    return Path.home() / "apps/poznamkovnik"


def default_repository(project: Path) -> str:
    try:
        result = command("git", "-C", str(project), "remote", "get-url", "origin")
        if result.returncode == 0:
            return validate_repository(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, DeploymentError, ValueError):
        pass
    return DEFAULT_REPOSITORY


def repository_url(project: Path) -> str:
    result = command("git", "-C", str(project), "remote", "get-url", "origin")
    if result.returncode:
        raise DeploymentError("Nepodarilo sa načítať origin tejto inštalácie. Skontroluj repository/; adresa sa nenahrádza automaticky.")
    return validate_repository(result.stdout.strip())


def version(root: Path) -> str:
    path = root / "current/VERSION"
    value = path.read_text().strip() if path.is_file() else ""
    return value if re.fullmatch(TAG_PATTERN, "v" + value) else "žiadne aktívne vydanie"


def preflight(root: Path, host: str, port: int, service: str, *, new: bool) -> None:
    safe_root(str(root))
    if new:
        if (root / "shared/server.json").exists():
            raise DeploymentError("Inštalácia už existuje. Vyber aktualizáciu alebo iný priečinok.")
        if root.exists() and {item.name for item in root.iterdir()} - {"repository", "releases", "shared", ".update.lock"}:
            raise DeploymentError("Cieľ obsahuje neznáme súbory. Použi samostatný prázdny priečinok.")
        unit = Deployment(root).unit_dir / service
        if unit.exists() or unit.is_symlink() or unit.with_name(service + ".d").exists():
            raise DeploymentError("Zvolená služba alebo jej doplnky už existujú. Použi iný názov.")
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as listener:
                listener.bind((host, port))
        except OSError as error:
            raise DeploymentError(f"Port {port} na adrese {host} nie je dostupný. Zvoľ iný port; existujúci proces sa nevypne.") from error
    parent = root
    while not parent.exists():
        parent = parent.parent
    if not os.access(parent, os.W_OK | os.X_OK):
        raise DeploymentError("Do cieľového priečinka nemáš právo zapisovať.")
    free = shutil.disk_usage(parent).free
    print(f"Voľné miesto na cieľovom disku: {free / 1024 ** 3:.2f} GiB.")
    if free < 256 * 1024 ** 2:
        raise DeploymentError("Na disku je menej než 256 MiB; najprv uvoľni miesto aj pre úplnú zálohu.")
    print("Cesta a oprávnenia: OK. " + ("Port je momentálne voľný." if new else "Existujúci port sa zachováva."))
    print("Veľkosť úplnej zálohy závisí od dát; pri nedostatku miesta sa aktivácia nevykoná.")


def check_git(repository: str, tag: str | None = None) -> None:
    validate_repository(repository)
    if tag and not re.fullmatch(TAG_PATTERN, tag):
        raise DeploymentError("Neplatný Git tag.")
    args = ["git", "ls-remote", "--exit-code", "--tags", "--", repository]
    if tag:
        args.append("refs/tags/" + tag)
    try:
        result = command(*args, timeout=30)
    except subprocess.TimeoutExpired as error:
        raise DeploymentError("Git neodpovedal do 30 sekúnd. Skontroluj sieť, DNS/Pi-hole a SSH pripojenie; nič sa nemenilo.") from error
    if result.returncode == 2 and tag:
        raise DeploymentError("Vybraný Git tag sa nenašiel. Najprv musí byť otestovaný a zverejnený.")
    if result.returncode:
        # Do not echo authentication diagnostics: helpers may include credentials.
        raise DeploymentError("Čítanie Gitu zlyhalo. Skontroluj DNS/Pi-hole, SSH kľúč, dôveryhodnosť hostiteľa a prístup k privátnemu repozitáru. Návod: docs/private-git-access.md. DNS ani SSH nastavenia sa automaticky nemenia.")
    print("Čítanie privátneho Gitu" + (f" a dostupnosť {tag}" if tag else "") + ": OK.")
    print("Read-only oprávnenie nastavuješ na GitHube; kontrola neskúša push ani nepotvrdzuje zákaz zápisu.")


def backup_rows(root: Path) -> list[tuple[str, str, str]]:
    rows = []
    directory = root / "shared/update-backups"
    if directory.is_symlink():
        raise DeploymentError("Priečinok záloh nesmie byť odkaz.")
    for path in sorted(directory.glob("before-*"), reverse=True):
        if path.is_symlink() or not path.is_dir() or not re.fullmatch(r"before-[A-Za-z0-9_-]+", path.name):
            continue
        if not (path / "VERIFIED").is_file():
            continue
        try:
            manifest = json.loads((path / "manifest.json").read_text())
            when = str(manifest["time"])
            previous = Path(manifest["previous"]).name if manifest["previous"] else "pred prvou inštaláciou"
            if any(ord(char) < 32 for char in when + previous):
                continue
            rows.append((path.name, when, previous))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return rows


def diagnostics(root: Path) -> None:
    print(f"Počítač: {socket.gethostname()}\nInštalácia: {root}\nVerzia: {version(root)}")
    print(f"Python: {sys.version.split()[0]}")
    for name in ("git", "systemctl", "ocrmypdf", "tesseract", "pdftoppm"):
        print(f"{name}: {'dostupný' if shutil.which(name) else 'chýba'}")
    pihole = Path("/etc/pihole").exists() or shutil.which("pihole") is not None
    print("Pi-hole: " + ("zistená inštalácia" if pihole else "lokálna inštalácia nezistená (môže byť v kontajneri alebo na inom zariadení)"))
    print("DNS sa nemení. Pri problémoch skontroluj systémový resolver, Pi-hole a jeho upstream; nezadávaj náhodný náhradný DNS.")
    try:
        result = command("systemctl", "--user", "show", "--property=Version")
        print("Používateľský systemd: " + ("dostupný" if result.returncode == 0 else "nedostupný; spusti v bežnej SSH relácii"))
    except (OSError, subprocess.TimeoutExpired):
        print("Používateľský systemd: nedostupný")
    if (root / "shared/server.json").is_file():
        deployment = Deployment(root)
        config = deployment.config()
        print(f"Služba: {config['service']}\nDáta a účty: {deployment.data}\nZálohy: {deployment.backups}")
        try:
            state = command("systemctl", "--user", "show", config["service"], "--property=ActiveState", "--value")
            print("Stav služby: " + (state.stdout.strip() if state.returncode == 0 else "nezistený"))
            if state.returncode == 0 and state.stdout.strip() == "active" and deployment.current() is not None:
                try:
                    deployment.health_timeout = 2
                    deployment.health(deployment.current(), config)
                    print("HTTP kontrola vydania, databázy a úložiska: OK")
                except (DeploymentError, OSError, ValueError):
                    print("HTTP kontrola: zlyhala; samotný stav active nepotvrdzuje funkčnú aplikáciu.")
        except (OSError, subprocess.TimeoutExpired):
            print("Stav služby: nezistený")
        local_host = "127.0.0.1" if config["host"] == "0.0.0.0" else config["host"]
        if ":" in local_host:
            local_host = f"[{local_host}]"
        print(f"Adresa na serveri: http://{local_host}:{config['port']}")
        if config["host"] == "0.0.0.0":
            print(f"Adresa pre LAN: http://{socket.gethostname()}:{config['port']} (alebo IP servera; dostupnosť z iného počítača treba overiť)")
        if deployment.state_path.is_file():
            state = json.loads(deployment.state_path.read_text())
            print(f"Posledná operácia: {state.get('status', 'nezistená')}")
        print(f"Zálohy so značkou overenia: {len(backup_rows(root))}; pred obnovou sa znova overí ich celý obsah.")
    else:
        print("V tomto priečinku nie je nakonfigurovaná inštalácia.")
    print("Táto diagnostika nič nemení, nekontaktuje Git ani neodosiela výpisy. Pred zdieľaním výpis skontroluj.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("default-root", "default-repository", "repository", "validate-root", "validate-repository", "overview", "config", "backups", "diagnose"):
        sub.add_parser(name).add_argument("value")
    check = sub.add_parser("preflight")
    check.add_argument("value")
    check.add_argument("--host", required=True)
    check.add_argument("--port", type=int, required=True)
    check.add_argument("--service", required=True)
    check.add_argument("--new", action="store_true")
    git = sub.add_parser("check-git")
    git.add_argument("value")
    git.add_argument("--tag")
    args = parser.parse_args()
    if args.action == "default-root":
        print(default_root(Path(args.value)))
    elif args.action == "default-repository":
        print(default_repository(Path(args.value)))
    elif args.action == "repository":
        print(repository_url(Path(args.value)))
    elif args.action == "validate-root":
        print(safe_root(args.value))
    elif args.action == "validate-repository":
        validate_repository(args.value)
    elif args.action == "check-git":
        check_git(args.value, args.tag)
    else:
        root = safe_root(args.value)
        if args.action == "overview":
            print("Inštalácia: " + (str(root) if (root / "shared/server.json").is_file() else "nenájdená"))
            print("Verzia: " + version(root))
        elif args.action == "config":
            config = Deployment(root).config()
            print(config["host"]); print(config["port"]); print(config["service"])
        elif args.action == "backups":
            for row in backup_rows(root):
                print("\t".join(row))
        elif args.action == "preflight":
            Deployment.validate_config({"host": args.host, "port": args.port, "service": args.service})
            preflight(root, args.host, args.port, args.service, new=args.new)
        elif args.action == "diagnose":
            diagnostics(root)


if __name__ == "__main__":
    try:
        main()
    except (DeploymentError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print(f"Kontrola zlyhala: {error}", file=sys.stderr)
        raise SystemExit(1)
