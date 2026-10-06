from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ActivityLevel, ExperienceLevel, Sex, TrainingLocation, UnitSystem
from app.schemas.reference import EquipmentOut, GoalOut


class ProfileUpdate(BaseModel):
    """Only fields present in the request are changed; an explicit null clears a field."""

    model_config = ConfigDict(extra="forbid")

    age: int | None = Field(None, ge=13, le=100)
    height_cm: float | None = Field(None, ge=90, le=250)
    weight_kg: float | None = Field(None, ge=25, le=400)
    sex: Sex | None = None
    experience_level: ExperienceLevel | None = None
    goal_id: int | None = None
    activity_level: ActivityLevel | None = None
    training_location: TrainingLocation | None = None
    training_days_per_week: int | None = Field(None, ge=1, le=7)
    preferred_workout_minutes: int | None = Field(None, ge=10, le=240)
    unit_preference: UnitSystem | None = None
    preferred_training_days: list[int] | None = Field(None, max_length=7)
    equipment_ids: list[int] | None = Field(None, max_length=50)

    @field_validator("preferred_training_days")
    @classmethod
    def _weekdays(cls, v):
        if v is None:
            return v
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("Weekdays must be between 0 (Monday) and 6 (Sunday).")
        return sorted(set(v))

    @field_validator("equipment_ids")
    @classmethod
    def _unique_ids(cls, v):
        return None if v is None else sorted(set(v))


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    sex: Sex | None = None
    experience_level: ExperienceLevel | None = None
    goal: GoalOut | None = None
    activity_level: ActivityLevel | None = None
    training_location: TrainingLocation | None = None
    training_days_per_week: int | None = None
    preferred_workout_minutes: int | None = None
    unit_preference: UnitSystem = UnitSystem.metric
    preferred_training_days: list[int] = []
    equipment: list[EquipmentOut] = []
    onboarding_complete: bool = False
