#!/usr/bin/env python3
"""Root-owned receipts for narrowly scoped, independently confirmed system actions."""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import ipaddress
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
if __package__:
    from .install_support import safe_root
    from .server_manage import Deployment, DeploymentError, read_json, run, write_json
else:
    from install_support import safe_root
    from server_manage import Deployment, DeploymentError, read_json, run, write_json


REGISTRY = Path("/var/lib/poznamkovnik-system")
IDENTITY = re.compile(r"[a-f0-9]{32}\Z")


class SystemOperations:
    def linger(self, user: str) -> bool:
        value = run("loginctl", "show-user", user, "--property=Linger", "--value")
        if value not in {"yes", "no"}:
            raise DeploymentError("Stav linger sa nepodarilo jednoznačne overiť.")
        return value == "yes"

    def set_linger(self, user: str, enabled: bool) -> None:
        run("loginctl", "enable-linger" if enabled else "disable-linger", user)

    def dependent_units(self, user: str, uid: int) -> list[str]:
        prefix = ("runuser", "-u", user, "--", "env", f"XDG_RUNTIME_DIR=/run/user/{uid}", "systemctl", "--user")
        enabled = run(*prefix, "list-unit-files", "--state=enabled", "--no-legend", "--no-pager")
        active = run(*prefix, "list-units", "--state=active", "--type=service,socket,timer", "--no-legend", "--no-pager")
        # The session bus itself is infrastructure, not proof that another app needs linger.
        infrastructure = {"dbus.service", "dbus-broker.service", "dbus.socket"}
        names = {line.split()[0] for line in (enabled + "\n" + active).splitlines() if line.strip()}
        return sorted(names - infrastructure)

    def firewall_rules(self) -> list[dict] | None:
        if not Path("/usr/sbin/ufw").is_file():
            return None
        value = run("/usr/sbin/ufw", "status", "numbered")
        if "Status: active" not in value:
            return None
        result = []
        for line in value.splitlines():
            if not re.match(r"\[\s*\d+\]", line):
                continue
            match = re.fullmatch(r"\[\s*\d+\]\s+(\d+)/tcp\s+ALLOW IN\s+(\S+?)(?:\s+#\s*(.*))?\s*", line)
            if match:
                source = match[2]
                try:
                    source = str(ipaddress.ip_network(source))
                except ValueError:
                    pass
                result.append({"port": int(match[1]), "network": source, "comment": (match[3] or "").strip()})
            else:
                # Unknown rules are never removed. Markers in them still prevent unsafe cleanup.
                result.append({"unknown": line})
        return result

    def firewall(self, rule: dict, *, remove: bool = False) -> None:
        command = ["/usr/sbin/ufw"]
        if remove:
            command.append("delete")
        command += ["allow", "from", rule["network"], "to", "any", "port", str(rule["port"]),
                    "proto", "tcp", "comment", rule["comment"]]
        run(*command)

    def backup(self, action: str, user: str) -> str:
        directory = Path(tempfile.mkdtemp(prefix="poznamkovnik-system-", dir="/var/backups"))
        directory.chmod(0o700)
        if action == "firewall":
            shutil.copytree("/etc/ufw", directory / "ufw", symlinks=True)
            (directory / "status-before.txt").write_text(run("/usr/sbin/ufw", "status", "numbered"))
        else:
            (directory / "linger-before.txt").write_text(f"{user}: {self.linger(user)}\n")
        print(f"Nová záloha systémového nastavenia: {directory}", flush=True)
        return str(directory)


class SystemChanges:
    def __init__(self, registry: Path = REGISTRY, *, operations=None, owner_uid: int = 0):
        self.registry = registry
        self.operations = operations or SystemOperations()
        self.owner_uid = owner_uid

    def check_registry(self) -> None:
        if self.registry.resolve() != self.registry or self.registry.is_symlink():
            raise DeploymentError("Register systémových zmien nesmie byť odkaz.")
        if self.registry.exists():
            info = self.registry.stat()
            if not self.registry.is_dir() or info.st_uid != self.owner_uid or info.st_mode & 0o022:
                raise DeploymentError("Register systémových zmien nemá bezpečného vlastníka alebo práva.")

    @contextlib.contextmanager
    def locked(self):
        self.check_registry()
        self.registry.mkdir(mode=0o700, parents=False, exist_ok=True)
        path = self.registry / ".lock"
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "r+") as lock:
            if os.fstat(lock.fileno()).st_uid != self.owner_uid:
                raise DeploymentError("Nesprávny vlastník zámku registra.")
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def profile(self, root: Path, uid: int) -> dict:
        root = safe_root(str(root))
        user = pwd.getpwuid(uid)
        if root == Path(user.pw_dir) or root.stat().st_uid != uid:
            raise DeploymentError("Inštalácia nepatrí používateľovi, ktorý spustil sudo.")
        path = root / "shared/server.json"
        if path.resolve() != path or path.is_symlink() or path.stat().st_uid != uid:
            raise DeploymentError("Konfigurácia nie je samostatný súbor používateľa inštalácie.")
        config = read_json(path)
        Deployment.validate_config(config)
        identity = config.get("installation_id", "")
        if not isinstance(identity, str) or not IDENTITY.fullmatch(identity) or config.get("installation_root") != str(root):
            raise DeploymentError("Chýba overiteľný identifikátor tejto inštalácie. Staré systémové nastavenia sa nepreberajú.")
        return {"format": 1, "id": identity, "root": str(root), "uid": uid, "user": user.pw_name,
                "service": config["service"], "port": config["port"], "changes": {}}

    def load(self, identity: str, uid: int) -> dict | None:
        if not IDENTITY.fullmatch(identity):
            raise DeploymentError("Neplatný identifikátor systémového dokladu.")
        self.check_registry()
        path = self.registry / f"{identity}.json"
        if not path.exists() and not path.is_symlink():
            return None
        if path.is_symlink() or not path.is_file() or path.stat().st_uid != self.owner_uid or path.stat().st_mode & 0o022:
            raise DeploymentError("Systémový doklad nemá bezpečné vlastníctvo alebo práva.")
        receipt = read_json(path)
        if receipt.get("format") != 1 or receipt.get("id") != identity or receipt.get("uid") != uid:
            raise DeploymentError("Systémový doklad nepatrí tomuto používateľovi alebo inštalácii.")
        if receipt.get("user") != pwd.getpwuid(uid).pw_name or not isinstance(receipt.get("changes"), dict):
            raise DeploymentError("Neplatný obsah systémového dokladu.")
        return receipt

    def receipt(self, profile: dict) -> dict:
        previous = self.load(profile["id"], profile["uid"])
        if previous and any(previous.get(key) != profile.get(key) for key in ("root", "user", "service", "port")):
            raise DeploymentError("Identifikátor už patrí inej konfigurácii; doklad sa neprepíše.")
        return previous or profile

    def save(self, receipt: dict) -> None:
        write_json(self.registry / f"{receipt['id']}.json", receipt)

    @staticmethod
    def firewall_rule(profile: dict, network: str) -> dict:
        try:
            subnet = ipaddress.ip_network(network, strict=True)
        except ValueError as error:
            raise DeploymentError("Zadaj konkrétnu IPv4 sieť v CIDR.") from error
        if subnet.version != 4 or subnet.prefixlen == 0:
            raise DeploymentError("Nepovoľuje sa celý internet ani IPv6 týmto krokom.")
        return {"port": profile["port"], "network": str(subnet), "comment": "Poznamkovnik " + profile["id"]}

    def apply_linger(self, profile: dict) -> None:
        with self.locked():
            receipt = self.receipt(profile)
            if self.operations.linger(profile["user"]):
                if "linger" not in receipt["changes"]:
                    receipt["changes"]["linger"] = {"changed": False, "status": "preexisting"}
                self.save(receipt)
                print("Linger tejto inštalácie už je evidovaný." if receipt["changes"]["linger"].get("changed")
                      else "Linger už bol povolený. Existujúce nastavenie si neprisvojujeme.")
                return
            change = {"changed": False, "status": "pending", "backup": self.operations.backup("linger", profile["user"])}
            receipt["changes"]["linger"] = change
            self.save(receipt)
            self.operations.set_linger(profile["user"], True)
            if not self.operations.linger(profile["user"]):
                raise DeploymentError("Povolenie linger sa nepotvrdilo; doklad zostáva neurčitý.")
            change.update(changed=True, status="applied")
            self.save(receipt)
            print("Linger povolený a jeho pôvod zaznamenaný.")

    def apply_firewall(self, profile: dict, network: str) -> None:
        rule = self.firewall_rule(profile, network)
        with self.locked():
            receipt = self.receipt(profile)
            rules = self.operations.firewall_rules()
            if rules is None:
                raise DeploymentError("UFW nie je aktívny alebo jeho stav nie je overiteľný. Nič sa nepovoľuje.")
            # UFW can update a pre-existing rule's comment instead of adding a new rule.
            # Do not risk relabelling an app-profile/interface rule we cannot fully parse.
            for item in rules:
                if "unknown" not in item:
                    continue
                row = item["unknown"].split("#", 1)[0]
                match = re.search(r"\s+(ALLOW|DENY|REJECT|LIMIT)\s+(IN|OUT|FWD)\s+(.+?)\s*$", row)
                if match and (match[1] != "ALLOW" or match[2] != "IN"):
                    continue
                if match:
                    source = match[3].strip()
                    if source.endswith("(v6)"):
                        continue
                    if source == "Anywhere":
                        source = "0.0.0.0/0"
                    try:
                        if str(ipaddress.ip_network(source)) != rule["network"]:
                            continue
                    except ValueError:
                        pass
                raise DeploymentError("UFW obsahuje neoveriteľné pravidlo pre túto sieť. Aby sa nepreznačilo cudzie pravidlo, zmenu najprv priprav ručne.")
            existing = [item for item in rules if item.get("port") == rule["port"] and item.get("network") == rule["network"]]
            if existing:
                if "firewall" not in receipt["changes"]:
                    receipt["changes"]["firewall"] = {"changed": False, "status": "preexisting", "rule": rule}
                self.save(receipt)
                print("Zodpovedajúce pravidlo už existovalo; nemení sa a pri odinštalovaní sa neodoberie.")
                return
            if "firewall" in receipt["changes"] and receipt["changes"]["firewall"].get("status") not in {"removed", "preexisting"}:
                raise DeploymentError("Inštalácia už eviduje iný alebo nedokončený zásah do UFW. Najprv ho skontroluj.")
            change = {"changed": False, "status": "pending", "rule": rule,
                      "backup": self.operations.backup("firewall", profile["user"])}
            receipt["changes"]["firewall"] = change
            self.save(receipt)
            self.operations.firewall(rule)
            rules = self.operations.firewall_rules()
            if rules is None or rules.count(rule) != 1:
                raise DeploymentError("Vznik presného označeného pravidla sa nepotvrdil. Automatické upratanie sa nepovolí.")
            change.update(changed=True, status="applied")
            self.save(receipt)
            print("Pravidlo UFW pridané s jedinečným označením inštalácie.")

    def cleanup(self, identity: str, uid: int, *, approval, plan_only: bool = False) -> None:
        receipt = self.load(identity, uid)
        if receipt is None:
            print("Chýba koreňový doklad. Systémové nastavenia zostávajú bez zmeny.")
            return
        print(f"Systémový doklad: {identity}\nInštalácia: {receipt['root']}\nPoužívateľ: {receipt['user']}")
        if plan_only:
            for name, change in receipt["changes"].items():
                print(f"  {name}: {change.get('status')}, vytvorené touto inštaláciou: {change.get('changed')}")
            print("Iba plán. Aktuálny stav a vlastníctvo sa znovu overia pred prípadným zásahom.")
            return
        with self.locked():
            receipt = self.load(identity, uid)
            firewall = receipt["changes"].get("firewall", {})
            if firewall.get("changed") and firewall.get("status") == "applied":
                expected = self.firewall_rule(receipt, firewall["rule"]["network"])
                if firewall["rule"] != expected:
                    raise DeploymentError("Systémový doklad UFW má neočakávané údaje.")
                rules = self.operations.firewall_rules()
                if rules is None:
                    print("UFW nie je aktívny/overiteľný; pravidlá sa nemenia.")
                elif not any(rule == expected or expected["comment"] in str(rule) for rule in rules):
                    firewall["status"] = "removed"
                    self.save(receipt)
                    print("Označené pravidlo už neexistuje; iné pravidlá sa nemenia.")
                elif rules.count(expected) == 1 and sum(expected["comment"] in str(rule) for rule in rules) == 1:
                    if approval(f"Odobrať iba UFW TCP {expected['port']} zo siete {expected['network']} s označením {expected['comment']}?"):
                        # Re-check after the user has taken time to decide.
                        if self.operations.firewall_rules() != rules:
                            raise DeploymentError("Počas rozhodovania sa firewall zmenil; nič sa neodoberie.")
                        firewall["cleanup_backup"] = self.operations.backup("firewall", receipt["user"])
                        self.save(receipt)
                        self.operations.firewall(expected, remove=True)
                        after = self.operations.firewall_rules()
                        if after is None or expected in after:
                            raise DeploymentError("Odstránenie pravidla sa nepotvrdilo.")
                        firewall["status"] = "removed"
                        self.save(receipt)
                else:
                    print("Pravidlo bolo upravené alebo je nejednoznačné; zostáva bez zmeny.")
            linger = receipt["changes"].get("linger", {})
            if linger.get("changed") and linger.get("status") == "applied":
                if not self.operations.linger(receipt["user"]):
                    linger["status"] = "removed"
                    self.save(receipt)
                else:
                    enabled = self.operations.dependent_units(receipt["user"], uid)
                    if enabled:
                        print("Linger zostáva: povolené alebo aktívne používateľské jednotky: " + ", ".join(enabled))
                    elif approval("Vypnúť linger, ktorý sme pôvodne povolili? Týka sa celého používateľského správcu služieb."):
                        if self.operations.dependent_units(receipt["user"], uid):
                            raise DeploymentError("Medzitým pribudla povolená jednotka; linger zostáva.")
                        linger["cleanup_backup"] = self.operations.backup("linger", receipt["user"])
                        self.save(receipt)
                        self.operations.set_linger(receipt["user"], False)
                        if self.operations.linger(receipt["user"]):
                            raise DeploymentError("Vypnutie linger sa nepotvrdilo.")
                        linger["status"] = "removed"
                        self.save(receipt)
            pending = [name for name, change in receipt["changes"].items()
                       if change.get("status") == "pending" or (change.get("changed") and change.get("status") == "applied")]
            if pending:
                print("Zostávajúce/neurčité systémové kroky: " + ", ".join(pending))
                print(f"Doklad {identity} zostáva v {self.registry}. Možno ho neskôr skontrolovať cez cleanup --receipt {identity}.")


def confirm(prompt: str) -> bool:
    return input(prompt + " [a/N]: ").strip().casefold() in {"a", "ano", "áno"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["apply-linger", "apply-firewall", "cleanup"])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--root", type=Path)
    target.add_argument("--receipt")
    parser.add_argument("--network")
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0 or not os.environ.get("SUDO_UID", "").isdigit() or int(os.environ["SUDO_UID"]) == 0:
        parser.error("Tento samostatný krok spusti cez sudo z bežného používateľského účtu.")
    if not args.plan and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        parser.error("Systémové zmeny vyžadujú osobný interaktívny terminál.")
    if args.action != "cleanup" and args.receipt:
        parser.error("Príprava systémového kroku potrebuje --root.")
    if args.action == "apply-firewall" and not args.network:
        parser.error("Chýba --network.")
    os.umask(0o077)
    os.environ["LC_ALL"] = "C"
    uid = int(os.environ["SUDO_UID"])
    changes = SystemChanges()
    if args.action == "cleanup":
        if args.receipt:
            identity = args.receipt
        else:
            config = read_json(args.root / "shared/server.json")
            identity = config.get("installation_id")
            if not isinstance(identity, str) or not IDENTITY.fullmatch(identity):
                print("Stará inštalácia nemá overiteľný identifikátor. Linger a firewall sa nemenia.")
                return 0
            profile = changes.profile(args.root, uid)
            receipt = changes.load(identity, uid)
            if receipt and any(profile[key] != receipt[key] for key in ("root", "service", "port")):
                raise DeploymentError("Systémový doklad nezodpovedá aktuálnej konfigurácii.")
        changes.cleanup(identity, uid, approval=confirm, plan_only=args.plan)
    else:
        profile = changes.profile(args.root, uid)
        print(f"Samostatný systémový krok: {args.action}\nInštalácia: {profile['root']}\nIdentifikátor: {profile['id']}")
        if args.action == "apply-firewall":
            print(changes.firewall_rule(profile, args.network))
        print("Pred zmenou vznikne nová záloha systémového nastavenia. DNS a Pi-hole sa nemenia.")
        if not args.plan and confirm("Vykonať uvedený krok?"):
            if args.action == "apply-linger":
                changes.apply_linger(profile)
            else:
                changes.apply_firewall(profile, args.network)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DeploymentError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"Systémový krok sa nedokončil: {error}. Existujúce nastavenia a doklad najprv skontroluj.", file=sys.stderr)
        raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        print("\nZrušené. Už vykonané a zaznamenané kroky zostávajú.", file=sys.stderr)
        raise SystemExit(130)
