from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import WorkoutStatus
from app.schemas.exercise import ExerciseOut


def _half_steps(v: float | None) -> float | None:
    if v is not None and (v * 2) != int(v * 2):
        raise ValueError("RPE must be between 1 and 10 in steps of 0.5.")
    return v


class SetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight_kg: float | None = Field(None, ge=0, le=1000)
    reps: int | None = Field(None, ge=0, le=1000)
    rpe: float | None = Field(None, ge=1, le=10)
    rir: int | None = Field(None, ge=0, le=10)
    rest_seconds: int | None = Field(None, ge=0, le=3600)
    notes: str | None = Field(None, max_length=500)
    is_completed: bool = False

    @field_validator("rpe")
    @classmethod
    def _rpe_steps(cls, v):
        return _half_steps(v)


class SessionExerciseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: int
    notes: str | None = Field(None, max_length=1000)
    sets: list[SetIn] = Field(default_factory=list, max_length=30)


class SessionCreate(BaseModel):
    """Phase 0 endpoint: record a whole session in one request (e.g. an imported or retroactive one)."""

    model_config = ConfigDict(extra="forbid")

    plan_id: int | None = None
    performed_on: date | None = None
    duration_minutes: int | None = Field(None, ge=1, le=600)
    status: WorkoutStatus = WorkoutStatus.planned
    notes: str | None = Field(None, max_length=2000)
    exercises: list[SessionExerciseIn] = Field(default_factory=list, max_length=40)


class SessionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_day_id: int
    performed_on: date | None = None  # the user's local date; defaults to today on the server


class SetUpdate(BaseModel):
    """Partial update: only fields present are changed; an explicit null clears a value."""

    model_config = ConfigDict(extra="forbid")

    weight_kg: float | None = Field(None, ge=0, le=1000)
    reps: int | None = Field(None, ge=0, le=1000)
    rpe: float | None = Field(None, ge=1, le=10)
    rir: int | None = Field(None, ge=0, le=10)
    rest_seconds: int | None = Field(None, ge=0, le=3600)
    notes: str | None = Field(None, max_length=500)
    is_completed: bool | None = None

    @field_validator("rpe")
    @classmethod
    def _rpe_steps(cls, v):
        return _half_steps(v)

    @field_validator("is_completed")
    @classmethod
    def _completion_not_null(cls, v):
        if v is None:  # only runs when the field was sent
            raise ValueError("Must be true or false.")
        return v


class SessionComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_minutes: int | None = Field(None, ge=1, le=600)
    notes: str | None = Field(None, max_length=2000)


class SetOut(SetIn):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: int
    set_number: int
    target_reps_min: int | None = None
    target_reps_max: int | None = None


class SessionExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    notes: str | None = None
    rest_seconds: int | None = None
    exercise: ExerciseOut
    sets: list[SetOut] = []


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int | None = None
    plan_day_id: int | None = None
    name: str | None = None
    performed_on: date
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_minutes: int | None = None
    status: WorkoutStatus
    notes: str | None = None
    exercises: list[SessionExerciseOut] = []
    created_at: datetime
