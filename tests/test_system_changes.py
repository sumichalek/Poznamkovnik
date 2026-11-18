from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.server_manage import DeploymentError
from scripts import system_changes as system_module
from scripts.system_changes import SystemChanges, SystemOperations


KORUNKA_UFW_STATUS = """Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 22/tcp                     ALLOW IN    192.168.0.0/24
[ 2] 53                         ALLOW IN    192.168.0.0/24
[ 3] 80/tcp                     ALLOW IN    192.168.0.0/24
[ 4] 67/udp on enp1s0           ALLOW IN    Anywhere
[ 5] 67/udp (v6) on enp1s0      ALLOW IN    Anywhere (v6)
"""


class FakeOperations:
    def __init__(self):
        self.linger_value = False
        self.rules = []
        self.units = []
        self.actions = []
        self.backups = []
        self.fail_firewall = False

    def linger(self, user): return self.linger_value
    def dependent_units(self, user, uid): return list(self.units)
    def firewall_rules(self): return copy.deepcopy(self.rules)

    def set_linger(self, user, enabled):
        self.actions.append(("linger", user, enabled))
        self.linger_value = enabled

    def backup(self, action, user):
        self.backups.append((action, user))
        return "/fixture-system-backup/" + str(len(self.backups))

    def firewall(self, rule, *, remove=False):
        if self.fail_firewall:
            raise DeploymentError("fixture UFW failure")
        self.actions.append(("firewall", copy.deepcopy(rule), remove))
        if remove:
            self.rules.remove(rule)
        else:
            self.rules.append(copy.deepcopy(rule))


class SystemChangesTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="poznamkovnik-system-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "installation"
        (self.root / "shared").mkdir(parents=True)
        self.identity = "a" * 32
        self.config = {"installation_id": self.identity, "installation_root": str(self.root),
                       "service": "fixture.service", "port": 19111, "host": "127.0.0.1"}
        self.config_path = self.root / "shared/server.json"
        self.config_path.write_text(json.dumps(self.config))
        self.uid = os.getuid()
        self.ops = FakeOperations()
        self.registry = self.base / "root-only-receipts"
        self.changes = SystemChanges(self.registry, operations=self.ops, owner_uid=os.getuid())
        self.profile = self.changes.profile(self.root, self.uid)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def cleanup(self, **kwargs):
        self.changes.cleanup(self.identity, self.uid, approval=lambda prompt: True, **kwargs)

    @staticmethod
    def parse_rules(status):
        with patch("scripts.system_changes.Path.is_file", return_value=True), patch("scripts.system_changes.run", return_value=status):
            return SystemOperations().firewall_rules()

    def test_missing_receipt_plan_and_cleanup_change_nothing(self):
        self.cleanup(plan_only=True)
        self.cleanup()
        self.assertFalse(self.registry.exists())
        self.assertEqual(self.ops.actions, [])
        self.assertEqual(self.ops.backups, [])

    def test_existing_linger_is_never_adopted(self):
        self.ops.linger_value = True
        self.changes.apply_linger(self.profile)
        self.cleanup()
        self.assertTrue(self.ops.linger_value)
        self.assertEqual(self.ops.actions, [])
        self.assertFalse(self.changes.load(self.identity, self.uid)["changes"]["linger"]["changed"])

    def test_owned_linger_is_removed_only_without_other_enabled_units(self):
        self.changes.apply_linger(self.profile)
        self.ops.units = ["ssh-agent.socket", "other.timer"]
        self.cleanup()
        self.assertTrue(self.ops.linger_value)
        self.ops.units = []
        self.cleanup()
        self.assertFalse(self.ops.linger_value)
        self.assertEqual(len(self.ops.backups), 2)

    def test_reapplying_linger_keeps_original_ownership(self):
        self.changes.apply_linger(self.profile)
        self.changes.apply_linger(self.profile)
        self.assertEqual(len(self.ops.backups), 1)
        self.cleanup()
        self.assertFalse(self.ops.linger_value)

    def test_linger_is_rechecked_after_user_confirmation(self):
        self.changes.apply_linger(self.profile)
        def approval(prompt):
            self.ops.units = ["newly-enabled.service"]
            return True
        with self.assertRaisesRegex(DeploymentError, "pribudla"):
            self.changes.cleanup(self.identity, self.uid, approval=approval)
        self.assertTrue(self.ops.linger_value)

    def test_deferred_receipt_can_be_cleaned_after_app_root_is_gone(self):
        self.changes.apply_linger(self.profile)
        self.ops.units = ["second-instance.service"]
        self.cleanup()
        shutil.rmtree(self.root)
        self.ops.units = []
        self.cleanup()
        self.assertFalse(self.ops.linger_value)

    def test_existing_firewall_rule_is_not_relabelled_or_removed(self):
        original = {"port": 19111, "network": "192.168.0.0/24", "comment": "another application"}
        self.ops.rules = [copy.deepcopy(original)]
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.cleanup()
        self.assertEqual(self.ops.rules, [original])
        self.assertEqual(self.ops.actions, [])

    def test_only_exact_owned_rule_is_removed_and_other_ports_survive(self):
        dns = {"port": 53, "network": "192.168.0.0/24", "comment": "Pi-hole"}
        ssh = {"port": 22, "network": "192.168.0.0/24", "comment": "SSH"}
        self.ops.rules = [dns, ssh]
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.assertEqual(len(self.ops.rules), 3)
        self.cleanup()
        self.assertEqual(self.ops.rules, [dns, ssh])
        self.assertEqual(len(self.ops.backups), 2)

    def test_modified_or_duplicate_owned_rule_is_left_alone(self):
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.ops.rules[0]["port"] = 19112
        self.cleanup()
        self.assertEqual(self.ops.rules[0]["port"], 19112)
        self.ops.rules[0]["port"] = 19111
        self.ops.rules.append(copy.deepcopy(self.ops.rules[0]))
        self.cleanup()
        self.assertEqual(len(self.ops.rules), 2)
        self.assertEqual(len(self.ops.actions), 1)

    def test_firewall_change_during_confirmation_aborts_cleanup(self):
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        def approval(prompt):
            self.ops.rules.append({"unknown": "new unrelated rule"})
            return True
        with self.assertRaisesRegex(DeploymentError, "firewall zmenil"):
            self.changes.cleanup(self.identity, self.uid, approval=approval)
        self.assertEqual(len(self.ops.actions), 1)

    def test_failed_application_never_proves_ownership(self):
        self.ops.fail_firewall = True
        with self.assertRaises(DeploymentError):
            self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        receipt = self.changes.load(self.identity, self.uid)
        self.assertEqual(receipt["changes"]["firewall"]["status"], "pending")
        self.assertFalse(receipt["changes"]["firewall"]["changed"])
        self.ops.fail_firewall = False
        self.cleanup()
        self.assertEqual(self.ops.actions, [])

    def test_decline_and_plan_do_not_modify_system_or_receipt(self):
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        receipt = self.registry / f"{self.identity}.json"
        before = receipt.read_bytes()
        self.cleanup(plan_only=True)
        self.changes.cleanup(self.identity, self.uid, approval=lambda prompt: False)
        self.assertEqual(receipt.read_bytes(), before)
        self.assertEqual(len(self.ops.actions), 1)

    def test_receipts_cannot_cross_users_roots_or_installation_ids(self):
        self.changes.apply_linger(self.profile)
        with self.assertRaises(DeploymentError):
            self.changes.load(self.identity, self.uid + 1)
        altered = dict(self.profile, root=str(self.base / "another-installation"))
        with self.assertRaises(DeploymentError):
            self.changes.apply_linger(altered)
        self.config["installation_root"] = str(self.base / "wrong")
        self.config_path.write_text(json.dumps(self.config))
        with self.assertRaises(DeploymentError):
            self.changes.profile(self.root, self.uid)

    def test_untrusted_registry_and_symlinked_receipt_are_refused(self):
        self.changes.apply_linger(self.profile)
        self.registry.chmod(0o777)
        with self.assertRaises(DeploymentError): self.cleanup()
        self.registry.chmod(0o700)
        path = self.registry / f"{self.identity}.json"
        outside = self.base / "outside-receipt"
        path.rename(outside)
        path.symlink_to(outside)
        with self.assertRaises(DeploymentError): self.cleanup()
        self.assertTrue(self.ops.linger_value)

    def test_firewall_rejects_entire_internet_and_inactive_ufw(self):
        for network in ("0.0.0.0/0", "::/0", "not-a-network"):
            with self.subTest(network=network), self.assertRaises(DeploymentError):
                self.changes.apply_firewall(self.profile, network)
        self.ops.rules = None
        with self.assertRaisesRegex(DeploymentError, "nie je aktívny"):
            self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.assertEqual(self.ops.actions, [])

    def test_status_parser_keeps_unknown_rules_and_exact_comments(self):
        text = "Status: active\n[ 1] 19111/tcp ALLOW IN 192.168.0.0/24 # Poznamkovnik " + self.identity + "\n[ 2] DNS ALLOW IN Anywhere # Pi-hole\n"
        with patch("scripts.system_changes.Path.is_file", return_value=True), patch("scripts.system_changes.run", return_value=text):
            rules = SystemOperations().firewall_rules()
        self.assertEqual(rules[0], {"port": 19111, "network": "192.168.0.0/24", "comment": "Poznamkovnik " + self.identity})
        self.assertIn("unknown", rules[1])

    def test_active_unenabled_units_also_block_linger_cleanup(self):
        enabled = "ssh-agent.socket enabled enabled\n"
        active = "dbus.service loaded active running Session bus\nmanual.service loaded active running User app\n"
        with patch("scripts.system_changes.run", side_effect=[enabled, active]):
            units = SystemOperations().dependent_units("fixture", 1000)
        self.assertEqual(units, ["manual.service", "ssh-agent.socket"])

    def test_host_source_is_normalized_so_existing_rule_is_not_adopted(self):
        text = "Status: active\n[ 1] 19111/tcp ALLOW IN 192.168.0.7 # old rule\n"
        with patch("scripts.system_changes.Path.is_file", return_value=True), patch("scripts.system_changes.run", return_value=text):
            self.ops.rules = SystemOperations().firewall_rules()
        self.changes.apply_firewall(self.profile, "192.168.0.7/32")
        self.assertEqual(self.ops.actions, [])

    def test_ambiguous_profile_rule_cannot_be_relabelled(self):
        self.ops.rules = [{"unknown": "[ 1] CustomApp ALLOW IN 192.168.0.0/24 # existing app"}]
        with self.assertRaisesRegex(DeploymentError, "nepreznačilo"):
            self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.assertEqual(self.ops.actions, [])

    def test_unrelated_profile_with_different_source_is_left_untouched(self):
        unknown = {"unknown": "[ 1] OpenSSH ALLOW IN Anywhere # SSH"}
        self.ops.rules = [unknown]
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.cleanup()
        self.assertEqual(self.ops.rules, [unknown])

    def test_korunka_status_allows_app_rule_and_preserves_dns_dhcp_and_ssh(self):
        self.config["port"] = 1112
        self.config_path.write_text(json.dumps(self.config))
        self.profile = self.changes.profile(self.root, self.uid)
        original = self.parse_rules(KORUNKA_UFW_STATUS)
        self.ops.rules = copy.deepcopy(original)

        self.changes.apply_firewall(self.profile, "192.168.0.0/24")

        expected = {"port": 1112, "network": "192.168.0.0/24", "comment": "Poznamkovnik " + self.identity}
        self.assertEqual(self.ops.rules, original + [expected])
        self.assertEqual(self.ops.actions, [("firewall", expected, False)])
        receipt = self.changes.load(self.identity, self.uid)["changes"]["firewall"]
        self.assertTrue(receipt["changed"])
        self.assertEqual(receipt["status"], "applied")

        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.assertEqual(len(self.ops.actions), 1)
        self.assertEqual(len(self.ops.backups), 1)
        self.cleanup()
        self.assertEqual(self.ops.rules, original)
        self.assertEqual(self.ops.actions, [("firewall", expected, False), ("firewall", expected, True)])
        self.assertEqual(len(self.ops.backups), 2)

    def test_unrelated_numeric_ports_and_udp_are_left_opaque_and_untouched(self):
        for destination in ("53", "53/udp", "53 on enp1s0", "53/tcp on enp1s0",
                            "19111/udp", "19111/udp on enp1s0"):
            with self.subTest(destination=destination):
                original = self.parse_rules(f"Status: active\n[ 1] {destination} ALLOW IN 192.168.0.0/24 # foreign rule\n")
                self.assertIn("unknown", original[0])
                self.ops.rules = copy.deepcopy(original)
                self.changes.apply_firewall(self.profile, "192.168.0.0/24")
                self.assertEqual(self.ops.rules[:-1], original)
                self.cleanup()
                self.assertEqual(self.ops.rules, original)

    def test_same_port_ambiguous_protocol_interface_and_ranges_are_not_adopted(self):
        for destination in ("19111", "19111 on enp1s0", "19111/tcp on enp1s0",
                            "19111,19112/tcp", "19110:19112/tcp", "CustomApp"):
            with self.subTest(destination=destination):
                self.ops.rules = self.parse_rules(f"Status: active\n[ 1] {destination} ALLOW IN 192.168.0.0/24 # foreign rule\n")
                original = copy.deepcopy(self.ops.rules)
                with self.assertRaisesRegex(DeploymentError, "nepreznačilo"):
                    self.changes.apply_firewall(self.profile, "192.168.0.0/24")
                self.assertEqual(self.ops.rules, original)
                self.assertEqual(self.ops.actions, [])
                self.assertEqual(self.ops.backups, [])
                self.assertIsNone(self.changes.load(self.identity, self.uid))

    def test_ambiguous_rule_error_identifies_the_blocking_row_without_comment(self):
        self.ops.rules = self.parse_rules("Status: active\n[ 7] CustomApp ALLOW IN 192.168.0.0/24 # foreign comment\n")
        with self.assertRaises(DeploymentError) as error:
            self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.assertIn("[ 7] CustomApp ALLOW IN 192.168.0.0/24", str(error.exception))
        self.assertNotIn("foreign comment", str(error.exception))
        self.assertEqual(self.ops.actions, [])

    def test_opaque_owned_marker_cannot_authorize_removing_other_rule_formats(self):
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        for destination in ("19111", "19111/udp", "19111/tcp on enp1s0"):
            with self.subTest(destination=destination):
                self.ops.rules = self.parse_rules(f"Status: active\n[ 1] {destination} ALLOW IN 192.168.0.0/24 # Poznamkovnik {self.identity}\n")
                original = copy.deepcopy(self.ops.rules)
                self.cleanup()
                self.assertEqual(self.ops.rules, original)
                self.assertEqual(len(self.ops.actions), 1)
                self.assertEqual(len(self.ops.backups), 1)

    def test_unparseable_rule_still_blocks_without_any_firewall_mutation(self):
        self.ops.rules = [{"unknown": "[ 8] unrecognized firewall output"}]
        with self.assertRaisesRegex(DeploymentError, "nepreznačilo"):
            self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.assertEqual(self.ops.actions, [])
        self.assertEqual(self.ops.backups, [])

    def test_firewall_only_cleanup_never_queries_or_changes_owned_linger(self):
        self.changes.apply_linger(self.profile)
        other = {"port": 53, "network": "192.168.0.0/24", "comment": "Pi-hole"}
        self.ops.rules = [other]
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        linger = copy.deepcopy(self.changes.load(self.identity, self.uid)["changes"]["linger"])
        with patch.object(self.ops, "linger", side_effect=AssertionError("must not query linger")), patch.object(self.ops, "dependent_units", side_effect=AssertionError("must not query units")), patch.object(self.ops, "set_linger", side_effect=AssertionError("must not change linger")):
            self.cleanup(firewall_only=True)
        self.assertEqual(self.ops.rules, [other])
        self.assertTrue(self.ops.linger_value)
        receipt = self.changes.load(self.identity, self.uid)
        self.assertEqual(receipt["changes"]["linger"], linger)
        self.assertEqual(receipt["changes"]["firewall"]["status"], "removed")
        self.assertEqual(len(self.ops.backups), 3)
        self.assertEqual(self.ops.actions[-1][0], "firewall")
        self.assertTrue(self.ops.actions[-1][2])

    def test_firewall_can_be_removed_and_readded_for_a_different_network_without_linger_change(self):
        self.changes.apply_linger(self.profile)
        original = self.parse_rules(KORUNKA_UFW_STATUS)
        self.ops.rules = copy.deepcopy(original)
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        with self.assertRaisesRegex(DeploymentError, "iný alebo nedokončený"):
            self.changes.apply_firewall(self.profile, "192.168.0.9/32")
        self.cleanup(firewall_only=True)
        self.assertEqual(self.ops.rules, original)
        self.changes.apply_firewall(self.profile, "192.168.0.9/32")
        rule = self.changes.firewall_rule(self.profile, "192.168.0.9/32")
        self.assertEqual(self.ops.rules, original + [rule])
        self.assertEqual(self.changes.load(self.identity, self.uid)["changes"]["firewall"]["rule"], rule)
        self.assertTrue(self.ops.linger_value)
        self.assertEqual([action for action in self.ops.actions if action[0] == "linger"], [("linger", self.profile["user"], True)])

    def test_firewall_only_cleanup_keeps_preexisting_rule_and_linger(self):
        self.changes.apply_linger(self.profile)
        original = {"port": 19111, "network": "192.168.0.0/24", "comment": "shared application rule"}
        self.ops.rules = [original]
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        actions = copy.deepcopy(self.ops.actions)
        backups = list(self.ops.backups)
        self.cleanup(firewall_only=True)
        self.assertEqual(self.ops.rules, [original])
        self.assertEqual(self.ops.actions, actions)
        self.assertEqual(self.ops.backups, backups)
        self.assertTrue(self.ops.linger_value)

    def test_firewall_only_cleanup_leaves_modified_rule_untouched(self):
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        self.ops.rules[0]["comment"] = "modified by owner " + self.ops.rules[0]["comment"]
        original = copy.deepcopy(self.ops.rules)
        self.cleanup(firewall_only=True)
        self.assertEqual(self.ops.rules, original)
        self.assertEqual(len(self.ops.actions), 1)
        self.assertEqual(len(self.ops.backups), 1)

    def test_firewall_only_plan_reads_no_live_system_state_and_preserves_receipt(self):
        self.changes.apply_linger(self.profile)
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        receipt = self.registry / f"{self.identity}.json"
        before = receipt.read_bytes()
        with patch.object(self.ops, "firewall_rules", side_effect=AssertionError("plan must not query firewall")), patch.object(self.ops, "linger", side_effect=AssertionError("plan must not query linger")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.cleanup(firewall_only=True, plan_only=True)
        self.assertIn("firewall:", output.getvalue())
        self.assertNotIn("linger:", output.getvalue())
        self.assertEqual(receipt.read_bytes(), before)
        self.assertEqual(len(self.ops.actions), 2)
        self.assertEqual(len(self.ops.backups), 2)

    def test_firewall_only_decline_keeps_rule_and_receipt(self):
        self.changes.apply_firewall(self.profile, "192.168.0.0/24")
        receipt = self.registry / f"{self.identity}.json"
        before = receipt.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.changes.cleanup(self.identity, self.uid, approval=lambda prompt: False, firewall_only=True)
        self.assertIn("existujúce pravidlo zostáva zachované", output.getvalue())
        self.assertEqual(receipt.read_bytes(), before)
        self.assertEqual(len(self.ops.actions), 1)
        self.assertEqual(len(self.ops.backups), 1)

    def test_firewall_only_without_root_receipt_changes_nothing(self):
        self.cleanup(firewall_only=True)
        self.assertFalse(self.registry.exists())
        self.assertEqual(self.ops.actions, [])
        self.assertEqual(self.ops.backups, [])

    def test_remove_firewall_cli_routes_only_firewall_plan(self):
        uid = self.uid or 1
        profile = {key: self.profile[key] for key in ("root", "service", "port")}
        with patch.object(sys, "argv", ["system_changes.py", "remove-firewall", "--root", str(self.root), "--plan"]), patch.object(os, "geteuid", return_value=0), patch.dict(os.environ, {"SUDO_UID": str(uid)}), patch.object(system_module, "SystemChanges") as factory:
            changes = factory.return_value
            changes.profile.return_value = profile
            changes.load.return_value = profile
            self.assertEqual(system_module.main(), 0)
            changes.cleanup.assert_called_once_with(self.identity, uid, approval=system_module.confirm, plan_only=True, firewall_only=True)


if __name__ == "__main__":
    unittest.main()
