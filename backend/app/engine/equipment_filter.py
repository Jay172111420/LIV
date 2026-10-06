"""The one place that decides whether an exercise is usable with the equipment on hand."""
from collections.abc import Iterable

from app.engine.types import ExerciseInfo

BODYWEIGHT = "bodyweight"

# Gear that makes sense at a "home, bodyweight" location. Anything else the user ticked is ignored there.
HOME_BODYWEIGHT_ALLOWED = frozenset({BODYWEIGHT, "resistance_bands", "pull_up_bar"})


class EquipmentFilter:
    """An exercise is allowed only if EVERY piece of equipment it needs is available."""

    def __init__(self, available: Iterable[str], location: str | None = None):
        chosen = {str(s) for s in available} | {BODYWEIGHT}
        location = str(getattr(location, "value", location)) if location else None
        if location == "home_bodyweight":
            self.available = frozenset(chosen & HOME_BODYWEIGHT_ALLOWED)
        else:
            self.available = frozenset(chosen)
        self.ignored = frozenset(chosen - self.available)

    def allows(self, exercise: ExerciseInfo) -> bool:
        return exercise.is_active and (exercise.equipment - {BODYWEIGHT}) <= self.available

    def filter(self, exercises: Iterable[ExerciseInfo]) -> list[ExerciseInfo]:
        return [e for e in exercises if self.allows(e)]
