"""Hotel inventory loading. Nothing hotel-specific lives in code -- it all
comes from inventory.json, including how many rooms exist and what the
'children under N stay free' cutoff is."""

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Room:
    type: str
    price: int
    available: int
    base_occupancy: int
    max_occupancy: int
    extra_bed_price: int
    ac: bool

    @property
    def extra_bed_capacity(self) -> int:
        return max(0, self.max_occupancy - self.base_occupancy)


class Inventory:
    def __init__(self, data: dict[str, Any]):
        self.raw = data
        self.hotel_id = data.get("hotel_id", "")
        self.hotel_name = data.get("hotel_name", "the hotel")
        self.currency = data.get("currency", "INR")
        self.check_in_time = data.get("check_in_time")
        self.check_out_time = data.get("check_out_time")
        self.policies: dict[str, Any] = data.get("policies", {}) or {}
        self.rooms: list[Room] = [
            Room(
                type=r["type"],
                price=int(r["price"]),
                available=int(r.get("available", 0)),
                base_occupancy=int(r.get("base_occupancy", 1)),
                max_occupancy=int(r.get("max_occupancy", r.get("base_occupancy", 1))),
                extra_bed_price=int(r.get("extra_bed_price", 0)),
                ac=bool(r.get("ac", False)),
            )
            for r in data.get("rooms", [])
        ]

    @classmethod
    def load(cls, path: str = "inventory.json") -> "Inventory":
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh))

    @property
    def free_child_age_cutoff(self) -> int:
        """Read 'children_under_5_free': true as a cutoff of 5, without
        hardcoding the number 5. Returns 0 when no such policy exists."""
        for key, value in self.policies.items():
            match = re.fullmatch(r"children_under_(\d+)_free", key)
            if match and value:
                return int(match.group(1))
        return 0

    @property
    def has_ac_rooms(self) -> bool:
        return any(r.ac and r.available > 0 for r in self.rooms)

    @property
    def has_non_ac_rooms(self) -> bool:
        return any(not r.ac and r.available > 0 for r in self.rooms)

    def rooms_for_preference(self, preference: str | None) -> list[Room]:
        rooms = [r for r in self.rooms if r.available > 0]
        if preference == "ac":
            return [r for r in rooms if r.ac]
        if preference == "non_ac":
            return [r for r in rooms if not r.ac]
        return rooms

    def money(self, amount: int) -> str:
        symbol = {"INR": "Rs ", "USD": "$", "EUR": "€"}.get(self.currency, self.currency + " ")
        return f"{symbol}{amount:,}"

    def policy_entries(self) -> dict[str, object]:
        """Raw facts the agent is allowed to state as hotel policy. Values are
        returned verbatim; response.py decides how they read."""
        entries: dict[str, object] = {}
        if self.check_in_time:
            entries["check_in_time"] = self.check_in_time
        if self.check_out_time:
            entries["check_out_time"] = self.check_out_time
        for key, value in self.policies.items():
            if isinstance(value, bool):
                if value:
                    entries[key] = True
            else:
                entries[key] = value
        return entries
