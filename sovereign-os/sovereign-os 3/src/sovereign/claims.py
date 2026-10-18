"""MemoryClaim lifecycle rules (ADR-0003).

Pure domain logic with no storage or provider dependency. A claim is an
interpretation derived from source records; it is never evidence itself.

Every claim is created `proposed`. Only an explicit human action moves it, and
only along TRANSITIONS. `rejected` and `superseded` are terminal, so a rejected
claim can never silently become authoritative again; a corrected claim is
replaced by a new `proposed` claim that links back to it.
"""
from __future__ import annotations

STATUSES = ("proposed", "approved", "rejected", "contested", "superseded")
ORIGINS = ("human", "model")

TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset({"approved", "rejected", "contested", "superseded"}),
    # An approved claim must be contested before it can be rejected (two explicit steps).
    "approved": frozenset({"contested", "superseded"}),
    "contested": frozenset({"approved", "rejected", "superseded"}),
    "rejected": frozenset(),
    "superseded": frozenset(),
}

MAX_TEXT, MAX_NOTE, MAX_SOURCES, MAX_HISTORY = 2000, 500, 8, 100


class TransitionError(ValueError):
    """A requested status change is not permitted by the lifecycle."""


def check_transition(current: str, target: str, support: str | None = None) -> None:
    """Raise TransitionError unless `current -> target` is allowed.

    `support` is the claim's derived evidence state; pass None to skip the
    evidence check (import replay of a past, already-recorded decision).
    """
    if target not in TRANSITIONS.get(current, ()):
        raise TransitionError(f"A {current} claim cannot become {target}.")
    if target == "approved" and support is not None and support != "supported":
        raise TransitionError(f"Cannot approve a claim whose evidence is {support}.")


def support_of(source_states: list[str]) -> str:
    """Derive evidence support from each source's state: active | superseded | deleted | missing."""
    if any(s in ("deleted", "missing") for s in source_states):
        return "orphaned"
    if any(s == "superseded" for s in source_states):
        return "stale"
    return "supported"


def is_authoritative(status: str, support: str) -> bool:
    """Only an approved claim whose evidence is intact counts as approved memory."""
    return status == "approved" and support == "supported"


def validate_history(history: list, origin: str, status: str) -> None:
    """Check that an imported event history is a legal lifecycle ending at `status`."""
    if not isinstance(history, list) or not 0 < len(history) <= MAX_HISTORY:
        raise ValueError("Invalid claim history.")
    previous = None
    for event in history:
        if not isinstance(event, dict):
            raise ValueError("Invalid claim history.")
        if event.get("from_status") != previous:
            raise ValueError("Claim history is not contiguous.")
        to, actor, note = event.get("to_status"), event.get("actor"), event.get("note")
        if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE):
            raise ValueError("Invalid claim history note.")
        if not isinstance(event.get("at"), str):
            raise ValueError("Invalid claim history time.")
        if previous is None:
            if to != "proposed" or actor != origin:
                raise ValueError("Claim history must start with its creation as proposed.")
        else:
            if actor != "human":
                raise ValueError("Only a human may change a claim's status.")
            check_transition(previous, to)
        previous = to
    if previous != status:
        raise ValueError("Claim status does not match its history.")
