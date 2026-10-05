"""Closed vocabularies stored as VARCHAR columns (portable, no native DB enums)."""
from enum import Enum

from sqlalchemy import Enum as SAEnum


class Sex(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class ExperienceLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class ActivityLevel(str, Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    active = "active"
    very_active = "very_active"


class TrainingLocation(str, Enum):
    commercial_gym = "commercial_gym"
    home_gym = "home_gym"
    home_bodyweight = "home_bodyweight"


class UnitSystem(str, Enum):
    metric = "metric"
    imperial = "imperial"


class MovementPattern(str, Enum):
    squat = "squat"
    hinge = "hinge"
    lunge = "lunge"
    push = "push"
    pull = "pull"
    carry = "carry"
    rotation = "rotation"
    core = "core"
    other = "other"


class ExerciseType(str, Enum):
    compound = "compound"
    isolation = "isolation"
    cardio = "cardio"
    mobility = "mobility"
    plyometric = "plyometric"


class WorkoutStatus(str, Enum):
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"


class BodyMetricType(str, Enum):
    weight = "weight"
    body_fat = "body_fat"
    waist = "waist"
    chest = "chest"
    arm = "arm"
    thigh = "thigh"
    hip = "hip"
    neck = "neck"
    custom = "custom"


class DietaryPreference(str, Enum):
    no_preference = "no_preference"
    vegetarian = "vegetarian"
    vegan = "vegan"
    pescatarian = "pescatarian"
    other = "other"


class RestrictionKind(str, Enum):
    allergy = "allergy"
    restriction = "restriction"


def db_enum(enum_cls: type[Enum]) -> SAEnum:
    """Enum column that stores the .value strings and enforces them with a CHECK constraint."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
