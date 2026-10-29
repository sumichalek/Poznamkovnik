#!/usr/bin/env python3
"""Boot a committed release in a clean venv and temporary data directory."""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from server_manage import Deployment, DeploymentError, run, write_json


def check_release(reference: str) -> None:
    project = Path(__file__).resolve().parents[1]
    if run("git", "status", "--porcelain", cwd=project):
        raise DeploymentError("Najprv ulož otestované zmeny do commitu; kontrola používa iba obsah Gitu.")
    commit = run("git", "rev-parse", "--verify", "--end-of-options", f"{reference}^{{commit}}", cwd=project)
    with tempfile.TemporaryDirectory(prefix="poznamkovnik-release-check-") as temporary:
        root = Path(temporary)
        source = root / "source"
        source.mkdir()
        run("git", "archive", "--format=tar", f"--output={root / 'source.tar'}", commit, cwd=project)
        with tarfile.open(root / "source.tar") as archive:
            if not hasattr(tarfile, "data_filter"):
                raise DeploymentError("Na kontrolu archívu použi Python s tarfile.data_filter (3.11.8+).")
            archive.extractall(source, filter="data")
        version = (source / "VERSION").read_text().strip()
        write_json(source / ".release.json", {"commit": commit, "tag": f"v{version}"})
        print(f"Overujem commit {commit}, verzia {version}, v čistom prostredí…", flush=True)
        run(sys.executable, "-m", "venv", str(source / ".venv"))
        python = str(source / ".venv/bin/python")
        run(python, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(source / "requirements.lock"))
        run(python, "-m", "pip", "check")
        deployment = Deployment(root / "installation")
        deployment.root.mkdir()
        (deployment.root / "current").symlink_to(source)
        unit = root / "poznamkovnik-release-check.service"
        unit.write_text(deployment.unit_text({"host": "127.0.0.1", "port": 1111}))
        run("systemd-analyze", "--user", "verify", str(unit))
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        opener = build_opener(ProxyHandler({}))
        with (root / "server.log").open("w+") as log:
            process = subprocess.Popen(
                [python, "-u", str(source / "server.py"), "--host", "127.0.0.1", "--port", str(port),
                 "--data-dir", str(root / "data")], cwd=source, stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        with opener.open(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                            result = json.load(response)
                        if result.get("status") == "ok" and result.get("version") == version and result.get("commit") == commit:
                            with opener.open(f"http://127.0.0.1:{port}/", timeout=2) as response:
                                html = response.read().decode("utf-8")
                            if f'data-app-version="{version}"' not in html:
                                raise DeploymentError("HTML neobsahuje číslo kontrolovaného vydania.")
                            with opener.open(f"http://127.0.0.1:{port}/assets/app.js", timeout=2) as response:
                                if response.status != 200 or not response.read(1):
                                    raise DeploymentError("Zostavený frontend nie je dostupný.")
                            print("OK: uzamknuté závislosti, systemd služba, štart, databáza, HTTP zdravie, verzia aj frontend.")
                            return
                    except (OSError, ValueError):
                        pass
                    time.sleep(0.2)
                log.flush()
                log.seek(0)
                raise DeploymentError(f"Vydanie neprešlo skúšobným štartom:\n{log.read()[-3000:]}")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", nargs="?", default="HEAD", help="Commit alebo tag na overenie (predvolené HEAD)")
    args = parser.parse_args()
    try:
        check_release(args.reference)
        return 0
    except (DeploymentError, OSError, ValueError, tarfile.TarError) as error:
        print(f"Chyba: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
