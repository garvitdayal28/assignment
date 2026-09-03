"""The final guest-facing reply, produced entirely in Python.

Every sentence here is assembled from inventory.json or from numbers
recommender.py computed, so no reply can contain a price, a room name or a
policy the hotel did not publish. The LLM is not in this path: it only told
us what the guest said. Replies are templated in English and Hinglish and
chosen off `state.language`.

Nothing in this module knows the hotel's name, room types or prices; it
reads them off the Inventory object it is handed.
"""

import re

import dates
from inventory import Inventory
from state import BookingState

# Synonyms for the policy topics almost every hotel publishes, including the
# Hinglish ones. Matched against whatever keys inventory.json actually
# contains, so a hotel with different keys still works.
POLICY_MATCHERS: list[tuple[str, str]] = [
    (r"early check[\s-]?in|early arrival|jaldi", "early_check_in"),
    (r"check[\s-]?in|arrival|kab aa", "check_in_time"),
    (r"check[\s-]?out|leave|departure|kab tak", "check_out_time"),
    (r"cancel|refund policy|cancellation", "cancellation"),
    (r"child|children|kid|bacch?e|baby|infant", "children_under_"),
]

# Words that carry no topic on their own, so they never make a key match.
KEY_STOPWORDS = {"free", "under", "time", "allowed", "policy", "charge",
                 "charges", "chargeable", "hours", "before", "after", "the"}

LABELS = {
    "en": {"cheapest": "Cheapest", "fewest_rooms": "Fewest rooms",
           "most_space": "Most space", "alternative": "Alternative",
           "best_fit": "Best fit"},
    "hinglish": {"cheapest": "Sabse sasta", "fewest_rooms": "Kam rooms",
                 "most_space": "Zyada space", "alternative": "Doosra option",
                 "best_fit": "Best fit"},
}

# How a date phrase was read. Not a default: the guest said something that
# named both ends of the stay, and this discloses how it was interpreted.
NOTES = {
    "en": {"weekend_sat_sun": "weekend means Saturday to Sunday, 1 night"},
    "hinglish": {"weekend_sat_sun": "weekend ka matlab Saturday se Sunday, 1 raat"},
}


def _lang(state: BookingState) -> str:
    return "hinglish" if state.language == "hinglish" else "en"


def _nights(count: int, language: str) -> str:
    if language == "hinglish":
        return f"{count} raat"
    return f"{count} night" if count == 1 else f"{count} nights"


def _guests(count: int, language: str) -> str:
    if language == "hinglish":
        return f"{count} guest"
    return f"{count} guest" if count == 1 else f"{count} guests"


# --------------------------------------------------------------------------
# asking for what is missing
# --------------------------------------------------------------------------

# The plain slots, joined into one "just tell me A, B and C" sentence.
ASKS = {
    "en": {
        "check_in": "which date you are arriving",
        "check_out": "how many nights you are staying",
        "adults": "how many guests are staying",
        "ac_preference": "whether you want AC or non-AC",
    },
    "hinglish": {
        "check_in": "kis date ko aa rahe hain",
        "check_out": "kitni raat rukna hai",
        "adults": "kitne guests hain",
        "ac_preference": "AC chahiye ya non-AC",
    },
}

# The child questions carry their own conjunction, so they get their own
# sentence rather than being joined into the list above.
CHILD_ASKS = {
    "en": {
        "children": "Are any of them children? If so, I need their ages.",
        "children_ages": "How old are the children?",
    },
    "hinglish": {
        "children": "Unme koi bachcha bhi hai? Agar hai to umar bhi bata dijiye.",
        "children_ages": "Bachche kitne saal ke hain?",
    },
}


def _join(items: list[str], language: str) -> str:
    final = "aur" if language == "hinglish" else "and"
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} {final} {items[-1]}"


def slot_question(state: BookingState, inv: Inventory) -> str:
    """One message asking for everything still missing -- never two.

    Every required slot the guest has not given is asked for in this single
    message, so filling them never costs more than one round trip.
    """
    language = _lang(state)
    missing = state.missing()
    hinglish = language == "hinglish"

    asks = [ASKS[language][slot] for slot in missing if slot in ASKS[language]]
    child_slot = next((slot for slot in missing if slot in CHILD_ASKS[language]), None)

    if not asks and not child_slot:
        return ("Stay ki details ek baar confirm kar dijiye." if hinglish
                else "Could you confirm the details of your stay?")

    lead = (f"{inv.hotel_name} mein room ke liye main help kar deta hoon." if hinglish
            else f"Happy to help with a room at {inv.hotel_name}.")
    parts = [lead]

    if asks:
        joined = _join(asks, language)
        parts.append(f"Bas bata dijiye {joined}." if hinglish else f"Just tell me {joined}.")

    if child_slot:
        parts.append(CHILD_ASKS[language][child_slot])
        # Say why the ages matter, using this hotel's own cutoff.
        cutoff = inv.free_child_age_cutoff
        if cutoff:
            parts.append(f"{cutoff} saal se chhote bachche free rehte hain." if hinglish
                         else f"Children under {cutoff} stay free.")

    return " ".join(parts)


# --------------------------------------------------------------------------
# recommending
# --------------------------------------------------------------------------

def describe_rooms(option: dict, language: str) -> str:
    """Room types come from inventory.json, so they stay verbatim."""
    parts = []
    for entry in option["rooms"]:
        text = f"{entry['count']}x {entry['type']}"
        beds = entry["extra_beds"]
        if beds:
            if language == "hinglish":
                text += f" (+{beds} extra bed)"
            else:
                text += f" (+{beds} extra bed{'s' if beds > 1 else ''})"
        parts.append(text)
    return " + ".join(parts)


def describe(option: dict, inv: Inventory, language: str = "en") -> str:
    rooms = describe_rooms(option, language)
    money = inv.money(option["total_price"])
    nights = _nights(option["nights"], language)
    if language == "hinglish":
        return f"{rooms} - total {money}, {nights} ke liye"
    return f"{rooms} - {money} total for {nights}"


def stay_line(state: BookingState, inv: Inventory, guests: int) -> str:
    language = _lang(state)
    joiner = " se " if language == "hinglish" else " to "
    parts = [dates.human(state.check_in) + joiner + dates.human(state.check_out)]
    parts.append(_nights(state.nights or 1, language))
    parts.append(_guests(guests, language))

    free = state.free_children(inv.free_child_age_cutoff)
    if free:
        cutoff = inv.free_child_age_cutoff
        if language == "hinglish":
            parts.append(f"{free} bachcha {cutoff} saal se chhota, free")
        else:
            parts.append(f"{free} child under {cutoff} stays free")

    if state.ac_preference == "ac":
        parts.append("AC")
    elif state.ac_preference == "non_ac":
        parts.append("non-AC")
    return ", ".join(parts)


def offer(state: BookingState, inv: Inventory, options: list[dict], guests: int) -> str:
    language = _lang(state)
    lines = [stay_line(state, inv, guests) + ":"]
    for option in options:
        label = LABELS[language].get(option["label"], option["label"])
        lines.append(f"{option['rank']}. {describe(option, inv, language)} ({label})")
    for key in state.assumptions:
        note = NOTES[language].get(key, key)
        if language == "hinglish":
            lines.append(f"({note} maan liya hai - galat ho to bata dijiye.)")
        else:
            lines.append(f"(Assumed {note} - tell me if that is wrong.)")
    lines.append("Inme se kaunsa hold karun?" if language == "hinglish"
                 else "Which one should I hold for you?")
    return "\n".join(lines)


def no_options(state: BookingState, inv: Inventory, guests: int) -> str:
    """Explain *why* nothing fits, and offer the one lever that helps."""
    import recommender

    language = _lang(state)
    preference = state.ac_preference
    nights = state.nights or 1

    if state.rooms_wanted:
        relaxed = recommender.recommend(inv, guests, nights, preference, None)
        if relaxed:
            quote = describe(relaxed[0], inv, language)
            if language == "hinglish":
                return (f"{guests} guests ke liye theek {state.rooms_wanted} room mein nahi ho payega, "
                        f"lekin {quote} ho jayega. Isse chalu karun?")
            return (f"For {guests} guests I cannot do it in exactly {state.rooms_wanted} "
                    f"room{'s' if state.rooms_wanted > 1 else ''}, but {quote} works. "
                    f"Shall I go with that?")

    if preference in ("ac", "non_ac"):
        other = "non_ac" if preference == "ac" else "ac"
        relaxed = recommender.recommend(inv, guests, nights, other)
        if relaxed:
            asked = "AC" if preference == "ac" else "non-AC"
            available = "non-AC" if other == "non_ac" else "AC"
            quote = describe(relaxed[0], inv, language)
            if language == "hinglish":
                return (f"Un dates par {guests} guests ke liye itne {asked} rooms free nahi hain. "
                        f"{available} mein {quote} ho jayega. Wo chalega?")
            return (f"I do not have enough {asked} rooms free for {guests} guests on those dates. "
                    f"In {available} I can do {quote}. Want that instead?")

    if language == "hinglish":
        return (f"Un dates par {guests} guests ke liye abhi kuch free nahi hai. "
                f"Dates flexible hain to doosri date bata dijiye, main phir check karta hoon.")
    return (f"I cannot fit {guests} guests on those dates with what is free right now. "
            f"If your dates are flexible, tell me another date and I will check again.")


# --------------------------------------------------------------------------
# confirming
# --------------------------------------------------------------------------

def reference(state: BookingState, inv: Inventory, option: dict) -> str:
    seed = (state.check_in.toordinal() * 31 + option["total_price"]) % 100000
    return f"{inv.hotel_id or 'BK'}-{seed:05d}"

def confirmation(state: BookingState, inv: Inventory, option: dict) -> str:
    language = _lang(state)
    rooms = describe_rooms(option, language)
    money = inv.money(option["total_price"])
    nights = _nights(option["nights"], language)
    ref = reference(state, inv, option)
    check_in, check_out = dates.human(state.check_in), dates.human(state.check_out)

    if language == "hinglish":
        lines = [f"Ho gaya - {rooms} hold kar liya {inv.hotel_name} mein, total {money} {nights} ke liye.",
                 f"{check_in} se {check_out}. Reference {ref}."]
        if inv.check_in_time:
            lines.append(f"Check-in {inv.check_in_time} se"
                         + (f", check-out {inv.check_out_time} tak." if inv.check_out_time else "."))
        if state.special_requests:
            lines.append("Note kar liya: " + "; ".join(state.special_requests) + ".")
        lines.append("Hotel aapko payment details ke liye call karega.")
        return "\n".join(lines)

    lines = [f"Done - holding {rooms} at {inv.hotel_name}, {money} total for {nights}.",
             f"{check_in} to {check_out}. Reference {ref}."]
    if inv.check_in_time:
        lines.append(f"Check-in from {inv.check_in_time}"
                     + (f", check-out by {inv.check_out_time}." if inv.check_out_time else "."))
    if state.special_requests:
        lines.append("Noted: " + "; ".join(state.special_requests) + ".")
    lines.append("The hotel will call you to take payment details.")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# questions that are not booking
# --------------------------------------------------------------------------

def _render_policy(key: str, value: object, language: str) -> str:
    if key == "check_in_time":
        return f"Check-in {value} se hai." if language == "hinglish" else f"Check-in is from {value}."
    if key == "check_out_time":
        return f"Check-out {value} tak hai." if language == "hinglish" else f"Check-out is by {value}."
    if key.startswith("children_under_") and value is True:
        age = re.search(r"(\d+)", key)
        age = age.group(1) if age else "?"
        return (f"{age} saal se chhote bachche free hain."
                if language == "hinglish" else f"Children under {age} stay free.")
    pretty = key.replace("_", " ").capitalize()
    if value is True:
        return f"{pretty}: yes."
    return f"{pretty}: {value}."


def _match_key_words(question: str, keys: list[str]) -> str | None:
    """Fallback used when there is no LLM: match the words in a policy key
    name against the question, so `pets_allowed` answers "pets?" on any
    hotel's inventory without a hardcoded pattern for it.

    Only a word that belongs to exactly one key counts. "check" appears in
    check_in_time, check_out_time and early_check_in, so it identifies
    nothing on its own and is left to the curated patterns above.
    """
    words = set(re.findall(r"[a-z]+", question.lower()))
    tokens_by_key = {
        key: {token for token in re.split(r"[_\d]+", key)
              if len(token) >= 4 and token not in KEY_STOPWORDS}
        for key in keys
    }
    shared: dict[str, int] = {}
    for tokens in tokens_by_key.values():
        for token in tokens:
            shared[token] = shared.get(token, 0) + 1

    for key, tokens in tokens_by_key.items():
        if any(token in words and shared[token] == 1 for token in tokens):
            return key
    return None


def answer_question(question: str, inv: Inventory, language: str = "en",
                    policy_key: str | None = None) -> tuple[str, bool]:
    """Answer only from inventory.json. Returns (text, answered).

    Three ways to find the right policy, in order of confidence: the key the
    LLM picked out of this hotel's own key list, the curated synonym patterns,
    then the words in the key names themselves. If none of them lands, we say
    we do not know and hand it to the hotel rather than guessing.
    """
    entries = inv.policy_entries()
    text = question.lower()

    if policy_key and policy_key in entries:
        return _render_policy(policy_key, entries[policy_key], language), True

    for pattern, key_prefix in POLICY_MATCHERS:
        if not re.search(pattern, text):
            continue
        for key, value in entries.items():
            if key.startswith(key_prefix):
                return _render_policy(key, value, language), True

    loose = _match_key_words(text, list(entries))
    if loose:
        return _render_policy(loose, entries[loose], language), True

    if language == "hinglish":
        return (f"{inv.hotel_name} ke liye ye mere paas confirm nahi hai, isliye main guess "
                f"nahi karunga - hotel ko bata deta hoon, wo aapko confirm kar denge."), False
    return (f"I do not have that confirmed for {inv.hotel_name}, so I would rather not guess - "
            f"I will pass it to the hotel and they will confirm."), False


def which_option(state: BookingState, count: int, picked: int | None = None) -> str:
    """The guest said yes without saying to what. Never pick for them."""
    hinglish = _lang(state) == "hinglish"
    if picked:
        return (f"Mere paas sirf {count} option hain - 1 se {count} mein se koi ek number bata dijiye."
                if hinglish else
                f"I only have {count} options - tell me a number from 1 to {count}.")
    return (f"Zaroor - {count} options mein se kaunsa? Number bata dijiye."
            if hinglish else
            f"Happy to - which of the {count} should I hold? Just give me the number.")


def nudge(state: BookingState) -> str:
    if state.status != "recommending":
        return ""
    if _lang(state) == "hinglish":
        return "Inme se koi ek final kar dun?"
    return "Shall I go ahead with one of the options above?"
