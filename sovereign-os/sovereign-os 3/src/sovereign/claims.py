"""MemoryClaim lifecycle rules (ADR-0003).

Pure domain logic with no storage or provider dependency. A claim is an
interpretation derived from source records; it is never evidence itself.

Every claim is created `proposed`. Only an explicit human action moves it, and
only along TRANSITIONS. `rejected` and `superseded` are terminal, so a rejected
claim can never silently become authoritative again; a corrected claim is
replaced by a new `proposed` claim that links back to it. The same table is
compiled into the SQLite triggers in `store.py`, so storage enforces it too.
"""
from __future__ import annotations

STATUSES = ("proposed", "approved", "rejected", "contested", "superseded")
# Provenance classes, not provider names. `human`: written through the local UI/API.
# `model`: reserved for future internal model extraction (never browser-supplied).
# `imported`: arrived through an untrusted ordinary import.
ORIGINS = ("human", "model", "imported")

TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset({"approved", "rejected", "contested", "superseded"}),
    # Human authority is immediately revocable; contesting is optional, not a required step.
    "approved": frozenset({"contested", "rejected", "superseded"}),
    "contested": frozenset({"approved", "rejected", "superseded"}),
    "rejected": frozenset(),
    "superseded": frozenset(),
}

# Creation-time limits, also enforced by storage CHECKs/triggers so every stored claim is restorable.
# There is deliberately no limit on history length: approve/contest cycles are legitimate and unbounded.
MAX_TEXT, MAX_NOTE, MAX_SOURCES = 2000, 500, 8


class TransitionError(ValueError):
    """A requested status change is not permitted by the lifecycle or lost a race."""


def transition_keys() -> list[str]:
    """Allowed transitions as 'from>to' strings, for the storage triggers."""
    return sorted(f"{a}>{b}" for a, targets in TRANSITIONS.items() for b in targets)


def check_transition(current: str, target: str, support: str | None = None) -> None:
    """Raise TransitionError unless `current -> target` is allowed.

    `support` is the claim's derived evidence state; pass None to skip the
    evidence check (trusted-restore replay of a past, already-recorded decision).
    """
    if target not in TRANSITIONS.get(current, ()):
        raise TransitionError(f"A {current} claim cannot become {target}.")
    if target == "approved" and support is not None and support != "supported":
        raise TransitionError(f"Cannot approve a claim whose evidence is {support}.")


# The only evidence states that are present and hash-verified: current evidence, or evidence since corrected.
VERIFIED_STATES = frozenset({"active", "superseded"})


def support_of(source_states: list[str]) -> str:
    """Derive evidence support from each source's state: active | superseded | missing | unverified.

    Positive validation (ADR-0006, F-3): a claim is `supported` only if it has at least one evidence link and
    every link is `active`, and `stale` only if every link is `active` or `superseded`. Anything else, including
    a missing or unverified link, no links at all (Issue #6), and any state outside the storage CHECK set
    (writable by a connection that disables CHECK constraints), is `orphaned`.
    """
    if not source_states or any(s not in VERIFIED_STATES for s in source_states):
        return "orphaned"
    if any(s == "superseded" for s in source_states):
        return "stale"
    return "supported"


def is_authoritative(status: str, support: str) -> bool:
    """Only an approved claim whose evidence is intact counts as approved memory."""
    return status == "approved" and support == "supported"


def validate_history(history: list, origin: str, status: str) -> None:
    """Check that a backup's event history is a legal lifecycle ending at `status`.

    An empty history is accepted only for a `proposed` claim (a claim row stored without its
    creation event can exist, but can never have changed status).
    """
    if not isinstance(history, list):
        raise ValueError("Invalid claim history.")
    if not history:
        if status != "proposed":
            raise ValueError("Claim status does not match its history.")
        return
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
