"""Shared adapter contract primitives."""

from dataclasses import dataclass
from typing import Any, Generic, TypeVar


T = TypeVar("T")


@dataclass(slots=True)
class Page(Generic[T]):
    items: list[T]
    next_cursor: str | None
    has_more: bool
    raw: dict[str, Any]
