from fastapi import APIRouter, Query, status

from app.deps import CurrentUser, DbSession
from app.schemas.workout import SessionCreate, SessionOut
from app.services import workout_service

router = APIRouter(prefix="/workout-sessions", tags=["workout-sessions"])


@router.get("", response_model=list[SessionOut])
def list_sessions(user: CurrentUser, db: DbSession,
                  limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    return workout_service.list_sessions(db, user.id, limit, offset)


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(data: SessionCreate, user: CurrentUser, db: DbSession):
    return workout_service.create_session(db, user.id, data)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: int, user: CurrentUser, db: DbSession):
    return workout_service.get_session(db, user.id, session_id)
