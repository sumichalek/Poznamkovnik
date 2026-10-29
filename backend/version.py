from __future__ import annotations

import json
import re
from pathlib import Path


def release_info(base_dir: Path) -> dict[str, str | None]:
    version = (base_dir / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", version):
        raise ValueError("Súbor VERSION nemá platnú verziu.")
    commit = None
    metadata_path = base_dir / ".release.json"
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        candidate = str(metadata.get("commit", ""))
        if re.fullmatch(r"[0-9a-f]{40,64}", candidate):
            commit = candidate
    return {"version": version, "commit": commit}
