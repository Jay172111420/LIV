"""Importing this package registers every table on Base.metadata."""
from app.models.base import Base
from app.models.body_metric import BodyMetric
from app.models.exercise import Exercise, exercise_equipment, exercise_secondary_muscles
from app.models.nutrition import NutritionProfile, NutritionRestriction
from app.models.profile import UserProfile, UserTrainingDay, profile_equipment
from app.models.reference import Equipment, FitnessGoal, MuscleGroup
from app.models.progression import (
    ExerciseProgressionSetting,
    PersonalRecord,
    ProgressionRecommendation,
    UserIncrementPreference,
)
from app.models.user import AuthSession, User
from app.models.workout import (
    PlanDay,
    PlanExercise,
    WorkoutExercise,
    WorkoutPlan,
    WorkoutSession,
    WorkoutSet,
    plan_equipment,
)

__all__ = [
    "Base", "User", "AuthSession", "UserProfile", "UserTrainingDay", "FitnessGoal", "Equipment",
    "MuscleGroup", "Exercise", "WorkoutPlan", "PlanDay", "PlanExercise", "WorkoutSession", "WorkoutExercise", "WorkoutSet",
    "BodyMetric", "NutritionProfile", "NutritionRestriction", "profile_equipment",
    "ProgressionRecommendation", "PersonalRecord", "ExerciseProgressionSetting",
    "UserIncrementPreference", "exercise_equipment", "exercise_secondary_muscles", "plan_equipment",
]
