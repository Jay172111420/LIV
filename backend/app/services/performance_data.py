"""Reads completed workout data and converts it into engine objects. The only place that bridges the two."""
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.engine.metrics import SessionPerformance, SetPerformance
from app.models import Exercise, WorkoutExercise, WorkoutSession
from app.models.enums import WorkoutStatus


@dataclass
class LoggedExercise:
    session_id: int
    session_name: str | None
    performed_on: date
    exercise: Exercise
    sets: tuple[SetPerformance, ...]


def load_logged(db: Session, user_id: int, *, exercise_id: int | None = None, since: date | None = None,
                exclude_session_id: int | None = None) -> list[LoggedExercise]:
    """Every completed exercise entry (only completed sets with reps), newest workout first."""
    stmt = (
        select(WorkoutExercise, WorkoutSession)
        .join(WorkoutSession, WorkoutExercise.session_id == WorkoutSession.id)
        .where(WorkoutSession.user_id == user_id, WorkoutSession.status == WorkoutStatus.completed)
        .options(selectinload(WorkoutExercise.sets),
                 selectinload(WorkoutExercise.exercise).selectinload(Exercise.primary_muscle_group))
        .order_by(WorkoutSession.performed_on.desc(), WorkoutSession.id.desc(), WorkoutExercise.position)
    )
    if exercise_id is not None:
        stmt = stmt.where(WorkoutExercise.exercise_id == exercise_id)
    if since is not None:
        stmt = stmt.where(WorkoutSession.performed_on >= since)
    if exclude_session_id is not None:
        stmt = stmt.where(WorkoutSession.id != exclude_session_id)
    out = []
    for we, session in db.execute(stmt):
        sets = tuple(
            SetPerformance(weight_kg=s.weight_kg, reps=s.reps, rir=s.rir, rpe=s.rpe)
            for s in we.sets if s.is_completed and s.reps and s.reps >= 1)
        if sets:
            out.append(LoggedExercise(session.id, session.name, session.performed_on, we.exercise, sets))
    return out


def to_performances(rows: list[LoggedExercise]) -> list[SessionPerformance]:
    """One SessionPerformance per workout (an exercise listed twice in a workout is merged), order kept."""
    merged: dict[int, SessionPerformance] = {}
    for r in rows:
        if r.session_id in merged:
            prev = merged[r.session_id]
            merged[r.session_id] = SessionPerformance(prev.performed_on, prev.sets + r.sets, r.session_id)
        else:
            merged[r.session_id] = SessionPerformance(r.performed_on, r.sets, r.session_id)
    return list(merged.values())


def load_performances(db: Session, user_id: int, exercise_id: int, *, limit: int | None = None,
                      exclude_session_id: int | None = None) -> list[SessionPerformance]:
    """Newest first. `limit` caps the number of workouts."""
    perfs = to_performances(load_logged(db, user_id, exercise_id=exercise_id, exclude_session_id=exclude_session_id))
    return perfs[:limit] if limit else perfs
