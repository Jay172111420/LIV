from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ExperienceLevel, WorkoutStatus
from app.schemas.exercise import ExerciseOut
from app.schemas.reference import EquipmentOut, GoalOut


class PlanCreate(BaseModel):
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
        v = v.strip()
        if not v:
            raise ValueError("Name can't be empty.")
        return v

    @field_validator("equipment_ids")
    @classmethod
    def _unique(cls, v):
        return sorted(set(v))


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    goal: GoalOut | None = None
    days_per_week: int | None = None
    experience_level: ExperienceLevel | None = None
    duration_minutes: int | None = None
    equipment: list[EquipmentOut] = []
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight_kg: float | None = Field(None, ge=0, le=1000)
    reps: int | None = Field(None, ge=0, le=1000)
    rpe: float | None = Field(None, ge=1, le=10)
    rir: int | None = Field(None, ge=0, le=10)
    rest_seconds: int | None = Field(None, ge=0, le=3600)
    is_completed: bool = False


class SessionExerciseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: int
    notes: str | None = Field(None, max_length=1000)
    sets: list[SetIn] = Field(default_factory=list, max_length=30)


class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: int | None = None
    performed_on: date | None = None
    duration_minutes: int | None = Field(None, ge=1, le=600)
    status: WorkoutStatus = WorkoutStatus.planned
    notes: str | None = Field(None, max_length=2000)
    exercises: list[SessionExerciseIn] = Field(default_factory=list, max_length=40)


class SetOut(SetIn):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    id: int
    set_number: int


class SessionExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    position: int
    notes: str | None = None
    exercise: ExerciseOut
    sets: list[SetOut] = []


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int | None = None
    performed_on: date
    duration_minutes: int | None = None
    status: WorkoutStatus
    notes: str | None = None
    exercises: list[SessionExerciseOut] = []
    created_at: datetime
