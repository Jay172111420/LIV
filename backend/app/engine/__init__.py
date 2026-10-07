"""Deterministic workout engine. Pure Python: no database, no HTTP, no randomness.

Same inputs and same exercise pool always produce the same plan.
"""
from app.engine.equipment_filter import EquipmentFilter
from app.engine.exercise_selector import ExerciseSelector
from app.engine.split_generator import SplitGenerator
from app.engine.substitution import ExerciseSubstitutionService
from app.engine.types import ExerciseInfo, GeneratedPlan, GenerationInput, PlannedDay, PlannedExercise
from app.engine.metrics import SessionPerformance, SetPerformance
from app.engine.progression import (
    Action, ProgressionConfig, ProgressionEngine, ProgressionInput, ProgressionStrategy, Recommendation,
)
from app.engine.records import RecordEvent, detect_records
from app.engine.workout_generator import WorkoutGenerator

__all__ = [
    "EquipmentFilter", "ExerciseSelector", "SplitGenerator", "ExerciseSubstitutionService",
    "ExerciseInfo", "GeneratedPlan", "GenerationInput", "PlannedDay", "PlannedExercise",
    "WorkoutGenerator", "SessionPerformance", "SetPerformance", "Action", "ProgressionConfig",
    "ProgressionEngine", "ProgressionInput", "ProgressionStrategy", "Recommendation", "RecordEvent",
    "detect_records",
]
