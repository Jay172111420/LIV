from fastapi import APIRouter, Query, Response, status

from app.deps import CurrentUser, DbSession
from app.models.enums import WorkoutStatus
from app.schemas.workout import SessionComplete, SessionCreate, SessionOut, SessionStart, SetUpdate
from app.services import workout_service
from app.services.workout_session_service import WorkoutSessionService

router = APIRouter(prefix="/workout-sessions", tags=["workout-sessions"])


@router.get("", response_model=list[SessionOut])
def list_sessions(user: CurrentUser, db: DbSession,
                  limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                  status_filter: WorkoutStatus | None = Query(None, alias="status")):
    return workout_service.list_sessions(db, user.id, limit, offset, status_filter)


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(data: SessionCreate, user: CurrentUser, db: DbSession):
    return workout_service.create_session(db, user.id, data)


@router.get("/active", response_model=SessionOut | None)
def active_session(user: CurrentUser, db: DbSession):
    """The workout currently in progress, or null."""
    return WorkoutSessionService(db, user.id).active()


@router.post("/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(data: SessionStart, user: CurrentUser, db: DbSession):
    return WorkoutSessionService(db, user.id).start(data)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: int, user: CurrentUser, db: DbSession):
    return workout_service.get_session(db, user.id, session_id)


@router.patch("/{session_id}/sets/{set_id}", response_model=SessionOut)
def update_set(session_id: int, set_id: int, data: SetUpdate, user: CurrentUser, db: DbSession):
    return WorkoutSessionService(db, user.id).update_set(session_id, set_id, data)


@router.post("/{session_id}/exercises/{workout_exercise_id}/sets", response_model=SessionOut,
             status_code=status.HTTP_201_CREATED)
def add_set(session_id: int, workout_exercise_id: int, user: CurrentUser, db: DbSession):
    return WorkoutSessionService(db, user.id).add_set(session_id, workout_exercise_id)


@router.delete("/{session_id}/exercises/{workout_exercise_id}/sets/{set_id}", response_model=SessionOut)
def delete_set(session_id: int, workout_exercise_id: int, set_id: int, user: CurrentUser, db: DbSession):
    return WorkoutSessionService(db, user.id).delete_set(session_id, workout_exercise_id, set_id)


@router.post("/{session_id}/complete", response_model=SessionOut)
def complete_session(session_id: int, data: SessionComplete, user: CurrentUser, db: DbSession):
    return WorkoutSessionService(db, user.id).complete(session_id, data)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_session(session_id: int, user: CurrentUser, db: DbSession):
    """Discards a workout that is still in progress. Finished workouts are kept as history."""
    WorkoutSessionService(db, user.id).discard(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
