from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import json


@dataclass
class MacroEvent:
    type: str
    delay: float
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MacroEvent":
        return cls(
            type=value["type"],
            delay=float(value.get("delay", 0)),
            data=dict(value.get("data", {})),
        )


def save_macro(path: str, events: list[MacroEvent]) -> None:
    payload = {
        "version": 1,
        "events": [event.to_dict() for event in events],
    }
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def load_macro(path: str) -> list[MacroEvent]:
    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)
    return [MacroEvent.from_dict(item) for item in payload.get("events", [])]
