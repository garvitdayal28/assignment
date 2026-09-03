# Hotel Booking Agent

A hotel-agnostic booking agent. Text in, text out: it holds context across turns, asks only for what is missing, and replies with at most three ranked room combinations and a total price. Hotel name, room types, prices, occupancy and policies all come from `inventory.json` — nothing hotel-specific is in the code. Flask API plus a React/Vite/Tailwind dashboard, and a CLI.

## Run it

```bash
pip install -r requirements.txt      # 1
python main.py                       # 2  API on :5000        (leave running)
npm --prefix frontend run dev        # 3  dashboard on :5173  (second terminal)
```

Open <http://localhost:5173>. Put a Gemini key in `.env` first (`cp .env.example .env`); step 3 installs the frontend's dependencies itself. Without a key the agent still runs on its regex fallback. Terminal-only: `python main.py --cli`.

The task sheet names `gemini-2.5-flash`, but that model now 404s for new API keys ("no longer available to new users"), so the default is `gemini-3.1-flash-lite` — `GEMINI_MODEL` overrides it.

## Architecture

The **LLM does one job**: turn a guest message, English or Hinglish, into structured slots — dates, headcount, children and ages, room count, AC preference, special requests, intent. It never calculates, never decides, never writes a reply. **Python does everything else**: validate those slots, merge them into per-session state, resolve dates, read the inventory, check occupancy and availability, build and price room combinations, rank three, work out what is still missing, set the status, and write the reply. I drew the line there because occupancy and pricing are exactly what a model gets confidently wrong and are trivial to express as code, while *"kal ke liye 2 room chahiye AC wala"* is the reverse. The consequence is that no price, room name or policy can be hallucinated — none of them pass through model output. Replies are templated in both languages, so Hinglish in gives Hinglish out with no model in the reply path. If Gemini is unreachable a regex extractor takes over and the agent still runs end to end.

`llm.py` the only file that calls Gemini, plus that fallback · `state.py` state, validation, merge rules · `dates.py` kal / parso / "15th to 17th" / "2 raat" / this weekend · `recommender.py` occupancy, extra beds, combinations, ranking · `response.py` the reply and policy answers in both languages · `agent.py` one turn end to end · `main.py` Flask API · `frontend/` dashboard.

## Conversation state

One `BookingState` per session, in a dict in the Flask process; nothing is persisted. The dashboard mints a session id on every page load, so a refresh starts a new conversation. Each turn returns the reply plus `{state, status, missing, assumptions, recommendations, intent}`, where status is `gathering | recommending | confirmed`.

The merge rules are the part that matters:

- **A null never overwrites a known value**, so state survives a change of mind: *"AC room chahiye"* → three turns later *"non-AC me kya rate hai"* keeps the dates and headcount and flips only the preference.
- **Nothing is quoted until `check_in`, `check_out`, `adults`, `children` and `ac_preference` are all known.** No assumed length of stay, no assumed AC preference. Everything still missing is asked for in a single message.
- **A vague headcount is not an adult count.** *"4 adults"* already answers the child question; *"4 of us"* / *"3 log hain"* only gives a total, so the agent stores `party_size` and asks whether any of them are children and their ages — the free-child cutoff in that question is read from `inventory.json`. The answer re-derives the adult count.
- **Duration is remembered separately from the dates**, so *"2 nights"* said before a date, or a later change of date, never causes a re-ask.
- **Extracted numbers are range-checked** and dropped, not clamped, when out of range — `adults: 0` never reaches the pricing math.
- **A booking is never guessed**: *"book it"* with three options on the table asks which one.

Pricing is plain arithmetic in `recommender.py`: guests fill `base_occupancy` first, then extra beds are bought cheapest-first up to `max_occupancy`; total is `nights × (Σ room price + Σ extra bed price)`. Combinations that carry a room nobody needs are pruned, the rest are ranked by price then fewest rooms, deduplicated by room mix, and cut to three.

## Questions outside booking

Answered only from `inventory.json`. The model picks *which* published policy key the question is about — it is handed this hotel's own key list and rejected if it invents one — and Python states that key's value verbatim. *"Do you have a swimming pool?"* matches no published policy, so the agent says it cannot confirm and will pass it to the hotel rather than improvising an amenity: an invented pool is the failure mode that costs a hotel a real guest. A side question never costs the guest their place in the booking flow.

## What I would build next, given a week

1. **Date-aware availability.** `available` is a flat integer, so the agent cannot see that 3 rooms are free on the 15th but only 1 on the 16th. Biggest gap.
2. **Per-night rates**, so a total stops being `nights × per_night`.
3. **Actually holding inventory**, with a TTL and an idempotency key so a repeated *"haan book kar do"* cannot double-book.
4. **An eval set** — ~80 labelled messages (Hinglish, typos, mind-changes) with expected slot patches, run against both the LLM and the regex path in CI. The extraction prompt is what regresses silently.

## Honest notes on what is not finished

- **Availability is not date-aware**, as above. With real inventory this is wrong.
- **Nothing is actually booked.** `confirmed` is a state plus a reference number; the reply says the hotel will call.
- **One deliberate deviation from the task sheet.** Its example *"2 rooms for tomorrow, 4 of us, AC"* is supposed to need zero follow-ups, but it never says how long the stay is and I would not quote a price off a guessed one — it gets exactly one question. The sheet's other example, *"2 rooms, 15th to 17th, 4 adults, AC"*, is complete and does recommend immediately. To revert: drop `check_out` from `REQUIRED` in `state.py`.
- **"This weekend" is read as Saturday→Sunday.** A hotel might mean Friday→Sunday.
- **Replies are templated and read like it** — the price of keeping the model out of the reply path. `REPLY_STYLING=1` enables an optional re-wording pass that cannot change a number; everything below is the default path.
- **No test suite.** The transcripts below are the only evidence of behaviour; replay any of them with `python main.py --cli`. The dashboard has no component tests.
- **Date coverage is common cases only** — *kal*, *parso*, *aaj*, this/next weekend, "15th to 17th", "N nights/raat". Weekday names like "next Friday" are not handled deterministically.
- **Sessions are unauthenticated and in-process**; anyone with a `session_id` can continue that conversation.

## Test transcripts

All six conversations from the task sheet, captured from real runs.

Hotel: **Hotel Sahu** (from `inventory.json`) · run on 2026-09-03 · model: `gemini-3.1-flash-lite`

### 1. Vague opener

```
guest > Room available for tomorrow?
bot   > Happy to help with a room at Hotel Sahu. Just tell me how many nights you are staying, how many guests are staying and whether you want AC or non-AC.
json  > {"status": "gathering", "state": {"check_in": "2026-09-04", "check_out": null, "nights": null, "party_size": null, "adults": null, "children": null, "children_ages": [], "rooms_wanted": null, "ac_preference": null, "special_requests": [], "language": "en"}, "missing": ["check_out", "adults", "ac_preference"]}

guest > 2 of us, 1 night, AC
bot   > Happy to help with a room at Hotel Sahu. Are any of them children? If so, I need their ages. Children under 5 stay free.
json  > {"status": "gathering", "state": {"check_in": "2026-09-04", "check_out": "2026-09-05", "nights": 1, "party_size": 2, "adults": 2, "children": null, "children_ages": [], "rooms_wanted": null, "ac_preference": "ac", "special_requests": [], "language": "en"}, "missing": ["children"]}

guest > no kids
bot   > 4 Sep to 5 Sep, 1 night, 2 guests, AC:
1. 1x Deluxe Double AC - Rs 2,200 total for 1 night (Cheapest)
2. 1x Super Deluxe AC - Rs 2,900 total for 1 night (Alternative)
3. 1x Family Suite AC - Rs 4,500 total for 1 night (Most space)
Which one should I hold for you?
json  > {"status": "recommending", "state": {"check_in": "2026-09-04", "check_out": "2026-09-05", "nights": 1, "party_size": 2, "adults": 2, "children": 0, "children_ages": [], "rooms_wanted": null, "ac_preference": "ac", "special_requests": [], "language": "en"}, "missing": []}

```

### 2. Everything in one message — no follow-up allowed

```
guest > 2 rooms, 15th to 17th, 4 adults, AC
bot   > 15 Sep to 17 Sep, 2 nights, 4 guests, AC:
1. 2x Deluxe Double AC - Rs 8,800 total for 2 nights (Cheapest)
2. 1x Deluxe Double AC + 1x Super Deluxe AC - Rs 10,200 total for 2 nights (Alternative)
3. 2x Super Deluxe AC - Rs 11,600 total for 2 nights (Most space)
Which one should I hold for you?
json  > {"status": "recommending", "state": {"check_in": "2026-09-15", "check_out": "2026-09-17", "nights": 2, "party_size": null, "adults": 4, "children": 0, "children_ages": [], "rooms_wanted": 2, "ac_preference": "ac", "special_requests": [], "language": "en"}, "missing": []}

```

### 3. Hinglish

```
guest > kal ke liye room chahiye, 3 log hain
bot   > Hotel Sahu mein room ke liye main help kar deta hoon. Bas bata dijiye kitni raat rukna hai aur AC chahiye ya non-AC. Unme koi bachcha bhi hai? Agar hai to umar bhi bata dijiye. 5 saal se chhote bachche free rehte hain.
json  > {"status": "gathering", "state": {"check_in": "2026-09-04", "check_out": null, "nights": null, "party_size": 3, "adults": 3, "children": null, "children_ages": [], "rooms_wanted": null, "ac_preference": null, "special_requests": [], "language": "hinglish"}, "missing": ["check_out", "children", "ac_preference"]}

guest > 2 raat, AC wala
bot   > Hotel Sahu mein room ke liye main help kar deta hoon. Unme koi bachcha bhi hai? Agar hai to umar bhi bata dijiye. 5 saal se chhote bachche free rehte hain.
json  > {"status": "gathering", "state": {"check_in": "2026-09-04", "check_out": "2026-09-06", "nights": 2, "party_size": 3, "adults": 3, "children": null, "children_ages": [], "rooms_wanted": null, "ac_preference": "ac", "special_requests": [], "language": "hinglish"}, "missing": ["children"]}

guest > koi bachcha nahi
bot   > 4 Sep se 6 Sep, 2 raat, 3 guest, AC:
1. 1x Deluxe Double AC (+1 extra bed) - total Rs 5,600, 2 raat ke liye (Sabse sasta)
2. 1x Super Deluxe AC (+1 extra bed) - total Rs 7,000, 2 raat ke liye (Doosra option)
3. 1x Family Suite AC - total Rs 9,000, 2 raat ke liye (Zyada space)
Inme se kaunsa hold karun?
json  > {"status": "recommending", "state": {"check_in": "2026-09-04", "check_out": "2026-09-06", "nights": 2, "party_size": 3, "adults": 3, "children": 0, "children_ages": [], "rooms_wanted": null, "ac_preference": "ac", "special_requests": [], "language": "hinglish"}, "missing": []}

```

### 4. Preference change mid-conversation

```
guest > AC room chahiye
bot   > Hotel Sahu mein room ke liye main help kar deta hoon. Bas bata dijiye kis date ko aa rahe hain, kitni raat rukna hai aur kitne guests hain.
json  > {"status": "gathering", "state": {"check_in": null, "check_out": null, "nights": null, "party_size": null, "adults": null, "children": null, "children_ages": [], "rooms_wanted": null, "ac_preference": "ac", "special_requests": [], "language": "hinglish"}, "missing": ["check_in", "check_out", "adults"]}

guest > kal se 2 raat
bot   > Hotel Sahu mein room ke liye main help kar deta hoon. Bas bata dijiye kitne guests hain.
json  > {"status": "gathering", "state": {"check_in": "2026-09-04", "check_out": "2026-09-06", "nights": 2, "party_size": null, "adults": null, "children": null, "children_ages": [], "rooms_wanted": null, "ac_preference": "ac", "special_requests": [], "language": "hinglish"}, "missing": ["adults"]}

guest > hum 2 log hain
bot   > Hotel Sahu mein room ke liye main help kar deta hoon. Unme koi bachcha bhi hai? Agar hai to umar bhi bata dijiye. 5 saal se chhote bachche free rehte hain.
json  > {"status": "gathering", "state": {"check_in": "2026-09-04", "check_out": "2026-09-06", "nights": 2, "party_size": 2, "adults": 2, "children": null, "children_ages": [], "rooms_wanted": null, "ac_preference": "ac", "special_requests": [], "language": "hinglish"}, "missing": ["children"]}

guest > no kids
bot   > 4 Sep se 6 Sep, 2 raat, 2 guest, AC:
1. 1x Deluxe Double AC - total Rs 4,400, 2 raat ke liye (Sabse sasta)
2. 1x Super Deluxe AC - total Rs 5,800, 2 raat ke liye (Doosra option)
3. 1x Family Suite AC - total Rs 9,000, 2 raat ke liye (Zyada space)
Inme se kaunsa hold karun?
json  > {"status": "recommending", "state": {"check_in": "2026-09-04", "check_out": "2026-09-06", "nights": 2, "party_size": 2, "adults": 2, "children": 0, "children_ages": [], "rooms_wanted": null, "ac_preference": "ac", "special_requests": [], "language": "hinglish"}, "missing": []}

guest > non-AC me kya rate hai
bot   > 4 Sep se 6 Sep, 2 raat, 2 guest, non-AC:
1. 1x Standard Non-AC - total Rs 2,800, 2 raat ke liye (Best fit)
Inme se kaunsa hold karun?
json  > {"status": "recommending", "state": {"check_in": "2026-09-04", "check_out": "2026-09-06", "nights": 2, "party_size": 2, "adults": 2, "children": 0, "children_ages": [], "rooms_wanted": null, "ac_preference": "non_ac", "special_requests": [], "language": "hinglish"}, "missing": []}

```

### 5. Group with children

```
guest > We are 7 people, 2 kids aged 4 and 6, need rooms this weekend
bot   > Happy to help with a room at Hotel Sahu. Just tell me whether you want AC or non-AC.
json  > {"status": "gathering", "state": {"check_in": "2026-09-05", "check_out": "2026-09-06", "nights": 1, "party_size": 7, "adults": 5, "children": 2, "children_ages": [4, 6], "rooms_wanted": null, "ac_preference": null, "special_requests": [], "language": "en"}, "missing": ["ac_preference"], "assumptions": ["weekend_sat_sun"]}

guest > AC please
bot   > 5 Sep to 6 Sep, 1 night, 6 guests, 1 child under 5 stays free, AC:
1. 2x Deluxe Double AC (+2 extra beds) - Rs 5,600 total for 1 night (Cheapest)
2. 1x Family Suite AC (+2 extra beds) - Rs 6,100 total for 1 night (Fewest rooms)
3. 1x Deluxe Double AC (+1 extra bed) + 1x Super Deluxe AC (+1 extra bed) - Rs 6,300 total for 1 night (Most space)
(Assumed weekend means Saturday to Sunday, 1 night - tell me if that is wrong.)
Which one should I hold for you?
json  > {"status": "recommending", "state": {"check_in": "2026-09-05", "check_out": "2026-09-06", "nights": 1, "party_size": 7, "adults": 5, "children": 2, "children_ages": [4, 6], "rooms_wanted": null, "ac_preference": "ac", "special_requests": [], "language": "en"}, "missing": [], "assumptions": ["weekend_sat_sun"]}

```

### 6. Out-of-scope question mid-flow

```
guest > 2 rooms for tomorrow, 4 adults AC
bot   > Happy to help with a room at Hotel Sahu. Just tell me how many nights you are staying.
json  > {"status": "gathering", "state": {"check_in": "2026-09-04", "check_out": null, "nights": null, "party_size": null, "adults": 4, "children": 0, "children_ages": [], "rooms_wanted": 2, "ac_preference": "ac", "special_requests": [], "language": "en"}, "missing": ["check_out"]}

guest > 1 night
bot   > 4 Sep to 5 Sep, 1 night, 4 guests, AC:
1. 2x Deluxe Double AC - Rs 4,400 total for 1 night (Cheapest)
2. 1x Deluxe Double AC + 1x Super Deluxe AC - Rs 5,100 total for 1 night (Alternative)
3. 2x Super Deluxe AC - Rs 5,800 total for 1 night (Most space)
Which one should I hold for you?
json  > {"status": "recommending", "state": {"check_in": "2026-09-04", "check_out": "2026-09-05", "nights": 1, "party_size": null, "adults": 4, "children": 0, "children_ages": [], "rooms_wanted": 2, "ac_preference": "ac", "special_requests": [], "language": "en"}, "missing": []}

guest > Do you have a swimming pool?
bot   > I do not have that confirmed for Hotel Sahu, so I would rather not guess - I will pass it to the hotel and they will confirm.

Shall I go ahead with one of the options above?
json  > {"status": "recommending", "state": {"check_in": "2026-09-04", "check_out": "2026-09-05", "nights": 1, "party_size": null, "adults": 4, "children": 0, "children_ages": [], "rooms_wanted": 2, "ac_preference": "ac", "special_requests": [], "language": "en"}, "missing": []}

guest > ok option 1 book kar do
bot   > Done - holding 2x Deluxe Double AC at Hotel Sahu, Rs 4,400 total for 1 night.
4 Sep to 5 Sep. Reference H001-40153.
Check-in from 12:00, check-out by 11:00.
The hotel will call you to take payment details.
json  > {"status": "confirmed", "state": {"check_in": "2026-09-04", "check_out": "2026-09-05", "nights": 1, "party_size": null, "adults": 4, "children": 0, "children_ages": [], "rooms_wanted": 2, "ac_preference": "ac", "special_requests": [], "language": "en"}, "missing": []}

```
