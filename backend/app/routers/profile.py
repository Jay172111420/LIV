from fastapi import APIRouter

from app.deps import CurrentUser, DbSession
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.services import profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def read_profile(user: CurrentUser):
    return profile_service.to_out(profile_service.get_profile(user))


@router.put("", response_model=ProfileOut)
def update_profile(data: ProfileUpdate, user: CurrentUser, db: DbSession):
    return profile_service.to_out(profile_service.update_profile(db, user, data))
