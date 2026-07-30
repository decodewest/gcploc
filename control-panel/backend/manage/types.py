"""Manage action specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class ActionSpec:
    id: str
    label: str
    handler: Callable[[dict[str, Any]], Any]
    destructive: bool = False
    confirm_field: str | None = None
    fields: list[dict[str, Any]] = field(default_factory=list)
