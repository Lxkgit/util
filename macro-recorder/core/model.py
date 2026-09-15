from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class MacroEvent:
    type: str
    delay: float
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MacroEvent":
        return cls(value["type"], float(value.get("delay", 0)), dict(value.get("data", {})))


def save_macro(path: str, events: list[MacroEvent]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump({"version": 2, "events": [event.to_dict() for event in events]}, file, ensure_ascii=False, indent=2)


def load_macro(path: str) -> list[MacroEvent]:
    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)
    return [MacroEvent.from_dict(item) for item in payload.get("events", [])]
