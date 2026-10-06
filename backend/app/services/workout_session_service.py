"""Running a workout: start from a plan day, log sets, rest metadata, complete or discard.

Every method is scoped to one user. Another user's records are reported as "not found".
"""
import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError, ConflictError, NotFoundError
from app.models import WorkoutExercise, WorkoutSession, WorkoutSet
from app.models.base import utcnow
from app.models.enums import WorkoutStatus
from app.schemas.workout import SessionComplete, SessionStart, SetUpdate
from app.services import plan_service
from app.services.workout_service import _SESSION_EAGER, get_session

MAX_SETS_PER_EXERCISE = 20
DURATION_SLACK_MINUTES = 5  # a typed duration may exceed elapsed time by this much (clock drift, edits)
MAX_DURATION_MINUTES = 600


class WorkoutSessionService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    # ------------------------------------------------------------ reading
    def active(self) -> WorkoutSession | None:
        return self.db.scalar(
            select(WorkoutSession).where(WorkoutSession.user_id == self.user_id,
                                         WorkoutSession.status == WorkoutStatus.in_progress)
            .options(*_SESSION_EAGER))

    def _in_progress(self, session_id: int) -> WorkoutSession:
        session = get_session(self.db, self.user_id, session_id)
        if session.status != WorkoutStatus.in_progress:
            raise ConflictError("This workout is already finished and can't be changed.",
                                code="workout_not_active")
        return session

    @staticmethod
    def _find_set(session: WorkoutSession, set_id: int) -> tuple[WorkoutExercise, WorkoutSet]:
        for we in session.exercises:
            for s in we.sets:
                if s.id == set_id:
                    return we, s
        raise NotFoundError("Set not found.")

    # ------------------------------------------------------------ starting
    def start(self, data: SessionStart) -> WorkoutSession:
        existing = self.active()
        if existing:
            raise ConflictError("You already have a workout in progress.", code="workout_in_progress",
                                details={"session_id": existing.id})
        plan, day = plan_service.get_day_by_id(self.db, self.user_id, data.plan_day_id)
        if day.is_rest:
            raise AppError("That's a rest day. Pick a training day to start.", code="rest_day")
        if not day.exercises:
            raise AppError("This workout has no exercises yet. Add some first.", code="empty_workout")

        today = utcnow().date()
        performed_on = data.performed_on or today
        if abs((performed_on - today).days) > 1:
            raise AppError("That date isn't valid for a workout you're starting now.", code="invalid_date")

        last = self._last_performance([e.exercise_id for e in day.exercises])
        session = WorkoutSession(
            user_id=self.user_id, plan_id=plan.id, plan_day_id=day.id, name=day.name,
            performed_on=performed_on, started_at=utcnow(), status=WorkoutStatus.in_progress,
            exercises=[
                WorkoutExercise(
                    exercise_id=pe.exercise_id, position=pos, rest_seconds=pe.rest_seconds, notes=pe.notes,
                    sets=[self._new_set(n, pe, last.get(pe.exercise_id, [])) for n in range(1, pe.sets + 1)],
                )
                for pos, pe in enumerate(day.exercises, 1)
            ],
        )
        self.db.add(session)
        try:
            self.db.commit()
        except IntegrityError:  # two starts raced; the unique index allowed only one
            self.db.rollback()
            raise ConflictError("You already have a workout in progress.", code="workout_in_progress")
        return get_session(self.db, self.user_id, session.id)

    @staticmethod
    def _new_set(number: int, pe, previous: list[WorkoutSet]) -> WorkoutSet:
        """Pre-fills weight and reps from the same set last time, so repeating a workout is one tap per set."""
        prev = previous[number - 1] if number <= len(previous) else (previous[-1] if previous else None)
        return WorkoutSet(
            set_number=number, weight_kg=prev.weight_kg if prev else None, reps=prev.reps if prev else None,
            rest_seconds=pe.rest_seconds, target_reps_min=pe.rep_min, target_reps_max=pe.rep_max,
        )

    def _last_performance(self, exercise_ids: list[int]) -> dict[int, list[WorkoutSet]]:
        found: dict[int, list[WorkoutSet]] = {}
        for ex_id in exercise_ids:
            we_id = self.db.scalar(
                select(WorkoutExercise.id).join(WorkoutSession)
                .where(WorkoutSession.user_id == self.user_id, WorkoutSession.status == WorkoutStatus.completed,
                       WorkoutExercise.exercise_id == ex_id)
                .order_by(WorkoutSession.performed_on.desc(), WorkoutSession.id.desc()).limit(1))
            if we_id:
                found[ex_id] = list(self.db.scalars(
                    select(WorkoutSet).where(WorkoutSet.workout_exercise_id == we_id, WorkoutSet.is_completed)
                    .order_by(WorkoutSet.set_number)))
        return found

    # ------------------------------------------------------------ logging
    def update_set(self, session_id: int, set_id: int, data: SetUpdate) -> WorkoutSession:
        session = self._in_progress(session_id)
        _, target = self._find_set(session, set_id)
        changes = data.model_dump(exclude_unset=True)

        reps = changes["reps"] if "reps" in changes else target.reps
        done = changes["is_completed"] if "is_completed" in changes else target.is_completed
        if done and (reps is None or reps < 1):
            raise AppError("Enter the reps you completed before marking the set done.", code="set_incomplete")

        for field, value in changes.items():
            setattr(target, field, round(value, 2) if field == "weight_kg" and value is not None else value)
        self.db.commit()
        return get_session(self.db, self.user_id, session_id)

    def add_set(self, session_id: int, workout_exercise_id: int) -> WorkoutSession:
        session = self._in_progress(session_id)
        we = next((e for e in session.exercises if e.id == workout_exercise_id), None)
        if we is None:
            raise NotFoundError("Exercise not found in this workout.")
        if len(we.sets) >= MAX_SETS_PER_EXERCISE:
            raise AppError(f"An exercise can have at most {MAX_SETS_PER_EXERCISE} sets.", code="too_many_sets")
        last = we.sets[-1] if we.sets else None
        we.sets.append(WorkoutSet(
            set_number=(max((s.set_number for s in we.sets), default=0) + 1),
            weight_kg=last.weight_kg if last else None, reps=last.reps if last else None,
            rest_seconds=last.rest_seconds if last else we.rest_seconds,
            target_reps_min=last.target_reps_min if last else None,
            target_reps_max=last.target_reps_max if last else None,
        ))
        self.db.commit()
        return get_session(self.db, self.user_id, session_id)

    def delete_set(self, session_id: int, workout_exercise_id: int, set_id: int) -> WorkoutSession:
        session = self._in_progress(session_id)
        we = next((e for e in session.exercises if e.id == workout_exercise_id), None)
        target = next((s for s in (we.sets if we else []) if s.id == set_id), None)
        if target is None:
            raise NotFoundError("Set not found.")
        if len(we.sets) <= 1:
            raise AppError("An exercise needs at least one set.", code="last_set")
        we.sets.remove(target)
        self.db.commit()
        return get_session(self.db, self.user_id, session_id)

    # ------------------------------------------------------------ finishing
    def complete(self, session_id: int, data: SessionComplete) -> WorkoutSession:
        session = self._in_progress(session_id)
        if not any(s.is_completed for we in session.exercises for s in we.sets):
            raise AppError("Complete at least one set before finishing, or discard this workout.",
                           code="no_completed_sets")

        now = utcnow()
        elapsed = self._elapsed_minutes(session, now)
        if data.duration_minutes is not None:
            if data.duration_minutes > elapsed + DURATION_SLACK_MINUTES:
                raise AppError(
                    f"That duration is longer than the {elapsed} minutes since you started this workout.",
                    code="invalid_duration")
            duration = data.duration_minutes
        else:
            duration = elapsed

        # Skipped work isn't history: keep only completed sets, and only exercises that have any.
        for we in list(session.exercises):
            for s in [s for s in we.sets if not s.is_completed]:
                we.sets.remove(s)
            if not we.sets:
                session.exercises.remove(we)

        session.status = WorkoutStatus.completed
        session.ended_at = now
        session.duration_minutes = duration
        if data.notes is not None:
            session.notes = data.notes
        self.db.commit()
        return get_session(self.db, self.user_id, session_id)

    @staticmethod
    def _elapsed_minutes(session: WorkoutSession, now: datetime) -> int:
        start = session.started_at or now
        minutes = math.ceil(max(0.0, (now - start).total_seconds()) / 60)
        return max(1, min(MAX_DURATION_MINUTES, minutes))

    def discard(self, session_id: int) -> None:
        session = self._in_progress(session_id)
        self.db.delete(session)
        self.db.commit()
