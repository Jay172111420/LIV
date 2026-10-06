"""Picks the best exercise for a slot from the equipment- and experience-eligible pool."""
from collections import Counter
from collections.abc import Iterable

from app.engine.equipment_filter import EquipmentFilter
from app.engine.split_generator import Slot
from app.engine.types import ExerciseInfo, level_index

# Preference for equipment style by goal (higher = preferred). Unknown goals get no bias.
STYLE_BONUS: dict[str, dict[str, int]] = {
    "strength": {"barbell": 3, "dumbbell": 1, "machine": 0, "bodyweight": 0, "band": -1},
    "muscle_gain": {"barbell": 2, "dumbbell": 2, "machine": 1, "bodyweight": 0, "band": -1},
    "recomposition": {"barbell": 2, "dumbbell": 2, "machine": 1, "bodyweight": 1, "band": 0},
    "fat_loss": {"barbell": 1, "dumbbell": 2, "machine": 0, "bodyweight": 2, "band": 0},
    "general_fitness": {"barbell": 0, "dumbbell": 2, "machine": 1, "bodyweight": 2, "band": 1},
}
REPEAT_PENALTY = 4  # per earlier use in the same plan, so A/B days differ
# Strength programs deliberately repeat their main lifts through the week.
GOAL_REPEAT_PENALTY = {"strength": 1}


def equipment_style(ex: ExerciseInfo) -> str:
    if "barbell" in ex.equipment:
        return "barbell"
    if ex.equipment & {"machines", "cable_machine"}:
        return "machine"
    if ex.equipment & {"dumbbells", "kettlebell"}:
        return "dumbbell"
    if "resistance_bands" in ex.equipment:
        return "band"
    return "bodyweight"


def _role_matches(ex: ExerciseInfo, role: str) -> bool:
    if role == "conditioning":
        return ex.is_conditioning
    if ex.is_conditioning or ex.exercise_type == "mobility":
        return False
    if role == "compound":
        return ex.exercise_type == "compound" and ex.is_compound
    return ex.exercise_type == "isolation" or not ex.is_compound


class ExerciseSelector:
    def __init__(self, pool: Iterable[ExerciseInfo], equipment: EquipmentFilter, experience: str, goal: str):
        level = level_index(experience)
        self.experience = experience
        self.goal = goal
        # Equipment and experience are hard limits applied here, once, and never relaxed afterwards.
        self.eligible = sorted(
            (e for e in equipment.filter(pool) if level_index(e.min_experience) <= level),
            key=lambda e: (e.name, e.id),
        )

    def score(self, ex: ExerciseInfo, plan_use: Counter) -> int:
        level = level_index(self.experience)
        diff = level_index(ex.difficulty)
        fit = 3 if diff == level else (2 if diff < level else -2)
        style = STYLE_BONUS.get(self.goal, {}).get(equipment_style(ex), 0)
        if level == 0 and equipment_style(ex) == "barbell":
            style -= 1
        return fit + style - GOAL_REPEAT_PENALTY.get(self.goal, REPEAT_PENALTY) * plan_use[ex.id]

    def select(self, slot: Slot, used_in_day: set[int], plan_use: Counter,
               muscles: Iterable[str] | None = None) -> ExerciseInfo | None:
        """Tries the strictest match first, then relaxes the movement pattern, then the role.
        Equipment and experience are never relaxed. An exercise is never used twice in one day."""
        targets = {slot.muscle} if muscles is None else set(muscles)
        base = [e for e in self.eligible if e.id not in used_in_day and e.primary_muscle in targets]
        passes = [
            [e for e in base if _role_matches(e, slot.role)
             and (not slot.patterns or e.movement_pattern in slot.patterns)],
            [e for e in base if _role_matches(e, slot.role)],
        ]
        if slot.role != "conditioning":
            passes.append([e for e in base if not e.is_conditioning and e.exercise_type != "mobility"])
        for candidates in passes:
            if candidates:
                return max(candidates, key=lambda e: (self.score(e, plan_use), -e.id))
        return None
