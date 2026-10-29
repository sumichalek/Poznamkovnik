#!/usr/bin/env python3
"""Git releases with mandatory offline snapshots. Uses only Python's standard library."""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener


TAG_PATTERN = r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?"
MARKER = "# Managed by Poznamkovnik Git deployment"


class DeploymentError(RuntimeError):
    pass


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise DeploymentError(f"Príkaz {args[0]} zlyhal: {result.stderr.strip()[-2000:]}")
    return result.stdout.strip()


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}-{uuid.uuid4().hex}")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DeploymentError(f"Neplatný konfiguračný súbor: {path}")
    return value


def exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def check_plain_tree(path: Path) -> None:
    """Do not silently omit mounted/symlinked data or capture outside the configured tree."""
    if not exists(path):
        return
    paths = [path, *path.rglob("*")] if path.is_dir() and not path.is_symlink() else [path]
    for item in paths:
        if item.is_symlink() or not (item.is_file() or item.is_dir()):
            raise DeploymentError(f"Záloha nepodporuje odkaz ani špeciálny súbor: {item}")


def copy_path(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


class UserService:
    def __init__(self, name: str):
        self.name = name

    def command(self, *args: str) -> str:
        return run("systemctl", "--user", *args, self.name)

    def active(self) -> bool:
        state = self.command("show", "--property=ActiveState", "--value")
        if state in {"activating", "deactivating", "reloading"}:
            raise DeploymentError("Služba práve mení stav; zopakuj operáciu po dokončení.")
        return state == "active"

    def stop(self) -> None:
        if self.command("show", "--property=LoadState", "--value") == "not-found":
            return
        self.command("stop")
        if self.active():
            raise DeploymentError("Služba sa nezastavila; dáta sa nesmú zálohovať počas zápisov.")

    def start(self) -> None:
        self.command("start")

    def reload(self) -> None:
        run("systemctl", "--user", "daemon-reload")

    def enable(self) -> None:
        self.command("enable")


class Deployment:
    def __init__(self, root: Path, *, service=None, unit_dir: Path | None = None, health_timeout: float = 45):
        self.root = root.expanduser().absolute()
        if self.root.resolve() in {Path("/"), Path.home().resolve()} or (self.root / ".git").exists():
            raise DeploymentError("Použi samostatný inštalačný priečinok, nie koreň, domov ani pracovný projekt.")
        self.shared = self.root / "shared"
        self.releases = self.root / "releases"
        self.repository = self.root / "repository"
        self.data = self.shared / "data"
        self.backups = self.shared / "update-backups"
        self.config_path = self.shared / "server.json"
        self.state_path = self.shared / "update-state.json"
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        self.unit_dir = unit_dir or config_home / "systemd/user"
        self.service_override = service
        self.health_timeout = health_timeout

    @contextlib.contextmanager
    def locked(self):
        for path in (self.root, self.shared, self.releases, self.backups):
            if path.is_symlink():
                raise DeploymentError(f"Inštalačný priečinok nesmie byť odkaz: {path}")
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / ".update.lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise DeploymentError("V tejto inštalácii už prebieha iná aktualizácia.") from error
            yield

    def config(self) -> dict:
        value = read_json(self.config_path)
        self.validate_config(value)
        return value

    @staticmethod
    def validate_config(value: dict) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.service", str(value.get("service", ""))):
            raise DeploymentError("Neplatný názov systemd služby.")
        if not isinstance(value.get("port"), int) or not 1 <= value["port"] <= 65535:
            raise DeploymentError("Neplatný port servera.")
        host = str(value.get("host", ""))
        if not re.fullmatch(r"[A-Za-z0-9.:_-]+", host):
            raise DeploymentError("Neplatná adresa servera.")

    def service(self, config: dict):
        return self.service_override or UserService(config["service"])

    def settings_paths(self, config: dict) -> dict[str, Path]:
        paths = {
            "server.json": self.config_path,
            "service": self.unit_dir / config["service"],
            "service.d": self.unit_dir / f"{config['service']}.d",
            "service-enabled": self.unit_dir / "default.target.wants" / config["service"],
            "config.env": self.shared / "config.env",
        }
        for index, raw in enumerate(config.get("backup_paths", [])):
            path = Path(raw).expanduser().absolute()
            resolved = path.resolve()
            if resolved in {Path("/"), Path.home(), self.root.resolve(), Path.cwd()}:
                raise DeploymentError(f"Príliš široká cesta k nastaveniam: {path}")
            if resolved == self.data.resolve() or resolved in self.root.resolve().parents:
                raise DeploymentError(f"Nastavenia prekrývajú inštaláciu alebo dáta: {path}")
            if self.root.resolve() in resolved.parents:
                raise DeploymentError("Dodatočné nastavenia musia byť mimo inštalácie; shared/config.env sa zálohuje automaticky.")
            paths[f"extra-{index}"] = path
        # The enabled symlink intentionally refers to the same unit file.
        targets = [path for key, path in paths.items() if key != "service-enabled"]
        for index, path in enumerate(targets):
            for other in targets[index + 1:]:
                if path.resolve() == other.resolve() or path.resolve() in other.resolve().parents or other.resolve() in path.resolve().parents:
                    raise DeploymentError("Cesty zálohovaných nastavení sa prekrývajú.")
        return paths

    def current(self) -> Path | None:
        pointer = self.root / "current"
        if not exists(pointer):
            return None
        if not pointer.is_symlink():
            raise DeploymentError("current musí byť symbolický odkaz na vydanie.")
        release = pointer.resolve(strict=True)
        if release.parent != self.releases.resolve():
            raise DeploymentError("current ukazuje mimo priečinka releases.")
        return release

    def point_to(self, release: Path | None) -> None:
        pointer = self.root / "current"
        if release is None:
            if pointer.is_symlink():
                pointer.unlink()
            return
        if release.parent.resolve() != self.releases.resolve():
            raise DeploymentError("Vydanie je mimo spravovanej inštalácie.")
        temporary = self.root / f".current-{uuid.uuid4().hex}"
        temporary.symlink_to(release)
        temporary.replace(pointer)

    def state(self, status: str, **values) -> None:
        write_json(self.state_path, {"status": status, "time": datetime.now(timezone.utc).isoformat(), **values})

    def check_release(self, release: Path, commit: str | None = None) -> str:
        if release.is_symlink() or release.parent.resolve() != self.releases.resolve():
            raise DeploymentError("Vydanie musí byť samostatný adresár v releases.")
        actual = run("git", "-C", str(release), "rev-parse", "HEAD")
        if commit and actual != commit:
            raise DeploymentError("Existujúce vydanie má iný Git commit.")
        if run("git", "-C", str(release), "status", "--porcelain", "--untracked-files=all"):
            raise DeploymentError(f"Vydanie má lokálne zmeny: {release}")
        for relative in ("server.py", "VERSION", "requirements.lock", "assets/app.js", "assets/app.css", "index.html"):
            if not (release / relative).is_file():
                raise DeploymentError(f"Vydaniu chýba povinný súbor {relative}.")
        return actual

    def prepare(self, tag: str) -> Path:
        if not re.fullmatch(TAG_PATTERN, tag):
            raise DeploymentError("Zadaj konkrétny tag vydania, napríklad v0.57.0.")
        run("git", "-C", str(self.repository), "fetch", "origin", "--tags")
        commit = run("git", "-C", str(self.repository), "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
        release = self.releases / tag
        if not exists(release):
            run("git", "-C", str(self.repository), "worktree", "add", "--detach", str(release), commit)
        self.check_release(release, commit)
        if (release / "VERSION").read_text().strip() != tag[1:]:
            raise DeploymentError("Git tag nesúhlasí so súborom VERSION vo vydaní.")
        self.prepare_environment(release)
        write_json(release / ".release.json", {"commit": commit, "tag": tag})
        return release

    def prepare_environment(self, release: Path) -> None:
        run(sys.executable, "-m", "venv", str(release / ".venv"))
        python = str(release / ".venv/bin/python")
        run(python, "-m", "pip", "install", "-r", str(release / "requirements.lock"))
        run(python, "-m", "pip", "check")
        run(python, "-c", "from backend.api import AppContext, AppHandler", cwd=release)

    def unit_text(self, config: dict) -> str:
        def quote(value: object) -> str:
            text = str(value)
            if "\n" in text or "\r" in text:
                raise DeploymentError("Cesta obsahuje neplatný znak.")
            return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"'
        current = self.root / "current"
        return (
            f"{MARKER}\n# Deployment root: {self.root}\n[Unit]\nDescription=Poznamkovnik Git server\nStartLimitIntervalSec=0\n\n"
            f"[Service]\nType=simple\nWorkingDirectory={quote(current)}\n"
            f"ExecStart={quote(current / '.venv/bin/python')} {quote(current / 'server.py')} "
            f"--host {quote(config['host'])} --port {config['port']} --data-dir {quote(self.data)}\n"
            f"Environment=PYTHONUNBUFFERED=1\nEnvironmentFile=-{quote(self.shared / 'config.env')}\n"
            "Restart=on-failure\nRestartSec=5\nTimeoutStopSec=30\nKillSignal=SIGINT\n\n"
            "[Install]\nWantedBy=default.target\n"
        )

    def initialize(self, repository: str, tag: str, host: str, port: int, name: str, backup_paths: list[str]) -> None:
        with self.locked():
            if exists(self.config_path) or self.current() is not None:
                raise DeploymentError("Inštalácia už existuje; použi príkaz update.")
            if exists(self.unit_dir / name):
                raise DeploymentError("Systemd služba už existuje. Použi nový názov služby alebo samostatný serverový účet.")
            config = {"service": name, "host": host, "port": port, "backup_paths": backup_paths}
            # Validate before creating the persistent configuration or fetching Git code.
            self.validate_config(config)
            if self.service_override is None and UserService(name).active():
                raise DeploymentError("Služba už beží; prvá inštalácia ju nesmie prevziať.")
            self.settings_paths(config)
            if not exists(self.repository):
                run("git", "clone", "--no-checkout", "--", repository, str(self.repository))
            self.data.mkdir(exist_ok=True, mode=0o700)
            write_json(self.config_path, config)
            self._update(tag, first=True)

    def update(self, tag: str) -> None:
        with self.locked():
            self._update(tag)

    def _update(self, tag: str, *, first: bool = False) -> None:
        config = self.config()
        self.settings_paths(config)
        old = self.current()
        if old is not None:
            self.check_release(old)
            unit = self.unit_dir / config["service"]
            if not unit.is_file() or MARKER not in unit.read_text() or f"# Deployment root: {self.root}\n" not in unit.read_text():
                raise DeploymentError("Služba nepatrí tejto Git inštalácii.")
        elif not first:
            # A failed initial preparation may be retried using update.
            if exists(self.unit_dir / config["service"]):
                raise DeploymentError("Inštalácia nemá current, ale služba už existuje.")
        if self.state_path.exists() and read_json(self.state_path).get("status") in {"stopped", "backed_up", "activating", "recovery_required"}:
            raise DeploymentError("Predošlá operácia sa nedokončila. Pozri status a obnov uvedenú zálohu príkazom rollback.")
        if old is not None and old.name == tag:
            print("Toto vydanie už je aktívne.")
            return
        print(f"Pripravujem Git vydanie {tag}…", flush=True)
        release = self.prepare(tag)
        if old == release:
            print("Toto vydanie už je aktívne.")
            return
        self.activate(release, config, install=old is None)

    def snapshot(self, config: dict, previous: Path | None) -> Path:
        if self.data.is_symlink() or not self.data.is_dir():
            raise DeploymentError("Dáta musia byť v spravovanom shared/data adresári.")
        check_plain_tree(self.data)
        settings = self.settings_paths(config)
        for key, path in settings.items():
            if key == "service-enabled" and path.is_symlink():
                if path.resolve() != settings["service"].resolve():
                    raise DeploymentError("Odkaz automatického spúšťania ukazuje na inú službu.")
            else:
                check_plain_tree(path)
        snapshot = Path(tempfile.mkdtemp(prefix="before-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"), dir=self.backups))
        os.chmod(snapshot, 0o700)
        manifest = {
            "format": 1, "root": str(self.root), "previous": str(previous) if previous else None,
            "commit": self.check_release(previous) if previous else None,
            "time": datetime.now(timezone.utc).isoformat(), "settings": {}, "files": {},
        }
        with tarfile.open(snapshot / "data.tar.gz", "w:gz") as archive:
            archive.add(self.data, arcname="data")
        for key, path in settings.items():
            present = exists(path)
            manifest["settings"][key] = {"target": str(path), "present": present, "directory": path.is_dir()}
            if path.is_symlink():
                manifest["settings"][key]["link"] = os.readlink(path)
            elif present:
                copy_path(path, snapshot / "settings" / key)
        for path in sorted(snapshot.rglob("*")):
            if path.is_file():
                manifest["files"][str(path.relative_to(snapshot))] = digest(path)
        write_json(snapshot / "manifest.json", manifest)
        self._verify_snapshot_payload(snapshot, config)
        # A failed verification must never leave a success marker behind.
        with (snapshot / "VERIFIED").open("x") as marker:
            marker.write(digest(snapshot / "manifest.json") + "\n")
            marker.flush()
            os.fsync(marker.fileno())
        print(f"Nová záloha dát aj nastavení bola overená: {snapshot}", flush=True)
        return snapshot

    def verify_snapshot(self, snapshot: Path, config: dict) -> dict:
        manifest = self._verify_snapshot_payload(snapshot, config)
        if (snapshot / "VERIFIED").read_text().strip() != digest(snapshot / "manifest.json"):
            raise DeploymentError("Kontrolný súčet manifestu zálohy nesedí.")
        return manifest

    def _verify_snapshot_payload(self, snapshot: Path, config: dict) -> dict:
        snapshot = snapshot.absolute()
        if snapshot.is_symlink() or snapshot.parent.resolve() != self.backups.resolve():
            raise DeploymentError("Záloha musí byť v update-backups tejto inštalácie.")
        check_plain_tree(snapshot)
        manifest = read_json(snapshot / "manifest.json")
        if manifest.get("format") != 1 or manifest.get("root") != str(self.root):
            raise DeploymentError("Záloha nepatrí tejto inštalácii.")
        expected_settings = {key: str(path) for key, path in self.settings_paths(config).items()}
        actual_settings = {key: item["target"] for key, item in manifest["settings"].items()}
        if actual_settings != expected_settings:
            raise DeploymentError("Záloha má odlišný zoznam ciest k nastaveniam.")
        for key, item in manifest["settings"].items():
            saved = snapshot / "settings" / key
            if "link" in item:
                target = Path(item["target"])
                if key != "service-enabled" or not item["present"] or exists(saved) or (target.parent / item["link"]).resolve() != Path(expected_settings["service"]).resolve():
                    raise DeploymentError("Neplatná záloha odkazu automatického spúšťania.")
                continue
            if exists(saved) != item["present"] or (item["present"] and saved.is_dir() != item["directory"]):
                raise DeploymentError(f"Záloha nastavení je neúplná: {key}")
        files = {str(path.relative_to(snapshot)) for path in snapshot.rglob("*") if path.is_file()} - {"manifest.json", "VERIFIED"}
        if files != set(manifest["files"]):
            raise DeploymentError("Záloha má neúplný alebo neočakávaný obsah.")
        for relative, expected in manifest["files"].items():
            if digest(snapshot / relative) != expected:
                raise DeploymentError(f"Kontrolný súčet zálohy nesedí: {relative}")
        with tarfile.open(snapshot / "data.tar.gz", "r:gz") as archive:
            members = archive.getmembers()
            if not members or not any(item.name == "data" and item.isdir() for item in members):
                raise DeploymentError("V zálohe chýba dátový adresár.")
            for member in members:
                parts = Path(member.name).parts
                if not parts or parts[0] != "data" or ".." in parts or not (member.isfile() or member.isdir()):
                    raise DeploymentError("Záloha obsahuje nepodporovanú cestu alebo typ súboru.")
                if member.isfile():
                    with archive.extractfile(member) as stream:
                        while stream.read(1024 * 1024):
                            pass
        return manifest

    def restore(self, snapshot: Path, config: dict) -> Path | None:
        manifest = self.verify_snapshot(snapshot, config)
        previous = Path(manifest["previous"]) if manifest["previous"] else None
        if previous:
            if previous.parent.resolve() != self.releases.resolve():
                raise DeploymentError("Pôvodné vydanie je mimo releases.")
            self.check_release(previous, manifest["commit"])
        recovery = Path(tempfile.mkdtemp(prefix="recovery-", dir=self.shared))
        with tarfile.open(snapshot / "data.tar.gz", "r:gz") as archive:
            # Older Python 3.11 lacks extraction filters; verify_snapshot already
            # allows only plain files/directories under the single data/ root.
            options = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
            archive.extractall(recovery / "restored", **options)
        # Every displaced file is kept. A failed restoration leaves the service stopped.
        self.data.replace(recovery / "data-after-update")
        (recovery / "restored/data").replace(self.data)
        for key, item in manifest["settings"].items():
            target = Path(item["target"])
            if exists(target):
                destination = recovery / "settings-after-update" / key
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target), str(destination))
            if item["present"]:
                if "link" in item:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(item["link"])
                else:
                    copy_path(snapshot / "settings" / key, target)
        self.point_to(previous)
        print(f"Stav po pokuse je zachovaný v {recovery}", flush=True)
        return previous

    def health(self, release: Path, config: dict) -> None:
        metadata = read_json(release / ".release.json")
        host = config["host"]
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1" if host == "0.0.0.0" else "::1"
        if ":" in host:
            host = f"[{host}]"
        url = f"http://{host}:{config['port']}/api/health"
        expected_instance = hashlib.sha256(str(self.data.resolve()).encode()).hexdigest()[:24]
        opener = build_opener(ProxyHandler({}))
        deadline = time.monotonic() + self.health_timeout
        last_error = "Server neodpovedá."
        while time.monotonic() < deadline:
            try:
                with opener.open(url, timeout=2) as response:
                    result = json.load(response)
                if (result.get("status") == "ok" and result.get("commit") == metadata["commit"]
                        and result.get("version") == metadata["tag"][1:] and result.get("instance") == expected_instance):
                    return
                last_error = "HTTP odpoveď nezodpovedá vydaniu alebo dátam tejto inštalácie."
            except (OSError, ValueError, URLError) as error:
                last_error = str(error)
            time.sleep(0.2)
        raise DeploymentError(f"Nové vydanie neprešlo kontrolou dostupnosti: {last_error}")

    def activate(self, release: Path, config: dict, *, install: bool = False, restore_from: Path | None = None) -> None:
        service = self.service(config)
        old = self.current()
        was_active = service.active()
        snapshot = None
        activation_started = False
        try:
            service.stop()
            self.state("stopped", previous=str(old) if old else None)
            snapshot = self.snapshot(config, old)
            self.state("backed_up", snapshot=str(snapshot))
            # No data, settings or active code changes may precede the verified snapshot.
            activation_started = True
            self.state("activating", snapshot=str(snapshot), target=str(release))
            if restore_from:
                self.restore(restore_from, config)
                config = self.config()
            else:
                if install:
                    self.unit_dir.mkdir(parents=True, exist_ok=True)
                    (self.unit_dir / config["service"]).write_text(self.unit_text(config))
                self.point_to(release)
            service.reload()
            service.start()
            self.health(release, config)
            if install:
                service.enable()
            self.state("completed", snapshot=str(snapshot), release=str(release))
            print(f"Aktívne vydanie: {release.name}. Záloha: {snapshot}", flush=True)
        except (Exception, KeyboardInterrupt) as error:
            if not activation_started:
                try:
                    if was_active:
                        service.start()
                except Exception as restart_error:
                    self.state("recovery_required", error=str(error), recovery_error=str(restart_error), previous=str(old) if old else None)
                    raise DeploymentError(f"Aktivácia neprebehla, ale pôvodnú službu sa nepodarilo spustiť: {restart_error}") from restart_error
                self.state("backup_failed", error=str(error), previous=str(old) if old else None)
                raise DeploymentError(f"Aktualizácia bola zastavená pred aktiváciou: {error}") from error
            try:
                service.stop()
                previous = self.restore(snapshot, config)
                service.reload()
                if previous and was_active:
                    service.start()
                    self.health(previous, self.config())
                self.state("rolled_back", snapshot=str(snapshot), error=str(error))
            except (Exception, KeyboardInterrupt) as recovery_error:
                self.state("recovery_required", snapshot=str(snapshot), error=str(error), recovery_error=str(recovery_error))
                raise DeploymentError(f"Obnova vyžaduje zásah; službu nechaj zastavenú. Záloha: {snapshot}. {recovery_error}") from recovery_error
            raise DeploymentError(f"Aktualizácia zlyhala; pôvodný stav bol obnovený. {error}") from error

    def rollback(self, snapshot: Path) -> None:
        with self.locked():
            config = self.config()
            manifest = self.verify_snapshot(snapshot, config)
            if not manifest["previous"]:
                raise DeploymentError("Táto záloha je spred prvej inštalácie a neobsahuje staré vydanie.")
            previous = Path(manifest["previous"])
            self.check_release(previous, manifest["commit"])
            self.activate(previous, config, restore_from=snapshot)

    def status(self) -> dict:
        config = self.config()
        release = self.current()
        return {
            "root": str(self.root), "service": config["service"], "active": self.service(config).active(),
            "release": str(release) if release else None,
            "lastOperation": read_json(self.state_path) if self.state_path.exists() else None,
            "backups": [str(path) for path in sorted(self.backups.glob("before-*")) if (path / "VERIFIED").is_file()],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Git aktualizácie Poznámkovníka s povinnou zálohou dát aj nastavení.")
    parser.add_argument("--root", type=Path, default=Path.home() / "apps/poznamkovnik")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Prvá inštalácia do samostatného serverového priečinka")
    init.add_argument("tag")
    init.add_argument("--repository", default="git@github.com:sumichalek/Poznamkovnik.git")
    init.add_argument("--host", default="127.0.0.1")
    init.add_argument("--port", type=int, default=1111)
    init.add_argument("--service", default="poznamkovnik.service")
    init.add_argument("--backup-path", action="append", default=[])
    update = commands.add_parser("update", help="Načítaj Git tag, zálohuj a aktivuj vydanie")
    update.add_argument("tag")
    rollback = commands.add_parser("rollback", help="Obnov dáta, nastavenia aj vydanie z technickej zálohy")
    rollback.add_argument("snapshot", type=Path)
    verify = commands.add_parser("verify", help="Over obsah a kontrolné súčty technickej zálohy")
    verify.add_argument("snapshot", type=Path)
    commands.add_parser("status", help="Aktívna verzia, posledná operácia a dostupné zálohy")
    args = parser.parse_args()
    os.umask(0o077)
    def interrupted(_number, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        deployment = Deployment(args.root)
        if args.command == "init":
            deployment.initialize(args.repository, args.tag, args.host, args.port, args.service, args.backup_path)
        elif args.command == "update":
            deployment.update(args.tag)
        elif args.command == "rollback":
            deployment.rollback(args.snapshot)
        elif args.command == "verify":
            deployment.verify_snapshot(args.snapshot, deployment.config())
            print("Záloha dát aj nastavení je v poriadku.")
        else:
            print(json.dumps(deployment.status(), ensure_ascii=False, indent=2))
        return 0
    except (DeploymentError, OSError, ValueError, tarfile.TarError) as error:
        print(f"Chyba: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operácia bola prerušená; pred ďalšou aktualizáciou skontroluj status.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
