"""Idempotent reference data: goals, equipment, muscle groups and the built-in exercise library."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Equipment, Exercise, FitnessGoal, MuscleGroup
from app.seed_data.exercise_library import EXERCISE_LIBRARY

GOALS = [
    ("fat_loss", "Fat loss", "Lose body fat while keeping muscle."),
    ("muscle_gain", "Muscle gain", "Build muscle size."),
    ("recomposition", "Body recomposition", "Lose fat and build muscle at the same time."),
    ("strength", "Strength", "Lift heavier over time."),
    ("general_fitness", "General fitness", "Feel and move better overall."),
]

EQUIPMENT = [
    ("bodyweight", "Bodyweight", "none"),
    ("dumbbells", "Dumbbells", "free weights"),
    ("barbell", "Barbell", "free weights"),
    ("kettlebell", "Kettlebell", "free weights"),
    ("bench", "Bench", "furniture"),
    ("squat_rack", "Squat rack", "racks"),
    ("pull_up_bar", "Pull-up bar", "racks"),
    ("cable_machine", "Cable machine", "machines"),
    ("machines", "Machines", "machines"),
    ("resistance_bands", "Resistance bands", "accessories"),
]

MUSCLES = [
    ("chest", "Chest"), ("back", "Back"), ("shoulders", "Shoulders"), ("biceps", "Biceps"),
    ("triceps", "Triceps"), ("forearms", "Forearms"), ("quads", "Quads"),
    ("hamstrings", "Hamstrings"), ("glutes", "Glutes"), ("calves", "Calves"),
    ("core", "Core"), ("full_body", "Full body"),
]

def seed_reference_data(db: Session) -> None:
    existing = {g.slug for g in db.scalars(select(FitnessGoal))}
    for i, (slug, name, desc) in enumerate(GOALS):
        if slug not in existing:
            db.add(FitnessGoal(slug=slug, name=name, description=desc, sort_order=i))

    existing = {e.slug for e in db.scalars(select(Equipment))}
    for slug, name, category in EQUIPMENT:
        if slug not in existing:
            db.add(Equipment(slug=slug, name=name, category=category))

    existing = {m.slug for m in db.scalars(select(MuscleGroup))}
    for slug, name in MUSCLES:
        if slug not in existing:
            db.add(MuscleGroup(slug=slug, name=name))
    db.flush()

    equipment = {e.slug: e for e in db.scalars(select(Equipment))}
    muscles = {m.slug: m for m in db.scalars(select(MuscleGroup))}
    sync_exercise_library(db, equipment, muscles)
    db.commit()


def sync_exercise_library(db: Session, equipment: dict, muscles: dict) -> None:
    """The library file is the source of truth: new entries are added, existing built-ins are updated."""
    built_in = {e.name: e for e in db.scalars(select(Exercise).where(Exercise.owner_user_id.is_(None)))}
    for item in EXERCISE_LIBRARY:
        row = built_in.get(item["name"])
        if row is None:
            row = Exercise(name=item["name"])
            db.add(row)
        row.description = item["description"]
        row.instructions = item["instructions"]
        row.primary_muscle_group = muscles[item["primary"]]
        row.secondary_muscle_groups = [muscles[m] for m in item["secondary"]]
        row.movement_pattern = item["pattern"]
        row.exercise_type = item["type"]
        row.difficulty = item["difficulty"]
        row.min_experience_level = item["min_level"]
        row.equipment = [equipment[g] for g in item["equipment"]]
        row.rep_min = item["rep_min"]
        row.rep_max = item["rep_max"]
        row.recommended_sets = item["sets"]
        row.is_compound = item["is_compound"]
        row.is_timed = item["is_timed"]
        row.is_active = True
