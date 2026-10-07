"""Training metrics: estimated 1RM, volume, performance score, trend and decline detection.

Pure Python, no database or HTTP. Everything here is a *rough* measure built from logged numbers. Estimated
1RM and volume are estimates, never measurements, and the API labels them that way.
"""
from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

WEIGHT_TOLERANCE = 0.01  # kg: two weights closer than this are "the same weight"
WORKING_SET_FRACTION = 0.8  # a set lighter than 80% of the session's top weight is treated as a warm-up
MAX_E1RM_REPS = 12  # Epley is unreliable far beyond this
TREND_THRESHOLD = 0.025  # +/-2.5% between the older and newer half of the history
DECLINE_MILD = 0.05  # both recent sessions at least 5% below the normal level
DECLINE_MARKED = 0.10
MIN_SESSIONS_FOR_DECLINE = 4  # two recent sessions plus at least two to compare against


@dataclass(frozen=True)
class SetPerformance:
    """One completed set. `weight_kg` is None (or 0) for bodyweight work."""

    weight_kg: float | None
    reps: int
    rir: int | None = None
    rpe: float | None = None

    @property
    def load(self) -> float | None:
        """Added load in kg, or None when no weight was used."""
        return self.weight_kg if self.weight_kg and self.weight_kg > 0 else None

    @property
    def effective_rir(self) -> float | None:
        """Reps in reserve. Falls back to 10 - RPE when RIR wasn't logged. Never negative."""
        if self.rir is not None:
            return float(self.rir)
        if self.rpe is not None:
            return max(0.0, 10.0 - self.rpe)
        return None


@dataclass(frozen=True)
class SessionPerformance:
    """Every completed set of one exercise in one workout."""

    performed_on: date
    sets: tuple[SetPerformance, ...]
    session_id: int | None = None

    @property
    def valid_sets(self) -> tuple[SetPerformance, ...]:
        return tuple(s for s in self.sets if s.reps >= 1)


@dataclass(frozen=True)
class PerformanceFlag:
    code: str
    message: str
    level: str = "info"  # info | mild | marked
    detail: str | None = None


# --------------------------------------------------------------------------- basics
def same_weight(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= WEIGHT_TOLERANCE


def estimate_1rm(weight_kg: float | None, reps: int) -> float | None:
    """Epley estimate: weight x (1 + reps / 30). An estimate only; None when it can't be applied."""
    if not weight_kg or weight_kg <= 0 or reps < 1 or reps > MAX_E1RM_REPS:
        return None
    return round(weight_kg if reps == 1 else weight_kg * (1 + reps / 30), 1)


def set_volume(s: SetPerformance) -> float:
    """weight x reps. Zero for bodyweight sets (volume doesn't apply to them)."""
    return round(s.load * s.reps, 2) if s.load else 0.0


def session_volume(sets: Iterable[SetPerformance]) -> float:
    return round(sum(set_volume(s) for s in sets), 2)


def top_weight(sets: Iterable[SetPerformance]) -> float | None:
    loads = [s.load for s in sets if s.load and s.reps >= 1]
    return max(loads) if loads else None


def working_sets(sets: Iterable[SetPerformance]) -> tuple[SetPerformance, ...]:
    """The sets that count when judging a session: those at the heaviest weight used.

    Lighter sets (warm-ups, back-off sets) are ignored. Bodyweight sessions use every set.
    """
    valid = [s for s in sets if s.reps >= 1]
    top = top_weight(valid)
    if top is None:
        return tuple(valid)
    return tuple(s for s in valid if same_weight(s.load, top))


def is_working_weight(weight: float | None, top: float | None) -> bool:
    """Used for records: filters warm-up sets out so they can't produce junk rep PRs."""
    if top is None:
        return True
    return weight is not None and weight >= top * WORKING_SET_FRACTION


# --------------------------------------------------------------------------- scores and trends
def performance_score(session: SessionPerformance) -> float | None:
    """One number per session so sessions can be compared.

    Weighted work: the best estimated 1RM among working sets (reps above 12 are counted as 12 so a long set
    can't inflate it). Bodyweight work: average reps per set.
    """
    sets = session.valid_sets
    if not sets:
        return None
    top = top_weight(sets)
    if top is None:
        return round(sum(s.reps for s in sets) / len(sets), 2)
    scores = [estimate_1rm(s.load, min(s.reps, MAX_E1RM_REPS)) for s in sets if is_working_weight(s.load, top)]
    scores = [x for x in scores if x is not None]
    return max(scores) if scores else None


def trend_direction(scores_oldest_first: Sequence[float]) -> tuple[str, float | None]:
    """('improving' | 'steady' | 'declining' | 'insufficient_data', percent change).

    Compares the average of the older half of the last eight scores with the newer half.
    """
    values = [x for x in scores_oldest_first if x is not None][-8:]
    if len(values) < 3:
        return "insufficient_data", None
    newer = values[len(values) // 2:]
    older = values[:len(values) // 2]
    base = statistics.fmean(older)
    if base <= 0:
        return "insufficient_data", None
    change = (statistics.fmean(newer) - base) / base
    if change > TREND_THRESHOLD:
        return "improving", round(change * 100, 1)
    if change < -TREND_THRESHOLD:
        return "declining", round(change * 100, 1)
    return "steady", round(change * 100, 1)


def detect_decline(scores_newest_first: Sequence[float | None]) -> PerformanceFlag | None:
    """Rule: the last two sessions are both well below the median of the four before them.

    Deliberately simple and explainable. It only describes logged numbers: it says nothing about why
    performance dipped (sleep, stress, a planned lighter week and technique all do this).
    """
    scores = [x for x in scores_newest_first if x is not None]
    if len(scores) < MIN_SESSIONS_FOR_DECLINE:
        return None
    recent, baseline = scores[:2], statistics.median(scores[2:6])
    if baseline <= 0:
        return None
    shortfall = [(baseline - r) / baseline for r in recent]
    if min(shortfall) < DECLINE_MILD:
        return None
    level = "marked" if min(shortfall) >= DECLINE_MARKED else "mild"
    return PerformanceFlag(
        code="performance_decline", level=level,
        message="Your recent performance is below your normal trend.",
        detail="This only reflects your logged numbers. If you lowered the weight on purpose, that's expected.",
    )


# --------------------------------------------------------------------------- calendar and aggregation
def week_start(d: date) -> date:
    """Monday of the week containing `d`."""
    return d - timedelta(days=d.weekday())


@dataclass
class VolumeTotals:
    volume_kg: float = 0.0
    sets: int = 0
    reps: int = 0

    def add(self, sets: Iterable[SetPerformance]) -> None:
        for s in sets:
            if s.reps < 1:
                continue
            self.sets += 1
            self.reps += s.reps
            self.volume_kg = round(self.volume_kg + set_volume(s), 2)
