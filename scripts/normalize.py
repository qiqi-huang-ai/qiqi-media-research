"""Helpers for writing normalized research entities."""

from pathlib import Path
from typing import Iterable

from scripts.raw_store import write_jsonl


def write_normalized(root: str | Path, entity: str, records: Iterable[object]) -> Path:
    target = Path(root) / "normalized" / f"{entity}.jsonl"
    return write_jsonl(target, records)
