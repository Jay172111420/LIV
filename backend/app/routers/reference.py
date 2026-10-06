"""Read-only lookup lists. Login required so the API surface stays private by default."""
from fastapi import APIRouter
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import Equipment, FitnessGoal
from app.schemas.reference import EquipmentOut, GoalOut

router = APIRouter(tags=["reference"])


@router.get("/equipment", response_model=list[EquipmentOut])
def list_equipment(_: CurrentUser, db: DbSession):
    return db.scalars(select(Equipment).where(Equipment.is_active).order_by(Equipment.id)).all()


@router.get("/goals", response_model=list[GoalOut])
def list_goals(_: CurrentUser, db: DbSession):
    return db.scalars(
        select(FitnessGoal).where(FitnessGoal.is_active).order_by(FitnessGoal.sort_order)
    ).all()
