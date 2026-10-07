"""Personal-record detection. Pure Python: replays history in order and reports what each session beat.

Rules
- The first session of an exercise sets the baseline. It produces no records (nothing was beaten).
- Weight PR: a heavier weight than any earlier set. Only counts when earlier weighted sets exist.
- Rep PR: more reps than any earlier set at the same or a heavier weight, on a working set. A new heaviest
  weight is a weight PR, not also a rep PR. Warm-up sets (under 80% of the session's top weight) are ignored.
- Volume PR: more total weight x reps in one session than any earlier session. Weighted work only.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.engine.metrics import (
    WEIGHT_TOLERANCE,
    SessionPerformance,
    is_working_weight,
    session_volume,
    top_weight,
)

WEIGHT, REPS, VOLUME = "weight", "reps", "volume"


@dataclass(frozen=True)
class RecordEvent:
    record_type: str
    value: float
    weight_kg: float | None
    reps: int | None
    previous_value: float | None
    achieved_on: date
    session_id: int | None = None


def detect_records(history_oldest_first: Sequence[SessionPerformance]) -> list[RecordEvent]:
    """Events for every session after the first, in chronological order."""
    events: list[RecordEvent] = []
    earlier: list = []  # every valid set seen so far
    best_weight: float | None = None
    best_volume = 0.0

    for session in history_oldest_first:
        sets = session.valid_sets
        if not sets:
            continue
        top = top_weight(sets)
        volume = session_volume(sets)

        if earlier:
            events.extend(_session_events(session, sets, top, volume, earlier, best_weight, best_volume))

        earlier.extend(sets)
        if top is not None and (best_weight is None or top > best_weight):
            best_weight = top
        best_volume = max(best_volume, volume)
    return events


def _session_events(session, sets, top, volume, earlier, best_weight, best_volume) -> list[RecordEvent]:
    out: list[RecordEvent] = []
    on, sid = session.performed_on, session.session_id

    # weight PR
    if top is not None and best_weight is not None and top > best_weight + WEIGHT_TOLERANCE:
        reps = max(s.reps for s in sets if s.load and abs(s.load - top) <= WEIGHT_TOLERANCE)
        out.append(RecordEvent(WEIGHT, top, top, reps, best_weight, on, sid))

    # rep PR: best candidate among working sets that have something comparable to beat
    candidate = None
    for s in sets:
        if not is_working_weight(s.load, top):
            continue
        level = s.load or 0.0
        comparable = [e.reps for e in earlier if (e.load or 0.0) >= level - WEIGHT_TOLERANCE]
        if not comparable or s.reps <= max(comparable):
            continue
        key = (s.reps, level)
        if candidate is None or key > candidate[0]:
            candidate = (key, s, max(comparable))
    if candidate:
        _, s, previous = candidate
        out.append(RecordEvent(REPS, float(s.reps), s.load, s.reps, float(previous), on, sid))

    # volume PR (weighted sessions only)
    if volume > 0 and best_volume > 0 and volume > best_volume + 0.01:
        out.append(RecordEvent(VOLUME, volume, None, None, best_volume, on, sid))
    return out
