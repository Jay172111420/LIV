from fastapi import APIRouter

from app.deps import CurrentUser, DbSession
from app.schemas.nutrition import NutritionProfileOut, NutritionProfileUpdate
from app.services import nutrition_service

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


@router.get("/profile", response_model=NutritionProfileOut)
def read_profile(user: CurrentUser):
    return user.nutrition_profile


@router.put("/profile", response_model=NutritionProfileOut)
def update_profile(data: NutritionProfileUpdate, user: CurrentUser, db: DbSession):
    return nutrition_service.update_nutrition_profile(db, user, data)
