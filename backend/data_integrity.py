"""Read-only consistency checks for user-managed application files."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import Database
from .files import FileStore
from .radio_recording import RadioRecordingManager


class DataIntegrityService:
    """Checks file references without ever repairing or deleting user data."""

    def __init__(self, database: Database, files: FileStore, radio_recordings: RadioRecordingManager) -> None:
        self.database = database
        self.files = files
        self.radio_recordings = radio_recordings

    def inspect(self, user_id: str) -> dict[str, Any]:
        references_by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for reference in self.database.data_integrity_blob_references(user_id):
            blob_hash = str(reference.get("blob_hash") or "").lower()
            if blob_hash:
                references_by_hash[blob_hash].append(reference)

        issues: list[dict[str, Any]] = []
        verified_bytes = 0
        for blob_hash, references in references_by_hash.items():
            state = self.files.inspect_blob(blob_hash)
            verified_bytes += int(state.get("sizeBytes") or 0)
            for reference in references:
                expected_size = reference.get("expected_size_bytes")
                issue = self._blob_issue(state, expected_size)
                if issue:
                    issues.append(self._reference_issue(issue, reference))

        stored_entries = self.files.list_stored_blobs()
        globally_referenced = self.database.all_referenced_blob_hashes()
        orphan_count = sum(
            1
            for entry in stored_entries
            if not entry["canonical"] or str(entry["blobHash"]).lower() not in globally_referenced
        )
        if orphan_count:
            issues.append(
                {
                    "severity": "warning",
                    "kind": "orphan",
                    "title": "Nepriradené súbory v úložisku",
                    "detail": f"{orphan_count} súborov nie je naviazaných na žiadny uložený prvok.",
                    "targetType": "",
                    "targetId": "",
                }
            )

        radio_entries = self.database.data_integrity_radio_recordings(user_id)
        radio_bytes = 0
        for recording in radio_entries:
            state = self._inspect_radio_recording(user_id, recording)
            radio_bytes += state["sizeBytes"]
            expected_size = int(recording.get("size_bytes") or 0)
            if state["missing"]:
                issues.append(
                    self._recording_issue(
                        recording,
                        "missing",
                        "Nahrávka rádia sa v úložisku nenašla.",
                        "error",
                    )
                )
            elif expected_size and state["sizeBytes"] != expected_size:
                issues.append(
                    self._recording_issue(
                        recording,
                        "size_mismatch",
                        "Veľkosť nahrávky rádia sa nezhoduje so záznamom.",
                        "warning",
                    )
                )

        errors = sum(issue["severity"] == "error" for issue in issues)
        return {
            "status": "error" if errors else "warning" if issues else "ok",
            "checkedFiles": len(references_by_hash) + len(radio_entries),
            "storedFiles": len(stored_entries) + len(radio_entries),
            "storageBytes": verified_bytes + radio_bytes,
            "issues": issues,
            "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    @staticmethod
    def _blob_issue(state: dict[str, Any], expected_size: Any) -> tuple[str, str, str] | None:
        if state.get("status") == "missing":
            return ("missing", "Súbor sa v úložisku nenašiel.", "error")
        if state.get("status") in {"invalid", "hash_mismatch"}:
            return ("hash_mismatch", "Obsah súboru nezodpovedá jeho kontrolnému súčtu.", "error")
        try:
            expected = int(expected_size)
        except (TypeError, ValueError):
            return None
        if expected >= 0 and expected != int(state.get("sizeBytes") or 0):
            return ("size_mismatch", "Veľkosť súboru sa nezhoduje so záznamom.", "warning")
        return None

    @staticmethod
    def _reference_issue(issue: tuple[str, str, str], reference: dict[str, Any]) -> dict[str, Any]:
        kind, detail, severity = issue
        return {
            "severity": severity,
            "kind": kind,
            "title": str(reference.get("title") or "Neznámy prvok"),
            "detail": detail,
            "context": str(reference.get("detail") or ""),
            "targetType": str(reference.get("target_type") or ""),
            "targetId": str(reference.get("target_id") or ""),
        }

    def _inspect_radio_recording(self, user_id: str, recording: dict[str, Any]) -> dict[str, Any]:
        try:
            path = self.radio_recordings.path_for_recording(user_id, recording)
        except ValueError:
            return {"missing": True, "sizeBytes": 0}
        return {"missing": not path.is_file(), "sizeBytes": path.stat().st_size if path.is_file() else 0}

    @staticmethod
    def _recording_issue(recording: dict[str, Any], kind: str, detail: str, severity: str) -> dict[str, Any]:
        return {
            "severity": severity,
            "kind": kind,
            "title": str(recording.get("station_title") or "Nahrávka rádia"),
            "detail": detail,
            "context": str(recording.get("filename") or ""),
            "targetType": "",
            "targetId": "",
        }
