"""Deterministic date resolution. The LLM is allowed to *guess* ISO dates,
but this module has the final say -- so a model that says "2025-09-15" for
"15th" in September 2026 can never leak a past date into a quote."""

import re
from datetime import date, timedelta

TODAY_WORDS = r"(today|aaj|tonight|abhi|aj)"
TOMORROW_WORDS = r"(tomorrow|tommorow|tmrw|kal|kl)"
DAY_AFTER_WORDS = r"(day after tomorrow|parso|parson)"
WEEKEND_WORDS = r"weekend"
NIGHTS_RE = re.compile(r"(\d+)\s*(nights?|raat|ratein|raatein|din|days?)", re.I)
RANGE_RE = re.compile(
    r"(\d{1,2})\s*(?:st|nd|rd|th)?\s*(?:to|till|until|-|se|–|—)\s*(\d{1,2})\s*(?:st|nd|rd|th)?",
    re.I,
)
SINGLE_DAY_RE = re.compile(r"\b(\d{1,2})\s*(?:st|nd|rd|th)\b", re.I)


def _has(pattern: str, text: str) -> bool:
    return re.search(r"\b" + pattern + r"\b", text, re.I) is not None


def next_weekday(today: date, weekday: int, allow_today: bool = True) -> date:
    """weekday: Monday=0 ... Sunday=6."""
    delta = (weekday - today.weekday()) % 7
    if delta == 0 and not allow_today:
        delta = 7
    return today + timedelta(days=delta)


def roll_forward(day_of_month: int, today: date) -> date | None:
    """'15th' -> the next 15th that has not passed yet."""
    for month_offset in (0, 1, 2):
        month = today.month + month_offset
        year = today.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        try:
            candidate = date(year, month, day_of_month)
        except ValueError:
            continue
        if candidate >= today:
            return candidate
    return None


def parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except (ValueError, AttributeError):
        return None


def nights_from_text(text: str) -> int | None:
    match = NIGHTS_RE.search(text)
    if not match:
        return None
    count = int(match.group(1))
    return count if 1 <= count <= 30 else None


def resolve_from_text(text: str, today: date) -> tuple[date | None, date | None, str | None]:
    """Return (check_in, check_out, note_key) parsed purely from the raw
    message. `note_key` names an assumption for response.py to word.
    Returns (None, None, None) when no date expression is recognised."""
    text = text.lower()

    range_match = RANGE_RE.search(text)
    if range_match and not re.search(r"\d+\s*(guests?|adults?|people|log|pax|rooms?|kids?)", range_match.group(0), re.I):
        start, end = int(range_match.group(1)), int(range_match.group(2))
        if 1 <= start <= 31 and 1 <= end <= 31 and end != start:
            check_in = roll_forward(start, today)
            check_out = roll_forward(end, today)
            if check_in and check_out:
                if check_out <= check_in:
                    check_out = roll_forward(end, check_in + timedelta(days=1))
                return check_in, check_out, None

    if _has(DAY_AFTER_WORDS, text):
        check_in = today + timedelta(days=2)
    elif _has(TOMORROW_WORDS, text):
        check_in = today + timedelta(days=1)
    elif _has(TODAY_WORDS, text):
        check_in = today
    elif re.search(WEEKEND_WORDS, text, re.I):
        saturday = next_weekday(today, 5)
        if re.search(r"next\s+weekend", text, re.I):
            saturday += timedelta(days=7)
        return saturday, saturday + timedelta(days=1), "weekend_sat_sun"
    else:
        single = SINGLE_DAY_RE.search(text)
        if single and 1 <= int(single.group(1)) <= 31:
            check_in = roll_forward(int(single.group(1)), today)
        else:
            return None, None, None

    if check_in is None:
        return None, None, None
    nights = nights_from_text(text)
    if nights:
        return check_in, check_in + timedelta(days=nights), None
    return check_in, None, None


def sanitize(check_in: date | None, check_out: date | None, today: date) -> tuple[date | None, date | None]:
    """Never quote a date in the past; never quote a non-positive stay."""
    if check_in and check_in < today:
        check_in = roll_forward(check_in.day, today) or today
        check_out = None
    if check_in and check_out and check_out <= check_in:
        check_out = None
    return check_in, check_out


def human(day: date | None) -> str:
    return f"{day.day} {day:%b}" if day else "?"
