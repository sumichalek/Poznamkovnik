#!/usr/bin/env python3
"""Conservative removal of one managed installation; data is retained by default."""
from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
if __package__:
    from .install_support import default_root, safe_root
    from .server_manage import Deployment, DeploymentCancelled, DeploymentError, MARKER, exists, read_json, run, validate_repository, write_json
else:
    from install_support import default_root, safe_root
    from server_manage import Deployment, DeploymentCancelled, DeploymentError, MARKER, exists, read_json, run, validate_repository, write_json


ROOT_ENTRIES = {"repository", "releases", "current", "shared", ".update.lock"}


def check_removal_tree(path: Path) -> None:
    """Do not traverse mounts, even same-filesystem bind mounts; unlink symlinks only."""
    mounts = set()
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        if len(fields) >= 5:
            decoded = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), fields[4])
            mounts.add(Path(decoded))
    if any(point == path or path in point.parents for point in mounts):
        raise DeploymentError(f"V odstraňovanom priečinku je pripojený súborový systém: {path}. Nič sa neodstráni.")
    if path.is_symlink() or not path.is_dir():
        return
    for directory, directories, files in os.walk(path, followlinks=False):
        for name in directories + files:
            item = Path(directory) / name
            info = item.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
                raise DeploymentError(f"Nepodporovaný špeciálny súbor: {item}")


class Uninstaller:
    def __init__(self, root: Path, *, service=None, unit_dir: Path | None = None, approval=None):
        self.root = safe_root(str(root))
        self.deployment = Deployment(self.root, service=service, unit_dir=unit_dir)
        self.approval = approval
        self.journal = self.deployment.shared / "uninstall-state.json"

    def plan(self, *, delete_data: bool = False) -> dict:
        deployment = self.deployment
        safe_root(str(self.root))
        if not self.root.is_dir() or self.root.stat().st_uid != os.getuid():
            raise DeploymentError("Inštalácia neexistuje alebo nepatrí aktuálnemu používateľovi.")
        if {item.name for item in self.root.iterdir()} - ROOT_ENTRIES:
            raise DeploymentError("Koreň obsahuje neznáme súbory. Najprv ich skontroluj alebo premiestni; nič sa neodstráni.")
        for path in (deployment.shared, deployment.config_path, self.journal, deployment.state_path,
                     self.root / ".update.lock", deployment.repository, deployment.releases):
            if path.is_symlink() or path.resolve() != path:
                raise DeploymentError(f"Spravovaná cesta nesmie byť odkaz: {path}")
        config = deployment.config()
        identity = config.get("installation_id")
        if identity is not None and (not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity)
                                     or config.get("installation_root") != str(self.root)):
            raise DeploymentError("Identifikátor inštalácie alebo uložený koreň nesúhlasí.")
        unit = deployment.unit_dir / config["service"]
        if unit.is_symlink() or unit.resolve() != unit:
            raise DeploymentError("Súbor služby ani jeho nadradený priečinok nesmie byť odkaz.")
        if exists(unit.with_name(config["service"] + ".d")):
            raise DeploymentError("Služba má dodatočné doplnky. Najprv ich osobne skontroluj a bezpečne odlož; odinštalátor ich nemaže.")
        if unit.exists():
            text = unit.read_text()
            if MARKER not in text or f"# Deployment root: {self.root}\n" not in text:
                raise DeploymentError("Služba nepatrí tejto Git inštalácii. Nič sa nezastaví ani neodstráni.")
            if "# Installation ID:" in text and f"# Installation ID: {identity}\n" not in text:
                raise DeploymentError("Služba má iný identifikátor inštalácie.")
        elif not identity:
            if not self.journal.is_file() or read_json(self.journal).get("root") != str(self.root):
                raise DeploymentError("Stará inštalácia nemá jednotku ani identifikátor; vlastníctvo nemožno bezpečne preukázať.")
        service = deployment.service(config)
        if deployment.service_override is None:
            fragment = service.command("show", "--property=FragmentPath", "--value")
            if fragment and Path(fragment) != unit:
                raise DeploymentError("Systemd má pod týmto názvom inú službu. Nič sa nezastaví.")
        if not unit.exists() and service.active():
            raise DeploymentError("Služba beží bez očakávanej jednotky. Najprv prever jej vlastníctvo.")
        pointer = self.root / "current"
        if exists(pointer) and (not pointer.is_symlink() or pointer.resolve().parent != deployment.releases):
            raise DeploymentError("current neukazuje na vydanie tejto inštalácie.")
        for release in deployment.releases.iterdir() if deployment.releases.is_dir() else []:
            if release.is_dir() and not release.is_symlink() and (release / ".git").exists():
                checked = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(release),
                                          "status", "--porcelain", "--untracked-files=all"],
                                         env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}, text=True, capture_output=True)
                if checked.returncode or checked.stdout.strip():
                    raise DeploymentError(f"Vydanie {release.name} má lokálne zmeny alebo neoveriteľný Git. Najprv zmeny odlož mimo inštalácie; kód sa nemaže.")
        # Retained data must not depend on a path that is about to disappear.
        if not delete_data:
            for directory, directories, files in os.walk(deployment.shared, followlinks=False):
                for name in directories + files:
                    item = Path(directory) / name
                    if item.is_symlink():
                        target = item.resolve()
                        if any(target == removed or removed in target.parents
                               for removed in (deployment.releases, deployment.repository)):
                            raise DeploymentError(f"shared/ obsahuje odkaz na odstraňovaný kód; najprv prever jeho cieľ: {item}")
        check_removal_tree(self.root)
        repository = config.get("repository")
        if repository is None and deployment.repository.is_dir():
            repository = run("git", "-C", str(deployment.repository), "remote", "get-url", "origin")
        if repository is not None:
            validate_repository(repository, allow_local=True)
        if not delete_data and not repository:
            raise DeploymentError("Chýba zdroj Gitu potrebný na opätovnú inštaláciu. Najprv doplň bezpečnú adresu repository do server.json.")
        lock = self.root / ".update.lock"
        if not lock.is_file() or lock.stat().st_nlink != 1:
            raise DeploymentError("Chýba bezpečný zámok inštalácie. Nič sa nemení.")
        return {"root": str(self.root), "service": config["service"], "unit": str(unit),
                "delete_data": delete_data, "repository": repository, "installation_id": identity,
                "remove": [str(pointer), str(deployment.releases), str(deployment.repository)],
                "retain": [] if delete_data else [str(deployment.shared)], "config": config}

    @staticmethod
    def print_plan(plan: dict) -> None:
        print("\nPlán odinštalovania Poznámkovníka")
        print(f"  Koreň: {plan['root']}\n  Zastaviť a odobrať službu: {plan['service']}\n  Jednotka: {plan['unit']}")
        for path in plan["remove"]:
            print(f"  Odstrániť kód: {path}")
        if plan["delete_data"]:
            print(f"  NATRVALO odstrániť celý koreň {plan['root']}, vrátane účtov, dát, záloh a recovery-*.")
            print("  Ide o nezvratné vymazanie; nová záloha sa pri tejto voľbe nevytvára.")
        else:
            print(f"  ZACHOVAŤ celý {plan['root']}/shared/ (dáta, účty, zálohy, konfiguráciu a recovery-*).")
        print("  Systémové zmeny: iba samostatne potvrdené kroky s koreňovým dokladom vlastníctva.")
        print("  Spoločné balíky, SSH kľúče, externé nastavenia, DNS, Pi-hole a router zostávajú bez zmien.")
        print("  Pomocný bootstrap checkout mimo tohto koreňa sa nemaže; nechaj si ho na obnovu.")

    def uninstall(self, *, delete_data: bool = False, system_cleanup=None) -> dict:
        plan = self.plan(delete_data=delete_data)
        if self.approval is not None and not self.approval(plan):
            raise DeploymentCancelled("Odinštalovanie bolo zrušené bez zmien.")
        descriptor = os.open(self.root / ".update.lock", os.O_RDWR | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "r+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise DeploymentError("Prebieha iná operácia. Odinštalovanie sa nespustilo.") from error
            # Revalidate after confirmation and after acquiring the shared lock.
            plan = self.plan(delete_data=delete_data)
            config = plan["config"]
            service = self.deployment.service(config)
            progress = {"root": str(self.root), "service": config["service"], "delete_data": delete_data,
                        "installation_id": plan["installation_id"], "status": "started", "removed": []}
            write_json(self.journal, progress)
            self.deployment.state("uninstalling")
            try:
                service.stop()
                if service.active():
                    raise DeploymentError("Služba sa nezastavila; súbory sa nesmú odstrániť.")
                unit = Path(plan["unit"])
                if unit.exists():
                    service.disable()
                    unit.unlink()
                    progress["removed"].append(str(unit))
                service.reload()
                progress["status"] = "service_removed"
                write_json(self.journal, progress)
                if system_cleanup is not None:
                    system_cleanup(plan)
                checked = self.plan(delete_data=delete_data)
                if any(checked[key] != plan[key] for key in ("installation_id", "service", "repository")):
                    raise DeploymentError("Konfigurácia sa počas rozhodovania zmenila; odstraňovanie kódu sa zastavilo.")
                # Store the legacy origin before removing its Git metadata.
                if not delete_data:
                    config["repository"] = plan["repository"]
                    write_json(self.deployment.config_path, config)
                for raw in plan["remove"]:
                    path = Path(raw)
                    if path.is_symlink():
                        path.unlink()
                    elif path.is_dir():
                        shutil.rmtree(path)
                    elif path.exists():
                        raise DeploymentError(f"Očakávaný priečinok bol nahradený súborom: {path}")
                    progress["removed"].append(raw)
                    write_json(self.journal, progress)
                if delete_data:
                    # All targets have been resolved and checked; never remove a parent directory.
                    shutil.rmtree(self.deployment.shared)
                    (self.root / ".update.lock").unlink()
                    self.root.rmdir()
                else:
                    progress["status"] = "completed"
                    write_json(self.journal, progress)
                    self.deployment.state("uninstalled", retained=str(self.deployment.shared))
                return progress
            except (Exception, KeyboardInterrupt) as error:
                # No hidden rollback of destructive or separately confirmed system actions.
                if self.deployment.shared.is_dir():
                    progress["status"] = "failed"
                    write_json(self.journal, progress)
                    self.deployment.state("uninstall_failed", error=str(error))
                raise


def confirm(prompt: str) -> bool:
    return input(prompt + " [a/N]: ").strip().casefold() in {"a", "ano", "áno"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root(Path(__file__).parent))
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--delete-data", action="store_true", help="Výslovne odstrániť aj všetky dáta, zálohy a odložené stavy")
    args = parser.parse_args()
    if not args.plan and (os.geteuid() == 0 or not sys.stdin.isatty() or not sys.stdout.isatty()):
        parser.error("Odinštalátor spusti osobne pod bežným účtom v interaktívnom termináli. --yes nie je podporované.")
    uninstaller = Uninstaller(args.root)
    uninstaller.print_plan(uninstaller.plan(delete_data=args.delete_data))
    if args.plan:
        print("\nIba plán: nič sa nezastavilo, nezapisovalo ani neodstránilo. Sudo sa nepoužilo.")
        return 0

    cleanup_selected = False

    def approval(plan):
        nonlocal cleanup_selected
        if not confirm("Vykonať tento plán odinštalovania?"):
            return False
        if plan["delete_data"]:
            answer = input("Zmažú sa aj všetky zálohy a účty. Na potvrdenie napíš úplnú cestu koreňa: ")
            if answer != plan["root"]:
                print("Cesta nesúhlasí; nič sa nezmenilo.")
                return False
        cleanup_selected = confirm("Ponúknuť aj kontrolu preukázateľne vytvorených systémových zmien cez sudo?")
        return True

    uninstaller.approval = approval
    def cleanup(plan):
        if cleanup_selected:
            subprocess.run(["sudo", "python3", "-B", str(Path(__file__).with_name("system_changes.py")),
                            "cleanup", "--root", plan["root"]], check=True)
    uninstaller.uninstall(delete_data=args.delete_data, system_cleanup=cleanup)
    if args.delete_data:
        print("Odinštalovanie dokončené. Kód, účty, dáta a aplikačné zálohy boli natrvalo odstránené; nie sú obnoviteľné týmto nástrojom.")
    else:
        print(f"Odinštalovanie dokončené. Dáta a zálohy zostali v {uninstaller.deployment.shared}.")
        print("Opätovnú inštaláciu spustíš z pomocného checkoutu voľbou Aktualizácia do rovnakého koreňa.")
    print("Systémové balíky ani SSH kľúče sa nemažú. DNS a Pi-hole neboli zmenené.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DeploymentCancelled as error:
        print(str(error))
        raise SystemExit(0)
    except (DeploymentError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Odinštalovanie sa nedokončilo: {error}\nUž vykonané kroky zostávajú. Skontroluj shared/uninstall-state.json; službu nespúšťaj naslepo.", file=sys.stderr)
        raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        print("\nPrerušené. Skontroluj posledný výpis a shared/uninstall-state.json; potvrdené kroky sa automaticky nevracajú.", file=sys.stderr)
        raise SystemExit(130)
