"""One turn of the conversation, start to finish.

    guest text -> llm.extract -> state.apply (validate + merge)
              -> deterministic decision -> response -> reply + JSON

The LLM appears once, at the front, and only to understand and structure
what the guest said. Everything after it -- validation, state, availability,
occupancy, pricing, ranking, status, and the wording of the reply itself --
is deterministic Python.
"""

from datetime import date

import llm
import recommender
import response
from inventory import Inventory
from state import BookingState


def _signature(options: list[dict]) -> tuple:
    return tuple(
        (tuple(sorted((r["type"], r["count"]) for r in o["rooms"])), o["total_price"])
        for o in options
    )


def handle_turn(message: str, state: BookingState, inv: Inventory,
                today: date | None = None) -> dict:
    today = today or date.today()

    # 1. language layer. It is given this hotel's own policy names, so a
    #    question can be pointed at one without any policy text being
    #    generated, and the slots the agent just asked for, so a terse reply
    #    like "4 and 6" is read as the answer to that question.
    awaiting = state.missing() or (["selected_option"] if state.awaiting_choice else [])
    patch = llm.extract(message, state.to_json(), today,
                        list(inv.policy_entries()), awaiting)
    intent = patch.get("intent") or "booking"

    # 2. state layer
    changed = state.apply(patch, today, message)
    slots_changed = [c for c in changed if c != "reset"]

    # 3. side questions are answered from inventory.json only, and never
    #    cost the guest their place in the booking flow
    info = ""
    if intent in ("policy", "out_of_scope") or patch.get("policy_key"):
        answer, grounded = response.answer_question(
            patch.get("question") or message, inv,
            language=state.language, policy_key=patch.get("policy_key"),
        )
        # Say "I cannot confirm that" only when we really have nothing else
        # to offer. "non-AC me kya rate hai" sometimes classifies as a
        # question, but it moved a booking slot, so the answer is the new
        # quote -- not an apology in front of it.
        if grounded or not slots_changed:
            info = answer

    # 4. deterministic decision
    state.assumptions = [state.date_note] if state.date_note else []
    missing = state.missing()
    guests = state.guest_count(inv.free_child_age_cutoff)
    options: list[dict] = []

    # Nothing is quoted until every required slot is filled -- no assumed
    # length of stay, no assumed AC preference.
    if not missing:
        options = recommender.recommend(
            inv, guests, state.nights, state.ac_preference, state.rooms_wanted
        )

    # Naming an option is itself a confirmation -- "option 2" on its own is
    # an answer, not a new booking question.
    picked = patch.get("selected_option")
    confirming = bool(state.last_offered) and (intent == "confirm" or isinstance(picked, int))

    if confirming:
        pool = state.last_offered
        valid = isinstance(picked, int) and 1 <= picked <= len(pool)
        if valid or len(pool) == 1:
            # One option on the table needs no number; otherwise the guest
            # has to name one. Booking the wrong room is not recoverable by
            # the guest, so this is never guessed.
            state.selected_option = pool[picked - 1] if valid else pool[0]
            state.status = "confirmed"
            state.awaiting_choice = False
            draft = response.confirmation(state, inv, state.selected_option)
        else:
            state.status = "recommending"
            state.awaiting_choice = True
            draft = response.which_option(state, len(pool), picked)
    elif missing:
        state.status = "gathering"
        draft = response.slot_question(state, inv)
    elif not options:
        state.status = "gathering"
        draft = response.no_options(state, inv, guests)
    else:
        repeat = (state.status == "recommending"
                  and not slots_changed
                  and _signature(options) == _signature(state.last_offered))
        state.status = "recommending"
        state.last_offered = options
        state.awaiting_choice = False
        # Do not re-dump the same three options just because the guest asked
        # a side question -- nudge instead.
        draft = response.nudge(state) if (repeat and info) else response.offer(state, inv, options, guests)

    # 5. the reply is what Python wrote, in the guest's language
    reply = "\n\n".join(part for part in (info, draft) if part)
    if llm.REPLY_STYLING:
        # Off by default. Optional polish pass that may only re-word the
        # reply, never change a fact -- see llm.phrase.
        reply = llm.phrase(reply, state.language)

    return {
        "reply": reply,
        "status": state.status,
        "state": state.to_json(),
        "missing": missing,
        "assumptions": state.assumptions,
        "recommendations": state.last_offered,
        "selected_option": state.selected_option,
        "intent": intent,
        "extraction": patch.get("_source"),
    }
