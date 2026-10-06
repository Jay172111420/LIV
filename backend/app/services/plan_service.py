"""Workout plans: generation, custom workouts, and editing days/exercises. All queries are user-scoped."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.engine import (
    ExerciseSubstitutionService,
    GenerationInput,
    WorkoutGenerator,
)
from app.engine.prescription import rest_seconds as default_rest
from app.errors import AppError, NotFoundError
from app.models import (
    Equipment,
    Exercise,
    FitnessGoal,
    PlanDay,
    PlanExercise,
    User,
    WorkoutPlan,
)
from app.models.enums import PlanKind, SplitType
from app.schemas.plan import (
    CustomWorkoutCreate,
    GeneratePlanIn,
    PlanCreate,
    PlanExerciseIn,
    PlanExerciseUpdate,
    PlanUpdate,
)
from app.services import engine_adapter
from app.services.exercise_service import _visible_to, resolve_substitutes
from app.services.profile_service import load_equipment

MAX_EXERCISES_PER_DAY = 20

_EX = (
    selectinload(WorkoutPlan.days).selectinload(PlanDay.exercises)
    .selectinload(PlanExercise.exercise).selectinload(Exercise.primary_muscle_group),
    selectinload(WorkoutPlan.days).selectinload(PlanDay.exercises)
    .selectinload(PlanExercise.exercise).selectinload(Exercise.secondary_muscle_groups),
    selectinload(WorkoutPlan.days).selectinload(PlanDay.exercises)
    .selectinload(PlanExercise.exercise).selectinload(Exercise.equipment),
    selectinload(WorkoutPlan.equipment),
    selectinload(WorkoutPlan.goal),
)


# ---------------------------------------------------------------- reading
def list_plans(db: Session, user_id: int, kind: PlanKind | None = None) -> list[WorkoutPlan]:
    stmt = (select(WorkoutPlan).where(WorkoutPlan.user_id == user_id)
            .options(selectinload(WorkoutPlan.days).selectinload(PlanDay.exercises),
                     selectinload(WorkoutPlan.equipment),
                     selectinload(WorkoutPlan.goal))
            .order_by(WorkoutPlan.created_at.desc(), WorkoutPlan.id.desc()))
    if kind:
        stmt = stmt.where(WorkoutPlan.kind == kind)
    return list(db.scalars(stmt))


def get_plan(db: Session, user_id: int, plan_id: int) -> WorkoutPlan:
    plan = db.scalar(select(WorkoutPlan).where(WorkoutPlan.id == plan_id, WorkoutPlan.user_id == user_id)
                     .options(*_EX).execution_options(populate_existing=True))
    if plan is None:
        raise NotFoundError("Workout plan not found.")
    return plan


def get_day(db: Session, user_id: int, plan_id: int, day_id: int) -> tuple[WorkoutPlan, PlanDay]:
    plan = get_plan(db, user_id, plan_id)
    day = next((d for d in plan.days if d.id == day_id), None)
    if day is None:
        raise NotFoundError("Workout day not found.")
    return plan, day


def get_day_by_id(db: Session, user_id: int, day_id: int) -> tuple[WorkoutPlan, PlanDay]:
    plan_id = db.scalar(select(PlanDay.plan_id).join(WorkoutPlan, WorkoutPlan.id == PlanDay.plan_id)
                        .where(PlanDay.id == day_id, WorkoutPlan.user_id == user_id))
    if plan_id is None:
        raise NotFoundError("Workout day not found.")
    return get_day(db, user_id, plan_id, day_id)


def _plan_day_for_edit(db: Session, user_id: int, plan_id: int, day_id: int):
    plan, day = get_day(db, user_id, plan_id, day_id)
    if day.is_rest:
        raise AppError("Rest days can't have exercises.", code="rest_day")
    return plan, day


def _get_plan_exercise(day: PlanDay, plan_exercise_id: int) -> PlanExercise:
    item = next((e for e in day.exercises if e.id == plan_exercise_id), None)
    if item is None:
        raise NotFoundError("Exercise not found in this workout.")
    return item


# ---------------------------------------------------------------- creating
def create_plan(db: Session, user_id: int, data: PlanCreate) -> WorkoutPlan:
    """Phase 0 endpoint: an empty plan shell with no days."""
    if data.goal_id is not None and not db.get(FitnessGoal, data.goal_id):
        raise AppError("That fitness goal doesn't exist.", code="invalid_goal")
    plan = WorkoutPlan(
        user_id=user_id, name=data.name, goal_id=data.goal_id, days_per_week=data.days_per_week,
        experience_level=data.experience_level, duration_minutes=data.duration_minutes,
        equipment=load_equipment(db, data.equipment_ids), kind=PlanKind.custom,
    )
    db.add(plan)
    db.commit()
    return get_plan(db, user_id, plan.id)


def generate_plan(db: Session, user: User, data: GeneratePlanIn) -> WorkoutPlan:
    """Resolves inputs (request first, profile as the fallback), runs the engine, and saves the result."""
    profile = user.profile
    goal_id = data.goal_id or profile.goal_id
    goal = db.scalar(select(FitnessGoal).where(FitnessGoal.id == goal_id, FitnessGoal.is_active)) \
        if goal_id else None
    if goal_id and goal is None:
        raise AppError("That fitness goal doesn't exist.", code="invalid_goal")
    experience = data.experience_level or profile.experience_level
    days = data.days_per_week or profile.training_days_per_week
    duration = data.duration_minutes or profile.preferred_workout_minutes
    location = data.training_location or profile.training_location
    equipment = (load_equipment(db, data.equipment_ids) if data.equipment_ids is not None
                 else list(profile.equipment))

    missing = [name for name, value in (("goal", goal), ("experience level", experience),
                                         ("training days per week", days), ("session length", duration),
                                         ("training location", location)) if not value]
    if missing:
        raise AppError(f"Add your {', '.join(missing)} before generating a plan.",
                       code="profile_incomplete", details=missing)

    pool = [engine_adapter.to_info(e) for e in engine_adapter.load_pool(db, None, include_custom=False)]
    generated = WorkoutGenerator(pool).generate(GenerationInput(
        goal=goal.slug, experience=experience.value, days_per_week=days, duration_minutes=duration,
        equipment=frozenset(e.slug for e in equipment), location=location.value,
        split_preference=data.split_preference,
    ))

    used_gear = {e.slug: e for e in db.scalars(select(Equipment).where(Equipment.slug.in_(generated.equipment)))}
    plan = WorkoutPlan(
        user_id=user.id,
        name=data.name or f"{generated.name}: {goal.name}",
        kind=PlanKind.generated, split_type=SplitType(generated.split),
        goal_id=goal.id, days_per_week=days, experience_level=experience, duration_minutes=duration,
        training_location=location, equipment=list(used_gear.values()),
        notes="\n".join(generated.warnings) or None,
        days=[
            PlanDay(
                day_index=d.day_index, name=d.name, focus=d.focus, is_rest=d.is_rest,
                exercises=[
                    PlanExercise(exercise_id=e.exercise_id, position=pos, sets=e.sets, rep_min=e.rep_min,
                                 rep_max=e.rep_max, rest_seconds=e.rest_seconds)
                    for pos, e in enumerate(d.exercises, 1)
                ],
            )
            for d in generated.days
        ],
    )
    # A user follows one generated plan at a time; older ones stay available but inactive.
    db.execute(update(WorkoutPlan).where(WorkoutPlan.user_id == user.id,
                                         WorkoutPlan.kind == PlanKind.generated).values(is_active=False))
    db.add(plan)
    db.commit()
    return get_plan(db, user.id, plan.id)


def _default_rx(ex: Exercise) -> dict:
    info = engine_adapter.to_info(ex)
    return {"sets": ex.recommended_sets, "rep_min": ex.rep_min, "rep_max": ex.rep_max,
            "rest_seconds": default_rest(info, "general_fitness", ex.rep_max)}


def _visible_exercise(db: Session, user_id: int, exercise_id: int) -> Exercise:
    ex = db.scalar(select(Exercise).where(Exercise.id == exercise_id, *_visible_to(user_id))
                   .options(*engine_adapter._EAGER))
    if ex is None:
        raise AppError("That exercise doesn't exist.", code="invalid_exercise", details=[exercise_id])
    return ex


def _build_plan_exercise(db: Session, user_id: int, item: PlanExerciseIn, position: int) -> PlanExercise:
    ex = _visible_exercise(db, user_id, item.exercise_id)
    rx = _default_rx(ex)
    for key in ("sets", "rep_min", "rep_max", "rest_seconds"):
        value = getattr(item, key)
        if value is not None:
            rx[key] = value
    if rx["rep_max"] < rx["rep_min"]:  # one end was given alone and crosses the default of the other
        raise AppError("Max reps can't be lower than min reps.", code="invalid_rep_range")
    return PlanExercise(exercise_id=ex.id, position=position, notes=item.notes, **rx)


def create_custom_workout(db: Session, user_id: int, data: CustomWorkoutCreate) -> WorkoutPlan:
    ids = [e.exercise_id for e in data.exercises]
    if len(ids) != len(set(ids)):
        raise AppError("An exercise can only appear once in a workout.", code="duplicate_exercise_in_day")
    plan = WorkoutPlan(
        user_id=user_id, name=data.name, kind=PlanKind.custom,
        days=[PlanDay(day_index=1, name=data.name, focus="Custom workout", is_rest=False,
                      exercises=[_build_plan_exercise(db, user_id, item, pos)
                                 for pos, item in enumerate(data.exercises, 1)])],
    )
    db.add(plan)
    db.commit()
    return get_plan(db, user_id, plan.id)


# ---------------------------------------------------------------- editing plans
def update_plan(db: Session, user_id: int, plan_id: int, data: PlanUpdate) -> WorkoutPlan:
    plan = get_plan(db, user_id, plan_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        plan.name = changes["name"]
        if plan.kind == PlanKind.custom and len(plan.days) == 1:
            plan.days[0].name = changes["name"]  # a custom workout is named after its only day
    if changes.get("is_active") is not None:
        plan.is_active = changes["is_active"]
    db.commit()
    return get_plan(db, user_id, plan_id)


def delete_plan(db: Session, user_id: int, plan_id: int) -> None:
    plan = get_plan(db, user_id, plan_id)
    db.delete(plan)  # logged sessions are kept; their plan links are cleared by the database
    db.commit()


def rename_day(db: Session, user_id: int, plan_id: int, day_id: int, name: str) -> PlanDay:
    plan, day = get_day(db, user_id, plan_id, day_id)
    day.name = name
    if plan.kind == PlanKind.custom and len(plan.days) == 1:
        plan.name = name
    db.commit()
    return get_day(db, user_id, plan_id, day_id)[1]


# ---------------------------------------------------------------- editing days
def _renumber(day: PlanDay, ordered: list[PlanExercise]) -> None:
    for pos, item in enumerate(ordered, 1):
        item.position = pos


def add_exercise(db: Session, user_id: int, plan_id: int, day_id: int, data: PlanExerciseIn) -> PlanDay:
    plan, day = _plan_day_for_edit(db, user_id, plan_id, day_id)
    if len(day.exercises) >= MAX_EXERCISES_PER_DAY:
        raise AppError(f"A workout can have at most {MAX_EXERCISES_PER_DAY} exercises.", code="too_many_exercises")
    if any(e.exercise_id == data.exercise_id for e in day.exercises):
        raise AppError("That exercise is already in this workout.", code="duplicate_exercise_in_day")
    item = _build_plan_exercise(db, user_id, data, len(day.exercises) + 1)
    day.exercises.append(item)
    db.commit()
    return get_day(db, user_id, plan_id, day_id)[1]


def update_exercise(db: Session, user_id: int, plan_id: int, day_id: int, plan_exercise_id: int,
                    data: PlanExerciseUpdate) -> PlanDay:
    _, day = _plan_day_for_edit(db, user_id, plan_id, day_id)
    item = _get_plan_exercise(day, plan_exercise_id)
    changes = data.model_dump(exclude_unset=True)
    for key in ("sets", "rep_min", "rep_max", "rest_seconds"):
        if key in changes and changes[key] is None:
            raise AppError(f"{key.replace('_', ' ').capitalize()} can't be empty.", code="validation_error")
    lo = changes.get("rep_min", item.rep_min)
    hi = changes.get("rep_max", item.rep_max)
    if hi < lo:
        raise AppError("Max reps can't be lower than min reps.", code="invalid_rep_range")
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    return get_day(db, user_id, plan_id, day_id)[1]


def remove_exercise(db: Session, user_id: int, plan_id: int, day_id: int, plan_exercise_id: int) -> PlanDay:
    _, day = _plan_day_for_edit(db, user_id, plan_id, day_id)
    item = _get_plan_exercise(day, plan_exercise_id)
    day.exercises.remove(item)
    db.flush()
    _renumber(day, day.exercises)
    db.commit()
    return get_day(db, user_id, plan_id, day_id)[1]


def reorder(db: Session, user_id: int, plan_id: int, day_id: int, plan_exercise_ids: list[int]) -> PlanDay:
    _, day = _plan_day_for_edit(db, user_id, plan_id, day_id)
    current = {e.id: e for e in day.exercises}
    if sorted(plan_exercise_ids) != sorted(current) or len(set(plan_exercise_ids)) != len(plan_exercise_ids):
        raise AppError("The new order must list every exercise in this workout exactly once.",
                       code="invalid_order")
    _renumber(day, [current[i] for i in plan_exercise_ids])
    db.commit()
    return get_day(db, user_id, plan_id, day_id)[1]


# ---------------------------------------------------------------- substitution
def _substitution_service(db: Session, user: User, plan: WorkoutPlan) -> ExerciseSubstitutionService:
    """Generated plans substitute within the equipment they were built for; custom workouts use the
    user's current equipment."""
    profile = user.profile
    if plan.kind == PlanKind.generated:
        gear = engine_adapter.equipment_filter(plan.equipment, plan.training_location)
    else:
        gear = engine_adapter.profile_equipment_filter(profile)
    level = (plan.experience_level or profile.experience_level)
    pool = [engine_adapter.to_info(e) for e in engine_adapter.load_pool(db, user.id, include_custom=True)]
    return ExerciseSubstitutionService(pool, gear, level.value if level else "beginner")


def substitutes_for(db: Session, user: User, plan_id: int, day_id: int, plan_exercise_id: int,
                    limit: int = 8) -> list[dict]:
    plan, day = _plan_day_for_edit(db, user.id, plan_id, day_id)
    item = _get_plan_exercise(day, plan_exercise_id)
    service = _substitution_service(db, user, plan)
    found = service.candidates(engine_adapter.to_info(item.exercise),
                               exclude_ids=[e.exercise_id for e in day.exercises], limit=limit)
    return resolve_substitutes(db, user.id, found)


def replace_exercise(db: Session, user: User, plan_id: int, day_id: int, plan_exercise_id: int,
                     new_exercise_id: int) -> PlanDay:
    """Swaps the exercise but keeps its position, sets, rep range, rest and notes, so the workout keeps its
    intent. Only a valid substitute (same muscle, movement, equipment-available) is accepted."""
    plan, day = _plan_day_for_edit(db, user.id, plan_id, day_id)
    item = _get_plan_exercise(day, plan_exercise_id)
    replacement = _visible_exercise(db, user.id, new_exercise_id)
    service = _substitution_service(db, user, plan)
    if not service.is_valid_substitute(engine_adapter.to_info(item.exercise),
                                      engine_adapter.to_info(replacement),
                                      exclude_ids=[e.exercise_id for e in day.exercises]):
        raise AppError("That exercise isn't a suitable replacement: it must train the same muscle, use "
                       "your available equipment, and not already be in this workout.",
                       code="invalid_substitute")
    if replacement.is_timed != item.exercise.is_timed:  # reps <-> seconds: use the new exercise's defaults
        item.rep_min, item.rep_max = replacement.rep_min, replacement.rep_max
    item.exercise = replacement
    db.commit()
    return get_day(db, user.id, plan_id, day_id)[1]
