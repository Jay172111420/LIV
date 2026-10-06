from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.errors import AppError, NotFoundError
from app.engine import ExerciseSubstitutionService
from app.models import Equipment, Exercise, MuscleGroup, User, exercise_equipment
from app.schemas.exercise import ExerciseCreate
from app.services import engine_adapter
from app.services.profile_service import load_equipment

_EAGER = (
    selectinload(Exercise.primary_muscle_group),
    selectinload(Exercise.secondary_muscle_groups),
    selectinload(Exercise.equipment),
)


def _visible_to(user_id: int):
    """Built-in exercises plus the user's own custom ones. Never another user's."""
    return (Exercise.is_active, or_(Exercise.owner_user_id.is_(None), Exercise.owner_user_id == user_id))


def list_exercises(db: Session, user_id: int, *, q: str | None, muscle_group_id: int | None,
                   equipment_id: int | None, limit: int, offset: int,
                   available_for: User | None = None) -> list[Exercise]:
    """`available_for` restricts to exercises the given user can do with their equipment and location."""
    stmt = select(Exercise).where(*_visible_to(user_id)).options(*_EAGER)
    if available_for is not None:
        allowed = engine_adapter.profile_equipment_filter(available_for.profile).available
        allowed_ids = select(Equipment.id).where(Equipment.slug.in_(allowed))
        needs_missing_gear = select(exercise_equipment.c.exercise_id).where(
            exercise_equipment.c.equipment_id.not_in(allowed_ids))
        stmt = stmt.where(Exercise.id.not_in(needs_missing_gear))
    if q:
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Exercise.name.ilike(f"%{escaped}%", escape="\\"))
    if muscle_group_id:
        stmt = stmt.where(Exercise.primary_muscle_group_id == muscle_group_id)
    if equipment_id:
        stmt = stmt.where(
            Exercise.id.in_(
                select(exercise_equipment.c.exercise_id).where(
                    exercise_equipment.c.equipment_id == equipment_id
                )
            )
        )
    return list(db.scalars(stmt.order_by(Exercise.name).limit(limit).offset(offset)))


def get_exercise(db: Session, user_id: int, exercise_id: int) -> Exercise:
    ex = db.scalar(select(Exercise).where(Exercise.id == exercise_id, *_visible_to(user_id))
                   .options(*_EAGER))
    if ex is None:
        raise NotFoundError("Exercise not found.")
    return ex


def create_exercise(db: Session, user_id: int, data: ExerciseCreate) -> Exercise:
    muscle_ids = {data.primary_muscle_group_id, *data.secondary_muscle_group_ids}
    muscles = {m.id: m for m in db.scalars(select(MuscleGroup).where(MuscleGroup.id.in_(muscle_ids)))}
    if muscle_ids - muscles.keys():
        raise AppError("One or more muscle groups don't exist.", code="invalid_muscle_group")

    duplicate = db.scalar(
        select(Exercise.id).where(Exercise.owner_user_id == user_id,
                                  Exercise.name.ilike(data.name, escape="\\"))
    )
    if duplicate:
        raise AppError("You already have an exercise with this name.", code="duplicate_exercise")

    exercise = Exercise(
        owner_user_id=user_id,
        name=data.name,
        description=data.description,
        primary_muscle_group=muscles[data.primary_muscle_group_id],
        secondary_muscle_groups=[muscles[i] for i in data.secondary_muscle_group_ids
                                 if i != data.primary_muscle_group_id],
        movement_pattern=data.movement_pattern,
        difficulty=data.difficulty,
        exercise_type=data.exercise_type,
        instructions=data.instructions,
        equipment=load_equipment(db, data.equipment_ids),
        min_experience_level=data.min_experience_level or data.difficulty,
        is_compound=(data.exercise_type.value == "compound") if data.is_compound is None
        else data.is_compound,
        is_timed=data.is_timed,
        rep_min=data.rep_min,
        rep_max=data.rep_max,
        recommended_sets=data.recommended_sets,
    )
    db.add(exercise)
    db.commit()
    return get_exercise(db, user_id, exercise.id)


def substitutes(db: Session, user: User, exercise_id: int, *, limit: int = 8):
    """Replacement ideas for one exercise, using the user's own equipment, location and experience."""
    target = get_exercise(db, user.id, exercise_id)
    profile = user.profile
    service = ExerciseSubstitutionService(
        [engine_adapter.to_info(e) for e in engine_adapter.load_pool(db, user.id, include_custom=True)],
        engine_adapter.profile_equipment_filter(profile),
        (profile.experience_level.value if profile.experience_level else "beginner"),
    )
    return resolve_substitutes(db, user.id, service.candidates(engine_adapter.to_info(target), limit=limit))


def resolve_substitutes(db: Session, user_id: int, found) -> list[dict]:
    """Attaches the full exercise rows to engine results."""
    rows = {e.id: e for e in db.scalars(
        select(Exercise).where(Exercise.id.in_([f.exercise.id for f in found])).options(*_EAGER))}
    return [{"exercise": rows[f.exercise.id], "score": f.score, "reasons": list(f.reasons)} for f in found]
