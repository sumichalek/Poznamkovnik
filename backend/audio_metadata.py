from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    from mutagen import File as MutagenFile
except ImportError:  # The player remains usable even when metadata support is not installed yet.
    MutagenFile = None


def _value(tags: Any, key: str, maximum: int) -> str:
    if not tags:
        return ""
    raw = tags.get(key, "")
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else ""
    return str(raw or "").strip()[:maximum]


def read_audio_metadata(path: Path) -> dict[str, Any]:
    """Read common, user-facing tags without making audio upload depend on them."""

    metadata: dict[str, Any] = {
        "title": "",
        "artist": "",
        "album": "",
        "year": "",
        "genre": "",
        "trackNumber": "",
        "durationSeconds": 0.0,
    }
    if MutagenFile is None:
        return metadata
    try:
        audio = MutagenFile(path, easy=True)
    except Exception:
        return metadata
    if not audio:
        return metadata

    tags = getattr(audio, "tags", None)
    metadata["title"] = _value(tags, "title", 240)
    metadata["artist"] = _value(tags, "artist", 160)
    metadata["album"] = _value(tags, "album", 160)
    metadata["genre"] = _value(tags, "genre", 120)
    metadata["trackNumber"] = _value(tags, "tracknumber", 24).split("/", 1)[0]
    date_value = _value(tags, "date", 32)
    year_match = re.search(r"\b(\d{4})\b", date_value)
    metadata["year"] = year_match.group(1) if year_match else date_value[:12]

    duration = getattr(getattr(audio, "info", None), "length", 0)
    try:
        metadata["durationSeconds"] = max(0.0, min(43_200.0, round(float(duration), 3)))
    except (TypeError, ValueError):
        pass
    return metadata
