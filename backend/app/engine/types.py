"""Plain data structures shared by the engine. Strings are the enum values used by the database."""
from dataclasses import dataclass, field

LEVELS = {"beginner": 0, "intermediate": 1, "advanced": 2}


def level_index(level: str) -> int:
    return LEVELS[str(getattr(level, "value", level))]


@dataclass(frozen=True)
class ExerciseInfo:
    id: int
    name: str
    primary_muscle: str
    secondary_muscles: tuple[str, ...]
    movement_pattern: str
    equipment: frozenset[str]  # ALL required; "bodyweight" is never listed
    difficulty: str
    min_experience: str
    exercise_type: str  # compound | isolation | cardio | mobility | plyometric
    is_compound: bool
    is_timed: bool
    rep_min: int
    rep_max: int
    sets: int
    is_active: bool = True

    @property
    def is_conditioning(self) -> bool:
        return self.exercise_type in ("cardio", "plyometric")


@dataclass(frozen=True)
class GenerationInput:
    goal: str  # goal slug
    experience: str
    days_per_week: int
    duration_minutes: int
    equipment: frozenset[str]  # slugs the user has
    location: str | None = None
    split_preference: str = "auto"
    custom_days: tuple | None = None  # tuple[DayTemplate, ...] for split_preference == "custom"


@dataclass
class PlannedExercise:
    exercise_id: int
    name: str
    primary_muscle: str
    sets: int
    rep_min: int
    rep_max: int
    rest_seconds: int
    role: str  # compound | isolation | conditioning
    priority: int  # lower = more important; used when trimming to fit the session length


@dataclass
class PlannedDay:
    day_index: int  # 1..7 within the weekly cycle
    name: str
    focus: str
    is_rest: bool
    exercises: list[PlannedExercise] = field(default_factory=list)
    estimated_minutes: int | None = None


@dataclass
class GeneratedPlan:
    name: str
    split: str
    goal: str
    days: list[PlannedDay]
    equipment: frozenset[str]  # equipment actually allowed after filtering
    warnings: list[str] = field(default_factory=list)

    @property
    def training_days(self) -> list[PlannedDay]:
        return [d for d in self.days if not d.is_rest]
