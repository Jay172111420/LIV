"""Sets, rep ranges and rest: the rules that turn an exercise into a prescription."""
from dataclasses import dataclass

from app.engine.types import ExerciseInfo, level_index

# goal -> (compound, isolation), each (rep_min, rep_max, rest_seconds)
GOAL_RULES: dict[str, dict[str, tuple[int, int, int]]] = {
    "strength": {"compound": (3, 6, 180), "isolation": (8, 12, 90)},
    "muscle_gain": {"compound": (6, 10, 120), "isolation": (10, 15, 75)},
    "recomposition": {"compound": (6, 12, 90), "isolation": (10, 15, 60)},
    "fat_loss": {"compound": (8, 12, 60), "isolation": (12, 20, 45)},
    "general_fitness": {"compound": (8, 12, 75), "isolation": (12, 15, 60)},
}
DEFAULT_GOAL = "general_fitness"
CONDITIONING_REST = 30
MIN_REST, MAX_REST = 15, 300

SETUP_SECONDS = 60  # moving to / setting up the exercise
SECONDS_PER_REP = 3
WARMUP_MINUTES = 5  # reserved out of the session for warm-up


@dataclass(frozen=True)
class Prescription:
    sets: int
    rep_min: int
    rep_max: int
    rest_seconds: int


def goal_rules(goal: str) -> dict[str, tuple[int, int, int]]:
    return GOAL_RULES.get(goal, GOAL_RULES[DEFAULT_GOAL])


def kind_of(exercise: ExerciseInfo) -> str:
    if exercise.is_conditioning:
        return "conditioning"
    return "compound" if exercise.exercise_type == "compound" and exercise.is_compound else "isolation"


def rep_range(exercise: ExerciseInfo, goal: str) -> tuple[int, int]:
    """The goal's preferred range, kept inside the exercise's own safe/useful range."""
    ex_lo, ex_hi = exercise.rep_min, exercise.rep_max
    kind = kind_of(exercise)
    if exercise.is_timed or kind == "conditioning":
        return ex_lo, ex_hi
    g_lo, g_hi, _ = goal_rules(goal)[kind]
    lo, hi = max(g_lo, ex_lo), min(g_hi, ex_hi)
    if lo > hi:  # the two ranges don't overlap: stay inside the exercise range, nearest to the goal
        if g_lo > ex_hi:
            hi, lo = ex_hi, max(ex_lo, ex_hi - 4)
        else:
            lo, hi = ex_lo, min(ex_hi, ex_lo + 4)
    elif hi - lo < 2:  # too narrow to be useful: widen toward the open side of the exercise range
        if hi == ex_lo:
            hi = min(ex_hi, ex_lo + 2)
        else:
            lo = max(ex_lo, hi - 3)
    return lo, hi


def rest_seconds(exercise: ExerciseInfo, goal: str, rep_max: int) -> int:
    kind = kind_of(exercise)
    if kind == "conditioning":
        return CONDITIONING_REST
    rest = goal_rules(goal)[kind][2]
    if kind == "compound" and rep_max <= 6:
        rest += 30  # heavy singles-to-fives need longer recovery
    return max(MIN_REST, min(MAX_REST, rest))


def set_count(exercise: ExerciseInfo, goal: str, experience: str, lead_compound: bool) -> int:
    """Starts from the exercise's recommended sets, then adjusts for experience and goal."""
    sets = exercise.sets
    kind = kind_of(exercise)
    lvl = level_index(experience)
    if lvl == 0:
        sets -= 1
    elif lvl == 2 and kind == "compound":
        sets += 1
    if goal == "strength" and lead_compound and kind == "compound":
        sets += 1
    return max(2, min(5, sets))


def prescribe(exercise: ExerciseInfo, goal: str, experience: str, lead_compound: bool = False) -> Prescription:
    lo, hi = rep_range(exercise, goal)
    return Prescription(
        sets=set_count(exercise, goal, experience, lead_compound),
        rep_min=lo, rep_max=hi, rest_seconds=rest_seconds(exercise, goal, hi),
    )


def estimate_seconds(sets: int, rep_min: int, rep_max: int, rest: int, is_timed: bool = False) -> int:
    """Rough time for one exercise: work + rest between sets (none after the last) + setup."""
    average = (rep_min + rep_max) / 2
    work = average if is_timed else average * SECONDS_PER_REP
    return round(SETUP_SECONDS + sets * work + max(0, sets - 1) * rest)
