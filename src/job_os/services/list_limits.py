"""Optional list caps — None or 0 means return all matching items."""

from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


def apply_limit(items: list[T], limit: int | None) -> list[T]:
    if limit is None or limit <= 0:
        return items
    return items[:limit]
