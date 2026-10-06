"""The only bridge between database rows and the pure workout engine."""
from collections.abc import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.engine import EquipmentFilter, ExerciseInfo
from app.models import Equipment, Exercise, UserProfile


def to_info(ex: Exercise) -> ExerciseInfo:
    return ExerciseInfo(
        id=ex.id,
        name=ex.name,
        primary_muscle=ex.primary_muscle_group.slug,
        secondary_muscles=tuple(sorted(m.slug for m in ex.secondary_muscle_groups)),
        movement_pattern=ex.movement_pattern.value,
        equipment=frozenset(e.slug for e in ex.equipment),
        difficulty=ex.difficulty.value,
        min_experience=ex.min_experience_level.value,
        exercise_type=ex.exercise_type.value,
        is_compound=ex.is_compound,
        is_timed=ex.is_timed,
        rep_min=ex.rep_min,
        rep_max=ex.rep_max,
        sets=ex.recommended_sets,
        is_active=ex.is_active,
    )


_EAGER = (
    selectinload(Exercise.primary_muscle_group),
    selectinload(Exercise.secondary_muscle_groups),
    selectinload(Exercise.equipment),
)


def load_pool(db: Session, user_id: int | None, *, include_custom: bool) -> list[Exercise]:
    """Active exercises. The generator uses built-ins only (custom ones have user-chosen metadata);
    substitution also considers the user's own custom exercises."""
    owner = Exercise.owner_user_id.is_(None)
    if include_custom and user_id is not None:
        owner = or_(owner, Exercise.owner_user_id == user_id)
    return list(db.scalars(select(Exercise).where(Exercise.is_active, owner).options(*_EAGER)))


def equipment_filter(equipment: Iterable[Equipment], location) -> EquipmentFilter:
    return EquipmentFilter([e.slug for e in equipment], location)


def profile_equipment_filter(profile: UserProfile) -> EquipmentFilter:
    return equipment_filter(profile.equipment, profile.training_location)
