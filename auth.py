from fastapi import APIRouter, Request, Response, status

from app.deps import AppSettings, CurrentUser, DbSession
from app.schemas.auth import Credentials, RegisterIn, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, settings, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name, token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, response: Response, db: DbSession, settings: AppSettings):
    user = auth_service.register_user(db, data.email, data.password)
    _set_cookie(response, settings, auth_service.create_session(db, user, settings.session_ttl_hours))
    return user


@router.post("/login", response_model=UserOut)
def login(data: Credentials, response: Response, db: DbSession, settings: AppSettings):
    user = auth_service.authenticate(db, data.email, data.password)
    _set_cookie(response, settings, auth_service.create_session(db, user, settings.session_ttl_hours))
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession, settings: AppSettings):
    auth_service.end_session(db, request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
