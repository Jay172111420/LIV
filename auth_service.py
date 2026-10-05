from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, UnauthorizedError
from app.models import AuthSession, NutritionProfile, User, UserProfile
from app.models.base import utcnow
from app.security import hash_password, hash_token, new_session_token, verify_password


def register_user(db: Session, email: str, password: str) -> User:
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("An account with this email already exists.", code="email_taken")
    user = User(
        email=email,
        password_hash=hash_password(password),
        profile=UserProfile(),
        nutrition_profile=NutritionProfile(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two simultaneous sign-ups with the same email
        db.rollback()
        raise ConflictError("An account with this email already exists.", code="email_taken")
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(password, user.password_hash if user else None)
    if not (user and ok and user.is_active):
        raise UnauthorizedError("Email or password is incorrect.", code="invalid_credentials")
    return user


def create_session(db: Session, user: User, ttl_hours: int) -> str:
    token = new_session_token()
    now = utcnow()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
    )
    db.commit()
    return token


def user_for_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if session is None:
        return None
    if session.expires_at <= utcnow():
        db.delete(session)
        db.commit()
        return None
    return session.user if session.user.is_active else None


def end_session(db: Session, token: str | None) -> None:
    if not token:
        return
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if session:
        db.delete(session)
        db.commit()
