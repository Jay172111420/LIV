from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ExerciseType, ExperienceLevel, MovementPattern
from app.schemas.reference import EquipmentOut, MuscleGroupOut


class ExerciseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(None, max_length=1000)
    primary_muscle_group_id: int
    secondary_muscle_group_ids: list[int] = Field(default_factory=list, max_length=11)
    movement_pattern: MovementPattern = MovementPattern.other
    difficulty: ExperienceLevel = ExperienceLevel.beginner
    exercise_type: ExerciseType = ExerciseType.compound
    instructions: str | None = Field(None, max_length=4000)
    equipment_ids: list[int] = Field(default_factory=list, max_length=20)
    min_experience_level: ExperienceLevel | None = None  # defaults to `difficulty`
    is_compound: bool | None = None  # defaults to exercise_type == compound
    is_timed: bool = False
    rep_min: int = Field(8, ge=1, le=300)
    rep_max: int = Field(12, ge=1, le=300)
    recommended_sets: int = Field(3, ge=1, le=10)

    @model_validator(mode="after")
    def _rep_range(self):
        if self.rep_max < self.rep_min:
            raise ValueError("Max reps can't be lower than min reps.")
        return self

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters.")
        return v

    @field_validator("secondary_muscle_group_ids", "equipment_ids")
    @classmethod
    def _unique(cls, v):
        return sorted(set(v))


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    primary_muscle_group: MuscleGroupOut
    secondary_muscle_groups: list[MuscleGroupOut] = []
    movement_pattern: MovementPattern
    difficulty: ExperienceLevel
    exercise_type: ExerciseType
    instructions: str | None = None
    equipment: list[EquipmentOut] = []
    min_experience_level: ExperienceLevel = ExperienceLevel.beginner
    is_compound: bool = False
    is_timed: bool = False
    rep_min: int = 8
    rep_max: int = 12
    recommended_sets: int = 3
    is_custom: bool = False
    is_active: bool = True


class SubstituteOut(BaseModel):
    exercise: ExerciseOut
    score: int
    reasons: list[str] = []
