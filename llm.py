"""The only module that talks to the LLM, and in the default pipeline it has
exactly one job: understand the guest.

  extract()  -- turn a free-text (English or Hinglish) message into a flat,
                structured slot patch: dates, adults, children and their
                ages, room count, AC preference, special requests, intent,
                preference changes, language. No arithmetic, no availability
                lookups, no prices, no decisions.

Everything after that is deterministic Python, including the wording of the
guest-facing reply (see response.py).

  phrase()   -- an OPTIONAL polish pass, off unless REPLY_STYLING=1. It may
                only re-word a reply Python already wrote, and its output is
                discarded if any price in it changed. Nothing depends on it.

If the API key is missing or a call fails, extract() falls back to a regex
extractor, so the agent still runs end to end offline.
"""

import json
import os
import re
from datetime import date

# The task sheet mentions gemini-2.5-flash; that model now returns 404 for
# newly created API keys ("no longer available to new users"), so the default
# here is a current Flash model. Override with GEMINI_MODEL if you have a key
# that can still reach 2.5.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Fail fast instead of letting the SDK retry a 503 for minutes -- a timeout
# just means this turn is answered by the rule-based fallback.
TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS", "20000"))

# Off by default: the guest-facing reply is written by response.py. Set
# REPLY_STYLING=1 to let the model re-word it (facts still guarded).
REPLY_STYLING = os.environ.get("REPLY_STYLING", "0") not in ("0", "", "false", "False")

_client = None
_client_error: str | None = None
_last_error: str | None = None


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def client():
    global _client, _client_error
    if _client is not None or _client_error is not None:
        return _client
    _load_dotenv()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        _client_error = "GEMINI_API_KEY not set"
        return None
    try:
        from google import genai
        from google.genai import types
        _client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)),
        )
    except Exception as exc:  # noqa: BLE001
        _client_error = f"{type(exc).__name__}: {exc}"
    return _client


def llm_status() -> str:
    if client() is None:
        return f"offline ({_client_error})"
    return f"degraded ({_last_error})" if _last_error else "ready"


def _generate(prompt: str, system: str, as_json: bool) -> str | None:
    """Returns None on any failure -- the caller always has a fallback."""
    global _last_error
    cli = client()
    if cli is None:
        return None
    from google.genai import types

    def config(thinking: bool):
        return types.GenerateContentConfig(
            system_instruction=system,
            temperature=0 if as_json else 0.4,
            response_mime_type="application/json" if as_json else "text/plain",
            # Gemini 3.x thinks by default, which costs seconds we do not need
            # for slot filling or rephrasing.
            thinking_config=None if thinking else types.ThinkingConfig(thinking_budget=0),
        )

    for thinking in (False, True):
        try:
            response = cli.models.generate_content(model=MODEL, contents=prompt, config=config(thinking))
            _last_error = None
            return (response.text or "").strip() or None
        except Exception as exc:  # noqa: BLE001
            _last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
            if "thinking" not in str(exc).lower():
                break
    return None


# --------------------------------------------------------------------------
# 1. extraction
# --------------------------------------------------------------------------

EXTRACT_SYSTEM = """You are the language layer of a hotel booking agent.
Convert the guest's latest message into JSON. You never do arithmetic,
never invent prices, never decide availability.

Return exactly this shape, using null for anything the message does not
mention. Do NOT repeat values the guest did not just state.

{
  "intent": "booking" | "policy" | "out_of_scope" | "confirm" | "reset" | "chitchat",
  "check_in": "YYYY-MM-DD" or null,
  "check_out": "YYYY-MM-DD" or null,
  "nights": integer or null,
  "adults": integer or null,
  "total_guests": integer or null,
  "children": integer or null,
  "children_ages": list of integers or null,
  "rooms_wanted": integer or null,
  "ac_preference": "ac" | "non_ac" | "any" | null,
  "special_requests": list of strings or null,
  "question": string or null,
  "policy_key": string or null,
  "selected_option": integer or null,
  "reset": true or false,
  "language": "en" | "hinglish"
}

Rules:
- "adults" counts adults only, and ONLY when the guest actually says adults
  ("4 adults", "2 grown-ups"). A combined headcount — "we are 7", "3 log
  hain", "4 of us", "party of 5" — goes in "total_guests" and NOT in
  "adults", because it does not say how many of them are children.
- "children": the number of children. Return 0 when the guest says there are
  none ("no kids", "all adults", "koi bachcha nahi", "sirf adults"). Return
  null when they simply have not said. "children_ages" whenever ages are
  given, in years, one per child.
- The "Agent just asked for" line tells you what the guest is replying to. A
  bare "2" answering a nights question is nights; "4 and 6" answering a
  children question is children_ages; "no" answering it is children 0.
- "rooms_wanted" only when the guest states a number of rooms. "a room",
  "room chahiye", "rooms available?" are NOT a room count -- return null and
  let the booking engine decide how many rooms the party needs.
- Hinglish: kal = tomorrow, parso = day after tomorrow, log/jane = people,
  kamra/room = room, chahiye = need, raat/din = night, bina AC = non-AC,
  rate/kitna = price question, haan/theek hai = yes.
- intent "policy" when the guest asks about something this hotel has actually
  published a policy for; intent "out_of_scope" for any other non-booking
  question (pool, taxi, food, wifi, gym). Put the guest's question in
  "question" for both.
- "policy_key": the hotel's published policy the question is about, copied
  EXACTLY from the "Hotel policy keys" list in the user message. Match on
  meaning, not wording -- "can I bring my dog" is the pets policy, "when can
  I get in" is the check-in time. Return null if no key on that list answers
  the question. Never invent a key that is not on the list. You are choosing
  a key only; you never write the policy text.
- Anything about room prices, rates, availability or room types is intent
  "booking", never "policy" or "out_of_scope". "non-AC me kya rate hai" is a
  booking message with ac_preference "non_ac".
- intent "confirm" only when the guest accepts an option; put the option
  number in "selected_option" if they named one.
- "reset": true only when the guest abandons this trip and starts a new one.
- Preference changes are normal: if the guest asked for AC earlier and now
  asks about non-AC, return ac_preference "non_ac".
"""

HINGLISH_TOKENS = re.compile(
    r"\b(kal|kl|parso|aaj|chahiye|chaiye|hai|hain|kya|kyaa|mein|me|hum|humein|"
    r"log|jane|kamra|kamre|kitna|kitne|kitni|rate|bina|nahi|haan|theek|thik|bhai|"
    r"milega|mil|karo|kar|liye|wala|wale|raat|din|se|tak|bhi|acha|achha|"
    r"saal|ka|ki|ke|bachcha|bachche|nahi|sirf)\b",
    re.I,
)
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10, "ek": 1, "do": 2,
             "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
             "chhe": 6, "saat": 7}

NUMBER = (r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|ek|do|teen"
          r"|chaar|char|paanch|panch|chhe|saat)")


def _num(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return NUM_WORDS.get(token)


def _heuristic_extract(message: str, awaiting: list[str]) -> dict:
    """Offline fallback and safety net. Deliberately conservative."""
    text = message.lower()
    patch: dict = {}
    child_match = None

    # A bare number means whatever was just asked for. Without that context
    # "2" is unreadable: nights, guests or an option number.
    bare = re.fullmatch(r"\W*(\d{1,2})\W*", text.strip())
    if bare and awaiting:
        value = int(bare.group(1))
        slot = awaiting[0]
        if slot == "selected_option":
            patch["selected_option"] = value
        elif slot == "check_out":
            patch["nights"] = value
        elif slot == "adults":
            # "how many guests?" answered with a bare number is a headcount,
            # not an adult count -- the child question still has to be asked.
            patch["total_guests"] = value
        elif slot == "children":
            patch["children"] = value
        elif slot == "children_ages":
            patch["children_ages"] = [value]

    match = re.search(NUMBER + r"\s*(rooms?|kamra|kamre)", text)
    if match:
        patch["rooms_wanted"] = _num(match.group(1))

    if re.search(r"\b(no kids?|no children|without kids|all adults?|only adults?|"
                 r"just adults?|sirf adults?|koi bachcha nahi|bachche nahi)\b", text):
        patch["children"] = 0
    else:
        child_match = re.search(
            NUMBER + r"\s*(kids?|child|children|bacch?[ae]|bach?che|bach?cha)", text)
        if child_match:
            patch["children"] = _num(child_match.group(1))

    # Ages: "aged 4 and 6", "4 saal ka", "3 and 7 years old", "4 aur 6 saal".
    # Once an age word is present, every small number after the child count is
    # an age -- matching each number to its own unit misses "4 aur 6 saal".
    found: list[int] = []
    ages = re.search(r"ages?d?\s*([\d\s,and&]+)", text)
    if ages:
        found = [int(a) for a in re.findall(r"\d{1,2}", ages.group(1)) if int(a) <= 17]
    if not found:
        tail = text[child_match.end():] if child_match else text
        if re.search(r"saal|years?\b|yrs?\b|y\.?o\.?|umar", tail):
            found = [int(a) for a in re.findall(r"\d{1,2}", tail) if int(a) <= 17]
    if found:
        patch["children_ages"] = found

    match = re.search(NUMBER + r"\s*(adults?|grown[- ]?ups?)", text)
    if match:
        patch["adults"] = _num(match.group(1))
    else:
        match = (re.search(r"(?:we are|we r|hum)\s*" + NUMBER, text)
                 or re.search(NUMBER + r"\s*(people|person|persons|pax|guests?|log|jane|"
                                        r"banda|bande|of us)", text))
        if match:
            patch["total_guests"] = _num(match.group(1))

    if re.search(r"non[\s-]?ac|without ac|bina ac|no ac", text):
        patch["ac_preference"] = "non_ac"
    elif re.search(r"koi bhi|kuch bhi|any(thing)? (is )?fine|anything works|"
                   r"does ?n.t matter|no preference|whatever", text):
        patch["ac_preference"] = "any"
    elif re.search(r"\bac\b|a\.c\.|air[- ]?cond", text):
        patch["ac_preference"] = "ac"

    if re.search(r"\b(swimming pool|pool|taxi|cab|wifi|breakfast|food|restaurant|"
                 r"parking|refund|gym|spa|pickup|laundry)\b", text):
        patch["intent"] = "out_of_scope"
        patch["question"] = message.strip()
    elif re.search(r"\b(check[\s-]?in|check[\s-]?out|cancel|cancellation|policy|"
                   r"early check)\b", text):
        patch["intent"] = "policy"
        patch["question"] = message.strip()

    match = re.search(r"\b(?:option|number|no\.?)\s*(\d)\b", text)
    if match:
        patch["selected_option"] = int(match.group(1))
    if re.search(r"\b(book|booking|confirm|kar do|karo|haan|yes|theek hai|thik hai|"
                 r"ok done|go ahead|lock it)\b", text):
        patch.setdefault("intent", "confirm")

    patch["language"] = "hinglish" if len(HINGLISH_TOKENS.findall(text)) >= 2 else "en"
    return patch


def _coerce(raw: str | None) -> dict:
    if not raw:
        return {}
    text = raw.strip()
    if text.startswith("``"):
        text = re.sub(r"^`{3}[a-z]*\s*", "", text)
        text = re.sub(r"\s*`{3}$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def extract(message: str, state_json: dict, today: date,
            policy_keys: list[str] | None = None,
            awaiting: list[str] | None = None) -> dict:
    """Heuristics form the base; anything the LLM returns overrides them.

    `policy_keys` are the policy names this hotel actually published. The
    model may pick one of them, which is how a question like "can I bring my
    dog" reaches a `pets_allowed` policy -- it chooses the key, Python states
    the value.
    """
    patch = _heuristic_extract(message, awaiting or [])
    prompt = (
        f"Today is {today.isoformat()} ({today.strftime('%A')}).\n"
        f"Hotel policy keys: {json.dumps(policy_keys or [])}\n"
        f"Known state so far: {json.dumps(state_json)}\n"
        f"Agent just asked for: {json.dumps(awaiting or [])}\n"
        f"Guest message: {message}"
    )
    llm_patch = _coerce(_generate(prompt, EXTRACT_SYSTEM, as_json=True))
    for key, value in llm_patch.items():
        if value is not None and value != [] and value != "":
            patch[key] = value
    # Never trust a key the hotel did not publish.
    if patch.get("policy_key") not in (policy_keys or []):
        patch.pop("policy_key", None)
    patch["_source"] = "llm+rules" if llm_patch else "rules-only"
    return patch


# --------------------------------------------------------------------------
# 2. phrasing
# --------------------------------------------------------------------------

PHRASE_SYSTEM = """You are the voice of a hotel's WhatsApp booking assistant.
You will be given a draft reply that is already factually correct.

Rewrite it to sound like a warm, brisk human on WhatsApp. Hard rules:
- Never add, remove or change a fact: no new prices, dates, room names,
  totals or policies. Keep every number exactly as written.
- Keep it short. Never pad.
- If language is "hinglish", reply in casual romanised Hinglish. Otherwise
  reply in plain English.
- Keep option lines on separate lines, numbered exactly as in the draft.
- No "Dear guest", no markdown headings, no sign-off, and no emoji unless
  the guest used one first.
Return only the rewritten message.
"""


def phrase(draft: str, language: str) -> str:
    out = _generate(f"language: {language}\n\ndraft:\n{draft}", PHRASE_SYSTEM, as_json=False)
    if not out:
        return draft
    # Guard: the rephrasing must carry exactly the same prices. Small numbers
    # are ignored because "04 Sep" -> "4 Sep" is a harmless reformat, but any
    # invented or dropped price sends us back to the deterministic draft.
    def prices(text: str) -> set[int]:
        return {int(token.replace(",", "")) for token in re.findall(r"\d[\d,]*", text)
                if int(token.replace(",", "")) >= 100}

    if prices(out) != prices(draft):
        return draft
    return out
