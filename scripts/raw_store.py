"""Append-only storage for raw responses and normalized JSONL records."""

from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import secrets
from typing import Iterable, Mapping, Any


_SAFE_PART = re.compile(r"[^a-zA-Z0-9_-]+")


def _safe_part(value: str) -> str:
    cleaned = _SAFE_PART.sub("-", value).strip("-")
    if not cleaned:
        raise ValueError("path component must contain a letter or number")
    return cleaned


class RawStore:
    """Save each raw response under a unique path without overwriting."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def save(self, platform: str, operation: str, payload: Mapping[str, Any]) -> Path:
        target_dir = self.root / "raw" / _safe_part(platform)
        target_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        while True:
            suffix = secrets.token_hex(3)
            target = target_dir / f"{_safe_part(operation)}-{timestamp}-{suffix}.json"
            try:
                with target.open("x", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                return target
            except FileExistsError:
                continue


def write_jsonl(path: str | Path, records: Iterable[object]) -> Path:
    """Write dataclasses or mapping records as UTF-8 JSON Lines."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            if is_dataclass(record) and not isinstance(record, type):
                value = asdict(record)
            elif isinstance(record, Mapping):
                value = dict(record)
            else:
                raise TypeError("JSONL records must be dataclass instances or mappings")
            handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
    return target
