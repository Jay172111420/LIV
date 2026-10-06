from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.errors import UnauthorizedError
from app.models import User
from app.services import auth_service

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_current_user(request: Request, db: DbSession, settings: AppSettings) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    user = auth_service.user_for_token(db, token)
    if user is None:
        raise UnauthorizedError("Please log in to continue.", code="not_authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
