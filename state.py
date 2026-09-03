"""Conversation state: one BookingState per session, held in memory.

Merge rules matter more than anything else here: a value the guest has
already given is never overwritten by a null, and only an explicit new
value (or an explicit reset) can change it. That is what makes the state
survive a guest changing their mind."""

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

import dates


# Nothing is recommended until all of these are known. The agent never
# assumes a length of stay, a child count or an AC preference -- it asks,
# once, for everything still missing. `children` and `children_ages` are
# conditional: see BookingState.missing().
REQUIRED = ("check_in", "check_out", "adults", "children", "ac_preference")

# Accepted range per numeric slot, as (minimum, maximum). Anything the
# extraction layer returns outside its range is discarded, not clamped -- a
# wrong number silently corrected is worse than a slot left unknown.
LIMITS: dict[str, tuple[int, int]] = {
    "adults": (1, 30),
    "children": (0, 20),
    "rooms_wanted": (1, 10),
    "total_guests": (1, 40),
    "nights": (1, 30),
}


def _clean_int(value: object, low: int, high: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = int(value)
    return number if low <= number <= high else None


@dataclass
class BookingState:
    check_in: date | None = None
    check_out: date | None = None
    adults: int | None = None
    children: int | None = None
    children_ages: list[int] = field(default_factory=list)
    nights_wanted: int | None = None   # duration, survives a change of date
    party_size: int | None = None      # a vague headcount: "3 log hain"
    children_known: bool = False       # has the child question been settled?
    rooms_wanted: int | None = None
    ac_preference: str | None = None          # "ac" | "non_ac" | "any"
    special_requests: list[str] = field(default_factory=list)
    language: str = "en"                      # "en" | "hinglish"
    status: str = "gathering"                 # gathering | recommending | confirmed
    selected_option: dict | None = None
    awaiting_choice: bool = False      # the agent just asked "which option?"
    assumptions: list[str] = field(default_factory=list)   # rebuilt every turn
    date_note: str | None = None                           # how a fuzzy date was read
    last_offered: list[dict] = field(default_factory=list)

    # ---------- derived ----------

    @property
    def nights(self) -> int | None:
        if self.check_in and self.check_out:
            return (self.check_out - self.check_in).days
        return None

    def guest_count(self, free_child_cutoff: int) -> int:
        """Guests that need a bed. Children below the hotel's free-stay
        cutoff are not charged and are not counted against occupancy."""
        adults = self.adults or 0
        ages = self.children_ages
        if ages:
            paying_children = sum(1 for age in ages if age >= free_child_cutoff)
        else:
            # ages unknown -> count every child as needing a bed (never undersell)
            paying_children = self.children or 0
        return adults + paying_children

    def free_children(self, free_child_cutoff: int) -> int:
        return sum(1 for age in self.children_ages if age < free_child_cutoff)

    def missing(self) -> list[str]:
        """Required slots still unknown, in the order they read best in a
        question. The child slots are conditional: a guest who said "4 adults"
        has already answered them, a guest who said "4 of us" has not."""
        gaps: list[str] = []
        if self.check_in is None:
            gaps.append("check_in")
        if self.check_out is None:
            gaps.append("check_out")
        if self.adults is None:
            gaps.append("adults")
        elif not self.children_known:
            gaps.append("children")
        elif self.children and len(self.children_ages) < self.children:
            gaps.append("children_ages")
        if self.ac_preference is None:
            gaps.append("ac_preference")
        return gaps

    # ---------- merge ----------

    def apply(self, patch: dict, today: date, raw_message: str) -> list[str]:
        """Merge an extraction patch. Returns the list of slots that changed."""
        changed: list[str] = []

        if patch.get("reset"):
            fresh = BookingState(language=self.language)
            for key, value in asdict(fresh).items():
                setattr(self, key, value)
            self.check_in = self.check_out = None
            changed.append("reset")

        # Dates: deterministic parse of the raw text wins; the LLM's ISO
        # guess is only a fallback for phrasings the regexes do not cover.
        text_in, text_out, note = dates.resolve_from_text(raw_message, today)
        llm_in = dates.parse_iso(patch.get("check_in"))
        llm_out = dates.parse_iso(patch.get("check_out"))
        new_in = text_in or llm_in
        new_out = text_out or llm_out
        new_in, new_out = dates.sanitize(new_in, new_out, today)

        if new_in and new_in != self.check_in:
            self.check_in = new_in
            self.check_out = None          # a new arrival date invalidates the old departure
            changed.append("check_in")
            self.date_note = note
        if new_out and new_out != self.check_out and (not self.check_in or new_out > self.check_in):
            self.check_out = new_out
            changed.append("check_out")

        # How long the stay is, remembered separately from the dates. A guest
        # who says "2 nights" before naming a date, or who later moves the
        # date, is never asked for the duration twice.
        nights = (_clean_int(patch.get("nights"), *LIMITS["nights"])
                  or dates.nights_from_text(raw_message))
        if nights:
            self.nights_wanted = nights
        elif self.check_in and self.check_out:
            self.nights_wanted = (self.check_out - self.check_in).days

        if self.check_in and not self.check_out and self.nights_wanted:
            self.check_out = self.check_in + timedelta(days=self.nights_wanted)
            changed.append("check_out")

        # Validation: an extracted number outside these bounds is treated as a
        # misread and dropped rather than trusted. A model that returns
        # adults: 0 or rooms_wanted: 400 must not reach the pricing math.
        rooms = _clean_int(patch.get("rooms_wanted"), *LIMITS["rooms_wanted"])
        if rooms is not None and rooms != self.rooms_wanted:
            self.rooms_wanted = rooms
            changed.append("rooms_wanted")

        stated_adults = _clean_int(patch.get("adults"), *LIMITS["adults"])
        stated_children = _clean_int(patch.get("children"), *LIMITS["children"])
        stated_total = _clean_int(patch.get("total_guests"), *LIMITS["total_guests"])

        ages = patch.get("children_ages")
        if isinstance(ages, list) and ages:
            clean = [int(a) for a in ages
                     if isinstance(a, (int, float)) and not isinstance(a, bool) and 0 <= int(a) <= 17]
            if clean and clean != self.children_ages:
                self.children_ages = clean
                changed.append("children_ages")
                if stated_children is None or stated_children < len(clean):
                    stated_children = len(clean)

        # Any explicit statement about children settles the question -- and
        # "no kids" arrives here as a plain 0.
        if stated_children is not None:
            if stated_children != self.children:
                self.children = stated_children
                changed.append("children")
            self.children_known = True
            if stated_children == 0:
                self.children_ages = []

        if stated_total is not None and stated_total != self.party_size:
            self.party_size = stated_total
            changed.append("party_size")

        if stated_adults is not None:
            # "4 adults" names the grown-ups directly, so it also says there
            # are no children unless the guest mentioned some.
            if stated_adults != self.adults:
                self.adults = stated_adults
                changed.append("adults")
            self.party_size = None
            if self.children is None:
                self.children = 0
                changed.append("children")
            self.children_known = True
        elif self.party_size is not None:
            # A vague headcount ("3 log hain") is a total, not an adult count.
            # Adults are whatever is left once the children are known; until
            # then missing() keeps asking.
            derived = max(1, self.party_size - (self.children or 0))
            if derived != self.adults:
                self.adults = derived
                changed.append("adults")

        preference = patch.get("ac_preference")
        if preference in ("ac", "non_ac", "any") and preference != self.ac_preference:
            self.ac_preference = preference
            changed.append("ac_preference")

        requests = patch.get("special_requests")
        if isinstance(requests, list):
            for item in requests:
                if isinstance(item, str) and item.strip() and item not in self.special_requests:
                    self.special_requests.append(item.strip())
                    changed.append("special_requests")

        # Language is sticky: a guest who opens in Hinglish keeps getting
        # Hinglish even on a short message like "non-AC me kya rate hai",
        # which on its own does not look Hinglish enough to detect.
        language = patch.get("language")
        if language == "hinglish":
            self.language = "hinglish"
        elif language == "en" and self.language != "hinglish":
            self.language = "en"

        return changed

    # ---------- serialisation ----------

    def to_json(self) -> dict:
        return {
            "check_in": self.check_in.isoformat() if self.check_in else None,
            "check_out": self.check_out.isoformat() if self.check_out else None,
            "nights": self.nights,
            "party_size": self.party_size,
            "adults": self.adults,
            "children": self.children,
            "children_ages": self.children_ages,
            "rooms_wanted": self.rooms_wanted,
            "ac_preference": self.ac_preference,
            "special_requests": self.special_requests,
            "language": self.language,
        }
