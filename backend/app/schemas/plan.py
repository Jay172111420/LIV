from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ExperienceLevel, PlanKind, SplitType, TrainingLocation
from app.schemas.exercise import ExerciseOut
from app.schemas.reference import EquipmentOut, GoalOut

# `auto` lets the engine choose; `custom` is engine-only for now, so the API doesn't offer it.
SplitPreference = Literal["auto", "full_body", "upper_lower", "push_pull_legs", "push_pull", "bro_split"]


def _clean_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Name can't be empty.")
    return v


class PlanCreate(BaseModel):
    """Phase 0 endpoint: an empty plan shell. Kept for compatibility."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    goal_id: int | None = None
    days_per_week: int | None = Field(None, ge=1, le=7)
    experience_level: ExperienceLevel | None = None
    duration_minutes: int | None = Field(None, ge=10, le=240)
    equipment_ids: list[int] = Field(default_factory=list, max_length=50)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return _clean_name(v)

    @field_validator("equipment_ids")
    @classmethod
    def _unique(cls, v):
        return sorted(set(v))


class GeneratePlanIn(BaseModel):
    """Every field is optional: anything omitted is taken from the user's profile."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=120)
    goal_id: int | None = None
    experience_level: ExperienceLevel | None = None
    days_per_week: int | None = Field(None, ge=1, le=7)
    duration_minutes: int | None = Field(None, ge=10, le=240)
    training_location: TrainingLocation | None = None
    equipment_ids: list[int] | None = Field(None, max_length=50)
    split_preference: SplitPreference = "auto"

    @field_validator("name")
    @classmethod
    def _strip(cls, v):
        return None if v is None else _clean_name(v)

    @field_validator("equipment_ids")
    @classmethod
    def _unique(cls, v):
        return None if v is None else sorted(set(v))


class PlanExerciseIn(BaseModel):
    """Prescription fields left out are filled from the exercise's own recommendations."""

    model_config = ConfigDict(extra="forbid")

    exercise_id: int
    sets: int | None = Field(None, ge=1, le=10)
    rep_min: int | None = Field(None, ge=1, le=300)
    rep_max: int | None = Field(None, ge=1, le=300)
    rest_seconds: int | None = Field(None, ge=0, le=600)
    notes: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _range(self):
        if self.rep_min is not None and self.rep_max is not None and self.rep_max < self.rep_min:
            raise ValueError("Max reps can't be lower than min reps.")
        return self


class PlanExerciseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sets: int | None = Field(None, ge=1, le=10)
    rep_min: int | None = Field(None, ge=1, le=300)
    rep_max: int | None = Field(None, ge=1, le=300)
    rest_seconds: int | None = Field(None, ge=0, le=600)
    notes: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _range(self):
        if self.rep_min is not None and self.rep_max is not None and self.rep_max < self.rep_min:
            raise ValueError("Max reps can't be lower than min reps.")
        return self


class CustomWorkoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    exercises: list[PlanExerciseIn] = Field(default_factory=list, max_length=20)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return _clean_name(v)


class PlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=120)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip(cls, v):
        return None if v is None else _clean_name(v)


class DayUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return _clean_name(v)


class ReorderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_exercise_ids: list[int] = Field(max_length=20)


class ReplaceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: int


class PlanExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    exercise: ExerciseOut
    sets: int
    rep_min: int
    rep_max: int
    rest_seconds: int
    notes: str | None = None


class PlanDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    day_index: int
    name: str
    focus: str | None = None
    is_rest: bool
    estimated_minutes: int | None = None
    exercises: list[PlanExerciseOut] = []


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: PlanKind = PlanKind.custom
    split_type: SplitType | None = None
    goal: GoalOut | None = None
    days_per_week: int | None = None
    experience_level: ExperienceLevel | None = None
    duration_minutes: int | None = None
    training_location: TrainingLocation | None = None
    equipment: list[EquipmentOut] = []
    workout_count: int = 0
    exercise_count: int = 0
    start_day_id: int | None = None  # first day that can be started, if any
    warnings: list[str] = []
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PlanDetailOut(PlanOut):
    days: list[PlanDayOut] = []
