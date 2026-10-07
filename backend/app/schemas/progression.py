from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ProgressionStrategy, RecommendationAction, RecommendationChoice, RecordType


class FlagOut(BaseModel):
    code: str
    message: str
    level: str = "info"
    detail: str | None = None


class LastSetOut(BaseModel):
    weight_kg: float | None = None
    reps: int
    rir: int | None = None
    rpe: float | None = None


class LastSessionOut(BaseModel):
    performed_on: date
    sets: list[LastSetOut]


class RecommendationOut(BaseModel):
    """A suggestion for one exercise. `id` is null for a preview that hasn't been attached to a workout."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    exercise_id: int
    strategy: ProgressionStrategy
    action: RecommendationAction
    weight_kg: float | None = None
    rep_min: int
    rep_max: int
    reps_goal: int | None = None
    sets: int
    increment_kg: float | None = None
    reason: str
    confidence: str = "low"
    flags: list[FlagOut] = []
    last_session: LastSessionOut | None = None
    user_choice: RecommendationChoice = RecommendationChoice.pending
    chosen_weight_kg: float | None = None
    chosen_reps: int | None = None
    performed_weight_kg: float | None = None
    followed: bool | None = None


class RecommendationResponse(BaseModel):
    """The user's answer to a recommendation: accept it, edit it, or ignore it."""

    model_config = ConfigDict(extra="forbid")

    choice: Literal["accepted", "edited", "ignored"]
    weight_kg: float | None = Field(None, ge=0, le=1000)
    reps: int | None = Field(None, ge=1, le=1000)

    @model_validator(mode="after")
    def _shape(self):
        if self.choice == "edited" and self.weight_kg is None and self.reps is None:
            raise ValueError("Enter a weight or reps to use instead.")
        if self.choice != "edited" and (self.weight_kg is not None or self.reps is not None):
            raise ValueError("Weight and reps can only be sent when editing.")
        return self


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    exercise_name: str
    session_id: int
    record_type: RecordType
    value: float
    weight_kg: float | None = None
    reps: int | None = None
    previous_value: float | None = None
    achieved_on: date


class ProgressionSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: ProgressionStrategy | None = None  # null or "auto" = let Liv decide
    increment_kg: float | None = Field(None, gt=0, le=100)  # null = use the default for this equipment


class ProgressionSettingsOut(BaseModel):
    strategy: ProgressionStrategy = ProgressionStrategy.auto
    increment_kg: float | None = None
    effective_increment_kg: float | None = None
    default_increment_kg: float
    category: str
    uses_weight: bool


class IncrementPreferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    increment_kg: float | None = Field(None, gt=0, le=100)  # null resets to the default


class IncrementPreferenceOut(BaseModel):
    category: str
    default_kg: float
    custom_kg: float | None = None
    effective_kg: float


# ---------------------------------------------------------------- history
class HistorySetOut(BaseModel):
    weight_kg: float | None = None
    reps: int
    rir: int | None = None
    rpe: float | None = None
    estimated_1rm_kg: float | None = None


class HistorySessionOut(BaseModel):
    session_id: int
    performed_on: date
    sets: list[HistorySetOut]
    volume_kg: float
    total_reps: int
    top_weight_kg: float | None = None
    best_estimated_1rm_kg: float | None = None
    score: float | None = None


class BestOut(BaseModel):
    weight_kg: float | None = None
    weight_reps: int | None = None
    reps: int | None = None
    reps_at_weight_kg: float | None = None
    estimated_1rm_kg: float | None = None
    volume_kg: float | None = None  # best single-session volume


class TrendOut(BaseModel):
    direction: Literal["improving", "steady", "declining", "insufficient_data"]
    percent_change: float | None = None
    points: list[float] = []  # oldest to newest performance score, one per session
    dates: list[date] = []
    metric: Literal["estimated_1rm_kg", "average_reps"] = "estimated_1rm_kg"


class ExerciseHistoryOut(BaseModel):
    exercise_id: int
    exercise_name: str
    is_timed: bool
    uses_weight: bool
    session_count: int
    total_sets: int
    total_volume_kg: float
    best: BestOut
    recent_sessions: list[HistorySessionOut]
    records: list[RecordOut]
    trend: TrendOut
    flags: list[FlagOut] = []
    notes: list[str] = []


class TrainedExerciseOut(BaseModel):
    exercise_id: int
    name: str
    muscle_group: str
    session_count: int
    last_performed_on: date
    best_weight_kg: float | None = None
    flagged: bool = False


# ---------------------------------------------------------------- volume
class VolumeRow(BaseModel):
    key: str
    label: str
    volume_kg: float
    sets: int
    reps: int


class VolumeReportOut(BaseModel):
    weeks: int
    since: date
    by_week: list[VolumeRow]
    by_muscle_group: list[VolumeRow]
    by_exercise: list[VolumeRow]
    by_workout: list[VolumeRow]
    note: str


class ExerciseFlagOut(BaseModel):
    exercise_id: int
    name: str
    flag: FlagOut


class FlagReportOut(BaseModel):
    exercises: list[ExerciseFlagOut]
    overall: FlagOut | None = None
