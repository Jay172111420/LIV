"""Finds replacements for an exercise that keep the workout's intent."""
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.engine.equipment_filter import EquipmentFilter
from app.engine.exercise_selector import equipment_style
from app.engine.types import ExerciseInfo, level_index


@dataclass(frozen=True)
class Substitute:
    exercise: ExerciseInfo
    score: int
    reasons: tuple[str, ...] = field(default_factory=tuple)


MAJOR_PATTERNS = {"squat", "hinge", "lunge", "push", "pull"}


class ExerciseSubstitutionService:
    """A valid substitute MUST: be a different, active exercise; train the same primary muscle; have the
    same compound/isolation classification; use only available equipment; and be allowed for the user's
    experience. When the original is a major lift (squat, hinge, lunge, push, pull), substitutes keep its
    movement pattern whenever any exist; otherwise the closest pattern-agnostic matches are offered."""

    def __init__(self, pool: Iterable[ExerciseInfo], equipment: EquipmentFilter, experience: str):
        self.pool = list(pool)
        self.equipment = equipment
        self.experience = experience

    def _eligible(self, target: ExerciseInfo, candidate: ExerciseInfo, exclude: set[int]) -> bool:
        return (
            candidate.id != target.id
            and candidate.id not in exclude
            and self.equipment.allows(candidate)
            and level_index(candidate.min_experience) <= level_index(self.experience)
            and candidate.primary_muscle == target.primary_muscle
            and candidate.is_compound == target.is_compound
            and candidate.is_conditioning == target.is_conditioning
        )

    def _eligible_pool(self, target: ExerciseInfo, exclude: set[int]) -> list[ExerciseInfo]:
        pool = [c for c in self.pool if self._eligible(target, c, exclude)]
        if target.movement_pattern in MAJOR_PATTERNS:
            same = [c for c in pool if c.movement_pattern == target.movement_pattern]
            if same:
                return same
        return pool

    def _score(self, target: ExerciseInfo, c: ExerciseInfo) -> tuple[int, tuple[str, ...]]:
        score, reasons = 0, [f"Targets {c.primary_muscle.replace('_', ' ')}"]
        if c.movement_pattern == target.movement_pattern:
            score += 6
            reasons.append("Same movement pattern")
        reasons.append("Compound" if c.is_compound else "Isolation")
        shared = set(c.secondary_muscles) & set(target.secondary_muscles)
        score += len(shared)
        score -= abs(level_index(c.difficulty) - level_index(target.difficulty))
        if equipment_style(c) == equipment_style(target):
            score += 1
        if c.is_timed == target.is_timed:
            score += 1
        return score, tuple(reasons)

    def candidates(self, target: ExerciseInfo, exclude_ids: Iterable[int] = (), limit: int = 8) -> list[Substitute]:
        scored = []
        for c in self._eligible_pool(target, set(exclude_ids)):
            score, reasons = self._score(target, c)
            scored.append(Substitute(c, score, reasons))
        scored.sort(key=lambda s: (-s.score, s.exercise.name, s.exercise.id))
        return scored[:limit]

    def is_valid_substitute(self, target: ExerciseInfo, replacement: ExerciseInfo,
                            exclude_ids: Iterable[int] = ()) -> bool:
        return any(c.id == replacement.id for c in self._eligible_pool(target, set(exclude_ids)))
