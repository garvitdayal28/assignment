"""Room-combination search and pricing. Pure deterministic Python -- the
LLM never sees a number it has to add up.

A combination is a multiset of room types. For each combination we place
guests into base occupancy first, then buy extra beds (cheapest first)
for whoever is left over. A combination is rejected if it cannot seat
everyone, or if any single room in it is redundant."""

from itertools import product

from inventory import Inventory, Room

MAX_ROOMS_PER_COMBO = 5


def _price_combo(rooms: list[Room], guests: int, nights: int) -> dict | None:
    base_capacity = sum(r.base_occupancy for r in rooms)
    max_capacity = sum(r.max_occupancy for r in rooms)
    if max_capacity < guests:
        return None

    extra_beds_needed = max(0, guests - base_capacity)
    extra_bed_cost = 0
    beds_by_type: dict[str, int] = {}
    # cheapest extra beds first
    for room in sorted(rooms, key=lambda r: r.extra_bed_price):
        if extra_beds_needed == 0:
            break
        take = min(room.extra_bed_capacity, extra_beds_needed)
        if take:
            extra_bed_cost += take * room.extra_bed_price
            beds_by_type[room.type] = beds_by_type.get(room.type, 0) + take
            extra_beds_needed -= take
    if extra_beds_needed > 0:
        return None

    room_cost = sum(r.price for r in rooms)
    per_night = room_cost + extra_bed_cost
    counts: dict[str, int] = {}
    for room in rooms:
        counts[room.type] = counts.get(room.type, 0) + 1

    return {
        "rooms": [{"type": t, "count": c, "extra_beds": beds_by_type.get(t, 0)} for t, c in counts.items()],
        "room_count": len(rooms),
        "extra_beds": sum(beds_by_type.values()),
        "per_night": per_night,
        "nights": nights,
        "total_price": per_night * nights,
        "capacity": max_capacity,
        "spare_capacity": max_capacity - guests,
        "all_ac": all(r.ac for r in rooms),
        "any_ac": any(r.ac for r in rooms),
    }


def _is_minimal(rooms: list[Room], guests: int) -> bool:
    """Reject combos carrying a room nobody needs."""
    if len(rooms) == 1:
        return True
    max_capacity = sum(r.max_occupancy for r in rooms)
    return all(max_capacity - room.max_occupancy < guests for room in rooms)


def recommend(inv: Inventory, guests: int, nights: int, ac_preference: str | None,
              rooms_wanted: int | None = None, limit: int = 3) -> list[dict]:
    pool = inv.rooms_for_preference(ac_preference)
    if not pool or guests <= 0 or nights <= 0:
        return []

    room_cap = rooms_wanted if rooms_wanted else min(MAX_ROOMS_PER_COMBO, guests)
    ranges = [range(0, min(r.available, room_cap) + 1) for r in pool]

    priced: list[dict] = []
    for counts in product(*ranges):
        total_rooms = sum(counts)
        if total_rooms == 0 or total_rooms > room_cap:
            continue
        if rooms_wanted and total_rooms != rooms_wanted:
            continue
        rooms = [room for room, count in zip(pool, counts) for _ in range(count)]
        if not rooms_wanted and not _is_minimal(rooms, guests):
            continue
        option = _price_combo(rooms, guests, nights)
        if option:
            priced.append(option)

    # cheapest first, then fewest rooms, then least wasted capacity
    priced.sort(key=lambda o: (o["total_price"], o["room_count"], o["spare_capacity"]))

    # one option per distinct room mix, so the guest sees three real choices
    seen: set[tuple] = set()
    shortlist: list[dict] = []
    for option in priced:
        signature = tuple(sorted((r["type"], r["count"]) for r in option["rooms"]))
        if signature in seen:
            continue
        seen.add(signature)
        shortlist.append(option)
        if len(shortlist) == limit:
            break

    _label(shortlist)
    return shortlist


def _label(shortlist: list[dict]) -> None:
    """Give each option a distinct reason to exist. The label is a stable key;
    response.py owns how it reads in each language."""
    if len(shortlist) == 1:
        shortlist[0]["rank"] = 1
        shortlist[0]["label"] = "best_fit"
        return
    roomiest = max(shortlist, key=lambda o: (o["spare_capacity"], -o["total_price"]))
    fewest = min(shortlist, key=lambda o: (o["room_count"], o["total_price"]))
    used: set[str] = set()
    for index, option in enumerate(shortlist):
        option["rank"] = index + 1
        if index == 0:
            label = "cheapest"
        elif option is fewest and "fewest_rooms" not in used:
            label = "fewest_rooms"
        elif option is roomiest and option["spare_capacity"] > shortlist[0]["spare_capacity"]:
            label = "most_space"
        else:
            label = "alternative"
        used.add(label)
        option["label"] = label
